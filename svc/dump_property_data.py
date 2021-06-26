import io
from pathlib import Path

import boto3

from otokuna.dumping import build_search_url, iter_search_results
from otokuna.logging import setup_logger


def main(event, context):
    logger = setup_logger("dump-svc", include_timestamp=False, propagate=False)

    ward = event["ward"]
    output_bucket = event["output_bucket"]
    base_path = event["base_path"]

    # TODO: search_url should be passed via the event
    search_url = build_search_url(building_categories=("マンション",),
                                  wards=(ward,), only_today=True)
    iterator = iter_search_results(search_url, sleep_time=0, logger=logger)

    dump_path = Path(base_path) / ward
    logger.info(f"Logging properties from {ward} ward into: {dump_path}")
    s3_client = boto3.client('s3')
    for page, response in iterator:
        fileobj = io.BytesIO(response.content)
        path = str(dump_path / f"page_{page:06d}.html")
        s3_client.upload_fileobj(fileobj, output_bucket, str(path))
        logger.info(f"Saved to s3 page {page}: {path}")
