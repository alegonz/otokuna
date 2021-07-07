import build_search_url


def test_main(monkeypatch):
    monkeypatch.setattr(
        "build_search_url.build_search_url",
        lambda building_categories, wards, only_today: "dummyurl"
    )

    batch_name = "千代田区"
    base_path = "foo/bar"
    event = {
        "batch_name": batch_name,
        "base_path": base_path,
    }
    event_out = build_search_url.main(event, None)
    assert event_out is event
    assert event_out["search_url"] == "dummyurl"
