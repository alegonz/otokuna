import io
import os
from pathlib import Path

import asks
import boto3
import bs4
import trio

from otokuna.dumping import add_results_per_page_param, scrape_number_of_pages, add_params
from otokuna.logging import setup_logger


# Sometimes Suumo takes several seconds to respond, but, instead
# of setting a timeout for asks.get we instead try for as long as
# possible, until the hard timeout of Lambda expires.
async def get_page(search_url, page):
    search_page_url = add_params(search_url, {"page": [str(page)]})
    for attempt in range(3):
        try:
            response = await asks.get(search_page_url)
        except Exception:
            # TODO: catch specific exceptions
            await trio.sleep(10)
        else:
            break
    else:
        raise RuntimeError(f"Could not fetch page {page}")
    return response


async def get_number_of_pages(search_url):
    response = await get_page(search_url, page=1)
    search_results_soup = bs4.BeautifulSoup(response.text, "html.parser")
    return scrape_number_of_pages(search_results_soup)


async def main_async(event, context):
    logger = setup_logger("dump-svc", include_timestamp=False, propagate=False)

    output_bucket = os.environ["OUTPUT_BUCKET"]
    batch_name = event.get("batch_name", "")  # (path / '' == path) is True
    base_path = event["base_path"]
    search_url = add_results_per_page_param(event["search_url"])

    dump_path = Path(base_path) / batch_name
    s3_client = boto3.client('s3')
    logger.info(f"Logging properties from batch {batch_name} into: {dump_path}")

    max_simultaneous_workers = 5
    limiter = trio.CapacityLimiter(max_simultaneous_workers)
    n_pages = await get_number_of_pages(search_url)
    logger.info(f"Total result pages: {n_pages}")
    pages = list(range(n_pages, 0, -1))  # pages are 1-indexed

    async def save_page_content(content, bucket, key):
        fileobj = io.BytesIO(content)
        await trio.to_thread.run_sync(s3_client.upload_fileobj, fileobj, bucket, key)

    async def worker(wid):
        while pages:
            page = pages.pop()
            async with limiter:
                response = await get_page(search_url, page)
                logger.info(f"Got page {page} (worker {wid}): {response.url}")
                key = str(dump_path / f"page_{page:06d}.html")
                await save_page_content(response.content, output_bucket, key)
                logger.info(f"Saved to s3 page {page} (worker {wid}): {key}")

    async with trio.open_nursery() as nursery:
        for i in range(max_simultaneous_workers):
            nursery.start_soon(worker, i)

    return event


def main(event, context):
    return trio.run(main_async, event, context)
