import datetime
import json
import re
from pathlib import Path
from typing import List, Optional

import attr
import bs4
import requests

SUUMO_URL = "https://suumo.jp"


def now_str_jst(fmt="%Y%m%d%H%M%S"):
    """Returns the current datetime in JST in YYYYmmddHHMMSS format."""
    timezone_jst = datetime.timezone(datetime.timedelta(hours=+9), "JST")
    now = datetime.datetime.now(tz=timezone_jst)
    return now.strftime(fmt)


def get_condition_codes(soup, name):
    codes = {}
    for checkbox in soup.find_all("input", attrs=dict(type="checkbox", name=name)):
        label = soup.find("label", attrs={"for": checkbox["id"]})
        item_name = list(label.strings)[0]
        item_code = checkbox["value"]
        codes[item_name] = item_code
    return codes


def build_condition_codes():
    response = requests.get(f"{SUUMO_URL}/chintai/tokyo/city/")
    soup = bs4.BeautifulSoup(response.content, "html.parser")
    conditions = {}
    # sc = ward
    # ts = building type
    # kz = structure type
    # tc = special conditions
    for cond in ("sc", "ts", "kz", "tc"):
        conditions[cond] = get_condition_codes(soup, cond)
    return conditions


def build_search_url(search_conditions, *, only_today=True):
    """Build search url
    :param search_conditions: a dictionary of items by condition codes
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
    condition_codes = build_condition_codes()

    def build_url_param(condition_, item_):
        code = condition_codes[condition_][item_]
        return f"{condition_}={code}"

    url_params = []
    for condition, items in search_conditions.items():
        for item in items:
            url_params.append(build_url_param(condition, item))
    if only_today:
        url_params.append(build_url_param("tc", "本日の新着物件"))
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
    # TODO: pass conditions by json file and dump directory by command line argument
    datetime_str = now_str_jst()
    dump_dir = Path(f"dumped_data/{datetime_str}")
    dump_dir.mkdir(parents=True)
    search_conditions = {
        "sc": ["台東区"],
        "ts": ["マンション"]
    }

    with open(dump_dir / "search_conditions.json", "w") as f:
        json.dump(search_conditions, f)

    search_url = build_search_url(search_conditions, only_today=True)
    page = 1
    while search_url is not None:
        response = requests.get(search_url)
        search_results_soup = bs4.BeautifulSoup(response.text, "html.parser")
        if page == 1:
            n_pages = scrape_number_of_pages(search_results_soup)
            print(f"Total result pages: {n_pages}")
        print(f"Got page {page}:", search_url)
        with open(dump_dir / f"page_{page:03d}.html", "w") as f:
            f.write(response.text)
        search_url = scrape_next_page_url(search_results_soup)
        page += 1
        # properties = scrape_properties(search_results_soup)


if __name__ == "__main__":
    main()
