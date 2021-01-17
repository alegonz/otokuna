from functools import partial
from pathlib import Path

import pandas as pd
import pytest
from _pytest.python_api import RaisesContext

from otokuna.scraping import (
    parse_address, parse_age, parse_area, parse_floor_range,
    parse_floors, parse_layout, parse_money, parse_transportation,
    make_properties_dataframe, scrape_properties_from_file,
    ParsingError, Property, Building, Room,
)

DATA_DIR = Path(__file__).parent / "data"


def assert_parse(func, input_, expected):
    if isinstance(expected, RaisesContext):
        with expected:
            func(input_)
    else:
        assert func(input_) == expected


@pytest.mark.parametrize("address,expected", [
    ("東京都渋谷区恵比寿南１", ("渋谷区", "恵比寿南")),
    ("東京都渋谷区恵比寿南1", ("渋谷区", "恵比寿南")),
    ("東京都渋谷区神泉町", ("渋谷区", "神泉町")),
    ("神奈川県横浜市中区山下町２２", pytest.raises(ParsingError))
])
def test_parse_address(address, expected):
    assert_parse(parse_address, address, expected)


@pytest.mark.parametrize("age,expected", [
    ("新築", 0),
    ("築１２年", 12),
    ("築12年", 12),
    ("築1年", 1),
    ("築年", pytest.raises(ParsingError))
])
def test_parse_age(age, expected):
    assert_parse(parse_age, age, expected)


@pytest.mark.parametrize("area,expected", [
    ("30m2", 30),
    ("30.5m2", 30.5),
    (".8m2", 0.8),
    ("30.m2", pytest.raises(ParsingError)),
    ("30", pytest.raises(ParsingError))
])
def test_parse_area(area, expected):
    assert_parse(parse_area, area, expected)


@pytest.mark.parametrize("floor_range,expected", [
    ("2階", (2, 2)),  # second floor
    ("2-階", (2, 2)),  # second floor (improperly formatted)
    ("3-5階", (3, 5)),  # from 3rd to 5th floor (three floors)
    ("B1階", (0, 0)),  # basement 1st floor
    ("B1-1階", (0, 1)),  # basement 1st floor to 1st floor
    ("B2-B1階", (-1, 0)),  # basement 2nd floor to basement 1st floor
    ("1-B1階", (0, 1)),  # The range may be written in the inverse order
    ("階", pytest.raises(ParsingError))
])
def test_parse_floor_range(floor_range, expected):
    assert_parse(parse_floor_range, floor_range, expected)


@pytest.mark.parametrize("floors,expected", [
    ("3階建", 3),
    ("地下1地上3階建", 3),
    ("地上3階建", pytest.raises(ParsingError)),
])
def test_parse_floors(floors, expected):
    assert_parse(parse_floors, floors, expected)


@pytest.mark.parametrize("layout,expected", [
    # layout, (number of rooms, S?, L?, D?, K?)
    ("ワンルーム", (1, False, False, False, False)),
    ("1K", (1, False, False, False, True)),
    ("2DK", (2, False, False, True, True)),
    ("3LDK", (3, False, True, True, True)),
    ("4SLDK", (4, True, True, True, True))
])
def test_parse_layout(layout, expected):
    assert_parse(parse_layout, layout, expected)


@pytest.mark.parametrize("money,unit,expected", [
    ("-", "円", 0),
    ("-", "万円", 0),
    ("5000円", "円", 5000),
    ("8万円", "万円", 80000),
    ("8.5万円", "万円", 85000),
    (".5万円", "万円", 5000),
    ("8.万円", "万円", pytest.raises(ParsingError)),
])
def test_parse_money(money, unit, expected):
    assert_parse(partial(parse_money, unit=unit), money, expected)


