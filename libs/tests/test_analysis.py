import numpy as np
import pandas as pd
import pytest

from otokuna.analysis import _build_address_kanji, add_address_coords


@pytest.mark.parametrize("address,expected", [
    ("東京都渋谷区恵比寿南１", "東京都渋谷区恵比寿南一丁目"),
    ("東京都渋谷区恵比寿南1", "東京都渋谷区恵比寿南一丁目"),
    ("東京都渋谷区恵比寿南１２", "東京都渋谷区恵比寿南十二丁目"),
    ("東京都渋谷区神泉町", "東京都渋谷区神泉町"),
    ("東京都渋谷区千駄ヶ谷１", "東京都渋谷区千駄ケ谷一丁目"),
    ("invalid_address", "")
])
def test_build_address_kanji(address, expected):
    assert _build_address_kanji(address) == expected


def test_add_address_coords():
    df = pd.DataFrame.from_dict(
        {
            0: {"building_address": "東京都渋谷区恵比寿南１"},
            1: {"building_address": "invalid_address"},
        },
        orient="index"
    )
    df_copy = df.copy()

    expected = pd.DataFrame.from_dict(
        {
            0: {"building_address": "東京都渋谷区恵比寿南１",
                "latitude": 35.644942,
                "longitude": 139.709897},
            1: {"building_address": "invalid_address",
                "latitude": np.nan,
                "longitude": np.nan},
        },
        orient="index"
    )

    actual = add_address_coords(df)
    pd.testing.assert_frame_equal(actual, expected)

    expected_columns_df2 = pd.Index(["building_address", "latitude", "longitude"])
    pd.testing.assert_index_equal(actual.columns, expected_columns_df2)

    # Original df does not change
    pd.testing.assert_frame_equal(df, df_copy)
