import io
from pathlib import Path

import asks
import boto3
import bs4
import trio

from otokuna.dumping import scrape_number_of_pages
from otokuna.logging import setup_logger


async def get_page(search_url, page):
    search_page_url = f"{search_url}&page={page}"
    try:
        response = await asks.get(search_page_url, timeout=30, retries=3)
    except Exception as e:
        # TODO: catch specific exceptions
        raise RuntimeError(f"Could not fetch page {page}: {e}")
    return response


async def get_number_of_pages(search_url):
    response = await asks.get(search_url)
    search_results_soup = bs4.BeautifulSoup(response.text, "html.parser")
    return scrape_number_of_pages(search_results_soup)


async def main_async(event, context):
    logger = setup_logger("dump-svc", include_timestamp=False, propagate=False)

    batch_name = event.get("batch_name", "")  # (path / '' == path) is True
    output_bucket = event["output_bucket"]
    base_path = event["base_path"]
    search_url = event["search_url"]

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


def main(event, context):
    return trio.run(main_async, event, context)
