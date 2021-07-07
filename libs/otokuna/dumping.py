#!/usr/bin/env python3

import argparse
import datetime
import logging
import time
from pathlib import Path
from typing import Optional, Sequence, Dict, Tuple, Iterator, List
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import bs4
import requests

from otokuna import SUUMO_URL
from otokuna.logging import setup_logger, LOCAL_TIMEZONE

TOKYO_SPECIAL_WARDS = (
    "千代田区", "中央区", "港区", "新宿区", "文京区", "台東区", "墨田区", "江東区",
    "品川区", "目黒区", "大田区", "世田谷区", "渋谷区", "中野区", "杉並区", "豊島区",
    "北区", "荒川区", "板橋区", "練馬区", "足立区", "葛飾区", "江戸川区"
)
SUUMO_TOKYO_SEARCH_URL = f"{SUUMO_URL}/chintai/tokyo/city/"

# TODO: Consider bundling the 全国地方公共団体コード data to assert code-ward codes.
#   See: https://www.soumu.go.jp/denshijiti/code.html


def now_isoformat():
    """Returns the current datetime in JST in ISO format (dropping milliseconds)."""
    now = datetime.datetime.now(tz=LOCAL_TIMEZONE)
    return now.isoformat(timespec="seconds")


def _get_condition_codes_by_value(soup, cond_id):
    codes_by_value = {}
    for checkbox in soup.find_all("input", attrs=dict(type="checkbox", name=cond_id)):
        label = soup.find("label", attrs={"for": checkbox["id"]})
        value = list(label.strings)[0]
        code = checkbox["value"]
        codes_by_value[value] = code
    return codes_by_value


def _build_condition_codes(
        building_categories: Optional[Sequence[str]] = None,
        wards: Optional[Sequence[str]] = None,
        special_conditions: Optional[Sequence[str]] = None
) -> Dict[str, List[str]]:
    response = requests.get(SUUMO_TOKYO_SEARCH_URL)
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    condition_codes = {}
    values_by_cond_id = {
        "ts": building_categories,
        "sc": wards,
        "tc": special_conditions,
        # "kz" structure_types
    }
    for cond_id, values in values_by_cond_id.items():
        if values is not None:
            codes_by_value = _get_condition_codes_by_value(soup, cond_id)
            values_not_found = set(values) - set(codes_by_value.keys())
            if values_not_found:
                raise RuntimeError(f"invalid values for condition {cond_id}: {values_not_found}")
            condition_codes[cond_id] = sorted(code for value, code in codes_by_value.items() if value in values)
    return condition_codes


def remove_params(url, params):
    """Remove parameters (if any) from the given url.
    Based on: https://stackoverflow.com/a/7734686
    """
    u = urlparse(url)
    query = parse_qs(u.query, keep_blank_values=True)
    for param in params:
        query.pop(param, None)
    u2 = u._replace(query=urlencode(query, doseq=True))
    return urlunparse(u2)


def remove_page_param(url):
    """Remove page query parameter (if any) from the given url."""
    return remove_params(url, ["page"])


def add_params(url, values_by_param):
    """Adds parameters to a given url."""
    u = urlparse(url)
    query = parse_qs(u.query, keep_blank_values=True)
    for param, values in values_by_param.items():
        query[param] = values
    u2 = u._replace(query=urlencode(query, doseq=True))
    return urlunparse(u2)


def add_results_per_page_param(url):
    """Adds the 50 results per page query parameter to the given URL.
    If the parameter already exists (once or several times), it will
    set to once and to 50.
    """
    return add_params(url, {"pc": ["50"]})


def build_search_url(*, building_categories: Sequence[str], wards: Sequence[str], only_today=True):
    """Build search url for properties in Tokyo (東京)
    TODO: support arbitrary cities
    TODO: precompute condition codes

    :param building_categories
    :param wards
    :param only_today:
    :return: search url that filter the results according to the given search conditions

    Notes:
    FR301FC001 directs to 物件ごとに表示
    &ar=030&bs=040&ta=13 are some hidden inputs (don't know what these mean)
    &cb=0.0 means 賃料：下限なし
    &ct=9999999 means 賃料：上限なし
    &mb=0 means 専有面積：下限なし
    &mt=9999999 means 専有面積：上限なし
    &et=9999999 means 駅徒歩：指定しない
    &cn=9999999 means 築年数：指定しない
    &shkr1=03&shkr2=03&shkr3=03&shkr4=03 don't know what these mean
    &sngz= don't know what this means
    &po1=25 don't know what this means
    &pc=50 means 50 results per page
    """
    base_search_url = f"{SUUMO_URL}/jj/chintai/ichiran/FR301FC001/?" \
                      f"&ar=030&bs=040&ta=13" \
                      f"&cb=0.0&ct=9999999" \
                      f"&mb=0&mt=9999999" \
                      f"&et=9999999&cn=9999999" \
                      f"&pc=50"
    special_conditions = {"本日の新着物件"} if only_today else None
    condition_codes = _build_condition_codes(building_categories, wards, special_conditions)

    u = urlparse(base_search_url)
    query = parse_qs(u.query, keep_blank_values=True)
    query.update(condition_codes)
    return urlunparse(u._replace(query=urlencode(query, doseq=True)))


