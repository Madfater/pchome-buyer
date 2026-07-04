"""建立完全隔離（tmp_path-backed）Container 的共用邏輯

供 tests/conftest.py（FastAPI TestClient 測試）與 e2e/conftest.py（真實瀏覽器測試）共用，
確保兩邊都不會碰到專案根目錄的真實 products.json/checkouts.json/auth_state.json。
"""

from pathlib import Path

from pchome.api.deps import Container
from pchome.core import session as session_module
from pchome.services import auth_service as auth_service_module
from pchome.services.auth_service import AuthService
from pchome.services.checkout_store import CheckoutRecordStore
from pchome.services.event_bus import EventBus
from pchome.services.job_service import JobService
from pchome.services.product_store import ProductStore


def build_isolated_container(tmp_path: Path, monkeypatch) -> Container:
    """AUTH_STATE_FILE 在 auth_service.py 與 session.py 是各自獨立 import 的模組級名稱，兩邊都要換掉"""
    fake_auth_state = tmp_path / "auth_state.json"
    monkeypatch.setattr(auth_service_module, "AUTH_STATE_FILE", fake_auth_state)
    monkeypatch.setattr(session_module, "AUTH_STATE_FILE", fake_auth_state)
    store = ProductStore(tmp_path / "products.json")
    checkout_store = CheckoutRecordStore(tmp_path / "checkouts.json")
    bus = EventBus()
    jobs_svc = JobService(store, checkout_store, bus)
    auth_svc = AuthService()
    return Container(store, checkout_store, bus, jobs_svc, auth_svc)
