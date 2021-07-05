import json
from pathlib import Path

import bs4
import pytest

from otokuna.dumping import (
    _get_condition_codes_by_value, _build_condition_codes,
    build_search_url, iter_search_results, SUUMO_TOKYO_SEARCH_URL, drop_page_query
)
from otokuna.testing import build_mock_requests_get

DATA_DIR = Path(__file__).parent / "data"

EXPECTED_CODES_BY_VALUE = json.loads(
    (DATA_DIR / "expected_codes_by_value.json").read_text()
)


@pytest.mark.parametrize("cond_id", ["ts", "sc", "tc"])
def test_get_condition_codes_by_value(cond_id):
    with open(DATA_DIR / "chintai_tokyo_search_page.html") as f:
        soup = bs4.BeautifulSoup(f, "html.parser")
    assert _get_condition_codes_by_value(soup, cond_id) == EXPECTED_CODES_BY_VALUE[cond_id]


def test_build_condition_codes(monkeypatch):
    html_files_by_url = {SUUMO_TOKYO_SEARCH_URL: DATA_DIR / "chintai_tokyo_search_page.html"}
    monkeypatch.setattr("otokuna.dumping.requests.get", build_mock_requests_get(html_files_by_url))

    expected = {
        "ts": {"1"},
        "sc": {"13102", "13113"},
        "tc": {"0401303"}
    }
    assert _build_condition_codes(["マンション"], ["中央区", "渋谷区"], ["本日の新着物件"]) == expected


def test_build_condition_codes_invalid_value(monkeypatch):
    html_files_by_url = {SUUMO_TOKYO_SEARCH_URL: DATA_DIR / "chintai_tokyo_search_page.html"}
    monkeypatch.setattr("otokuna.dumping.requests.get", build_mock_requests_get(html_files_by_url))

    expected_error_msg = "invalid values for condition sc: {'あいうえお区'}"
    with pytest.raises(RuntimeError, match=expected_error_msg):
        _build_condition_codes(wards=["あいうえお区"])


@pytest.mark.parametrize("url", [
    "https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=030&bs=040&ta=13&sc=13107",
    "https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=030&bs=040&ta=13&sc=13107&page=123",
    "https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=030&bs=040&ta=13&sc=13107&page=1&page=2",
    "https://suumo.jp/jj/chintai/ichiran/FR301FC001/?page=1&ar=030&bs=040&ta=13&sc=13107",
    "https://suumo.jp/jj/chintai/ichiran/FR301FC001/?page=1&page=2&ar=030&bs=040&ta=13&sc=13107"
])
def test_drop_page_query(url):
    expected = "https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=030&bs=040&ta=13&sc=13107"
    assert drop_page_query(url) == expected


def test_build_search_url(monkeypatch):
    html_files_by_url = {SUUMO_TOKYO_SEARCH_URL: DATA_DIR / "chintai_tokyo_search_page.html"}
    monkeypatch.setattr("otokuna.dumping.requests.get", build_mock_requests_get(html_files_by_url))

    search_url = build_search_url(building_categories=["マンション"],
                                  wards=["中央区", "渋谷区"],
                                  only_today=True)
    # TODO: Consider making deterministic the order of params in the search url
    #  to allow testing existence of exact substring: "?ts=1&sc=13102&sc=13113&tc=0401303"
    for param in ("ts=1", "sc=13102", "sc=13113", "tc=0401303"):
        assert param in search_url


def test_iter_search_results(monkeypatch):
    html_files_by_url = {
        "dummyurl&page=1": DATA_DIR / "results_first_page.html",
        "dummyurl&page=2": DATA_DIR / "results_last_page.html"
    }
    monkeypatch.setattr("otokuna.dumping.requests.get", build_mock_requests_get(html_files_by_url))
    monkeypatch.setattr("otokuna.dumping.time.sleep", lambda _: _)
    for page, response in iter_search_results("dummyurl", 2):
        pass
    assert page == 2


def test_iter_search_results_fail(monkeypatch):
    def mock_requests_get_fail(url):
        raise Exception
    monkeypatch.setattr("otokuna.dumping.requests.get", mock_requests_get_fail)
    monkeypatch.setattr("otokuna.dumping.time.sleep", lambda _: _)
    with pytest.raises(RuntimeError):
        for page, response in iter_search_results("dummyurl", 2):
            pass
