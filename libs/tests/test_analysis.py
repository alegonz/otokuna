import numpy as np
import pandas as pd
import pytest

from otokuna.analysis import _build_address_kanji, add_address_coords, train_val_test_split


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


@pytest.mark.parametrize("array", [
    pd.Series(range(10)),
    pd.concat([pd.Series(range(10)), pd.Series(range(10))], axis=1)
])
def test_train_val_test_split(array):
    (train, val, test), *_ = train_val_test_split([array], val_ratio=0.2, test_ratio=0.3)
    assert len(train) == 5
    assert len(val) == 2
    assert len(test) == 3
    assert not set(train.index) & set(val.index)
    assert not set(train.index) & set(test.index)
    assert not set(val.index) & set(test.index)
