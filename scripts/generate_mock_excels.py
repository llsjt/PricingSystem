from __future__ import annotations

import argparse
import random
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape


PRODUCT_HEADERS = ["商品ID", "商品标题", "商品类目", "成本价", "当前售价", "库存", "商品状态"]
DAILY_HEADERS = [
    "统计日期",
    "商品ID",
    "商品标题",
    "访客数",
    "加购人数",
    "支付买家数",
    "支付件数",
    "支付金额",
    "退款金额",
    "支付转化率",
]
SKU_HEADERS = ["商品ID", "商品标题", "SKU ID", "SKU名称", "SKU属性", "SKU售价", "SKU成本价", "SKU库存"]
TRAFFIC_HEADERS = [
    "统计日期",
    "商品ID",
    "商品标题",
    "流量来源",
    "展现量",
    "点击量",
    "访客数",
    "花费",
    "支付金额",
    "ROI",
]

PRODUCT_SHEET = "商品基础信息"
DAILY_SHEET = "商品经营日报"
SKU_SHEET = "商品SKU"
TRAFFIC_SHEET = "流量推广日报"

CATEGORY_TOPICS: list[tuple[str, list[str]]] = [
    ("女装/外套", ["轻薄防晒衣", "短款针织开衫", "宽松牛仔外套"]),
    ("男装/T恤", ["速干运动T恤", "纯棉圆领短袖", "商务休闲Polo"]),
    ("鞋靴/休闲鞋", ["透气跑步鞋", "厚底小白鞋", "轻量徒步鞋"]),
    ("家居/收纳", ["可折叠收纳箱", "分格收纳盒", "抽屉整理篮"]),
    ("食品/零食", ["低糖坚果礼盒", "冻干水果脆", "手作曲奇礼袋"]),
    ("数码/配件", ["磁吸快充数据线", "降噪蓝牙耳机", "折叠手机支架"]),
    ("美妆/护肤", ["清润补水面膜", "控油洁面乳", "修护精华喷雾"]),
    ("母婴/用品", ["透气婴儿睡袋", "硅胶辅食分格盘", "宝宝云柔浴巾"]),
    ("宠物/用品", ["豆腐猫砂", "宠物冻干零食", "防滑宠物食盆"]),
    ("运动/户外", ["户外速开帐篷", "瑜伽弹力带", "保温运动水壶"]),
]
TITLE_PREFIXES = ["2026新款", "爆款升级", "高颜值", "轻奢质感", "旗舰款", "热卖同款"]
TITLE_SUFFIXES = ["", " 女款", " 男款", " 家用", " 旅行装", " 礼盒装"]
TITLE_SERIES = ["山系轻外出", "城市通勤", "周末出游", "居家回购", "办公室常备", "直播热推", "礼赠甄选", "亲子出行", "补货常备", "轻能量运动"]
FOCUS_TITLE_MARKERS = ["长周期日指标样本", "近90天截断样本", "多月经营轨迹样本"]
TRAFFIC_SOURCES = ["直通车", "万相台", "手淘搜索", "猜你喜欢", "活动会场", "短视频", "直播间"]
COLORS = ["雅黑", "云白", "雾蓝", "奶杏", "石墨灰", "抹茶绿", "樱花粉"]
SIZES = ["S", "M", "L", "XL", "2XL"]
VERSIONS = ["标准版", "升级版", "高配版", "轻享版"]


@dataclass(frozen=True)
class ProductSpec:
    product_id: str
    title: str
    category: str
    cost_price: Decimal
    sale_price: Decimal
    stock: int
    status: str
    popularity: float


