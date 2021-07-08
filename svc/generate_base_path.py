from pathlib import Path

from otokuna.dumping import now_local


def main_daily(event, context):
    datetime_str = now_local().isoformat(timespec="seconds")
    # TODO: Retire the dumped_data/predictions division after we revise
    #  the logic to store the dumped data and the predictions together.
    #  Retire base_path, and keep root_key which will eventually be something
    #  like 'jobs/[UUID]'
    base_path = Path("dumped_data") / "daily" / datetime_str / "東京都"
    root_key = Path("predictions") / "daily" / datetime_str
    event["base_path"] = str(base_path)
    event["root_key"] = str(root_key)
    return event
