#!/usr/bin/env python3

import argparse
import datetime
import logging
import time
from pathlib import Path
from typing import Optional, Sequence, Dict, Set

import bs4
import coloredlogs
import requests

SUUMO_URL = "https://suumo.jp"
TOKYO_SPECIAL_WARDS = (
    "千代田区", "中央区", "港区", "新宿区", "文京区", "台東区", "墨田区", "江東区",
    "品川区", "目黒区", "大田区", "世田谷区", "渋谷区", "中野区", "杉並区", "豊島区",
    "北区", "荒川区", "板橋区", "練馬区", "足立区", "葛飾区", "江戸川区"
)


def setup_logger(filename):
    logger = logging.getLogger("dump")
    loglevel = logging.INFO
    logger.setLevel(loglevel)
    logger.addHandler(logging.StreamHandler())
    log_format = "%(asctime)s.%(msecs)03d %(name)s[%(process)d] %(levelname)s %(message)s"

    file_handler = logging.FileHandler(filename)
    file_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(file_handler)

    coloredlogs.install(level=loglevel, logger=logger, fmt=log_format, datefmt="%Y-%m-%dT%H:%M:%S%z")
    return logger


def now_jst_isoformat():
    """Returns the current datetime in JST in ISO format (dropping milliseconds)."""
    timezone_jst = datetime.timezone(datetime.timedelta(hours=+9), "JST")
    now = datetime.datetime.now(tz=timezone_jst)
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
) -> Dict[str, Set[str]]:
    response = requests.get(f"{SUUMO_URL}/chintai/tokyo/city/")
    soup = bs4.BeautifulSoup(response.content, "html.parser")
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
            condition_codes[cond_id] = {code for value, code in codes_by_value.items() if value in values}
    return condition_codes


def build_search_url(*, building_categories: Sequence[str], wards: Sequence[str], only_today=True):
    """Build search url
    :param building_categories
    :param wards
    :param only_today:
    :return: search url that filter the results according to the given search conditions

    Notes:
    FR301FC001 directs to 物件ごとに表示
    &ar=030&bs=040&ta=13 are some hidden inputs (don't know what they mean)
    &cb=0.0 means 賃料：下限なし
    &ct=9999999 means 賃料：上限なし
    &mb=0 means 専有面積：下限なし
    &mt=9999999 means 専有面積：上限なし
    &et=9999999 means 駅徒歩：指定しない
    &cn=9999999 means 築年数：指定しない
    &shkr1=03&shkr2=03&shkr3=03&shkr4=03 don't know what these mean
    &sngz= don't know what this mean
    &po1=25 don't know what this mean
    &pc=50 means 50 results per page
    """
    search_url_template = f"{SUUMO_URL}/jj/chintai/ichiran/FR301FC001/" \
                          f"?{{}}" \
                          f"&ar=030&bs=040&ta=13" \
                          f"&cb=0.0&ct=9999999" \
                          f"&mb=0&mt=9999999" \
                          f"&et=9999999&cn=9999999" \
                          f"&pc=50"
    special_conditions = {"本日の新着物件"} if only_today else None
    condition_codes = _build_condition_codes(building_categories, wards, special_conditions)

    url_params = []
    for cond_id, codes in condition_codes.items():
        for code in codes:
            url_params.append(f"{cond_id}={code}")
    return search_url_template.format("&".join(url_params))


def scrape_number_of_pages(search_results_soup: bs4.BeautifulSoup) -> int:
    page_links = search_results_soup.select("ol.pagination-parts li a")
    # Beware of this number; the number of results might change while scraping?
    last_page_number = int(page_links[-1].text)
    return last_page_number


def scrape_next_page_url(search_results_soup: bs4.BeautifulSoup) -> Optional[str]:
    next_elem = search_results_soup.find("div", class_="pagination pagination_set-nav").find(string="次へ")
    return f"{SUUMO_URL}{next_elem.parent['href']}" if next_elem else None


def main():
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
    parser.add_argument("--sleep-time", default=2,
                        help="Time to sleep between fetches of result pages")

    args = parser.parse_args()
    datetime_str = now_jst_isoformat()
    dump_dir = Path(f"{args.dump_dir}/{datetime_str}")
    dump_dir.mkdir(parents=True)
    logger = setup_logger(dump_dir / "dump.log")

    search_url = build_search_url(building_categories=args.building_categories,
                                  wards=args.wards, only_today=args.only_today)
    n_attempts = 3
    page = 1
    while True:
        next_search_url = f"{search_url}&page={page}"
        for attempt in range(n_attempts):
            try:
                response = requests.get(next_search_url)
            except Exception as e:
                logger.error(f"Could not fetch page {page} (attempt: {attempt}): {e}")
                time.sleep(10)
            else:
                break
        else:
            continue
        search_results_soup = bs4.BeautifulSoup(response.text, "html.parser")
        if page == 1:
            n_pages = scrape_number_of_pages(search_results_soup)
            logger.info(f"Total result pages: {n_pages}")
        logger.info(f"Got page {page}: {next_search_url}")

        # dump html data to file
        with open(dump_dir / f"page_{page:03d}.html", "w") as f:
            f.write(response.text)

        if scrape_next_page_url(search_results_soup) is None:
            break
        page += 1
        time.sleep(args.sleep_time)


if __name__ == "__main__":
    main()
