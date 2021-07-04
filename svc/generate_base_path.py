import uuid
from pathlib import Path

from otokuna.dumping import now_local


def main_daily(event, context):
    now = now_local()
    datetime_str = now.isoformat(timespec="seconds")
    # TODO: Retire the dumped_data/predictions division after we revise
    #  the logic to store the dumped data and the predictions together.
    #  Retire base_path, and keep root_key which will eventually be something
    #  like 'jobs/[UUID]'
    base_path = Path("dumped_data") / "daily" / datetime_str / "東京都"
    root_key = Path("predictions") / "daily" / datetime_str
    event["base_path"] = str(base_path)
    event["root_key"] = str(root_key)
    event["timestamp"] = now.timestamp()
    return event


def main_user_requested(event, context):
    job_id = str(uuid.uuid4())
    root_key = Path("jobs") / job_id
    # 'property_data' (like '東京' in the daily case) will at first be the folder
    # where the html files are dumped, but then becomes the filename of the zip file
    # after compressing its contents
    # TODO: 'property_data' and '東京' should be parameters in the event
    base_path = root_key / "property_data"
    event["job_id"] = job_id
    event["base_path"] = str(base_path)
    event["root_key"] = str(root_key)
    event["timestamp"] = now_local().timestamp()
    return event
