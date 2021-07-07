import datetime
import io
import os
import zipfile

import boto3
from otokuna.logging import setup_logger
from otokuna.scraping import scrape_properties_from_files, make_properties_dataframe


def main(event, context):
    """Scrapes the property data from the zipped html data into a dataframe
    and uploads it as a pickle to the same bucket.
    """
    logger = setup_logger("scrape-property-data", include_timestamp=False, propagate=False)

    output_bucket = os.environ["OUTPUT_BUCKET"]
    html_file_fetched_at = event["timestamp"]
    raw_data_key = event["raw_data_key"]
    scraped_data_key = raw_data_key.replace(".zip", ".pickle")

    s3_client = boto3.client("s3")

    with io.BytesIO() as stream:
        s3_client.download_fileobj(Bucket=output_bucket, Key=raw_data_key, Fileobj=stream)
        with zipfile.ZipFile(stream) as zfile:
            filenames = sorted((zi for zi in zfile.infolist()), key=lambda zi: zi.filename)
        # TODO: joblib runs in sequential even for n_jobs > 1 due to limitations
        #   of multiprocessing module in AWS Lambda
        properties = scrape_properties_from_files(filenames, stream,
                                                  logger=logger, n_jobs=1)

    df = make_properties_dataframe(properties, html_file_fetched_at, logger)

    with io.BytesIO() as stream:
        df.to_pickle(stream, compression=None, protocol=5)
        stream.seek(0)
        s3_client.upload_fileobj(Fileobj=stream, Bucket=output_bucket, Key=scraped_data_key)

    event["scraped_data_key"] = scraped_data_key
    return event
