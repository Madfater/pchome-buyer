import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pchome.api.routers import auth, checkouts, events, jobs, products, settings
from tests.support.isolated_container import build_isolated_container


@pytest.fixture
def container(tmp_path, monkeypatch):
    """組出一個完全隔離的 Container：不碰真實 products.json/checkouts.json/auth_state.json"""
    return build_isolated_container(tmp_path, monkeypatch)


@pytest.fixture(autouse=True)
def no_network_product_meta(monkeypatch):
    """預設不打真實網路查商品展示資訊（fetch_product_meta 回傳 None）；
    需要測 meta 實際行為的測試會自行覆寫這個 monkeypatch"""
    monkeypatch.setattr(products, "fetch_product_meta", lambda pid: None)


@pytest.fixture
def app(container):
    fastapi_app = FastAPI()
    fastapi_app.state.container = container
    for router in (
        products.router,
        jobs.router,
        auth.router,
        checkouts.router,
        events.router,
        settings.router,
    ):
        fastapi_app.include_router(router)
    return fastapi_app


@pytest.fixture
def client(app):
    return TestClient(app)
