"""共用 MongoDB client 存取點：未來其他 store（products/checkouts/auth）遷移到
Mongo 時重複使用同一個連線，不用各自重新設計連線層。
"""

from pymongo import MongoClient
from pymongo.database import Database

from ..core.config import MONGO_DB_NAME, MONGO_URI

_client: MongoClient | None = None


def get_db() -> Database:
    """回傳 Mongo database handle；懶初始化一個共用 client。

    serverSelectionTimeoutMS 刻意設短（預設 30 秒太久）：Mongo 沒啟動時，
    啟動面板要快點噴出清楚的連線錯誤，而不是卡住半分鐘才失敗。
    """
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client[MONGO_DB_NAME]
