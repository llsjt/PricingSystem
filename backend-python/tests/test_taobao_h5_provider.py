import json
from decimal import Decimal
from hashlib import md5

from requests.cookies import RequestsCookieJar

from app.core.config import Settings
from app.services.competitor_providers.taobao_h5_provider import (
    TaobaoH5CompetitorProvider,
    extract_competitors_from_payload,
    parse_search_api_url,
    parse_taobao_response_text,
    sanitize_result,
    sign_taobao_h5,
)
from app.services.competitor_service import CompetitorService


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code
        self.headers = {}


class FakeSession:
    def __init__(self, response_text: str, status_code: int = 200):
        self.cookies = RequestsCookieJar()
        self.calls: list[tuple[str, dict]] = []
        self.response_text = response_text
        self.status_code = status_code

    def get(self, url, **kwargs):  # noqa: ANN001
        self.calls.append((url, kwargs))
        return FakeResponse(self.response_text, status_code=self.status_code)


def test_sign_taobao_h5_matches_formula():
    token = "0123456789abcdef0123456789abcdef"
    timestamp = "1700000000000"
    app_key = "12574478"
    data = json.dumps({"q": "coffee"}, separators=(",", ":"))
    expected = md5(f"{token}&{timestamp}&{app_key}&{data}".encode("utf-8")).hexdigest()

    assert sign_taobao_h5(token, timestamp, app_key, data) == expected


def test_parse_search_api_url_extracts_required_fields_and_clean_url():
    request = parse_search_api_url(
        "https://h5api.m.taobao.com/h5/mtop.taobao.search/1.0/"
        "?appKey=12574478&api=mtop.taobao.search&v=1.0"
        "&data=%7B%22q%22%3A%22old%22%2C%22page%22%3A1%7D"
    )

    assert request.url == "https://h5api.m.taobao.com/h5/mtop.taobao.search/1.0/"
    assert request.params["appKey"] == "12574478"
    assert request.params["api"] == "mtop.taobao.search"
    assert request.params["v"] == "1.0"
    assert request.data == {"q": "old", "page": 1}


def test_parse_taobao_response_text_supports_jsonp():
    payload = parse_taobao_response_text('mtopjsonp1({"ret":["SUCCESS::ok"],"data":{"itemsArray":[]}})')

    assert payload["ret"] == ["SUCCESS::ok"]
    assert payload["data"]["itemsArray"] == []


def test_sanitize_result_masks_item_url_by_default():
    raw = {
        "sourceStatus": "OK",
        "source": "TAOBAO_H5",
        "message": "ok",
        "rawItemCount": 1,
        "competitors": [
            {
                "competitorName": "Black Coffee",
                "price": 18.62,
                "originalPrice": None,
                "salesVolumeHint": "30 paid",
                "promotionTag": None,
                "shopType": "旗舰店",
                "sourcePlatform": "天猫",
                "itemUrl": "https://item.taobao.com/item.htm?id=1",
            }
        ],
    }

    sanitized = sanitize_result(raw)
    with_item_url = sanitize_result(raw, include_item_url=True)

    assert "itemUrl" not in sanitized["competitors"][0]
    assert with_item_url["competitors"][0]["itemUrl"] == "https://item.taobao.com/item.htm?id=1"


def test_extract_competitors_normalizes_multiple_item_shapes():
    payload = {
        "ret": ["SUCCESS::ok"],
        "data": {
            "itemsArray": [
                {
                    "title": "<span>Coffee A</span>",
                    "price": "49.90",
                    "reservePrice": "59.90",
                    "monthSales": "1000+ bought",
                    "promotionTag": "coupon",
                    "shopType": "tmall",
                    "itemUrl": "//item.taobao.com/item.htm?id=1",
                },
                {
                    "raw_title": "Coffee B",
                    "view_price": "39.8-45.0",
                    "view_sales": "500 sold",
                    "nick": "Shop B",
                    "detail_url": "https://item.taobao.com/item.htm?id=2",
                },
            ]
        },
    }

    competitors = extract_competitors_from_payload(payload, max_results=5, default_platform="淘宝")

    assert competitors == [
        {
            "competitorName": "Coffee A",
            "price": 49.9,
            "originalPrice": 59.9,
            "salesVolumeHint": "1000+ bought",
            "promotionTag": "coupon",
            "shopType": "天猫",
            "sourcePlatform": "天猫",
            "itemUrl": "https://item.taobao.com/item.htm?id=1",
        },
        {
            "competitorName": "Coffee B",
            "price": 39.8,
            "originalPrice": None,
            "salesVolumeHint": "500 sold",
            "promotionTag": None,
            "shopType": "Shop B",
            "sourcePlatform": "淘宝",
            "itemUrl": "https://item.taobao.com/item.htm?id=2",
        },
    ]


def test_extract_competitors_falls_back_when_preferred_list_items_invalid():
    payload = {
        "data": {
            "list": [{"title": "invalid without price"}],
            "nested": {
                "module": {
                    "itemsArray": [
                        {
                            "title": "有效商品A",
                            "price": "59.00",
                            "monthSales": "100+",
                        }
                    ]
                }
            },
        }
    }

    competitors = extract_competitors_from_payload(payload, max_results=5, default_platform="淘宝")

    assert [item["competitorName"] for item in competitors] == ["有效商品A"]


