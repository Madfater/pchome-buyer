"""使用者可調整設定的持久化（MongoDB `settings` collection，單一文件）

收納原本散落在 .env（CVC/AUTO_PAY）與 core/config.py、core/cart.py 常數裡的可調參數，
讓面板的設定視窗可以讀寫。核心模組（core/）維持不碰持久化：這裡讀出的值一律以明確參數
往下傳，不在 core/ 內部直接讀這個 store。
"""

from pathlib import Path

from pymongo.database import Database

from ..core.config import (
    DEFAULT_INTERVAL_SECS,
    DEFAULT_LEAD_SECS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY_SECS,
    FAST_POLL_WINDOW_SECS,
    LEGACY_ENV_FILE,
    RESYNC_SECS,
    SLOW_POLL_FACTOR,
)
from ..infra.mongo import get_db

_ID = "singleton"

_DEFAULTS = {
    "cvc": "",
    "auto_pay": False,
    "default_interval_secs": DEFAULT_INTERVAL_SECS,
    "default_lead_secs": DEFAULT_LEAD_SECS,
    "fast_poll_window_secs": FAST_POLL_WINDOW_SECS,
    "slow_poll_factor": SLOW_POLL_FACTOR,
    "resync_secs": RESYNC_SECS,
    "max_retries": DEFAULT_MAX_RETRIES,
    "retry_delay_secs": DEFAULT_RETRY_DELAY_SECS,
}

# 欄位邊界驗證（含）：field -> (min, max)
_BOUNDS = {
    "default_interval_secs": (0.05, 10),
    "default_lead_secs": (0, 3600),
    "fast_poll_window_secs": (0, 120),
    "slow_poll_factor": (1, 20),
    "resync_secs": (1, 600),
    "max_retries": (1, 10),
    "retry_delay_secs": (0, 5),
}


class SettingsRepository:
    def __init__(self, db: Database | None = None):
        self._col = (db if db is not None else get_db())["settings"]
        result = self._col.update_one(
            {"_id": _ID}, {"$setOnInsert": _DEFAULTS}, upsert=True
        )
        if result.upserted_id is not None:
            self._migrate_from_legacy_env()

    def get(self) -> dict:
        doc = self._col.find_one({"_id": _ID}) or dict(_DEFAULTS)
        doc.pop("_id", None)
        return doc

    def update(self, partial: dict) -> dict:
        """驗證後套用部分更新，回傳合併後的完整設定"""
        changes = {k: _validate(k, v) for k, v in partial.items()}
        if changes:
            self._col.update_one({"_id": _ID}, {"$set": changes})
        return self.get()

    def _migrate_from_legacy_env(self) -> None:
        """settings 文件第一次建立時，若有舊版 .env 就一次性搬入 CVC/AUTO_PAY"""
        try:
            legacy = _parse_env_file(LEGACY_ENV_FILE)
        except Exception:
            return
        changes: dict = {}
        if "CVC" in legacy:
            changes["cvc"] = legacy["CVC"]
        if "AUTO_PAY" in legacy:
            changes["auto_pay"] = legacy["AUTO_PAY"].strip().lower() == "true"
        if changes:
            self._col.update_one({"_id": _ID}, {"$set": changes})


def _validate(key: str, value):
    if key == "cvc":
        return str(value).strip()
    if key == "auto_pay":
        return bool(value)
    if key in _BOUNDS:
        lo, hi = _BOUNDS[key]
        num = int(value) if key == "max_retries" else float(value)
        if not (lo <= num <= hi):
            raise ValueError(f"{key} 必須介於 {lo} 到 {hi} 之間")
        return num
    raise ValueError(f"未知的設定欄位: {key}")


def _parse_env_file(path: Path) -> dict[str, str]:
    """簡單的 KEY=VALUE 解析，不依賴 python-dotenv（只用來做一次性 migration）"""
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result
