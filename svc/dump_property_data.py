import io
from pathlib import Path

import boto3

from otokuna.dumping import iter_search_results
from otokuna.logging import setup_logger


def main(event, context):
    logger = setup_logger("dump-svc", include_timestamp=False, propagate=False)

    batch_name = event.get("batch_name", "")  # (path / '' == path) is True
    output_bucket = event["output_bucket"]
    base_path = event["base_path"]
    search_url = event["search_url"]

    iterator = iter_search_results(search_url, sleep_time=0, logger=logger)

    dump_path = Path(base_path) / batch_name
    logger.info(f"Logging properties from batch {batch_name} into: {dump_path}")
    s3_client = boto3.client('s3')
    for page, response in iterator:
        fileobj = io.BytesIO(response.content)
        path = str(dump_path / f"page_{page:06d}.html")
        s3_client.upload_fileobj(fileobj, output_bucket, str(path))
        logger.info(f"Saved to s3 page {page}: {path}")
