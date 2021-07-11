from pathlib import Path

import json
import os

import boto3
import bs4
import requests
from otokuna.dumping import scrape_search_conditions


def get_search_conditions(search_url):
    response = requests.get(search_url)
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    return scrape_search_conditions(soup)


def main(event, context):
    output_bucket = os.environ["OUTPUT_BUCKET"]
    root_key = event["root_key"]

    items_to_save = (
        "job_id", "timestamp",
        "user_id", "search_url",
        "raw_data_key", "scraped_data_key", "prediction_data_key"
    )
    job_info = {item: event[item] for item in items_to_save}
    job_info["search_conditions"] = get_search_conditions(event["search_url"])
    job_info_key = str(Path(root_key) / "job_info.json")

    s3 = boto3.resource('s3')
    s3_obj = s3.Object(output_bucket, job_info_key)
    s3_obj.put(Body=(bytes(json.dumps(job_info).encode('UTF-8'))))

    event["job_info_key"] = job_info_key
    return event
