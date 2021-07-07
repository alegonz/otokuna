import io
import os
import zipfile

import boto3

from otokuna.logging import setup_logger


def remove_prefix(s, prefix):
    if s.startswith(prefix):
        return s[len(prefix):]
    return s


def datetime_to_truncated_tuple(datetime_):
    """Converts a datetime to a tuple of (year, month, day, hours, minutes, seconds)"""
    return datetime_.timetuple()[:6]


def build_zipinfo(zfile, filename, date_time):
    """Build ZipInfo object with the given filename and date_time and
    with the same compression setup as the containing ZipFile.

    This is to workaround a pitfall of ZipInfo that will instantiate
    objects with no compression by default.
    """
    zinfo = zipfile.ZipInfo(filename, date_time)
    zinfo.compress_type = zfile.compression
    zinfo._compresslevel = zfile.compresslevel
    return zinfo


def main(event, context):
    """Download objects from the base_path "folder" and upload them as a zip file.

    Objects with a key equal to the "folder" (with and without ending in "/"),
    are NOT included because they would imply a relative name of "" and "/",
    respectively, within the archive. Though they are valid names in Python they
    are not extracted in Ubuntu.

    If there is an object with the same filename as the zip file it will be overwritten.

    For example, if the bucket has these objects and the base_path is "a/b/c"
    * a/b/c
    * a/b/c/
    * a/b/c/d
    * a/b/c/f/g
    * a/b/c.zip
    * x/y/z

    then after this function the bucket will contain
    * a/b/c     (not included in the zip)
    * a/b/c/    (not included in the zip)
    * a/b/c.zip (overwritten)
    * x/y/z     (not included in the zip)

    And the a/b/c.zip file will contain
    * d
    * f/g
    """
    logger = setup_logger("zip-property-data", include_timestamp=False, propagate=False)

    output_bucket = os.environ["OUTPUT_BUCKET"]
    base_path = event["base_path"]  # TODO: rename as base_key
    s3_client = boto3.client("s3")

    assert not base_path.endswith("/")
    raw_data_key = f"{base_path}.zip"

    delete = []
    # an object with a key equal to the base_path is not included
    prefix = base_path + "/"
    with io.BytesIO() as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zfile:
            for obj in s3_client.list_objects_v2(Bucket=output_bucket, Prefix=prefix)["Contents"]:
                key = obj["Key"]
                # an object with a key equal to the prefix is not included
                if key == prefix:
                    continue
                delete.append(key)
                filename = remove_prefix(key, prefix)
                date_time = datetime_to_truncated_tuple(obj["LastModified"])
                logger.info(f"Downloading and compressing {key} -> {filename}")
                assert filename not in ("", "/")
                zinfo = build_zipinfo(zfile, filename, date_time)
                with zfile.open(zinfo, "w") as zarc:
                    s3_client.download_fileobj(Bucket=output_bucket, Key=key, Fileobj=zarc)

        stream.seek(0)
        logger.info(f"Uploading {raw_data_key}")
        s3_client.upload_fileobj(Fileobj=stream, Bucket=output_bucket, Key=raw_data_key)

    # Delete zipped objects
    for key in delete:
        logger.info(f"Deleting {key}")
        s3_client.delete_object(Bucket=output_bucket, Key=key)

    event["raw_data_key"] = raw_data_key
    return event
