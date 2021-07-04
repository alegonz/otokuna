from pathlib import Path

from otokuna.dumping import now_isoformat


def main_daily(event, context):
    datetime_str = now_isoformat()
    base_path = Path("dumped_data") / "daily" / datetime_str / "東京都"
    event["base_path"] = str(base_path)
    return event
