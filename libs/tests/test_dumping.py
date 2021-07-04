import json
from pathlib import Path

import bs4
import pytest

from otokuna.dumping import (
    _get_condition_codes_by_value, _build_condition_codes,
    build_search_url, scrape_number_of_pages, scrape_next_page_url,
    iter_search_results, SUUMO_TOKYO_SEARCH_URL
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


def test_scrape_number_of_pages():
    with open(DATA_DIR / "results_first_page.html") as f:
        search_results_soup = bs4.BeautifulSoup(f, "html.parser")
    assert scrape_number_of_pages(search_results_soup) == 1607


@pytest.mark.parametrize("page_filename,expected", [
    ("results_first_page.html", "https://suumo.jp/jj/chintai/ichiran/FR301FC001/"
                                "?ts=1&sc=13115&sc=13107&sc=13118&sc=13110&sc=13120"
                                "&sc=13109&sc=13123&sc=13103&sc=13113&sc=13122&sc=13104"
                                "&sc=13112&sc=13121&sc=13111&sc=13106&sc=13102&sc=13116"
                                "&sc=13101&sc=13117&sc=13108&sc=13119&sc=13105&sc=13114"
                                "&ar=030&bs=040&ta=13&cb=0.0&ct=9999999&mb=0&mt=9999999"
                                "&et=9999999&cn=9999999&pc=50&page=2"),
    ("results_last_page.html", None),
])
def test_scrape_next_page_url(page_filename, expected):
    with open(DATA_DIR / page_filename) as f:
        search_results_soup = bs4.BeautifulSoup(f, "html.parser")
    assert scrape_next_page_url(search_results_soup) == expected


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
