import io
from pathlib import Path

import boto3
import pandas as pd
from moto import mock_s3

import scrape_property_data

DATA_DIR = Path(__file__).parent / "data"


@mock_s3
def test_main():
    output_bucket = "somebucket"
    zipfile_key = "dumped_data/daily/2021-01-25T14:59:25+00:00/東京都.zip"
    picklefile_key = "dumped_data/daily/2021-01-25T14:59:25+00:00/東京都.pickle"

    # Upload zip file with property data
    s3_client = boto3.client("s3")
    s3_client.create_bucket(Bucket=output_bucket)
    s3_client.upload_file(Bucket=output_bucket, Key=zipfile_key, Filename=str(DATA_DIR / "results.zip"))

    # run main (downloads, creates dataframe, and uploads pickle)
    event = {
        "output_bucket": output_bucket,
        "zipfile_key": zipfile_key
    }
    event_out = scrape_property_data.main(event, None)
    assert event_out is event
    assert event_out["picklefile_key"] == picklefile_key

    # Download pickle and compare
    expected_df = pd.read_pickle(DATA_DIR / "results.pickle")
    with io.BytesIO() as stream:
        s3_client.download_fileobj(Bucket=output_bucket, Key=picklefile_key, Fileobj=stream)
        stream.seek(0)
        actual_df = pd.read_pickle(stream)
    pd.testing.assert_frame_equal(actual_df, expected_df)