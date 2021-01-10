import io
import os
from pathlib import Path

import boto3

from otokuna.dumping import now_isoformat, iter_search_results, TOKYO_SPECIAL_WARDS
from otokuna.logging import setup_logger


def dump_property_data(event, context):
    dump_bucket = os.environ["outputBucket"]
    logger = setup_logger("dump-svc")
    iterator = iter_search_results(
        building_categories=("マンション",),
        wards=TOKYO_SPECIAL_WARDS,
        only_today=True,
        sleep_time=0,
        logger=logger
    )
    datetime_str = now_isoformat()
    base_path = Path("dumped_data") / "daily" / datetime_str / "東京都"
    s3_client = boto3.client('s3')
    for page, response in iterator:
        fileobj = io.BytesIO(response.content)
        path = str(base_path / f"page_{page:06d}.html")
        # path = str(base_path / ward / f"page_{page:06d}.html")
        s3_client.upload_fileobj(fileobj, dump_bucket, str(path))
        logger.info(f"Saved to s3 page {page}: {path}")
