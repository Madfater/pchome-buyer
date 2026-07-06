"""建立完全隔離（mongomock-backed）Container 的共用邏輯

供 tests/conftest.py（FastAPI TestClient 測試）與 e2e/conftest.py（真實瀏覽器測試）共用，
確保兩邊都不會碰到真實 MongoDB 或專案根目錄的舊版 products.json/checkouts.json/
auth_state.json/.env。
"""

from pathlib import Path

import mongomock

from pchome.api.deps import Container
from pchome.infra.event_bus import EventBus
from pchome.repositories import settings_repository as settings_repository_module
from pchome.repositories.auth_state_repository import AuthStateRepository
from pchome.repositories.checkout_repository import CheckoutRecordRepository
from pchome.repositories.product_repository import ProductRepository
from pchome.repositories.settings_repository import SettingsRepository
from pchome.services.auth_service import AuthService
from pchome.services.job_service import JobService


def build_isolated_container(tmp_path: Path, monkeypatch) -> Container:
    """所有持久化 repository 一律注入同一個 mongomock 假 db（collections 各自命名空間，
    跟正式環境共用一個真實 Mongo database 的方式一致）；LEGACY_ENV_FILE 也要換掉，
    否則 SettingsRepository 的一次性 migration 會讀到專案根目錄真實的 .env（含真實 CVC）"""
    monkeypatch.setattr(
        settings_repository_module, "LEGACY_ENV_FILE", tmp_path / "does_not_exist.env"
    )
    fake_db = mongomock.MongoClient()["test"]
    product_repository = ProductRepository(db=fake_db)
    checkout_repository = CheckoutRecordRepository(db=fake_db)
    bus = EventBus()
    settings_repository = SettingsRepository(db=fake_db)
    auth_state_repository = AuthStateRepository(db=fake_db)
    jobs_svc = JobService(
        product_repository,
        checkout_repository,
        bus,
        settings_repository,
        auth_state_repository,
    )
    auth_svc = AuthService(auth_state_repository)
    return Container(
        product_repository,
        checkout_repository,
        bus,
        jobs_svc,
        auth_svc,
        settings_repository,
    )
