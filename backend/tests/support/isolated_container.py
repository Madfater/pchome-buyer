"""建立完全隔離（in-memory SQLite）Container 的共用邏輯

供 tests/conftest.py（FastAPI TestClient 測試）與 e2e/conftest.py（真實瀏覽器測試）共用，
確保兩邊都不會碰到真實 PostgreSQL 或專案根目錄的舊版 products.json/checkouts.json/
auth_state.json/.env。
"""

from pathlib import Path

from pchome.api.deps import Container
from pchome.infra.event_bus import EventBus
from pchome.repositories import settings_repository as settings_repository_module
from pchome.repositories.auth_state_repository import AuthStateRepository
from pchome.repositories.checkout_repository import CheckoutRecordRepository
from pchome.repositories.product_repository import ProductRepository
from pchome.repositories.settings_repository import SettingsRepository
from pchome.services.auth_service import AuthService
from pchome.services.job_service import JobService
from tests.support.db import memory_engine


def build_isolated_container(tmp_path: Path, monkeypatch) -> Container:
    """所有持久化 repository 一律注入同一個 in-memory SQLite engine（tables 各自獨立，
    跟正式環境共用一個 PostgreSQL database 的方式一致）；LEGACY_ENV_FILE 也要換掉，
    否則 SettingsRepository 的一次性 migration 會讀到專案根目錄真實的 .env（含真實 CVC）"""
    monkeypatch.setattr(
        settings_repository_module, "LEGACY_ENV_FILE", tmp_path / "does_not_exist.env"
    )
    engine = memory_engine()
    product_repository = ProductRepository(engine=engine)
    checkout_repository = CheckoutRecordRepository(engine=engine)
    bus = EventBus()
    settings_repository = SettingsRepository(engine=engine)
    auth_state_repository = AuthStateRepository(engine=engine)
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
