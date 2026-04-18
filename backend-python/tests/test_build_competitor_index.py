import sqlite3
from pathlib import Path

from scripts.build_competitor_index import build_index, parse_price, parse_sales


def test_parse_sales_handles_plus_and_wan_suffix():
    assert parse_sales("7000+") == 7000
    assert parse_sales("3.5万+") == 35000
    assert parse_sales("") is None
    assert parse_sales(None) is None
    assert parse_sales("abc") is None


def test_parse_price_returns_none_for_blank_or_zero():
    assert parse_price("19.9") == 19.9
    assert parse_price("0") is None
    assert parse_price("") is None
    assert parse_price(None) is None


_HEADER_FIELDS = [
    "商品ID", "年销量", "品牌名称",
    "二级类目ID", "二级类目名称", "一级类目ID", "一级类目名称",
    "主图URL", "发货地", "邮费",
    "卖家ID", "店铺名称", "短标题", "辅图URL", "副标题", "商品标题", "店铺类型",
    "基础销量（无效）", "白底图URL", "预售定金", "最终促销价", "预估凑单价", "预估凑单说明",
    "原价", "折后价", "核心优惠规则", "更多优惠规则", "优惠标签",
    "商品链接", "优惠券链接", "当日促销销量", "收益比例", "近2小时促销销量",
    "推广佣金", "佣金比例", "补贴金额", "补贴比例", "补贴上限",
    "优质品牌标识", "采集时间", "所属品类",
]


def _make_row(**overrides) -> str:
    defaults = {field: "" for field in _HEADER_FIELDS}
    defaults.update(overrides)
    return ",".join(defaults[field] for field in _HEADER_FIELDS) + "\n"


def test_build_index_writes_expected_schema_and_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    header = ",".join(_HEADER_FIELDS) + "\n"
    rows = [
        _make_row(
            **{
                "商品ID": "id-001",
                "年销量": "7000+",
                "品牌名称": "漫花",
                "二级类目ID": "50018994",
                "二级类目名称": "卷筒纸",
                "一级类目ID": "50025705",
                "一级类目名称": "洗护清洁剂",
                "店铺名称": "天猫超市",
                "店铺类型": "天猫超市",
                "短标题": "漫花卷纸",
                "商品标题": "漫花卷纸长标题",
                "原价": "69.9",
                "折后价": "39.9",
                "最终促销价": "20.75",
                "优惠标签": "满99减20",
                "采集时间": "2025-10-19 07:49:53",
                "所属品类": "天天特卖",
            }
        ),
        # Row missing 商品ID should be skipped.
        _make_row(**{"商品ID": "", "二级类目名称": "x"}),
        # Row missing both categories should be skipped.
        _make_row(**{"商品ID": "id-002"}),
    ]
    csv_path.write_text("\ufeff" + header + "".join(rows), encoding="utf-8")
    output = tmp_path / "out.sqlite"

    stats = build_index(csv_path, output, batch_size=10)

    assert stats["inserted"] == 1
    assert stats["skipped"] == 2
    assert output.exists()

    conn = sqlite3.connect(output)
    try:
        names = {r[1] for r in conn.execute("PRAGMA table_info(competitor)")}
        assert {
            "product_id",
            "brand",
            "primary_category",
            "secondary_category",
            "shop_type",
            "title",
            "yearly_sales",
            "promotion_tag",
        }.issubset(names)
        index_names = {r[1] for r in conn.execute("PRAGMA index_list(competitor)")}
        assert "idx_secondary_category" in index_names
        assert "idx_primary_category" in index_names
        assert "idx_brand" in index_names

        row = conn.execute(
            "SELECT product_id, brand, secondary_category, yearly_sales, "
            "promotion_tag, final_price, original_price, shop_type FROM competitor"
        ).fetchone()
        assert row == (
            "id-001",
            "漫花",
            "卷筒纸",
            7000,
            "满99减20",
            20.75,
            69.9,
            "天猫超市",
        )
    finally:
        conn.close()
