import build_search_url

def test_main(monkeypatch):
    monkeypatch.setattr(
        "build_search_url.build_search_url",
        lambda building_categories, wards, only_today: "dummyurl"
    )

    ward = "千代田区"
    output_bucket = "somebucket"
    base_path = "foo/bar"
    event = {
        "ward": ward,
        "output_bucket": output_bucket,
        "base_path": base_path,
    }
    event_out = build_search_url.main(event, None)
    assert event_out is event
    assert event_out["search_url"] == "dummyurl"
