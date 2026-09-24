"""商品卡片清單的持久化（PostgreSQL `products` table，一商品一列，`id` = 商品編號）

順序不靠資料庫的自然回傳順序（不保證穩定），而是靠明確的 `position` 欄位：
每次 add() 都在同一個 transaction 內取目前最大 position + 1，藉此重現舊版
「重複 id 覆寫後移到清單最後」的語意，且 update_sale_time() 不動 position，維持原位。

meta 是選填的商品展示資訊（名稱/圖片/價格/規格旗標，見 core/product_info.py
的 fetch_product_meta()），純資訊用途，缺欄位或缺 key 不影響任何購買邏輯。
"""

import json
import threading

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

from ..core.config import LEGACY_PRODUCTS_FILE
from ..infra.db import get_engine, products_table

_t = products_table


class ProductRepository:
    def __init__(self, engine: Engine | None = None):
        self._engine = engine if engine is not None else get_engine()
        # MAX(position)+1 是讀後寫：Postgres 預設 READ COMMITTED 下兩個並行 add() 可能拿到同一個值，
        # 本專案是單一 process，用 process 內的鎖序列化即可
        self._add_lock = threading.Lock()
        with self._engine.connect() as conn:
            empty = conn.execute(sa.select(_t.c.id).limit(1)).first() is None
        if empty:
            self._migrate_from_legacy_file()

    def list(self) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                sa.select(_t.c.id, _t.c.sale_time, _t.c.meta).order_by(
                    _t.c.position, _t.c.id
                )
            ).mappings()
            return [
                {"id": r["id"], "sale_time": r["sale_time"], "meta": r["meta"] or {}}
                for r in rows
            ]

    def add(self, pid: str, sale_time: str = "", meta: dict | None = None) -> None:
        """新增商品；重複的 id 以新的 sale_time/meta 覆寫，並移到清單最後（新 position）"""
        with self._add_lock, self._engine.begin() as conn:
            conn.execute(sa.delete(_t).where(_t.c.id == pid))
            conn.execute(
                sa.insert(_t).values(
                    id=pid,
                    sale_time=sale_time,
                    meta=meta or {},
                    position=_next_position(conn),
                )
            )

    def update_sale_time(self, pid: str, sale_time: str) -> bool:
        """更新既有商品的開賣時間（保留清單順序）；不存在回傳 False"""
        with self._engine.begin() as conn:
            result = conn.execute(
                sa.update(_t).where(_t.c.id == pid).values(sale_time=sale_time)
            )
            return result.rowcount > 0

    def remove(self, pid: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(sa.delete(_t).where(_t.c.id == pid))

    def _migrate_from_legacy_file(self) -> None:
        """table 第一次建構時若整個空，且舊版 products.json 存在，一次性搬入並保留原順序"""
        try:
            items = json.loads(LEGACY_PRODUCTS_FILE.read_text())
        except Exception:
            return
        rows = [
            {
                "id": item["id"],
                "sale_time": item.get("sale_time", ""),
                "meta": item.get("meta") or {},
                "position": i,
            }
            for i, item in enumerate(items, start=1)
        ]
        if rows:
            with self._engine.begin() as conn:
                conn.execute(sa.insert(_t), rows)


def _next_position(conn: Connection) -> int:
    current = conn.execute(sa.select(sa.func.max(_t.c.position))).scalar()
    return (current or 0) + 1
