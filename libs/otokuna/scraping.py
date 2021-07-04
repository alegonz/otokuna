#!/usr/bin/env python3
import datetime
import logging
import re
from argparse import ArgumentParser
from contextlib import ExitStack
from os import PathLike
from pathlib import Path
from statistics import mean
from typing import List, Tuple, Optional, Union, IO, Iterable
from zipfile import is_zipfile, ZipFile, ZipInfo

import attr
import bs4
import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from otokuna import SUUMO_URL
from otokuna.logging import setup_logger

_FileLike = Union[str, PathLike, IO[bytes]]


class ParsingError(Exception):
    pass


def _match_and_raise(pattern, string):
    match = re.match(pattern, string)
    if not match:
        raise ParsingError(f"Could not parse '{string}'")
    return match


def parse_age(s: str) -> int:
    """Parse the age of the building in years"""
    if s == "新築":
        return 0
    pattern = r"築(\d+)年"
    return int(_match_and_raise(pattern, s).group(1))


def parse_floors(s: str) -> int:
    """Parse number of floors of the building.
    Note: it only parses number of floors above the ground.
    """
    pattern = r"(地下\d+地上)?(\d+)階建"
    return int(_match_and_raise(pattern, s).group(2))


def parse_transportation(s: str) -> float:
    """Parse walking time to station in minutes. Properties that have
    driving times (e.g. '東京メトロ東西線/行徳駅 車15分(5.1km)') are not
    handled and will raise an error.
    """
    pattern = r".*歩(\d+)分$"  # TODO: should capture '.+' instead at the start
    return float(_match_and_raise(pattern, s).group(1))


def parse_address(s: str) -> Tuple[str, str]:
    """Parse ward and district (without the 丁目)"""
    ward, district = _match_and_raise(r"東京都(.+区)(\D*)", s).groups()
    return ward, district


def parse_money(s: str, *, unit="円") -> int:
    """Parse amount of money en JPY.
    The unit of string ("円" or "万円") can be chosen the to apply
    the appropriate conversion to JPY units.
    """
    if s == "-":
        return 0
    multipliers_by_unit = {"円": 1, "万円": 10000}
    pattern = rf"(\d*[.]?\d+){unit}"
    return int(float(_match_and_raise(pattern, s).group(1)) * multipliers_by_unit[unit])


def parse_floor_range(s: str) -> Tuple[int, int]:
    """Parse floor range (min_floor, max_floor).
    A property may have more than one floor and it may involve basement floors.
    We represent the floors as evenly spaced integers, so the basement floors
    are zero-based (e.g. B1 is floor 0) to avoid a "two floor" gap between B1 and 1.
    2階 = second floor
    2-階 = second floor (improperly formatted)
    3-5階 = from 3rd to 5th floor (three floors)
    B1階 = basement 1st floor
    B1-1階 = basement 1st floor to 1st floor
    B2-B1階 = basement 2nd floor to basement 1st floor
    """
    pattern = r"(B?\d+)-?(B?\d+)?階"
    min_floor_str, max_floor_str = _match_and_raise(pattern, s).groups()
    if min_floor_str is None or max_floor_str is None:
        min_floor_str = max_floor_str = min_floor_str or max_floor_str

    def parse_floor(floor_str):
        if floor_str.startswith("B"):
            return -int(floor_str[1:]) + 1
        return int(floor_str)

    min_floor, max_floor = parse_floor(min_floor_str), parse_floor(max_floor_str)
    # The range may be written in the inverse order e.g. 1-B1階
    min_floor, max_floor = sorted([min_floor, max_floor])
    return min_floor, max_floor


def parse_area(s: str) -> float:
    """Parse the room's surface area in m2"""
    pattern = r"(\d*[.]?\d+)m2"
    return float(_match_and_raise(pattern, s).group(1))


