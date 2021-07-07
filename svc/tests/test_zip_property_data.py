import io
import os
import zipfile
from pathlib import Path

import boto3
import pytest
from moto import mock_s3

import zip_property_data


def assert_date_time_equal(date_time_1, date_time_2):
    """Compare two ZipInfo date_time's.
    The seconds may differ by one second because of the limitations
    of the zip file format.
    See:
    - https://bugs.python.org/issue3233
    - https://bugs.python.org/issue5457
    """
    assert len(date_time_1) == len(date_time_2)
    assert date_time_1[:-1] == date_time_2[:-1]
    assert abs(date_time_1[-1] - date_time_2[-1]) in (0, 1)


@pytest.mark.parametrize("s,expected", [
    ("", ""),
    ("a/b/", ""),
    ("a/b/c", "c"),
    ("foo", "foo"),
])
def test_remove_prefix(s,expected):
    prefix = "a/b/"
    assert zip_property_data.remove_prefix(s, prefix) == expected


@mock_s3
def test_main(set_environ):
    output_bucket = os.environ["OUTPUT_BUCKET"]
    base_path = "some/folder"
    filename_template = "subfolder/file_{:03d}.txt"
    some_content = b"some content"
    some_content_template = "some content {}"
    n_files = 10
    other_keys = {base_path, base_path + "/", "other_key"}

    s3_client = boto3.client("s3")
    s3_client.create_bucket(Bucket=output_bucket)

    def list_objects():
        return {obj["Key"]: obj for obj in s3_client.list_objects_v2(Bucket=output_bucket)["Contents"]}

    # ---------- Put some objects
    def upload_obj(contents_: bytes, key_: str):
        with io.BytesIO(contents_) as fileobj:
            s3_client.upload_fileobj(fileobj, output_bucket, key_)

    # Put objects that should not be zipped nor deleted.
    # Objects with key same as the "folder", with and without and ending in "/",
    # are NOT included.
    for key in other_keys:
        upload_obj(some_content, key)

    # Objects in the "folder"
    for i in range(n_files):
        contents = some_content_template.format(i).encode()
        key = str(Path(base_path) / filename_template.format(i))
        upload_obj(contents, key)

    objects_by_key = list_objects()

    # ---------- Call handler and check
    raw_data_key = f"{base_path}.zip"
    event = {
        "base_path": base_path
    }
    event_out = zip_property_data.main(event, None)
    assert event_out is event
    assert event_out["raw_data_key"] == raw_data_key

    # ---------- Check results
    # All objects with the same prefix were zipped
    # and other objects were left untouched.
    assert set(list_objects()) == other_keys | {raw_data_key}

    # Check zipped file contents
    with io.BytesIO() as stream:
        s3_client.download_fileobj(Bucket=output_bucket, Key=raw_data_key, Fileobj=stream)
        with zipfile.ZipFile(stream) as zf:
            infolist = zf.infolist()
            assert len(infolist) == n_files

            for i, zi in enumerate(infolist):
                with zf.open(zi) as arc:
                    contents = arc.read()
                assert zi.filename == filename_template.format(i)
                assert contents == some_content_template.format(i).encode()
                key = str(Path(base_path) / filename_template.format(i))
                expected_date_time = zip_property_data.datetime_to_truncated_tuple(
                    objects_by_key[key]["LastModified"]
                )
                assert_date_time_equal(zi.date_time, expected_date_time)
