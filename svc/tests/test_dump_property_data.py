import boto3
import pytest
import trio
from moto import mock_s3
from trio.testing import trio_test

import dump_property_data

NUMBER_OF_PAGES = 22
# Minimum content necessary to scrape the number of pages
SEARCH_PAGE_CONTENT = f"""
<ol class="pagination-parts">
<li><a>{NUMBER_OF_PAGES}</a></li>
</ol>
"""


# Cannot use pytest.mark.trio with moto_s3
# See related issue: https://github.com/python-trio/pytest-trio/issues/42
@mock_s3
@trio_test
@pytest.mark.parametrize("batch_name", ["千代田区", None])
async def test_main_async(batch_name, monkeypatch):
    output_bucket = "somebucket"
    base_path = "foo/bar"
    search_url = "dummyurl"

    # Mock pages
    html_text_by_url = {f"{search_url}&page={page}": " ".join([str(page), SEARCH_PAGE_CONTENT])
                        for page in range(1, NUMBER_OF_PAGES + 1)}

    class MockResponse:
        def __init__(self, url, text):
            self.url = url
            self.text = text
            self.content = text.encode()

    async def mock_get(url, timeout=None, retries=1):
        await trio.sleep(0)
        return MockResponse(url, html_text_by_url[url])

    monkeypatch.setattr("dump_property_data.asks.get", mock_get)

    s3_client = boto3.client('s3')
    s3_client.create_bucket(Bucket=output_bucket)

    event = {
        "output_bucket": output_bucket,
        "base_path": base_path,
        "search_url": search_url,
    }
    if batch_name is not None:
        event["batch_name"] = batch_name
        expected_dump_path = f"{base_path}/{batch_name}"
    else:
        expected_dump_path = base_path

    event_out = await dump_property_data.main_async(event, None)
    assert event_out is None

    objects = s3_client.list_objects_v2(Bucket=output_bucket)["Contents"]
    keys = []
    for obj in objects:
        key = obj["Key"]
        content = s3_client.get_object(Bucket=output_bucket, Key=key)["Body"].read()
        page = int(content.split()[0])
        assert key == f"{expected_dump_path}/page_{page:06d}.html"
        keys.append(key)
    assert len(keys) == NUMBER_OF_PAGES
