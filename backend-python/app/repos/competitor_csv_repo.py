"""SQLite 竞品索引访问层。

`scripts/build_competitor_index.py` 把天猫 CSV 转成 `competitor_index.sqlite`，
本仓储负责按类目/标题关键词查询，并按销量降序返回 top-N 行。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.core.config import get_settings


_SAFE_LIKE_RE = str.maketrans({"%": r"\%", "_": r"\_"})


def _escape_like(value: str) -> str:
    return value.translate(_SAFE_LIKE_RE)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


class CompetitorCsvRepo:
    """轻量级 SQLite 访问，复用单连接（线程安全开 check_same_thread=False）。"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        settings = get_settings()
        resolved = Path(db_path) if db_path else Path(settings.competitor_csv_index_path)
        if not resolved.is_absolute():
            resolved = Path(settings.competitor_csv_index_path)
            if not resolved.is_absolute():
                resolved = Path(__file__).resolve().parents[1].parent / resolved
        self.db_path = resolved
        self._conn: sqlite3.Connection | None = None

    @property
    def available(self) -> bool:
        return self.db_path.exists()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            if not self.db_path.exists():
                raise FileNotFoundError(f"竞品索引未生成: {self.db_path}")
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._conn = conn
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── 查询 ─────────────────────────────────────────────────────
    def query_by_secondary_category(self, name: str, limit: int) -> list[dict[str, Any]]:
        if not name:
            return []
        sql = (
            "SELECT * FROM competitor WHERE secondary_category = ? "
            "ORDER BY COALESCE(yearly_sales,0) DESC LIMIT ?"
        )
        rows = self._get_conn().execute(sql, (name, limit)).fetchall()
        return [_row_to_dict(r) for r in rows]

    def query_by_primary_category(self, name: str, limit: int) -> list[dict[str, Any]]:
        if not name:
            return []
        sql = (
            "SELECT * FROM competitor WHERE primary_category = ? "
            "ORDER BY COALESCE(yearly_sales,0) DESC LIMIT ?"
        )
        rows = self._get_conn().execute(sql, (name, limit)).fetchall()
        return [_row_to_dict(r) for r in rows]

    def query_by_keyword(self, keyword: str, limit: int) -> list[dict[str, Any]]:
        if not keyword:
            return []
        pattern = f"%{_escape_like(keyword)}%"
        sql = (
            "SELECT * FROM competitor "
            "WHERE title LIKE ? ESCAPE '\\' OR short_title LIKE ? ESCAPE '\\' "
            "ORDER BY COALESCE(yearly_sales,0) DESC LIMIT ?"
        )
        rows = self._get_conn().execute(sql, (pattern, pattern, limit)).fetchall()
        return [_row_to_dict(r) for r in rows]
