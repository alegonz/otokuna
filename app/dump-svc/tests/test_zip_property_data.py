import io
import zipfile
from pathlib import Path

import boto3
import pytest
from moto import mock_s3

import zip_property_data


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
def test_main():
    output_bucket = "somebucket"
    base_path = "some/folder"
    filename_template = "subfolder/file_{:03d}.txt"
    some_content = b"some content"
    some_content_template = "some content {}"
    n_files = 10
    other_keys = {base_path, base_path + "/", "other_key"}

    s3_client = boto3.client("s3")
    s3_client.create_bucket(Bucket=output_bucket)

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
        key = Path(base_path) / filename_template.format(i)
        upload_obj(contents, str(key))

    # ---------- Call handler and check
    zipfile_key = f"{base_path}.zip"
    event = {
        "output_bucket": output_bucket,
        "base_path": base_path
    }
    event_out = zip_property_data.main(event, None)
    assert event_out is event
    assert event_out["zipfile_key"] == zipfile_key

    # ---------- Check results
    objects = {obj["Key"] for obj in s3_client.list_objects_v2(Bucket=output_bucket)["Contents"]}

    # All objects with the same prefix were zipped
    # and other objects were left untouched.
    assert objects == other_keys | {zipfile_key}

    # Check zipped file contents
    with io.BytesIO() as stream:
        s3_client.download_fileobj(Bucket=output_bucket, Key=zipfile_key, Fileobj=stream)
        with zipfile.ZipFile(stream) as zf:
            infolist = zf.infolist()
            assert len(infolist) == n_files

            for i, zi in enumerate(infolist):
                with zf.open(zi) as arc:
                    contents = arc.read()
                assert zi.filename == filename_template.format(i)
                assert contents == some_content_template.format(i).encode()
