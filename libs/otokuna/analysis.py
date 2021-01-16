import re

import numpy as np
import pandas as pd
from kanjize import int2kanji
from sklearn.tree import DecisionTreeRegressor

from otokuna import DATA_DIR


def remove_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Remove outliers from properties dataframe.

    It removes samples that fall in the top 2.5% percentile on
    either of the following columns:
    - area (e.g. 100m2)
    - number of rooms (e.g. 12)
    - building age (e.g. 99 years)

    TODO: remove by rent? (there are some outrageously expensive properties)
    """
    outlier_flag = False
    for col in ("area", "n_rooms", "building_age"):
        q = df[col].quantile(0.975)
        outlier_flag |= df[col] == q
    return df[~outlier_flag]


def _build_address_kanji(address: str) -> str:
    """Translate a Suumo address to an all-kanji representation.
    For example: 東京都渋谷区恵比寿南１ --> 東京都渋谷区恵比寿南一丁目

    Returns an empty string if the address could not be parsed.
    """
    pattern = r"(東京都)(.+区)(\D+)(\d*)"  # e.g. "東京都渋谷区恵比寿南１", "東京都渋谷区神泉町"
    match = re.match(pattern, address)
    if not match:
        return ""
    prefecture, ward, district, street_number = match.groups()
    street_number_jp = f"{int2kanji(int(street_number))}丁目" if street_number else ""

    # For some reason the data provided by 国土交通省 位置参照情報 ダウンロードサービス
    # uses "ケ" instead of "ヶ" for some names.
    # https://nlftp.mlit.go.jp/cgi-bin/isj/dls/_choose_method.cgi
    if district in {"千駄ヶ谷", "富ヶ谷", "幡ヶ谷"}:
        district = district.replace("ヶ", "ケ")
    # There are some malformed addresses in suumo such as:
    # x 三栄町 --> o 四谷三栄町
    # x 霞岳町 --> o 霞ヶ丘町
    # but these are very few and not worth the effort so we exclude them.

    return "".join([prefecture, ward, district, street_number_jp])


def add_address_coords(df: pd.DataFrame) -> pd.DataFrame:
    """Add latitude/longitude coordinates to each property (rows) in
    the given dataframe. The coordinates are obtained by looking up
    the building address in the location reference data for Tokyo.
    """
    filepath = DATA_DIR / "location_reference_tokyo" / "13_2019.csv"
    tokyo_df = pd.read_csv(filepath, encoding="sjis")
    tokyo_df.rename(columns={"緯度": "latitude", "経度": "longitude"}, inplace=True)

    # build address key e.g. "東京都渋谷区恵比寿南一丁目"
    df = df.copy()
    df["join_key"] = df.building_address.apply(_build_address_kanji)
    tokyo_df["join_key"] = tokyo_df["都道府県名"] + tokyo_df["市区町村名"] + tokyo_df["大字町丁目名"]

    tokyo_df = tokyo_df[["latitude", "longitude", "join_key"]]
    tokyo_df.set_index("join_key", inplace=True)
    return df.join(tokyo_df, on="join_key", how="left").drop(columns="join_key")


class DecisionTreeRegressorWithQuantiles(DecisionTreeRegressor):
    """Decision Tree Regressor that estimates (roughly) quantiles.

    It estimates the quantiles from the training samples that fall within
    each of the learned hyper-rectangles.

    Note that the tree does not directly optimize a quantile loss, and thus the
    training task is used as a proxy to partition the space in hyper-rectangles
    where hopefully the partitioned samples can be used to calculate non-parametric
    estimates of the quantile from the given features.

    Parameters
    ----------
    quantiles : float or array-like
        Quantile or sequence of quantiles to compute, which must be between
        0 and 1 inclusive.

    Other parameters are the same as DecisionTreeRegressor.

    Attributes
    ----------
    quantiles_by_leaf_ : dict[int, list[float]]
        The quantiles at each leaf node of the learned tree.

    Other attributes are the same as DecisionTreeRegressor.
    """

    def __init__(
            self, *, quantiles,
            criterion="mse", splitter="best", max_depth=None,
            min_samples_split=2, min_samples_leaf=1, min_weight_fraction_leaf=0.,
            max_features=None, random_state=None, max_leaf_nodes=None,
            min_impurity_decrease=0., min_impurity_split=None, ccp_alpha=0.0
    ):
        super().__init__(
            criterion=criterion, splitter=splitter, max_depth=max_depth,
            min_samples_split=min_samples_split, min_samples_leaf=min_samples_leaf, min_weight_fraction_leaf=min_weight_fraction_leaf,
            max_features=max_features, random_state=random_state, max_leaf_nodes=max_leaf_nodes,
            min_impurity_decrease=min_impurity_decrease, min_impurity_split=min_impurity_split, ccp_alpha=ccp_alpha)
        self.quantiles = quantiles

    def fit(self, X, y, sample_weight=None, check_input=True, X_idx_sorted="deprecated"):
        """Refer to `DecisionTreeRegressor.fit`"""
        super().fit(X, y, sample_weight, check_input, X_idx_sorted)
        try:
            quantiles = list(self.quantiles)
        except TypeError:
            quantiles = list([self.quantiles])

        leaf_idx_pred = self.apply(X)
        leaf_idxs, *_ = np.where(self.tree_.children_left == -1)

        # Sanity check
        assert np.all(np.sort(leaf_idxs) == np.unique(leaf_idx_pred))

        self.quantiles_by_leaf_idx_ = {}
        for leaf in leaf_idxs:
            self.quantiles_by_leaf_idx_[leaf] = list(np.quantile(y[leaf_idx_pred == leaf], quantiles))
        return self

    def predict_quantile(self, X, check_input=True):
        """Predict quantile values for X.

        For each sample in X it returns the (precomputed) quantile. The quantiles
        are estimated from the training samples that fall in the same leaf as the
        given sample.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            The input samples. Internally, it will be converted to
            ``dtype=np.float32`` and if a sparse matrix is provided
            to a sparse ``csr_matrix``.

        check_input : bool, default=True
            Allow to bypass several input checking.
            Don't use this parameter unless you know what you do.

        Returns
        -------
        y : array-like of shape (n_samples, n_quantiles)
            The predicted quantiles.
        """
        leaf_idx_pred = self.apply(X, check_input)
        return np.stack([np.asarray(self.quantiles_by_leaf_idx_[li]) for li in leaf_idx_pred])
