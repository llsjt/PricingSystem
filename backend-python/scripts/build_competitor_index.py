"""一次性脚本：把天猫商品 CSV 转换成精简的 SQLite 索引，供 MarketIntel 查询。

只保留 MarketIntel 真正需要的列，URL/链接/优惠券长字符串全部丢弃，
最终产物体积约为原 CSV 的 1/4 ~ 1/3，并按一级/二级类目、品牌建索引。

用法::

    python -m scripts.build_competitor_index --csv "../数据集/天猫数据_1月到11月.csv"
    python -m scripts.build_competitor_index --csv path/to.csv --output app/data/competitor_index.sqlite

可通过 --limit 测试小样。
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from pathlib import Path
from typing import Iterable, Iterator

CSV_HEADER_TO_DB = {
    "商品ID": "product_id",
    "品牌名称": "brand",
    "一级类目ID": "primary_category_id",
    "一级类目名称": "primary_category",
    "二级类目ID": "secondary_category_id",
    "二级类目名称": "secondary_category",
    "店铺名称": "shop_name",
    "店铺类型": "shop_type",
    "短标题": "short_title",
    "商品标题": "title",
    "原价": "original_price",
    "折后价": "discount_price",
    "最终促销价": "final_price",
    "年销量": "yearly_sales",
    "当日促销销量": "daily_promo_sales",
    "优惠标签": "promotion_tag",
    "采集时间": "collected_at",
    "所属品类": "campaign_label",
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS competitor (
    product_id TEXT PRIMARY KEY,
    brand TEXT,
    primary_category_id TEXT,
    primary_category TEXT,
    secondary_category_id TEXT,
    secondary_category TEXT,
    shop_name TEXT,
    shop_type TEXT,
    short_title TEXT,
    title TEXT,
    original_price REAL,
    discount_price REAL,
    final_price REAL,
    yearly_sales INTEGER,
    daily_promo_sales INTEGER,
    promotion_tag TEXT,
    collected_at TEXT,
    campaign_label TEXT
)
"""

CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_secondary_category ON competitor(secondary_category)",
    "CREATE INDEX IF NOT EXISTS idx_primary_category ON competitor(primary_category)",
    "CREATE INDEX IF NOT EXISTS idx_brand ON competitor(brand)",
]

INSERT_SQL = (
    "INSERT OR REPLACE INTO competitor ("
    + ", ".join(CSV_HEADER_TO_DB.values())
    + ") VALUES ("
    + ", ".join("?" for _ in CSV_HEADER_TO_DB)
    + ")"
)

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_sales(value: str | None) -> int | None:
    """把"7000+"、"6000+"、"3.5万+"等字符串解析为整数。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    multiplier = 1
    if "万" in text:
        multiplier = 10000
        text = text.replace("万", "")
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    try:
        return int(float(match.group(0)) * multiplier)
    except ValueError:
        return None


def parse_price(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    try:
        price = float(match.group(0))
    except ValueError:
        return None
    return price if price > 0 else None


def _strip_bom(name: str) -> str:
    return name.lstrip("\ufeff").strip()


def iter_csv_rows(csv_path: Path, limit: int | None = None) -> Iterator[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        if reader.fieldnames is None:
            raise RuntimeError(f"CSV 缺少表头: {csv_path}")
        # 兼容字段名前后空白
        normalized = [_strip_bom(name) for name in reader.fieldnames]
        reader.fieldnames = normalized
        for index, row in enumerate(reader):
            if limit is not None and index >= limit:
                return
            yield {(_strip_bom(k) if isinstance(k, str) else k): v for k, v in row.items()}


def row_to_record(row: dict[str, str]) -> tuple | None:
    product_id = (row.get("商品ID") or "").strip()
    if not product_id:
        return None
    primary_category = (row.get("一级类目名称") or "").strip()
    secondary_category = (row.get("二级类目名称") or "").strip()
    if not primary_category and not secondary_category:
        return None
    return (
        product_id,
        (row.get("品牌名称") or "").strip() or None,
        (row.get("一级类目ID") or "").strip() or None,
        primary_category or None,
        (row.get("二级类目ID") or "").strip() or None,
        secondary_category or None,
        (row.get("店铺名称") or "").strip() or None,
        (row.get("店铺类型") or "").strip() or None,
        (row.get("短标题") or "").strip() or None,
        (row.get("商品标题") or "").strip() or None,
        parse_price(row.get("原价")),
        parse_price(row.get("折后价")),
        parse_price(row.get("最终促销价")),
        parse_sales(row.get("年销量")),
        parse_sales(row.get("当日促销销量")),
        (row.get("优惠标签") or "").strip() or None,
        (row.get("采集时间") or "").strip() or None,
        (row.get("所属品类") or "").strip() or None,
    )


def build_index(
    csv_path: Path,
    output_path: Path,
    *,
    limit: int | None = None,
    batch_size: int = 5000,
) -> dict[str, int]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 不存在: {csv_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    inserted = 0
    skipped = 0
    conn = sqlite3.connect(output_path)
    try:
        conn.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;")
        conn.execute(CREATE_TABLE_SQL)
        buffer: list[tuple] = []
        for row in iter_csv_rows(csv_path, limit=limit):
            record = row_to_record(row)
            if record is None:
                skipped += 1
                continue
            buffer.append(record)
            if len(buffer) >= batch_size:
                conn.executemany(INSERT_SQL, buffer)
                inserted += len(buffer)
                buffer.clear()
        if buffer:
            conn.executemany(INSERT_SQL, buffer)
            inserted += len(buffer)
        for stmt in CREATE_INDEX_SQL:
            conn.execute(stmt)
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()
    return {"inserted": inserted, "skipped": skipped, "size_bytes": output_path.stat().st_size}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="天猫 CSV 路径")
    parser.add_argument(
        "--output",
        default="app/data/competitor_index.sqlite",
        help="生成的 SQLite 路径，默认 app/data/competitor_index.sqlite",
    )
    parser.add_argument("--limit", type=int, default=None, help="仅处理前 N 行（调试用）")
    parser.add_argument("--batch-size", type=int, default=5000)
    args = parser.parse_args(list(argv) if argv is not None else None)

    stats = build_index(
        Path(args.csv),
        Path(args.output),
        limit=args.limit,
        batch_size=args.batch_size,
    )
    print(
        f"done: inserted={stats['inserted']}, skipped={stats['skipped']}, "
        f"size={stats['size_bytes'] / 1024 / 1024:.2f} MB"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
