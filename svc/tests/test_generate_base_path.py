from freezegun import freeze_time

import generate_base_path


@freeze_time("2021-01-20T23:53:35+09:00")
def test_main_daily():
    event = {}
    event_out = generate_base_path.main_daily(event, None)
    assert event_out is event
    assert event_out["base_path"] == "dumped_data/daily/2021-01-20T23:53:35+09:00/東京都"
    assert event_out["base_path_predictions"] == "predictions/daily/2021-01-20T23:53:35+09:00"
