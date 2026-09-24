"""登入 session（Playwright storage_state）的持久化（PostgreSQL `auth_state` table，單一列）

state 欄位就是 Playwright storage_state() 的原始形狀 {"cookies": [...], "origins": [...]}。
跟 SettingsRepository 不同：這裡沒有預設值，table 第一次查詢若沒有 singleton 列、
且舊版 auth_state.json 存在，才一次性搬入；否則 get() 回傳 None（等同尚未登入）。
"""

import json

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from ..core.config import LEGACY_AUTH_STATE_FILE
from ..infra.db import auth_state_table, get_engine

_ID = "singleton"
_t = auth_state_table


class AuthStateRepository:
    def __init__(self, engine: Engine | None = None):
        self._engine = engine if engine is not None else get_engine()
        if self.get() is None:
            self._migrate_from_legacy_file()

    def get(self) -> dict | None:
        """回傳 storage_state dict；從未匯入過（或搬移舊檔也沒有）則回傳 None"""
        with self._engine.connect() as conn:
            return conn.execute(
                sa.select(_t.c.state).where(_t.c.id == _ID)
            ).scalar_one_or_none()

    def save(self, state: dict) -> None:
        with self._engine.begin() as conn:
            conn.execute(sa.delete(_t).where(_t.c.id == _ID))
            conn.execute(sa.insert(_t).values(id=_ID, state=state))

    def _migrate_from_legacy_file(self) -> None:
        try:
            state = json.loads(LEGACY_AUTH_STATE_FILE.read_text())
        except Exception:
            return
        if isinstance(state, dict) and "cookies" in state:
            self.save(state)
