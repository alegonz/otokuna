import numpy as np
import pandas as pd
import pytest

from otokuna.analysis import _build_address_kanji, add_address_coords, DecisionTreeRegressorWithQuantiles


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


@pytest.fixture
def dummy_data():
    """Dummy data that is perfectly separable at x=0 by a binary tree of depth 1"""
    X = np.concatenate([-np.ones(101), np.ones(101)]).reshape(-1, 1)
    y = np.concatenate([np.arange(0, 101), np.arange(1000, 1101)])
    yield X, y


class TestDecisionTreeRegressorWithQuantiles:
    def test_fit(self, dummy_data):
        X, y = dummy_data
        expected = {1: [25, 50], 2: [1025, 1050]}
        model = DecisionTreeRegressorWithQuantiles(max_depth=1, random_state=123, quantiles=[0.25, 0.50])
        model.fit(X, y)
        assert model.quantiles_by_leaf_idx_ == expected

    def test_predict_quantile(self, dummy_data):
        X, y = dummy_data
        model = DecisionTreeRegressorWithQuantiles(max_depth=1, random_state=123, quantiles=[0.25, 0.50])
        model.fit(X, y)
        expected = np.column_stack([
            np.concatenate([25 * np.ones(101), 1025 * np.ones(101)]),
            np.concatenate([50 * np.ones(101), 1050 * np.ones(101)]),
        ])
        np.testing.assert_equal(model.predict_quantile(X), expected)