def parse_layout(s: str) -> Tuple[int, bool, bool, bool, bool]:
    """Parse layout of the room. It returns a tuple of five elements:
    0. Number of rooms (int)
    1. Has service room? (bool)
    2. Has living room? (bool)
    3. Has dining room? (bool)
    4. Has kitchen? (bool)
    """
    if s == "ワンルーム":
        return 1, False, False, False, False
    pattern = r"(\d+)[SLDK]+"
    n_rooms = int(_match_and_raise(pattern, s).group(1))
    return n_rooms, *(char in s for char in "SLDK")


def parse_banner_timestamp(s: str) -> Optional[float]:
    """Get timestamp of rotation ad banner from an embedded script.
    The timestamp is rounded to seconds.
    """
    found = re.search(r"&times=(\d+)", s)
    if not found:
        return None
    timestamp_ns = float(found.group(1))
    return round(timestamp_ns / 1000, 0)


def get_banner_timestamp(soup: bs4.BeautifulSoup) -> Optional[float]:
    timestamp = None
    for script in soup.findAll("script"):
        timestamp = parse_banner_timestamp(script.string or '')
        if timestamp is not None:
            break
    return timestamp


def _zipinfo_date_time_to_timestamp(date_time: Tuple) -> float:
    """Converts a date_time of a ZipInfo object to a unix timestamp.
    The timestamp is rounded to seconds because that is the resolution of
    date_time.
    """
    timestamp = datetime.datetime(*date_time).timestamp()
    assert timestamp.is_integer()
    return timestamp


def _timestamp_to_zipinfo_date_time(timestamp: float) -> Tuple:
    """Converts a unix timestamp to a date_time for a ZipInfo object."""
    date_time = datetime.datetime.fromtimestamp(timestamp).timetuple()[:6]
    return date_time


def get_last_modified_at_timestamp(filename: Union[Path, ZipInfo]) -> float:
    """Get timestamp of last modified time of the given file.
    The timestamp is rounded to seconds.
    """
    if isinstance(filename, Path):
        return round(filename.stat().st_mtime, 0)
    elif isinstance(filename, ZipInfo):
        return _zipinfo_date_time_to_timestamp(filename.date_time)
    else:
        raise ValueError("Invalid filename type.")


def scrape_number_of_pages(search_results_soup: bs4.BeautifulSoup) -> int:
    """Scrape the total number of search pages from a results page."""
    page_links = search_results_soup.select("ol.pagination-parts li a")
    # Beware of this number; the number of results might change while scraping?
    last_page_number = int(page_links[-1].text)
    return last_page_number


def scrape_next_page_url(search_results_soup: bs4.BeautifulSoup) -> Optional[str]:
    """Scrape the url of the next page from a results page."""
    next_elem = search_results_soup.find("div", class_="pagination pagination_set-nav").find(string="次へ")
    return f"{SUUMO_URL}{next_elem.parent['href']}" if next_elem else None


# attrs does not play well with cloudpickle (required by joblib)
# See: https://github.com/python-attrs/attrs/issues/458
@attr.dataclass(repr=False)
class Building:
    category: str  # 建物種別 (e.g. "アパート", "賃貸マンション")
    title: str  # e.g. "Ｂｒｉｌｌｉａｉｓｔ元浅草"
    address: str  # e.g. "東京都台東区元浅草１"
    transportation: Tuple[str, ...]  # e.g. ("都営大江戸線/新御徒町駅 歩4分", ...)
    age: int  # years (新築 is casted to 0)
    floors: int  # floors (e.g. "11階建")

    @classmethod
    def from_tag(cls, tag: bs4.element.Tag):
        category = tag.find("div", class_="cassetteitem_content-label").text
        title = tag.find("div", class_="cassetteitem_content-title").text
        address = tag.find("li", class_="cassetteitem_detail-col1").text
        # Use tuple avoid unhashable error during pandas.drop_duplicates
        transportation = tuple(div.text for div in tag.select("li.cassetteitem_detail-col2 div"))
        age, floors = (div.text for div in tag.select("li.cassetteitem_detail-col3 div"))
        return cls(category, title, address, transportation,
                   parse_age(age), parse_floors(floors))


