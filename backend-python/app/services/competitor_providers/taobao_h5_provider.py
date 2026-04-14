from __future__ import annotations

import html
import json
import re
import time
from copy import deepcopy
from dataclasses import dataclass
from hashlib import md5
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import parse_qsl, quote, unquote, urlparse, urlunparse

import requests

from app.core.config import get_settings

SOURCE_NAME = "TAOBAO_H5"
DEFAULT_PLATFORM = "淘宝"
TMALL_PLATFORM = "天猫"
PRICE_KEYS = (
    "price",
    "priceWap",
    "salePrice",
    "actualPrice",
    "view_price",
    "viewPrice",
    "finalPrice",
    "discountPrice",
    "promotionPrice",
)
ORIGINAL_PRICE_KEYS = (
    "originalPrice",
    "reservePrice",
    "marketPrice",
    "originPrice",
    "view_original_price",
    "viewOriginalPrice",
)
TITLE_KEYS = ("title", "raw_title", "rawTitle", "name", "itemTitle", "shortTitle", "auctionTitle")
SALES_KEYS = (
    "salesVolumeHint",
    "monthSales",
    "view_sales",
    "viewSales",
    "realSales",
    "payNum",
    "sold",
    "soldCount",
    "tradeCount",
    "sale",
    "sales",
)
PROMOTION_KEYS = ("promotionTag", "promo", "promotion", "discount", "coupon", "benefit")
SHOP_TYPE_KEYS = ("shopType", "shop_type", "storeType", "sellerType", "nick", "shopName", "shop_name")
URL_KEYS = ("itemUrl", "item_url", "detailUrl", "detail_url", "url", "auctionURL", "auctionUrl")
ITEM_LIST_KEYS = {
    "itemsArray",
    "items",
    "auctions",
    "itemList",
    "resultList",
    "list",
    "dataList",
    "goodsList",
    "item",
}
KEYWORD_KEYS = {"q", "keyword", "keywords", "query", "searchWord", "searchword"}
PUBLIC_COMPETITOR_KEYS = (
    "competitorName",
    "price",
    "originalPrice",
    "salesVolumeHint",
    "promotionTag",
    "shopType",
    "sourcePlatform",
)
KEYWORD_TOKEN_ALIASES = {
    "短袖": ("t恤", "半袖", "半截袖"),
    "t恤": ("短袖", "半袖", "半截袖"),
    "半袖": ("短袖", "t恤", "半截袖"),
}
GENDER_TOKENS = {"男", "女", "男士", "女士", "男款", "女款"}
MALE_MARKERS = ("男士", "男款", "男装", "男")
FEMALE_MARKERS = ("女士", "女款", "女装", "女")
SHORT_SLEEVE_TOKENS = {"短袖", "t恤", "半袖", "半截袖"}


class TaobaoCrawlerError(RuntimeError):
    """Raised for expected crawler failures that should map to FAILED."""


@dataclass(frozen=True)
class TaobaoSearchRequest:
    url: str
    params: dict[str, str]
    data: dict[str, Any]


def sign_taobao_h5(token: str, timestamp: str, app_key: str, data: str) -> str:
    return md5(f"{token}&{timestamp}&{app_key}&{data}".encode("utf-8")).hexdigest()


