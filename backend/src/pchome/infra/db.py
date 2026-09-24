"""共用資料庫 engine 與 table 定義（SQLAlchemy Core，正式環境是 PostgreSQL）

所有 repository 共用同一個 engine（連線池本身 thread-safe，run-group 執行緒與 API 執行緒可並用）。
schema 很小（四張表），用 create_all 建表，不引入 migration 工具。
欄位型別只用可攜的 sa.JSON 等，讓單元測試能換成 in-memory SQLite 跑同一份程式碼。
"""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from ..core.config import DATABASE_URL

metadata = sa.MetaData()

# 使用者設定：單一列（id = "singleton"），data 是設定 dict
settings_table = sa.Table(
    "settings",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("data", sa.JSON, nullable=False),
)

# 登入 session：單一列，state 是 Playwright storage_state() 原始形狀
auth_state_table = sa.Table(
    "auth_state",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("state", sa.JSON, nullable=False),
)

# 商品卡片：position 決定清單順序（重新 add 會拿新的最大值，移到最後）
products_table = sa.Table(
    "products",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("sale_time", sa.Text, nullable=False, default=""),
    sa.Column("meta", sa.JSON, nullable=False),
    sa.Column("position", sa.BigInteger, nullable=False),
)

# 結帳紀錄：seq 自動遞增決定先後（新到舊 = seq DESC），id 是對外的紀錄 id
checkouts_table = sa.Table(
    "checkouts",
    metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("id", sa.Text, nullable=False, unique=True),
    sa.Column("created_at", sa.Text, nullable=False),
    sa.Column("gid", sa.Text, nullable=False),
    sa.Column("sale_time", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("completed", sa.Boolean, nullable=False, default=False),
    sa.Column("cart_results", sa.JSON, nullable=False),
    sa.Column("payinfo", sa.JSON, nullable=True),
    sa.Column("log_tail", sa.JSON, nullable=False),
)

_engine: Engine | None = None


def make_engine(url: str, **kwargs: Any) -> Engine:
    """建立 engine 並確保 schema 存在。

    connect_timeout 刻意設短：Postgres 沒啟動時，啟動面板要快點噴出清楚的連線錯誤，
    而不是卡很久才失敗。
    """
    if url.startswith("postgresql"):
        kwargs.setdefault("connect_args", {"connect_timeout": 5})
        kwargs.setdefault("pool_pre_ping", True)
    engine = sa.create_engine(url, **kwargs)
    metadata.create_all(engine)
    return engine


def get_engine() -> Engine:
    """回傳共用 engine；懶初始化"""
    global _engine
    if _engine is None:
        _engine = make_engine(DATABASE_URL)
    return _engine
