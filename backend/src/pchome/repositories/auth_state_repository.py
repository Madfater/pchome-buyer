"""登入 session（Playwright storage_state）的持久化（MongoDB `auth_state` collection，單一文件）

文件內容就是 Playwright storage_state() 的原始形狀 {"cookies": [...], "origins": [...]}。
跟 SettingsRepository 不同：這裡沒有預設值，collection 第一次查詢若沒有 singleton 文件、
且舊版 auth_state.json 存在，才一次性搬入；否則 get() 回傳 None（等同尚未登入）。
"""

import json

from pymongo.database import Database

from ..core.config import LEGACY_AUTH_STATE_FILE
from ..infra.mongo import get_db

_ID = "singleton"


class AuthStateRepository:
    def __init__(self, db: Database | None = None):
        self._col = (db if db is not None else get_db())["auth_state"]
        if self._col.find_one({"_id": _ID}) is None:
            self._migrate_from_legacy_file()

    def get(self) -> dict | None:
        """回傳 storage_state dict；從未匯入過（或搬移舊檔也沒有）則回傳 None"""
        doc = self._col.find_one({"_id": _ID})
        if doc is None:
            return None
        doc.pop("_id", None)
        return doc

    def save(self, state: dict) -> None:
        self._col.replace_one({"_id": _ID}, {"_id": _ID, **state}, upsert=True)

    def _migrate_from_legacy_file(self) -> None:
        try:
            state = json.loads(LEGACY_AUTH_STATE_FILE.read_text())
        except Exception:
            return
        if isinstance(state, dict) and "cookies" in state:
            self.save(state)
