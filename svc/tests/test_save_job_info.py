import json
import os
from pathlib import Path

import boto3
from moto import mock_s3
from otokuna.testing import build_mock_requests_get

import save_job_info

DATA_DIR = Path(__file__).parent / "data"


@mock_s3
def test_main(set_environ, monkeypatch):
    output_bucket = os.environ["OUTPUT_BUCKET"]

    job_id = "someuuid"
    timestamp = 1611154415.0
    user_id = "johndoe"
    search_url = "dummyurl"
    root_key = f"jobs/{job_id}"
    raw_data_key = f"jobs/{job_id}/property_data.zip"
    scraped_data_key = f"jobs/{job_id}/property_data.pickle"
    prediction_data_key = f"jobs/{job_id}/prediction.pickle"

    expected_search_conditions = "東京メトロ銀座線／虎ノ門 東京メトロ丸ノ内線／銀座 1LDK 30m2以上 オートロック"

    html_files_by_url = {
        search_url: DATA_DIR / "results_page_long_conditions.html"
    }
    monkeypatch.setattr("save_job_info.requests.get", build_mock_requests_get(html_files_by_url))

    event = {
        "root_key": root_key,
        "job_id": job_id,
        "timestamp": timestamp,
        "user_id": user_id,
        "search_url": search_url,
        "raw_data_key": raw_data_key,
        "scraped_data_key": scraped_data_key,
        "prediction_data_key": prediction_data_key,
    }

    s3_client = boto3.client('s3')
    s3_client.create_bucket(Bucket=output_bucket)

    save_job_info.main(event, None)

    expected_job_info = {
        "job_id": job_id,
        "timestamp": timestamp,
        "user_id": user_id,
        "search_url": search_url,
        "search_conditions": expected_search_conditions,
        "raw_data_key": raw_data_key,
        "scraped_data_key": scraped_data_key,
        "prediction_data_key": prediction_data_key,
    }

    expected_job_info_key = f"jobs/{job_id}/job_info.json"
    key = "/".join([root_key, "job_info.json"])
    contents = s3_client.get_object(Bucket=output_bucket, Key=key)["Body"].read()
    assert json.loads(contents) == expected_job_info
    assert event["job_info_key"] == expected_job_info_key
