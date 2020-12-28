import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from otokuna.dumping import _get_condition_codes_by_value, _build_condition_codes, build_search_url

DATA_DIR = Path(__file__).parent / "data"

EXPECTED_CODES_BY_VALUE = json.loads(
    (DATA_DIR / "expected_codes_by_value.json").read_text()
)


def mock_requests_get(url):
    class MockResponse:
        def __init__(self, text):
            self.text = text

    with open(DATA_DIR / "chintai_tokyo_search_page.html") as f:
        response = MockResponse(f.read())
    return response


@pytest.mark.parametrize("cond_id", ["ts", "sc", "tc"])
def test_get_condition_codes_by_value(cond_id):
    with open(DATA_DIR / "chintai_tokyo_search_page.html") as f:
        soup = BeautifulSoup(f, "html.parser")
    assert _get_condition_codes_by_value(soup, cond_id) == EXPECTED_CODES_BY_VALUE[cond_id]


def test_build_condition_codes(monkeypatch):
    def mock_requests_get(url):
        class MockResponse:
            def __init__(self, text):
                self.text = text
        with open(DATA_DIR / "chintai_tokyo_search_page.html") as f:
            response = MockResponse(f.read())
        return response

    monkeypatch.setattr("otokuna.dumping.requests.get", mock_requests_get)

    expected = {
        "ts": {"1"},
        "sc": {"13102", "13113"},
        "tc": {"0401303"}
    }
    assert _build_condition_codes(["マンション"], ["中央区", "渋谷区"], ["本日の新着物件"]) == expected


def test_build_condition_codes_invalid_value(monkeypatch):
    monkeypatch.setattr("otokuna.dumping.requests.get", mock_requests_get)

    expected_error_msg = "invalid values for condition sc: {'あいうえお区'}"
    with pytest.raises(RuntimeError, match=expected_error_msg):
        _build_condition_codes(wards=["あいうえお区"])


def test_build_search_url(monkeypatch):
    monkeypatch.setattr("otokuna.dumping.requests.get", mock_requests_get)
    search_url = build_search_url(building_categories=["マンション"],
                                  wards=["中央区", "渋谷区"],
                                  only_today=True)
    # TODO: Consider making deterministic the order of params in the search url
    #  to allow testing existence of exact substring: "?ts=1&sc=13102&sc=13113&tc=0401303"
    for param in ("ts=1", "sc=13102", "sc=13113", "tc=0401303"):
        assert param in search_url
