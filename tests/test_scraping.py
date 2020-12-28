from functools import partial

import pandas as pd
import pytest
from _pytest.python_api import RaisesContext

from otokuna.scraping import (
    parse_address, parse_age, parse_area, parse_floor_range,
    parse_floors, parse_layout, parse_money, parse_transportation,
    ParsingError, Property, Building, Room, make_properties_dataframe
)


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


def test_make_properties_dataframe():
    property_ = Property(
        building=Building(category="賃貸マンション", title="セントラルメゾン", address="東京都大田区中央１",
                          transportation=["ＪＲ京浜東北線/大森駅 バス7分 (バス停)臼田坂下 歩1分",
                                          "都営浅草線/西馬込駅 歩18分",
                                          "京急本線/平和島駅 歩24分"],
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
            "building_transportation": [["ＪＲ京浜東北線/大森駅 バス7分 (バス停)臼田坂下 歩1分", "都営浅草線/西馬込駅 歩18分", "京急本線/平和島駅 歩24分"]],
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
    )
    actual = make_properties_dataframe([property_])
    pd.testing.assert_frame_equal(actual, expected)
