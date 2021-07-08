from pathlib import Path

from otokuna.dumping import now_local


def main_daily(event, context):
    datetime_str = now_local().isoformat(timespec="seconds")
    base_path = Path("dumped_data") / "daily" / datetime_str / "東京都"
    # TODO: Retire this key after we revise the logic to store the
    #  dumped data and the predictions together
    base_path_predictions = Path("predictions") / "daily" / datetime_str

    event["base_path"] = str(base_path)
    event["base_path_predictions"] = str(base_path_predictions)
    return event
