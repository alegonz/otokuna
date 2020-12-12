import argparse
import datetime
import logging
import re
import time
from pathlib import Path
from typing import List, Optional, Sequence, Dict, Set

import attr
import bs4
import coloredlogs
import requests

SUUMO_URL = "https://suumo.jp"


def setup_logger():
    logger = logging.getLogger("scrape")
    loglevel = logging.INFO
    logger.setLevel(loglevel)
    logger.addHandler(logging.StreamHandler())
    coloredlogs.install(level=loglevel, logger=logger,
                        fmt='%(asctime)s.%(msecs)03d %(name)s[%(process)d] %(levelname)s %(message)s',
                        datefmt='%H:%M:%S')
    return logger


logger = setup_logger()


def now_str_jst(fmt="%Y%m%d%H%M%S"):
    """Returns the current datetime in JST in YYYYmmddHHMMSS format."""
    timezone_jst = datetime.timezone(datetime.timedelta(hours=+9), "JST")
    now = datetime.datetime.now(tz=timezone_jst)
    return now.strftime(fmt)


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
    logger.info(f"Search condition codes: {condition_codes}")

    url_params = []
    for cond_id, codes in condition_codes.items():
        for code in codes:
            url_params.append(f"{cond_id}={code}")
    return search_url_template.format("&".join(url_params))


@attr.dataclass
class Building:
    category: str  # 建物種別 (e.g. "アパート", "マンション")
    title: str  # e.g. "Ｂｒｉｌｌｉａｉｓｔ元浅草"
    address: str  # e.g. "東京都台東区元浅草１"
    transportation: List[str]  # e.g. ["都営大江戸線/新御徒町駅 歩4分", ...]
    age: int  # years (新築 is casted to 0)
    floors: int  # floors (e.g. "11階建")

    @classmethod
    def from_tag(cls, tag: bs4.element.Tag):
        category = tag.find("div", class_="cassetteitem_content-label").text
        title = tag.find("div", class_="cassetteitem_content-title").text
        address = tag.find("li", class_="cassetteitem_detail-col1").text
        transportation = [div.text for div in tag.select("li.cassetteitem_detail-col2 div")]
        age, floors = (div.text for div in tag.select("li.cassetteitem_detail-col3 div"))
        return cls(category, title, address, transportation, age, floors)


@attr.dataclass
class Room:
    rent: int  # 賃料 (¥)
    administration_fee: int  # 管理費 (¥)
    deposit: int  # 敷金 (¥)
    gratuity: int  # 礼金 (¥)
    layout: str  # 間取り (e.g. 1R, 2LDK)
    area: float  # 面積 m2
    floor: int  # 階 1階~
    detail_href: str  # e.g. https://suumo.jp/chintai/jnc_000054786764/?bc=100216408055
    jnc_id: str  # 物件ID e.g. "000054786764"

    @classmethod
    def from_tag(cls, tag: bs4.element.Tag):
        rent = tag.find("span", class_="cassetteitem_price cassetteitem_price--rent").text
        administration_fee = tag.find("span", class_="cassetteitem_price cassetteitem_price--administration").text
        deposit = tag.find("span", class_="cassetteitem_price cassetteitem_price--deposit").text
        gratuity = tag.find("span", class_="cassetteitem_price cassetteitem_price--gratuity").text
        layout = tag.find("span", class_="cassetteitem_madori").text
        area = tag.find("span", class_="cassetteitem_menseki").text
        floor, *_ = tag.find_all("td")[2].stripped_strings
        detail_href = tag.select_one("td.ui-text--midium.ui-text--bold a")["href"]
        jnc_id = re.search(r"jnc_([0-9]*)/", detail_href).group(1)
        return cls(rent, administration_fee, deposit, gratuity,
                   layout, area, floor, detail_href, jnc_id)


@attr.dataclass
class Property:
    building: Building
    room: Room


def parse_money(s: str, *, unit="円") -> int:
    multipliers_by_unit = {"円": 1, "万円": 10000}
    if s == "-":
        return 0
    pattern = rf"(\d+){unit}"
    return int(re.search(pattern, s).group(1)) * multipliers_by_unit[unit]


def scrape_properties(search_results_soup: bs4.BeautifulSoup) -> List[Property]:
    building_tags = search_results_soup.find_all("div", class_="cassetteitem")
    properties = []
    for building_tag in building_tags:
        building = Building.from_tag(building_tag)
        room_tags = building_tag.select("table.cassetteitem_other tbody")
        for room_tag in room_tags:
            room = Room.from_tag(room_tag)
            properties.append(Property(building, room))
    return properties


def scrape_number_of_pages(search_results_soup: bs4.BeautifulSoup) -> int:
    page_links = search_results_soup.select("ol.pagination-parts li a")
    # Beware of this number; the number of results might change while scraping?
    last_page_number = int(page_links[-1].text)
    return last_page_number


def scrape_next_page_url(search_results_soup: bs4.BeautifulSoup) -> Optional[str]:
    next_elem = search_results_soup.find("div", class_="pagination pagination_set-nav").find(string="次へ")
    return f"{SUUMO_URL}{next_elem.parent['href']}" if next_elem else None


def main():
    parser = argparse.ArgumentParser(description="Search and dump property data from suumo")
    parser.add_argument("--dump-dir", default="dumped_data",
                        help="Directory where to dump the pages data. If the directory"
                             "does not exist, it will be created.")
    parser.add_argument("--building-categories", nargs="*", required=True,
                        help="Categories of buildings (e.g. 'マンション')")
    parser.add_argument("--wards", nargs="*", required=True,
                        help="Tokyo wards (e.g. '港区', '中央区')")
    parser.add_argument("--only-today", action="store_true",
                        help="Search and dump properties added today")

    datetime_str = now_str_jst()
    args = parser.parse_args()
    dump_dir = Path(f"{args.dump_dir}/{datetime_str}")
    dump_dir.mkdir(parents=True)
    search_url = build_search_url(building_categories=args.building_categories,
                                  wards=args.wards, only_today=False)
    page = 1
    while True:
        response = requests.get(search_url)
        search_results_soup = bs4.BeautifulSoup(response.text, "html.parser")
        if page == 1:
            n_pages = scrape_number_of_pages(search_results_soup)
            logger.info(f"Total result pages: {n_pages}")
        logger.info(f"Got page {page}: {search_url}")
        with open(dump_dir / f"page_{page:03d}.html", "w") as f:
            f.write(response.text)
        # properties = scrape_properties(search_results_soup)
        search_url = scrape_next_page_url(search_results_soup)
        if search_url is None:
            break
        page += 1
        time.sleep(2)


if __name__ == "__main__":
    main()
