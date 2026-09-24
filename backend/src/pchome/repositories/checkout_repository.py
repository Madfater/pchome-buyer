"""結帳紀錄的持久化（PostgreSQL `checkouts` table，一筆結帳一列，`id` = 紀錄 id）

排序靠自動遞增的 `seq` 欄位，由新到舊排序（seq DESC），
不依賴資料庫自然順序或 created_at 字串（同一秒內新增多筆時字串排序不足以分出先後）。
"""

# class 內的 list 方法會遮蔽內建 list，型別註記需延遲求值
from __future__ import annotations

import json
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from ..core.config import LEGACY_CHECKOUTS_FILE
from ..infra.db import checkouts_table, get_engine

_t = checkouts_table
_FIELDS = (
    "id",
    "created_at",
    "gid",
    "sale_time",
    "status",
    "completed",
    "cart_results",
    "payinfo",
    "log_tail",
)
_UPDATABLE = frozenset(_FIELDS) - {"id"}
_COLUMNS = [_t.c[f] for f in _FIELDS]


class CheckoutRecordRepository:
    def __init__(self, engine: Engine | None = None):
        self._engine = engine if engine is not None else get_engine()
        with self._engine.connect() as conn:
            empty = conn.execute(sa.select(_t.c.seq).limit(1)).first() is None
        if empty:
            self._migrate_from_legacy_file()

    def list(self) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(sa.select(*_COLUMNS).order_by(_t.c.seq.desc()))
            return [dict(r) for r in rows.mappings()]

    def add(
        self,
        *,
        gid: str,
        sale_time: str,
        status: str,
        cart_results: list[dict],
        payinfo: dict | None,
        log_tail: list[str],
    ) -> dict:
        record = {
            "id": uuid.uuid4().hex,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "gid": gid,
            "sale_time": sale_time,
            "status": status,
            "completed": False,
            "cart_results": cart_results,
            "payinfo": payinfo,
            "log_tail": log_tail,
        }
        with self._engine.begin() as conn:
            conn.execute(sa.insert(_t).values(**record))
        return dict(record)

    def update(self, record_id: str, **fields) -> dict | None:
        """更新紀錄欄位，回傳更新後的紀錄；找不到回傳 None"""
        unknown = set(fields) - _UPDATABLE
        if unknown:
            raise ValueError(f"未知的結帳紀錄欄位: {sorted(unknown)}")
        with self._engine.begin() as conn:
            if fields:
                conn.execute(sa.update(_t).where(_t.c.id == record_id).values(**fields))
            row = (
                conn.execute(sa.select(*_COLUMNS).where(_t.c.id == record_id))
                .mappings()
                .first()
            )
            return dict(row) if row is not None else None

    def clear_completed(self) -> int:
        with self._engine.begin() as conn:
            result = conn.execute(sa.delete(_t).where(_t.c.completed.is_(True)))
            return result.rowcount

    def _migrate_from_legacy_file(self) -> None:
        try:
            records = json.loads(LEGACY_CHECKOUTS_FILE.read_text())
        except Exception:
            return
        # 舊檔新到舊排列；反轉後逐一插入，seq 遞增，seq DESC 排序後仍是新到舊
        rows = [
            {
                "id": r["id"],
                "created_at": r.get("created_at", ""),
                "gid": r.get("gid", ""),
                "sale_time": r.get("sale_time", ""),
                "status": r.get("status", ""),
                "completed": bool(r.get("completed", False)),
                "cart_results": r.get("cart_results") or [],
                "payinfo": r.get("payinfo"),
                "log_tail": r.get("log_tail") or [],
            }
            for r in reversed(records)
        ]
        if rows:
            with self._engine.begin() as conn:
                for row in rows:
                    conn.execute(sa.insert(_t).values(**row))