@attr.dataclass(repr=False)
class Room:
    rent: int  # 賃料 (¥)
    admin_fee: int  # 管理費 (¥)
    deposit: int  # 敷金 (¥)
    gratuity: int  # 礼金 (¥)
    layout: str  # 間取り (e.g. 1R, 2LDK)
    area: float  # 面積 m2
    min_floor: int  # min階 (e.g. 1, 2, 3. B1, B2 are 0, -1, respectively)
    max_floor: int  # max階 (when the property covers only one floor min_floor == max_floor)
    url: str  # e.g. https://suumo.jp/chintai/jnc_000054786764/?bc=100216408055
    jnc_id: str  # 物件ID e.g. "000054786764"
    new_arrival: bool  # whether the property is labeled as 本日の新着物件 or not

    @classmethod
    def from_tag(cls, tag: bs4.element.Tag):
        rent = tag.find("span", class_="cassetteitem_price cassetteitem_price--rent").text
        admin_fee = tag.find("span", class_="cassetteitem_price cassetteitem_price--administration").text
        deposit = tag.find("span", class_="cassetteitem_price cassetteitem_price--deposit").text
        gratuity = tag.find("span", class_="cassetteitem_price cassetteitem_price--gratuity").text
        layout = tag.find("span", class_="cassetteitem_madori").text
        area = tag.find("span", class_="cassetteitem_menseki").text
        floor, *_ = tag.find_all("td")[2].stripped_strings
        min_floor, max_floor = parse_floor_range(floor)
        detail_href = tag.select_one("td.ui-text--midium.ui-text--bold a")["href"]
        url = f"{SUUMO_URL}{detail_href}"
        jnc_id = re.search(r"jnc_([0-9]*)/", detail_href).group(1)
        new_arrival = tag.find(class_="cassetteitem_other-checkbox--newarrival") is not None
        return cls(parse_money(rent, unit="万円"),
                   parse_money(admin_fee, unit="円"),
                   parse_money(deposit, unit="万円"),
                   parse_money(gratuity, unit="万円"),
                   layout, parse_area(area),
                   min_floor, max_floor,
                   url, jnc_id, new_arrival)


@attr.dataclass(repr=False)
class Property:
    building: Building
    room: Room
    html_file_banner_timestamp: Optional[float]  # timestamp of the ad banner in the html file
    html_file_last_modified_at: float


def scrape_properties_from_file(
        filename: Union[str, Path, ZipInfo],
        zip_filename: Optional[_FileLike] = None,
        logger: Optional[logging.Logger] = None
) -> List[Property]:
    """Scrape properties from given html file. filename can any file-like object.
    The file may be contained in a zip archive, in which case the filename is
    treated as a filename within the zip archive and you must pass a file-like
    of the zip file that contains the file. In that case, filename may be a ZipInfo
    object.
    """
    logger = logger or logging.getLogger("dummy")

    with ExitStack() as stack:
        if zip_filename is not None:
            zfile = stack.enter_context(ZipFile(zip_filename))
            if not isinstance(filename, ZipInfo):
                filename = zfile.getinfo(filename)
            file = stack.enter_context(zfile.open(filename))
        else:
            file = stack.enter_context(open(filename))
        last_modified_at = get_last_modified_at_timestamp(filename)
        search_results_soup = bs4.BeautifulSoup(file, "html.parser")

    banner_timestamp = get_banner_timestamp(search_results_soup)
    building_tags = search_results_soup.find_all("div", class_="cassetteitem")
    properties = []
    for building_tag in building_tags:
        try:
            building = Building.from_tag(building_tag)
        except ParsingError as e:
            logger.info(f"Skipping building due to error: {e}")
            continue
        room_tags = building_tag.select("table.cassetteitem_other tbody")
        for room_tag in room_tags:
            try:
                room = Room.from_tag(room_tag)
            except ParsingError as e:
                logger.info(f"Skipping property due to error: {e}")
                continue
            property_ = Property(building, room, banner_timestamp, last_modified_at)
            properties.append(property_)
    logger.info(f"Scraped {filename} ({len(properties)})")
    return properties