def test_fetch_returns_unconfigured_when_cookie_or_url_missing():
    provider = TaobaoH5CompetitorProvider(cookie="", search_api_url="")

    result = provider.fetch(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "UNCONFIGURED"
    assert result["source"] == "TAOBAO_H5"
    assert result["competitors"] == []


def test_fetch_returns_unconfigured_when_search_api_url_invalid():
    provider = TaobaoH5CompetitorProvider(
        cookie="_m_h5_tk=0123456789abcdef0123456789abcdef_1700000000000",
        search_api_url="not-a-valid-url",
    )

    result = provider.fetch(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "UNCONFIGURED"
    assert "not a valid HTTP URL" in result["message"]


def test_fetch_returns_failed_when_session_expired():
    session = FakeSession('{"ret":["FAIL_SYS_SESSION_EXPIRED::SESSION失效"],"data":{}}')
    provider = TaobaoH5CompetitorProvider(
        cookie="_m_h5_tk=0123456789abcdef0123456789abcdef_1700000000000",
        search_api_url=(
            "https://h5api.m.taobao.com/h5/mtop.taobao.search/1.0/"
            "?appKey=12574478&api=mtop.taobao.search&v=1.0&data=%7B%22q%22%3A%22old%22%7D"
        ),
        session=session,
    )

    result = provider.fetch(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "FAILED"
    assert "SESSION" in result["message"]
    assert result["competitors"] == []


def test_fetch_returns_failed_on_tmd_risk_page():
    session = FakeSession('window.location.href = "https://h5api.m.taobao.com/_____tmd_____/page"')
    provider = TaobaoH5CompetitorProvider(
        cookie="_m_h5_tk=0123456789abcdef0123456789abcdef_1700000000000",
        search_api_url=(
            "https://h5api.m.taobao.com/h5/mtop.taobao.search/1.0/"
            "?appKey=12574478&api=mtop.taobao.search&v=1.0&data=%7B%22q%22%3A%22old%22%7D"
        ),
        session=session,
    )

    result = provider.fetch(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "FAILED"
    assert result["competitors"] == []


def test_fetch_returns_failed_on_http_non_200():
    session = FakeSession('{"ret":["SUCCESS::ok"],"data":{"itemsArray":[]}}', status_code=429)
    provider = TaobaoH5CompetitorProvider(
        cookie="_m_h5_tk=0123456789abcdef0123456789abcdef_1700000000000",
        search_api_url=(
            "https://h5api.m.taobao.com/h5/mtop.taobao.search/1.0/"
            "?appKey=12574478&api=mtop.taobao.search&v=1.0&data=%7B%22q%22%3A%22old%22%7D"
        ),
        session=session,
    )

    result = provider.fetch(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "FAILED"
    assert result["message"] == "HTTP 429"


def test_fetch_returns_failed_on_invalid_response_body():
    session = FakeSession("not-json-nor-jsonp")
    provider = TaobaoH5CompetitorProvider(
        cookie="_m_h5_tk=0123456789abcdef0123456789abcdef_1700000000000",
        search_api_url=(
            "https://h5api.m.taobao.com/h5/mtop.taobao.search/1.0/"
            "?appKey=12574478&api=mtop.taobao.search&v=1.0&data=%7B%22q%22%3A%22old%22%7D"
        ),
        session=session,
    )

    result = provider.fetch(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "FAILED"
    assert "JSON or JSONP" in result["message"]


def test_fetch_returns_failed_when_h5_token_missing():
    session = FakeSession('{"ret":["SUCCESS::ok"],"data":{"itemsArray":[]}}')
    provider = TaobaoH5CompetitorProvider(
        cookie="cna=abc",
        search_api_url=(
            "https://h5api.m.taobao.com/h5/mtop.taobao.search/1.0/"
            "?appKey=12574478&api=mtop.taobao.search&v=1.0&data=%7B%22q%22%3A%22old%22%7D"
        ),
        session=session,
    )

    result = provider.fetch(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "FAILED"
    assert "token" in result["message"]


def test_fetch_injects_keyword_and_sign_and_returns_ok():
    session = FakeSession(
        json.dumps(
            {
                "ret": ["SUCCESS::ok"],
                "data": {
                    "itemsArray": [
                        {
                            "title": "Coffee A",
                            "price": "49.90",
                            "reservePrice": "59.90",
                            "monthSales": "1000+ bought",
                            "promotionTag": "coupon",
                            "shopType": "tmall",
                            "itemUrl": "//item.taobao.com/item.htm?id=1",
                        }
                    ]
                },
            }
        )
    )
    provider = TaobaoH5CompetitorProvider(
        cookie="_m_h5_tk=0123456789abcdef0123456789abcdef_1700000000000; cna=abc",
        search_api_url=(
            "https://h5api.m.taobao.com/h5/mtop.taobao.search/1.0/"
            "?appKey=12574478&api=mtop.taobao.search&v=1.0&data=%7B%22q%22%3A%22old%22%7D"
        ),
        session=session,
        now_millis=lambda: 1700000000000,
    )

    result = provider.fetch(
        product_id=1,
        product_title="coffee",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "OK"
    assert result["rawItemCount"] == 1
    assert result["competitors"][0]["price"] == 49.9
    assert "itemUrl" not in result["competitors"][0]
    _, kwargs = session.calls[0]
    params = kwargs["params"]
    signed_data = params["data"]
    assert json.loads(signed_data)["q"] == "coffee"
    assert params["sign"] == sign_taobao_h5(
        "0123456789abcdef0123456789abcdef",
        "1700000000000",
        "12574478",
        signed_data,
    )


def test_fetch_keyword_filter_rejects_unrelated_items():
    session = FakeSession(
        json.dumps(
            {
                "ret": ["SUCCESS::ok"],
                "data": {
                    "itemsArray": [
                        {"title": "夏季男士短袖t恤", "price": "39.90"},
                        {"title": "黑咖啡速溶无糖", "price": "18.62"},
                    ]
                },
            },
            ensure_ascii=False,
        )
    )
    provider = TaobaoH5CompetitorProvider(
        cookie="_m_h5_tk=0123456789abcdef0123456789abcdef_1700000000000",
        search_api_url=(
            "https://h5api.m.taobao.com/h5/mtop.taobao.search/1.0/"
            "?appKey=12574478&api=mtop.taobao.search&v=1.0&data=%7B%22q%22%3A%22old%22%7D"
        ),
        session=session,
    )

    result = provider.fetch(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "OK"
    assert [item["competitorName"] for item in result["competitors"]] == ["黑咖啡速溶无糖"]


def test_fetch_keyword_filter_rejects_male_shoes_and_female_short_sleeve():
    session = FakeSession(
        json.dumps(
            {
                "ret": ["SUCCESS::ok"],
                "data": {
                    "itemsArray": [
                        {"title": "男士商务皮鞋", "price": "129.00"},
                        {"title": "女士短袖T恤", "price": "49.00"},
                        {"title": "男士美式短袖T恤", "price": "39.90"},
                        {"title": "cleanfit美式休闲半袖", "price": "52.91"},
                    ]
                },
            },
            ensure_ascii=False,
        )
    )
    provider = TaobaoH5CompetitorProvider(
        cookie="_m_h5_tk=0123456789abcdef0123456789abcdef_1700000000000",
        search_api_url=(
            "https://h5api.m.taobao.com/h5/mtop.taobao.search/1.0/"
            "?appKey=12574478&api=mtop.taobao.search&v=1.0&data=%7B%22q%22%3A%22old%22%7D"
        ),
        session=session,
    )

    result = provider.fetch(
        product_id=1,
        product_title="男士短袖",
        category_name="服饰",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "OK"
    assert [item["competitorName"] for item in result["competitors"]] == [
        "男士美式短袖T恤",
        "cleanfit美式休闲半袖",
    ]


def test_fetch_keyword_filter_keeps_short_sleeve_related_items():
    session = FakeSession(
        json.dumps(
            {
                "ret": ["SUCCESS::ok"],
                "data": {
                    "itemsArray": [
                        {"title": "男士美式短袖T恤", "price": "39.90"},
                        {"title": "cleanfit美式休闲半袖", "price": "52.91"},
                        {"title": "女士连衣裙", "price": "99.00"},
                    ]
                },
            },
            ensure_ascii=False,
        )
    )
    provider = TaobaoH5CompetitorProvider(
        cookie="_m_h5_tk=0123456789abcdef0123456789abcdef_1700000000000",
        search_api_url=(
            "https://h5api.m.taobao.com/h5/mtop.taobao.search/1.0/"
            "?appKey=12574478&api=mtop.taobao.search&v=1.0&data=%7B%22q%22%3A%22old%22%7D"
        ),
        session=session,
    )

    result = provider.fetch(
        product_id=1,
        product_title="男士短袖",
        category_name="服饰",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "OK"
    assert [item["competitorName"] for item in result["competitors"]] == [
        "男士美式短袖T恤",
        "cleanfit美式休闲半袖",
    ]


def test_competitor_service_uses_real_taobao_provider_and_returns_unconfigured_when_missing_settings(
    monkeypatch,
):
    from app.services.competitor_providers import taobao_h5_provider

    monkeypatch.setattr(
        taobao_h5_provider,
        "get_settings",
        lambda: Settings.model_validate(
            {
                "COMPETITOR_DATA_SOURCE": "taobao_h5",
                "TSDK_TAOBAO_COOKIE": "",
                "TSDK_TAOBAO_SEARCH_API_URL": "",
            }
        ),
    )
    service = CompetitorService(data_source="taobao_h5")

    assert isinstance(service.providers["taobao_h5"], TaobaoH5CompetitorProvider)
    result = service.get_competitor_result(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "UNCONFIGURED"
    assert result["source"] == "TAOBAO_H5"