def parse_search_api_url(api_url: str) -> TaobaoSearchRequest:
    if not api_url or not api_url.strip():
        raise ValueError("TSDK_TAOBAO_SEARCH_API_URL is blank")

    parsed = urlparse(api_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.path:
        raise ValueError("TSDK_TAOBAO_SEARCH_API_URL is not a valid HTTP URL")

    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    missing = [key for key in ("appKey", "api", "v", "data") if key not in params]
    if missing:
        raise ValueError("search API URL missing required query params: " + ", ".join(missing))

    try:
        data = json.loads(params.get("data") or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("search API URL data query param is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("search API URL data query param must be a JSON object")

    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return TaobaoSearchRequest(url=clean_url, params=params, data=data)


def parse_taobao_response_text(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise TaobaoCrawlerError("empty response body")
    if "_____tmd_____" in raw or "x5referer" in raw:
        raise TaobaoCrawlerError("Taobao anti-bot page returned")

    if raw.startswith("{"):
        return _load_json_object(raw)

    jsonp = re.match(r"^[\w.$]+\(([\s\S]*)\)\s*;?\s*$", raw)
    if jsonp:
        return _load_json_object(jsonp.group(1))

    raise TaobaoCrawlerError("response body is not JSON or JSONP")


def extract_competitors_from_payload(
    payload: dict[str, Any],
    max_results: int = 5,
    default_platform: str = DEFAULT_PLATFORM,
) -> list[dict[str, Any]]:
    competitors: list[dict[str, Any]] = []
    for item in _find_item_candidates(payload):
        competitor = _normalize_item(item, default_platform=default_platform)
        if competitor is None:
            continue
        competitors.append(competitor)
        if len(competitors) >= max(max_results, 1):
            break
    return competitors


def sanitize_result(result: dict[str, Any], include_item_url: bool = False) -> dict[str, Any]:
    sanitized = dict(result)
    competitors: list[dict[str, Any]] = []
    for competitor in result.get("competitors") or []:
        if not isinstance(competitor, dict):
            continue
        public_competitor = {key: competitor.get(key) for key in PUBLIC_COMPETITOR_KEYS}
        if include_item_url:
            public_competitor["itemUrl"] = competitor.get("itemUrl")
        competitors.append(public_competitor)
    sanitized["competitors"] = competitors
    return sanitized


class TaobaoH5CompetitorProvider:
    source = SOURCE_NAME

    def __init__(
        self,
        *,
        cookie: str | None = None,
        search_api_url: str | None = None,
        timeout_seconds: float | None = None,
        max_results: int | None = None,
        session: requests.Session | None = None,
        now_millis: Any | None = None,
    ) -> None:
        settings = get_settings()
        self.cookie = cookie if cookie is not None else settings.tsdk_taobao_cookie
        self.search_api_url = search_api_url if search_api_url is not None else settings.tsdk_taobao_search_api_url
        self.timeout_seconds = float(
            timeout_seconds if timeout_seconds is not None else settings.tsdk_crawler_timeout_seconds
        )
        self.max_results = int(max_results if max_results is not None else settings.tsdk_crawler_max_results)
        self.session = session or requests.Session()
        self.now_millis = now_millis or (lambda: int(time.time() * 1000))

    def fetch(
        self,
        *,
        product_id: int,
        product_title: str | None,
        category_name: str | None,
        current_price: Any,
    ) -> dict[str, Any]:
        del product_id, current_price
        keyword = (product_title or "").strip() or (category_name or "").strip()
        if not keyword:
            return self._result("UNCONFIGURED", "keyword is required (product_title/category_name)")
        if not (self.cookie or "").strip():
            return self._result("UNCONFIGURED", "TSDK_TAOBAO_COOKIE is required")
        if not (self.search_api_url or "").strip():
            return self._result("UNCONFIGURED", "TSDK_TAOBAO_SEARCH_API_URL is required")

        try:
            request = parse_search_api_url(self.search_api_url)
        except ValueError as exc:
            return self._result("UNCONFIGURED", str(exc))

        _load_cookie_string(self.session, self.cookie)
        token = _extract_h5_token(self.session, self.cookie)
        if not token:
            token = self._refresh_h5_token(request.url)
        if not token:
            return self._result("FAILED", "valid _m_h5_tk token not found")

        try:
            params = self._build_signed_params(
                request=request,
                token=token,
                keyword=keyword,
                category=category_name,
            )
            response = self.session.get(
                request.url,
                params=params,
                timeout=self.timeout_seconds,
                headers={"User-Agent": _default_user_agent()},
            )
            if getattr(response, "status_code", 0) != 200:
                return self._result("FAILED", f"HTTP {getattr(response, 'status_code', 'unknown')}")

            payload = parse_taobao_response_text(getattr(response, "text", ""))
            self._validate_ret(payload)
            raw_items = _find_item_candidates(payload)
            normalized_limit = max(self.max_results, 1)
            all_competitors = extract_competitors_from_payload(
                payload,
                max_results=max(len(raw_items), normalized_limit),
                default_platform=DEFAULT_PLATFORM,
            )
            competitors = _filter_competitors_by_keyword(all_competitors, keyword)[:normalized_limit]
            if not competitors:
                if raw_items and all_competitors:
                    return self._result("EMPTY", "请求成功但无关键词相关竞品", raw_item_count=len(raw_items))
                return self._result("EMPTY", "request succeeded but no priced competitors found", raw_item_count=len(raw_items))
            return sanitize_result(
                self._result(
                    "OK",
                    "request succeeded",
                    raw_item_count=len(raw_items),
                    competitors=competitors,
                )
            )
        except (requests.RequestException, TimeoutError) as exc:
            return self._result("FAILED", f"request failed: {exc.__class__.__name__}")
        except TaobaoCrawlerError as exc:
            return self._result("FAILED", str(exc))
        except Exception as exc:
            return self._result("FAILED", f"unexpected crawler error: {exc.__class__.__name__}")

    def _refresh_h5_token(self, url: str) -> str:
        try:
            self.session.get(url, timeout=self.timeout_seconds, headers={"User-Agent": _default_user_agent()})
        except Exception:
            return ""
        return _extract_h5_token(self.session, self.cookie)

    def _build_signed_params(
        self,
        *,
        request: TaobaoSearchRequest,
        token: str,
        keyword: str,
        category: str | None,
    ) -> dict[str, str]:
        timestamp = str(int(self.now_millis()))
        params = dict(request.params)
        data = _inject_search_terms(request.data, keyword=keyword, category=category)
        data_text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        app_key = params.get("appKey", "12574478")

        params.update(
            {
                "t": timestamp,
                "type": "json",
                "dataType": "json",
                "callback": "",
                "data": data_text,
            }
        )
        params["sign"] = sign_taobao_h5(token, timestamp, app_key, data_text)
        return params

    @staticmethod
    def _validate_ret(payload: dict[str, Any]) -> None:
        ret = payload.get("ret")
        if not isinstance(ret, list) or not ret:
            return
        ret_text = " | ".join(str(item) for item in ret)
        if "SESSION" in ret_text or "会话" in ret_text or "登录" in ret_text:
            raise TaobaoCrawlerError(ret_text)
        if not any("SUCCESS" in str(item).upper() for item in ret):
            raise TaobaoCrawlerError(ret_text)

    @staticmethod
    def _result(
        source_status: str,
        message: str,
        raw_item_count: int = 0,
        competitors: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "sourceStatus": source_status,
            "source": SOURCE_NAME,
            "message": message,
            "rawItemCount": raw_item_count,
            "competitors": competitors or [],
        }


def _load_json_object(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TaobaoCrawlerError("response body is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise TaobaoCrawlerError("response JSON root is not an object")
    return payload


def _load_cookie_string(session: requests.Session, cookie_text: str) -> None:
    parsed = SimpleCookie()
    parsed.load(cookie_text)
    for key, morsel in parsed.items():
        if key and morsel.value:
            session.cookies.set(key, morsel.value)


def _extract_h5_token(session: requests.Session, cookie_text: str) -> str:
    possible_values: list[str] = []
    try:
        value = session.cookies.get("_m_h5_tk")
        if value:
            possible_values.append(value)
    except Exception:
        pass

    parsed = SimpleCookie()
    try:
        parsed.load(cookie_text)
        if "_m_h5_tk" in parsed:
            possible_values.append(parsed["_m_h5_tk"].value)
    except Exception:
        pass

    for value in possible_values:
        token = str(value).split("_", 1)[0]
        if len(token) >= 32:
            return token[:32]
    return ""


def _inject_search_terms(data: dict[str, Any], keyword: str, category: str | None = None) -> dict[str, Any]:
    copied = deepcopy(data)
    if _replace_keyword_values(copied, keyword) == 0:
        copied["q"] = keyword
    if category and "category" not in copied and "cat" not in copied:
        copied["category"] = category
    return copied


def _replace_keyword_values(value: Any, keyword: str) -> int:
    replacements = 0
    if isinstance(value, dict):
        for key in list(value.keys()):
            if str(key).lower() in KEYWORD_KEYS:
                value[key] = _keyword_like(value.get(key), keyword)
                replacements += 1
            else:
                replacements += _replace_keyword_values(value[key], keyword)
                if isinstance(value[key], str):
                    parsed = _parse_json_string(value[key])
                    if parsed is not None:
                        nested_replacements = _replace_keyword_values(parsed, keyword)
                        if nested_replacements:
                            value[key] = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
                            replacements += nested_replacements
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            replacements += _replace_keyword_values(child, keyword)
            if isinstance(child, str):
                parsed = _parse_json_string(child)
                if parsed is not None:
                    nested_replacements = _replace_keyword_values(parsed, keyword)
                    if nested_replacements:
                        value[idx] = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
                        replacements += nested_replacements
    return replacements


def _parse_json_string(value: str) -> Any | None:
    text = value.strip()
    if not text or text[0] not in "{[":
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _keyword_like(original: Any, keyword: str) -> str:
    if isinstance(original, str) and _looks_url_encoded(original):
        return quote(keyword, safe="")
    return keyword


def _filter_competitors_by_keyword(competitors: list[dict[str, Any]], keyword: str) -> list[dict[str, Any]]:
    tokens = _keyword_match_tokens(keyword)
    if not tokens:
        return competitors
    return [competitor for competitor in competitors if _competitor_matches_tokens(competitor, tokens, keyword)]


def _keyword_match_tokens(keyword: str) -> list[str]:
    text = _normalize_match_text(keyword)
    if not text:
        return []

    tokens: list[str] = []
    if re.search(r"[\u4e00-\u9fff]", text):
        compact = re.sub(r"\s+", "", text)
        for segment in re.findall(r"[\u4e00-\u9fff]+", compact):
            if len(segment) == 1:
                tokens.append(segment)
            else:
                tokens.extend(segment[index : index + 2] for index in range(len(segment) - 1))
        tokens.extend(match.group(0) for match in re.finditer(r"[a-z0-9][a-z0-9-]*", text))
    else:
        tokens.extend(part for part in re.split(r"\s+", text) if part)

    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        expanded.extend(KEYWORD_TOKEN_ALIASES.get(token, ()))
    return _unique_nonempty(expanded)


def _competitor_matches_tokens(competitor: dict[str, Any], tokens: list[str], keyword: str) -> bool:
    haystack = _normalize_match_text(competitor.get("competitorName"))
    keyword_text = _normalize_match_text(keyword)
    if not haystack or not keyword_text:
        return False

    keyword_gender = _detect_gender(keyword_text)
    item_gender = _detect_gender(haystack)
    if keyword_gender and item_gender and keyword_gender != item_gender:
        return False

    if keyword_text in haystack:
        return True

    matched_tokens = [token for token in tokens if token in haystack]
    if not matched_tokens:
        return False

    if re.search(r"[\u4e00-\u9fff]", keyword_text):
        meaningful_query_tokens = _meaningful_tokens(tokens)
        meaningful_matched_tokens = _meaningful_tokens(matched_tokens)
        query_token_set = set(meaningful_query_tokens)
        matched_token_set = set(meaningful_matched_tokens)
        if query_token_set & SHORT_SLEEVE_TOKENS and matched_token_set & SHORT_SLEEVE_TOKENS:
            return True
        if len(meaningful_query_tokens) >= 2:
            return len(matched_token_set) >= 2
        return bool(meaningful_matched_tokens)
    return True


def _normalize_match_text(value: Any) -> str:
    text = _clean_text(value).lower()
    return re.sub(r"\s+", "", text)


def _unique_nonempty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = _normalize_match_text(value)
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _meaningful_tokens(tokens: list[str]) -> list[str]:
    result: list[str] = []
    for token in tokens:
        normalized = _normalize_match_text(token)
        if not normalized:
            continue
        if normalized in GENDER_TOKENS:
            continue
        if len(normalized) == 1 and normalized in {"男", "女"}:
            continue
        result.append(normalized)
    return _unique_nonempty(result)


def _detect_gender(text: str) -> str | None:
    for marker in MALE_MARKERS:
        if marker in text:
            return "male"
    for marker in FEMALE_MARKERS:
        if marker in text:
            return "female"
    return None


def _looks_url_encoded(value: str) -> bool:
    if "%" not in value:
        return False
    try:
        return unquote(value) != value
    except Exception:
        return False


def _find_item_candidates(payload: Any) -> list[dict[str, Any]]:
    preferred: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []
    _collect_items(payload, preferred=preferred, fallback=fallback)
    filtered_preferred = _dedupe_valid_items(preferred)
    filtered_fallback = _dedupe_valid_items(fallback)
    if not filtered_preferred:
        return filtered_fallback

    preferred_ids = {id(item) for item in filtered_preferred}
    merged = list(filtered_preferred)
    for item in filtered_fallback:
        if id(item) not in preferred_ids:
            merged.append(item)
    return merged


def _collect_items(value: Any, preferred: list[dict[str, Any]], fallback: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, list) and key in ITEM_LIST_KEYS:
                preferred.extend(item for item in child if isinstance(item, dict))
            _collect_items(child, preferred, fallback)
    elif isinstance(value, list):
        dict_items = [item for item in value if isinstance(item, dict)]
        fallback.extend(dict_items)
        for child in value:
            _collect_items(child, preferred, fallback)


def _dedupe_valid_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[int] = set()
    for item in items:
        item_id = id(item)
        if item_id in seen:
            continue
        seen.add(item_id)
        if _looks_like_item(item):
            deduped.append(item)
    return deduped


def _looks_like_item(item: dict[str, Any]) -> bool:
    return _parse_price(_lookup_any(item, PRICE_KEYS)) is not None and (
        _lookup_any(item, TITLE_KEYS) is not None or _lookup_any(item, URL_KEYS) is not None
    )


def _normalize_item(item: dict[str, Any], default_platform: str) -> dict[str, Any] | None:
    price = _parse_price(_lookup_any(item, PRICE_KEYS))
    if price is None or price <= 0:
        return None

    title = _clean_text(_lookup_any(item, TITLE_KEYS)) or _clean_text(_lookup_any(item, ("shopName", "nick")))
    if not title:
        title = "未知竞品"

    original_price = _parse_price(_lookup_any(item, ORIGINAL_PRICE_KEYS))
    shop_type = _normalize_shop_type(_lookup_any(item, SHOP_TYPE_KEYS))
    source_platform = _normalize_platform(item, default_platform=default_platform)
    if source_platform == TMALL_PLATFORM and not shop_type:
        shop_type = TMALL_PLATFORM

    return {
        "competitorName": title,
        "price": price,
        "originalPrice": original_price,
        "salesVolumeHint": _clean_text(_lookup_any(item, SALES_KEYS)) or None,
        "promotionTag": _normalize_promotion(_lookup_any(item, PROMOTION_KEYS)),
        "shopType": shop_type,
        "sourcePlatform": source_platform,
        "itemUrl": _normalize_url(_lookup_any(item, URL_KEYS)),
    }


def _lookup_any(item: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(item, dict):
        lowered = {str(key).lower(): key for key in item.keys()}
        for key in keys:
            actual = lowered.get(key.lower())
            if actual is not None and item.get(actual) not in (None, ""):
                return item.get(actual)
        for value in item.values():
            found = _lookup_any(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(item, list):
        for value in item:
            found = _lookup_any(value, keys)
            if found not in (None, ""):
                return found
    return None


def _parse_price(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        return round(numeric, 2) if numeric > 0 else None
    if isinstance(value, dict):
        for candidate in value.values():
            parsed = _parse_price(candidate)
            if parsed is not None:
                return parsed
        return None
    if isinstance(value, list):
        for candidate in value:
            parsed = _parse_price(candidate)
            if parsed is not None:
                return parsed
        return None

    text = _clean_text(value)
    if not text:
        return None
    matches = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text)
    for match in matches:
        numeric = float(match.replace(",", ""))
        if numeric > 0:
            return round(numeric, 2)
    return None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_clean_text(item) for item in value if _clean_text(item)).strip()
    if isinstance(value, dict):
        for key in ("text", "name", "title", "value"):
            if key in value:
                return _clean_text(value.get(key))
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_shop_type(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    if text.lower() in {"tmall", "天猫"}:
        return TMALL_PLATFORM
    return text


def _normalize_platform(item: dict[str, Any], default_platform: str) -> str:
    explicit = _clean_text(_lookup_any(item, ("sourcePlatform", "platform")))
    if explicit:
        return explicit
    if _is_tmall_item(item):
        return TMALL_PLATFORM
    return default_platform


def _is_tmall_item(item: dict[str, Any]) -> bool:
    text = json.dumps(item, ensure_ascii=False).lower()
    return any(marker in text for marker in ("tmall", "天猫", "旗舰店"))


def _normalize_promotion(value: Any) -> str | None:
    text = _clean_text(value)
    return text or None


def _normalize_url(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    if text.startswith("//"):
        return "https:" + text
    if text.startswith("http://") or text.startswith("https://"):
        return text
    return text


def _default_user_agent() -> str:
    return (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    )
