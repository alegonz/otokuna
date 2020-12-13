#!/usr/bin/env python3
import re
from argparse import ArgumentParser
from pathlib import Path
from statistics import mean
from typing import List, Tuple

import attr
import bs4
import pandas as pd


class ParsingError(Exception):
    pass


def _match_and_raise(pattern, string):
    match = re.match(pattern, string)
    if not match:
        raise ParsingError(f"Could not parse '{string}'")
    return match


def parse_age(s: str) -> int:
    if s == "新築":
        return 0
    pattern = r"築(\d+)年"
    return int(_match_and_raise(pattern, s).group(1))


def parse_floors(s: str) -> int:
    pattern = r"(地下\d+地上)?(\d+)階建"
    return int(_match_and_raise(pattern, s).group(2))


def parse_transportation(s: str) -> float:
    """Parse walking time to station in minutes"""
    pattern = r".*歩(\d+)分$"
    return float(_match_and_raise(pattern, s).group(1))


def parse_address(s: str) -> Tuple[str, str]:
    """Parse ward and district (without the 丁目)"""
    ward, district = _match_and_raise(r"東京都(.+区)(\D*)", s).groups()
    return ward, district


def parse_money(s: str, *, unit="円") -> int:
    if s == "-":
        return 0
    multipliers_by_unit = {"円": 1, "万円": 10000}
    pattern = rf"(\d*[.]?\d+){unit}"
    return int(float(_match_and_raise(pattern, s).group(1)) * multipliers_by_unit[unit])


def parse_floor(s: str) -> int:
    # Currently multi-floor (e.g. 2-7階) properties are not supported
    pattern = r"(\d+)階"
    return int(_match_and_raise(pattern, s).group(1))


def parse_area(s: str) -> float:
    pattern = r"(\d*[.]?\d+)m2"
    return float(_match_and_raise(pattern, s).group(1))


def parse_layout(s: str) -> Tuple[int, bool, bool, bool, bool]:
    if s == "ワンルーム":
        return 1, False, False, False, False
    pattern = r"(\d+)[SLDK]+"
    n_rooms = int(_match_and_raise(pattern, s).group(1))
    return n_rooms, *(char in s for char in "SLDK")


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
        return cls(category, title, address, transportation,
                   parse_age(age), parse_floors(floors))


@attr.dataclass
class Room:
    rent: int  # 賃料 (¥)
    admin_fee: int  # 管理費 (¥)
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
        admin_fee = tag.find("span", class_="cassetteitem_price cassetteitem_price--administration").text
        deposit = tag.find("span", class_="cassetteitem_price cassetteitem_price--deposit").text
        gratuity = tag.find("span", class_="cassetteitem_price cassetteitem_price--gratuity").text
        layout = tag.find("span", class_="cassetteitem_madori").text
        area = tag.find("span", class_="cassetteitem_menseki").text
        floor, *_ = tag.find_all("td")[2].stripped_strings
        detail_href = tag.select_one("td.ui-text--midium.ui-text--bold a")["href"]
        jnc_id = re.search(r"jnc_([0-9]*)/", detail_href).group(1)
        return cls(parse_money(rent, unit="万円"),
                   parse_money(admin_fee, unit="円"),
                   parse_money(deposit, unit="万円"),
                   parse_money(gratuity, unit="万円"),
                   layout, parse_area(area), parse_floor(floor),
                   detail_href, jnc_id)


@attr.dataclass
class Property:
    building: Building
    room: Room


def scrape_properties_from_html_file(filename: Path) -> List[Property]:
    with open(filename, "r") as file:
        search_results_soup = bs4.BeautifulSoup(file, "html.parser")
    building_tags = search_results_soup.find_all("div", class_="cassetteitem")
    properties = []
    for building_tag in building_tags:
        building = Building.from_tag(building_tag)
        room_tags = building_tag.select("table.cassetteitem_other tbody")
        for room_tag in room_tags:
            try:
                room = Room.from_tag(room_tag)
            except ParsingError as e:
                print(f"Skipping property due to error: {e}")
                continue
            properties.append(Property(building, room))
    return properties


def make_properties_dataframe(properties: List[Property]) -> pd.DataFrame:
    series = []
    for property_ in properties:
        # Building features
        feat_dict_ = {f"building_{key}": value
                      for key, value in attr.asdict(property_.building).items()}
        # Room features
        feat_dict_.update(attr.asdict(property_.room))
        # Layout features
        (feat_dict_["n_rooms"],
         feat_dict_["service_room"],
         feat_dict_["living_room"],
         feat_dict_["dining_room"],
         feat_dict_["kitchen"]) = parse_layout(property_.room.layout)
        # Transportation features:
        walking_times = [parse_transportation(t) for t in property_.building.transportation if t]
        feat_dict_["n_stations"] = len(walking_times)
        feat_dict_["walk_time_station_min"] = min(walking_times)
        feat_dict_["walk_time_station_avg"] = mean(walking_times)
        # Address features:
        feat_dict_["ward"], feat_dict_["district"] = parse_address(property_.building.address)

        series.append(pd.Series(feat_dict_))
    return pd.DataFrame(series)


def build_df_from_data_files(filenames: List[Path]):
    all_properties = []
    for filename in filenames:
        properties = scrape_properties_from_html_file(filename)
        all_properties.extend(properties)
        print(f"Scraped {filename} ({len(properties)}/{len(all_properties)})")
    return make_properties_dataframe(all_properties)


if __name__ == "__main__":
    parser = ArgumentParser(description="Scrape property data from paged html files "
                                        "and make a dataframe. The dataframe is stored "
                                        "in feather format.")
    parser.add_argument("html_dir", help="Path to html data. It can also be a folder with html data.")
    parser.add_argument("--output-filename", help="Output filename. By default it is set "
                                                  "to the basename of html_dir.")
    parser.add_argument("--output-format", choices=("feather", "csv"),
                        default="csv", help="Output file format")
    args = parser.parse_args()

    html_dir = Path(args.html_dir)
    filenames = sorted(html_dir.glob("*.html")) if html_dir.is_dir() else [html_dir]
    df = build_df_from_data_files(filenames)

    output_filename = Path(args.html_dir) if not args.output_filename else Path(args.output_filename)
    output_filename = output_filename.with_suffix(f".{args.output_format}").name
    if args.output_format == "feather":
        df.to_feather(output_filename)
    else:  # args.output_format == "csv"
        df.to_csv(output_filename)
