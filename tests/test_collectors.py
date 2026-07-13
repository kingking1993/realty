from datetime import date

from app.collectors.molit import _parse_item, recent_deal_ymds
from app.collectors.naver_land import _normalize_article, _parse_price
from app.collectors.naver_search import _clean, _parse_pub_date


def test_parse_price():
    assert _parse_price("22억") == 220000
    assert _parse_price("22억 5,000") == 225000
    assert _parse_price("5,000") == 5000
    assert _parse_price(85000) == 85000
    assert _parse_price("") == 0
    assert _parse_price(None) == 0


def test_normalize_article():
    item = {
        "articleNo": "2637766564", "tradeTypeName": "매매", "buildingName": "101동",
        "floorInfo": "12/25", "area2": 84.98, "dealOrWarrantPrc": "22억", "rentPrc": "",
        "articleFeatureDesc": "로얄층 남향",
    }
    norm = _normalize_article(item)
    assert norm["article_no"] == "2637766564"
    assert norm["price"] == 220000
    assert norm["area_exclusive"] == 84.98
    assert norm["dong"] == "101동"


def test_molit_parse_item():
    import xml.etree.ElementTree as ET

    xml = """<item>
        <aptNm>테스트단지</aptNm><dealAmount>218,000</dealAmount>
        <dealYear>2026</dealYear><dealMonth>6</dealMonth><dealDay>28</dealDay>
        <excluUseAr>84.98</excluUseAr><floor>12</floor><aptDong>101</aptDong>
        <cdealType></cdealType><umdNm>가락동</umdNm>
    </item>"""
    parsed = _parse_item(ET.fromstring(xml))
    assert parsed["price"] == 218000
    assert parsed["deal_date"] == date(2026, 6, 28)
    assert parsed["floor"] == 12
    assert parsed["apt_dong"] == "101"
    assert parsed["is_canceled"] is False


def test_recent_deal_ymds():
    assert recent_deal_ymds(date(2026, 1, 15)) == ["202601", "202512", "202511"]


def test_clean_html():
    assert _clean("<b>헬리오시티</b> 신고가 &quot;경신&quot;") == '헬리오시티 신고가 "경신"'


def test_parse_pub_date():
    dt = _parse_pub_date("Mon, 13 Jul 2026 09:30:00 +0900")
    assert dt is not None and dt.year == 2026
    assert _parse_pub_date("") is None