def parse_args() -> argparse.Namespace:
    today = date.today()
    default_start_id = int(today.strftime("%Y%m%d")) * 10000 + 1

    parser = argparse.ArgumentParser(
        description="Generate mock shopping-platform Excel exports for product import.",
    )
    parser.add_argument("--product-count", type=int, default=20, help="Rows in the product Excel.")
    parser.add_argument("--daily-count", type=int, default=120, help="Rows in the daily metric Excel.")
    parser.add_argument("--sku-count", type=int, default=60, help="Rows in the SKU Excel.")
    parser.add_argument("--traffic-count", type=int, default=140, help="Rows in the traffic Excel.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("mock-excels"),
        help="Directory where the Excel files will be written.",
    )
    parser.add_argument(
        "--start-product-id",
        type=int,
        default=default_start_id,
        help="First product ID to use. IDs increment from this value.",
    )
    parser.add_argument(
        "--start-date",
        type=lambda value: date.fromisoformat(value),
        default=today,
        help="Newest business date to generate, format: YYYY-MM-DD.",
    )
    parser.add_argument("--seed", type=int, default=20260402, help="Random seed for repeatable output.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validate_args(args)

    rng = random.Random(args.seed)
    products = build_product_catalog(args.product_count, args.start_product_id, rng)
    product_rows = build_product_rows(products)
    daily_rows = build_daily_rows(products, args.daily_count, args.start_date, rng)
    sku_rows = build_sku_rows(products, args.sku_count, rng)
    traffic_rows = build_traffic_rows(products, args.traffic_count, args.start_date, rng)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    files = [
        ("product_base_mock.xlsx", PRODUCT_SHEET, PRODUCT_HEADERS, product_rows),
        ("product_daily_metric_mock.xlsx", DAILY_SHEET, DAILY_HEADERS, daily_rows),
        ("product_sku_mock.xlsx", SKU_SHEET, SKU_HEADERS, sku_rows),
        ("traffic_promo_daily_mock.xlsx", TRAFFIC_SHEET, TRAFFIC_HEADERS, traffic_rows),
    ]

    for filename, sheet_name, headers, rows in files:
        write_xlsx(output_dir / filename, sheet_name, headers, rows)

    print(f"Generated 4 Excel files in: {output_dir.resolve()}")
    print(f"  - product rows : {len(product_rows)}")
    print(f"  - daily rows   : {len(daily_rows)}")
    print(f"  - sku rows     : {len(sku_rows)}")
    print(f"  - traffic rows : {len(traffic_rows)}")


def validate_args(args: argparse.Namespace) -> None:
    counts = {
        "--product-count": args.product_count,
        "--daily-count": args.daily_count,
        "--sku-count": args.sku_count,
        "--traffic-count": args.traffic_count,
    }
    for name, value in counts.items():
        if value <= 0:
            raise ValueError(f"{name} must be a positive integer.")

    for name, value in (
        ("--daily-count", args.daily_count),
        ("--sku-count", args.sku_count),
        ("--traffic-count", args.traffic_count),
    ):
        if value < args.product_count:
            raise ValueError(
                f"{name} must be >= --product-count so every product ID can appear in every Excel."
            )


def build_product_catalog(count: int, start_product_id: int, rng: random.Random) -> list[ProductSpec]:
    products: list[ProductSpec] = []
    for index in range(count):
        category, topic_pool = CATEGORY_TOPICS[index % len(CATEGORY_TOPICS)]
        topic = topic_pool[rng.randrange(len(topic_pool))]
        prefix = TITLE_PREFIXES[(index + rng.randrange(len(TITLE_PREFIXES))) % len(TITLE_PREFIXES)]
        suffix = TITLE_SUFFIXES[(index + rng.randrange(len(TITLE_SUFFIXES))) % len(TITLE_SUFFIXES)]
        title = build_product_title(index, prefix, topic, suffix, rng)

        cost_price = money(Decimal(str(rng.uniform(12, 220))))
        markup = Decimal(str(rng.uniform(1.2, 2.1)))
        sale_price = money(cost_price * markup)
        if sale_price <= cost_price:
            sale_price = money(cost_price * Decimal("1.20"))

        stock = rng.randint(60, 1200)
        status = rng.choices(["ON_SALE", "OFF_SHELF"], weights=[9, 1], k=1)[0]
        popularity = rng.uniform(0.8, 1.6)
        product_id = str(start_product_id + index)

        products.append(
            ProductSpec(
                product_id=product_id,
                title=title,
                category=category,
                cost_price=cost_price,
                sale_price=sale_price,
                stock=stock,
                status=status,
                popularity=popularity,
            )
        )
    return products


def build_product_rows(products: Iterable[ProductSpec]) -> list[list[object]]:
    rows: list[list[object]] = []
    for product in products:
        rows.append(
            [
                product.product_id,
                product.title,
                product.category,
                decimal_text(product.cost_price),
                decimal_text(product.sale_price),
                product.stock,
                product.status,
            ]
        )
    return rows


def build_daily_rows(
    products: list[ProductSpec],
    total_rows: int,
    newest_date: date,
    rng: random.Random,
) -> list[list[object]]:
    row_counts = allocate_daily_counts(total_rows, len(products), rng)
    rows: list[list[object]] = []

    for product, row_count in zip(products, row_counts):
        for offset in range(row_count):
            stat_date = newest_date - timedelta(days=offset)
            visitor_count = max(80, int(rng.uniform(120, 1600) * product.popularity))
            add_cart_count = clamp(int(visitor_count * rng.uniform(0.05, 0.18)), 5, visitor_count)
            pay_buyer_count = clamp(int(add_cart_count * rng.uniform(0.45, 0.85)), 1, add_cart_count)
            sales_count = max(pay_buyer_count, int(pay_buyer_count * rng.uniform(1.0, 1.3)))
            turnover = money(
                product.sale_price * Decimal(sales_count) * Decimal(str(rng.uniform(0.96, 1.04)))
            )
            refund_amount = money(turnover * Decimal(str(rng.uniform(0.00, 0.08))))
            conversion_rate = Decimal(sales_count) / Decimal(visitor_count)

            rows.append(
                [
                    stat_date.isoformat(),
                    product.product_id,
                    product.title,
                    visitor_count,
                    add_cart_count,
                    pay_buyer_count,
                    sales_count,
                    decimal_text(turnover),
                    decimal_text(refund_amount),
                    percent_text(conversion_rate),
                ]
            )

    rows.sort(key=lambda row: (str(row[0]), str(row[1])), reverse=True)
    return rows


def build_sku_rows(
    products: list[ProductSpec],
    total_rows: int,
    rng: random.Random,
) -> list[list[object]]:
    row_counts = allocate_counts(total_rows, len(products), rng)
    rows: list[list[object]] = []

    for product, row_count in zip(products, row_counts):
        base_stock = max(1, product.stock // row_count)
        for variant_index in range(row_count):
            color = COLORS[variant_index % len(COLORS)]
            size = SIZES[(variant_index // len(COLORS)) % len(SIZES)]
            version = VERSIONS[(variant_index // (len(COLORS) * len(SIZES))) % len(VERSIONS)]
            sku_id = f"{product.product_id}-{variant_index + 1:03d}"
            sku_attr = f"颜色:{color};尺码:{size};版本:{version}"
            sku_name = f"{product.title} - {color}{size} {version}"

            sale_price = money(product.sale_price * Decimal(str(rng.uniform(0.92, 1.08))))
            floor_price = money(product.cost_price * Decimal("1.05"))
            if sale_price < floor_price:
                sale_price = floor_price
            cost_price = money(product.cost_price * Decimal(str(rng.uniform(0.96, 1.04))))
            if cost_price >= sale_price:
                cost_price = money(sale_price * Decimal("0.84"))
            stock = max(3, int(base_stock * rng.uniform(0.7, 1.4)))

            rows.append(
                [
                    product.product_id,
                    product.title,
                    sku_id,
                    sku_name,
                    sku_attr,
                    decimal_text(sale_price),
                    decimal_text(cost_price),
                    stock,
                ]
            )

    rows.sort(key=lambda row: (str(row[0]), str(row[2])))
    return rows


def build_traffic_rows(
    products: list[ProductSpec],
    total_rows: int,
    newest_date: date,
    rng: random.Random,
) -> list[list[object]]:
    row_counts = allocate_counts(total_rows, len(products), rng)
    rows: list[list[object]] = []

    for product, row_count in zip(products, row_counts):
        for offset in range(row_count):
            traffic_source = TRAFFIC_SOURCES[offset % len(TRAFFIC_SOURCES)]
            stat_date = newest_date - timedelta(days=offset // len(TRAFFIC_SOURCES))
            click_through_rate = Decimal(str(rng.uniform(0.02, 0.09)))
            impression_count = max(400, int(rng.uniform(1800, 20000) * product.popularity))
            click_count = max(20, int(Decimal(impression_count) * click_through_rate))
            visitor_count = clamp(int(click_count * rng.uniform(0.60, 0.92)), 10, click_count)
            paid_orders = max(1, int(visitor_count * rng.uniform(0.01, 0.08)))
            pay_amount = money(
                product.sale_price * Decimal(paid_orders) * Decimal(str(rng.uniform(0.95, 1.08)))
            )

            roi_rate = Decimal(str(rng.uniform(0.05, 0.20))).quantize(
                Decimal("0.0001"),
                rounding=ROUND_HALF_UP,
            )
            cost_amount = money(pay_amount / (roi_rate * Decimal("100")))

            rows.append(
                [
                    stat_date.isoformat(),
                    product.product_id,
                    product.title,
                    traffic_source,
                    impression_count,
                    click_count,
                    visitor_count,
                    decimal_text(cost_amount),
                    decimal_text(pay_amount),
                    percent_text(roi_rate),
                ]
            )

    rows.sort(key=lambda row: (str(row[0]), str(row[1]), str(row[3])), reverse=True)
    return rows


def allocate_counts(total_rows: int, bucket_count: int, rng: random.Random) -> list[int]:
    counts = [1] * bucket_count
    remaining = total_rows - bucket_count
    for _ in range(remaining):
        counts[rng.randrange(bucket_count)] += 1
    return counts


def allocate_daily_counts(total_rows: int, bucket_count: int, rng: random.Random) -> list[int]:
    counts = [1] * bucket_count
    remaining = total_rows - bucket_count
    if remaining <= 0:
        return counts

    # 让前几个商品稳定形成长周期日指标，便于复现“详情页只显示最近 90 条”的情况。
    for index, focus_extra in enumerate((149, 119, 94)):
        if index >= bucket_count or remaining <= 0:
            break
        extra = min(focus_extra, remaining)
        counts[index] += extra
        remaining -= extra

    for _ in range(remaining):
        counts[rng.randrange(bucket_count)] += 1
    return counts


def build_product_title(
    index: int,
    prefix: str,
    topic: str,
    suffix: str,
    rng: random.Random,
) -> str:
    if index < len(FOCUS_TITLE_MARKERS):
        marker = FOCUS_TITLE_MARKERS[index]
    else:
        marker = TITLE_SERIES[(index + rng.randrange(len(TITLE_SERIES))) % len(TITLE_SERIES)]
    return f"【{marker}】{prefix}{topic}{suffix}".strip()


def write_xlsx(path: Path, sheet_name: str, headers: list[str], rows: list[list[object]]) -> None:
    sheet_rows: list[list[object]] = [headers, *rows]
    sheet_xml = build_sheet_xml(sheet_rows)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""

    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

    workbook_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""

    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1">
    <font>
      <sz val="11"/>
      <name val="Calibri"/>
      <family val="2"/>
    </font>
  </fonts>
  <fills count="2">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
  </fills>
  <borders count="1">
    <border><left/><right/><top/><bottom/><diagonal/></border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
  </cellXfs>
  <cellStyles count="1">
    <cellStyle name="Normal" xfId="0" builtinId="0"/>
  </cellStyles>
</styleSheet>"""

    app_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex Mock Export Generator</Application>
  <TitlesOfParts>
    <vt:vector size="1" baseType="lpstr">
      <vt:lpstr>{escape(sheet_name)}</vt:lpstr>
    </vt:vector>
  </TitlesOfParts>
  <HeadingPairs>
    <vt:vector size="2" baseType="variant">
      <vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant>
      <vt:variant><vt:i4>1</vt:i4></vt:variant>
    </vt:vector>
  </HeadingPairs>
</Properties>"""

    core_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:dcmitype="http://purl.org/dc/dcmitype/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created_at}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{created_at}</dcterms:modified>
</cp:coreProperties>"""

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types)
        workbook.writestr("_rels/.rels", root_rels)
        workbook.writestr("docProps/app.xml", app_xml)
        workbook.writestr("docProps/core.xml", core_xml)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        workbook.writestr("xl/styles.xml", styles_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def build_sheet_xml(rows: list[list[object]]) -> str:
    max_columns = max((len(row) for row in rows), default=1)
    end_ref = f"{column_letter(max_columns)}{max(len(rows), 1)}"
    row_xml = "".join(render_row(row_index, row) for row_index, row in enumerate(rows, start=1))
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:{end_ref}"/>
  <sheetViews>
    <sheetView workbookViewId="0"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <sheetData>
    {row_xml}
  </sheetData>
</worksheet>"""


def render_row(row_index: int, row: list[object]) -> str:
    cells = "".join(render_cell(row_index, column_index, value) for column_index, value in enumerate(row, start=1))
    return f'<row r="{row_index}">{cells}</row>'


def render_cell(row_index: int, column_index: int, value: object) -> str:
    cell_ref = f"{column_letter(column_index)}{row_index}"
    if value is None:
        return f'<c r="{cell_ref}"/>'
    if isinstance(value, bool):
        return f'<c r="{cell_ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return f'<c r="{cell_ref}"><v>{number_text(value)}</v></c>'

    text = escape(str(value))
    preserve = ' xml:space="preserve"' if text != text.strip() else ""
    return f'<c r="{cell_ref}" t="inlineStr"><is><t{preserve}>{text}</t></is></c>'


def column_letter(index: int) -> str:
    letters = []
    current = index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


def number_text(value: int | float | Decimal) -> str:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return str(value)


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def decimal_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def percent_text(rate: Decimal) -> str:
    percent = (rate * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{format(percent, 'f')}%"


def clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(value, upper))


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        raise SystemExit(f"Error: {exc}") from exc
