import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pchome.api.deps import Container
from pchome.api.routers import auth, checkouts, events, jobs, products
from pchome.core import session as session_module
from pchome.services import auth_service as auth_service_module
from pchome.services.auth_service import AuthService
from pchome.services.checkout_store import CheckoutRecordStore
from pchome.services.event_bus import EventBus
from pchome.services.job_service import JobService
from pchome.services.product_store import ProductStore


@pytest.fixture
def container(tmp_path, monkeypatch):
    """組出一個完全隔離的 Container：不碰真實 products.json/checkouts.json/auth_state.json

    AUTH_STATE_FILE 在 auth_service.py 與 session.py 是各自獨立 import 的模組級名稱，
    has_auth_state()/check_session_standalone() 走 session.py 那份，import_auth() 走
    auth_service.py 那份——兩邊都要換掉，否則讀到的是專案根目錄真實 auth_state.json。
    """
    fake_auth_state = tmp_path / "auth_state.json"
    monkeypatch.setattr(auth_service_module, "AUTH_STATE_FILE", fake_auth_state)
    monkeypatch.setattr(session_module, "AUTH_STATE_FILE", fake_auth_state)
    store = ProductStore(tmp_path / "products.json")
    checkout_store = CheckoutRecordStore(tmp_path / "checkouts.json")
    bus = EventBus()
    jobs_svc = JobService(store, checkout_store, bus)
    auth_svc = AuthService()
    return Container(store, checkout_store, bus, jobs_svc, auth_svc)


@pytest.fixture
def app(container):
    fastapi_app = FastAPI()
    fastapi_app.state.container = container
    for router in (products.router, jobs.router, auth.router, checkouts.router, events.router):
        fastapi_app.include_router(router)
    return fastapi_app


@pytest.fixture
def client(app):
    return TestClient(app)