def scrape_properties_from_files(
        filenames: Iterable[Union[str, Path, ZipInfo]],
        zip_filename: Optional[_FileLike] = None,
        logger: Optional[logging.Logger] = None,
        n_jobs: int = 1
) -> List[Property]:
    """Scrape properties from several files. Each file can be any file-like
    object.

    The files may be contained in a zip archive, in which case each file is
    treated as a filename within the zip archive and you must pass a file-like
    of the zip file that contains the files. In that case, each file may be a
    ZipInfo object.

    This function supports parallel processing via the `n_jobs` argument. Pass
    n_jobs=-1 to use all CPU cores (defaults to 1 core). It returns a flattened
    list with the properties scraped from all files.
    """
    lists = Parallel(n_jobs=n_jobs)(
        delayed(scrape_properties_from_file)(filename, zip_filename, logger) for filename in filenames
    )
    return [p for sublist in lists for p in sublist]  # flatten


def make_properties_dataframe(
        properties: List[Property],
        html_file_fetched_at: Optional[float] = None,
        logger: Optional[logging.Logger] = None
) -> pd.DataFrame:
    """Make a dataframe from the given properties.
    You may specify a timestamp indicating when the html files were fetched
    from suumo, and it will be added as a column (equal for all rows).
    """
    logger = logger or logging.getLogger('dummy')

    series = []
    for property_ in properties:
        dict_ = attr.asdict(property_, recurse=False)
        # Building features
        feat_dict_ = {
            f"building_{key}": value
            for key, value in attr.asdict(dict_.pop("building"), retain_collection_types=True).items()
        }
        # Room features
        feat_dict_.update(attr.asdict(dict_.pop("room")))
        # Remaining Property attributes
        feat_dict_.update(dict_)
        feat_dict_["html_file_banner_timestamp"] = feat_dict_["html_file_banner_timestamp"] or np.nan
        try:
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
        except ParsingError as e:
            logger.info(f"Skipping property due to error: {e}")
            continue

        series.append(pd.Series(feat_dict_))
    df = pd.DataFrame(series)
    if html_file_fetched_at is not None:
        df["html_file_fetched_at"] = html_file_fetched_at
    df.set_index("jnc_id", drop=True, inplace=True)
    return df


def _main():
    logger = setup_logger("scrape-properties")

    parser = ArgumentParser(description="Scrape property data from paged html files "
                                        "and make a dataframe.")
    parser.add_argument("html_dir", help="Path to html data. It can also be a folder with html data.")
    parser.add_argument("--output-filename", help="Output filename. By default it is set "
                                                  "to the basename of html_dir.")
    parser.add_argument("--output-format", choices=("csv", "pickle"),
                        default="csv", help="Output file format")
    parser.add_argument("--jobs", default=1, type=int, help="Number of jobs for parallelization")
    parser.add_argument("--fetched-today", action="store_true", help="Add current timestamp in a column.")
    args = parser.parse_args()

    html_dir = Path(args.html_dir)
    if is_zipfile(html_dir):
        with ZipFile(html_dir) as zfile:
            filenames = sorted(
                (zi for zi in zfile.infolist()
                 if not zi.is_dir() and zi.filename.endswith(".html")),
                key=lambda zi: zi.filename
            )
        zip_filename = html_dir
    else:
        if html_dir.is_dir():
            filenames = sorted(p for p in html_dir.glob("*.html") if not p.is_dir())
        else:
            filenames = [html_dir]
        zip_filename = None

    properties = scrape_properties_from_files(filenames, zip_filename, logger=logger, n_jobs=args.jobs)

    html_file_fetched_at = round(datetime.datetime.now().timestamp(), 0) if args.fetched_today else None
    df = make_properties_dataframe(properties, html_file_fetched_at, logger)

    if not args.output_filename:
        output_filename = Path(args.html_dir).resolve()
        output_filename = output_filename.with_suffix(f".{args.output_format}").name
    else:
        output_filename = args.output_filename

    if args.output_format == "csv":
        df.to_csv(output_filename)
    else:  # args.output_format == "pickle"
        df.to_pickle(output_filename)
