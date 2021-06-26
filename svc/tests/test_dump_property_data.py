import boto3
from moto import mock_s3

import dump_property_data


@mock_s3
def test_main(monkeypatch):
    pages_contents = [
        (1, b"foo"),
        (2, b"bar")
    ]

    class MockResponse:
        def __init__(self, content):
            self.content = content

    def mock_iter_search_results(search_url, sleep_time, logger):
        assert search_url == "dummyurl"
        for page, content in pages_contents:
            yield page, MockResponse(content)

    monkeypatch.setattr("dump_property_data.iter_search_results", mock_iter_search_results)

    ward = "千代田区"
    output_bucket = "somebucket"
    base_path = "foo/bar"
    search_url = "dummyurl"

    s3_client = boto3.client('s3')
    s3_client.create_bucket(Bucket=output_bucket)

    event = {
        "ward": ward,
        "output_bucket": output_bucket,
        "base_path": base_path,
        "search_url": search_url,
    }
    event_out = dump_property_data.main(event, None)
    assert event_out is None

    objects = s3_client.list_objects_v2(Bucket=output_bucket)["Contents"]
    for (page, content), obj in zip(pages_contents, objects):
        assert obj["Key"] == f"{base_path}/{ward}/page_{page:06d}.html"
        assert s3_client.get_object(Bucket=output_bucket, Key=obj["Key"])["Body"].read() == content
