from freezegun import freeze_time

import generate_base_path


@freeze_time("2021-01-20T23:53:35+09:00")
def test_main_daily():
    event = {}
    event_out = generate_base_path.main_daily(event, None)
    assert event_out is event
    assert event_out["base_path"] == "dumped_data/daily/2021-01-20T23:53:35+09:00/東京都"
    assert event_out["root_key"] == "predictions/daily/2021-01-20T23:53:35+09:00"
    assert event_out["timestamp"] == 1611154415.0


@freeze_time("2021-01-20T23:53:35+09:00")
def test_main_user_requested(monkeypatch):
    monkeypatch.setattr("generate_base_path.uuid.uuid4", lambda: "someuuid")
    event = {}
    event_out = generate_base_path.main_user_requested(event, None)
    assert event_out is event
    assert event_out["job_id"] == "someuuid"
    assert event_out["base_path"] == "jobs/someuuid/property_data"
    assert event_out["root_key"] == "jobs/someuuid"
    assert event_out["timestamp"] == 1611154415.0