@pytest.mark.parametrize("transportation,expected", [
    ("都営浅草線/西馬込駅 歩18分", 18),
    ("都営浅草線/西馬込駅 歩18", pytest.raises(ParsingError)),
    ("東京メトロ東西線/行徳駅 車15分(5.1km)", pytest.raises(ParsingError)),
])
def test_parse_transportation(transportation, expected):
    assert_parse(parse_transportation, transportation, expected)


def test_scrape_properties_from_file():
    properties = scrape_properties_from_file(DATA_DIR / "results_first_page.html")
    expected_first = Property(
        building=Building(
            category="賃貸マンション",
            title="スカイコート池袋第7",
            address="東京都豊島区上池袋１",
            transportation=("ＪＲ山手線/池袋駅 歩14分", "ＪＲ山手線/大塚駅 歩12分", "ＪＲ埼京線/板橋駅 歩12分"),
            age=14,
            floors=11
        ),
        room=Room(
            rent=77300,
            admin_fee=6200,
            deposit=77300,
            gratuity=77300,
            layout="1K",
            area=20.35,
            min_floor=5,
            max_floor=5,
            url="https://suumo.jp/chintai/jnc_000062096181/?bc=100220224172",
            jnc_id="000062096181"
        )
    )
    expected_last = Property(
        building=Building(
            category="賃貸マンション",
            title="エスコート・チエ",
            address="東京都江戸川区北小岩３",
            transportation=("京成本線/江戸川駅 歩3分", "ＪＲ総武線/小岩駅 歩17分", "京成本線/国府台駅 歩15分"),
            age=16,
            floors=2
        ),
        room=Room(
            rent=87000,
            admin_fee=3000,
            deposit=87000,
            gratuity=87000,
            layout="1LDK",
            area=41.74,
            min_floor=1,
            max_floor=1,
            url="https://suumo.jp/chintai/jnc_000062620201/?bc=100210051791",
            jnc_id="000062620201"
        )
    )
    assert len(properties) == 198
    assert properties[0] == expected_first
    assert properties[-1] == expected_last


def test_make_properties_dataframe():
    property_ = Property(
        building=Building(category="賃貸マンション", title="セントラルメゾン", address="東京都大田区中央１",
                          transportation=("ＪＲ京浜東北線/大森駅 バス7分 (バス停)臼田坂下 歩1分",
                                          "都営浅草線/西馬込駅 歩18分",
                                          "京急本線/平和島駅 歩24分"),
                          age=34, floors=4),
        room=Room(rent=69000, admin_fee=0, deposit=69000, gratuity=69000, layout="1K", area=22.1,
                  min_floor=3, max_floor=3, url=f"https://suumo.jp/chintai/jnc_000060701156/?bc=100206393921",
                  jnc_id="000060701156")
    )

    expected = pd.DataFrame.from_dict(
        data={
            "building_category": ["賃貸マンション"],
            "building_title": ["セントラルメゾン"],
            "building_address": ["東京都大田区中央１"],
            "building_transportation": [("ＪＲ京浜東北線/大森駅 バス7分 (バス停)臼田坂下 歩1分", "都営浅草線/西馬込駅 歩18分", "京急本線/平和島駅 歩24分")],
            "building_age": [34],
            "building_floors": [4],
            "rent": [69000],
            "admin_fee": [0],
            "deposit": [69000],
            "gratuity": [69000],
            "layout": ["1K"],
            "area": [22.1],
            "min_floor": [3],
            "max_floor": [3],
            "url": ["https://suumo.jp/chintai/jnc_000060701156/?bc=100206393921"],
            "jnc_id": ["000060701156"],
            "n_rooms": [1],
            "service_room": [False],
            "living_room": [False],
            "dining_room": [False],
            "kitchen": [True],
            "n_stations": [3],
            "walk_time_station_min": [1.0],
            "walk_time_station_avg": [14.333333333333334],
            "ward": ["大田区"],
            "district": ["中央"],
        },
        orient="columns"
    ).set_index("jnc_id", drop=True)
    actual = make_properties_dataframe([property_])
    pd.testing.assert_frame_equal(actual, expected)