def scrape_number_of_pages(search_results_soup: bs4.BeautifulSoup) -> int:
    page_links = search_results_soup.select("ol.pagination-parts li a")
    # Beware of this number; the number of results might change while scraping?
    last_page_number = int(page_links[-1].text)
    return last_page_number


def scrape_next_page_url(search_results_soup: bs4.BeautifulSoup) -> Optional[str]:
    next_elem = search_results_soup.find("div", class_="pagination pagination_set-nav").find(string="次へ")
    return f"{SUUMO_URL}{next_elem.parent['href']}" if next_elem else None


def iter_search_results(search_url: str, sleep_time: float,
                        logger: Optional[logging.Logger] = None) -> Iterator[Tuple[int, requests.Response]]:
    """Iterates over the search results pages from the given search URL.
    Each iteration yields a tuple with the page number (one-indexed) and the
    response object of the search results page.
    """
    logger = logger or logging.getLogger('dummy')
    n_attempts = 3
    page = 1
    while True:
        response = _get_page(search_url, page, n_attempts, logger)
        search_results_soup = bs4.BeautifulSoup(response.text, "html.parser")
        if page == 1:
            n_pages = scrape_number_of_pages(search_results_soup)
            logger.info(f"Total result pages: {n_pages}")

        yield page, response

        if scrape_next_page_url(search_results_soup) is None:
            break
        page += 1
        time.sleep(sleep_time)


def _get_page(search_url, page, n_attempts, logger):
    search_page_url = add_params(search_url, {"page": [str(page)]})
    for attempt in range(n_attempts):
        try:
            response = requests.get(search_page_url)
        except Exception as e:
            logger.error(f"Could not fetch page {page} (attempt: {attempt}): {e}")
            time.sleep(10)
        else:
            break
    else:
        raise RuntimeError(f"Could not get: {search_page_url}")
    logger.info(f"Got page {page}: {search_page_url}")
    return response


def dump_properties(dump_dir: str, building_categories: Sequence[str], wards: Sequence[str],
                    only_today: bool, sleep_time: float):
    """Dump the search results of property data to files, searched according to
    the given conditions. It dumps each search result page on a separate file.
    The data is written in a sub-folder named from the current timestamp in the
    given dump_dir.
    """
    datetime_str = now_isoformat()
    dump_dir = Path(f"{dump_dir}/{datetime_str}/東京都")
    dump_dir.mkdir(parents=True)
    logger = setup_logger("dump-properties", dump_dir / "dump.log")
    search_url = build_search_url(building_categories=building_categories,
                                  wards=wards, only_today=only_today)
    for page, response in iter_search_results(search_url, sleep_time, logger):
        # dump html data to file
        with open(dump_dir / f"page_{page:06d}.html", "w") as f:
            f.write(response.text)


def _main():
    parser = argparse.ArgumentParser(description="Search and dump property data of "
                                                 "Tokyo special wards from SUUMO.")
    parser.add_argument("--dump-dir", default="dumped_data",
                        help="Directory where to dump the pages data. If the directory"
                             "does not exist, it will be created.")
    parser.add_argument("--building-categories", nargs="*", default=("マンション",),
                        help="Categories of buildings (e.g. 'マンション', 'アパート')")
    parser.add_argument("--wards", nargs="*", default=TOKYO_SPECIAL_WARDS,
                        help="Tokyo wards (e.g. '港区', '中央区')")
    parser.add_argument("--only-today", action="store_true",
                        help="Search and dump properties added today")
    parser.add_argument("--sleep-time", default=2, type=float,
                        help="Time to sleep between fetches of result pages")

    args = parser.parse_args()
    dump_properties(**vars(args))
