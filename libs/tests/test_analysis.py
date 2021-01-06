import pytest

from otokuna.analysis import _build_address_kanji


@pytest.mark.parametrize("address,expected", [
    ("東京都渋谷区恵比寿南１", "東京都渋谷区恵比寿南一丁目"),
    ("東京都渋谷区恵比寿南1", "東京都渋谷区恵比寿南一丁目"),
    ("東京都渋谷区恵比寿南１２", "東京都渋谷区恵比寿南十二丁目"),
    ("東京都渋谷区神泉町", "東京都渋谷区神泉町"),
    ("東京都渋谷区千駄ヶ谷１", "東京都渋谷区千駄ケ谷一丁目"),
])
def test_build_address_kanji(address, expected):
    assert _build_address_kanji(address) == expected
