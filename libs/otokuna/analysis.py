import re

import pandas as pd
from kanjize import int2kanji

from otokuna import DATA_DIR


def remove_outliers(df: pd.DataFrame, thres=0.99) -> pd.DataFrame:
    """Remove outliers from properties dataframe.

    It removes samples that fall in the top (1 - thres) x 100 percentile
    on either of the following columns:
    - area (e.g. 100m2)
    - n_rooms (e.g. 12)
    - building_age (e.g. 99 years)
    - rent (e.g. 3,500,000 yen)
    - admin_fee/rent ratio (e.g. 2, likely due to typo in page)
    """
    df = df.assign(rent_admin_fee_ratio=df.admin_fee / df.rent)
    outlier_flag = False
    for col in ("area", "n_rooms", "building_age", "rent", "rent_admin_fee_ratio"):
        q = df[col].quantile(thres)
        outlier_flag |= df[col] == q
    df.drop(columns=["rent_admin_fee_ratio"], inplace=True)
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
