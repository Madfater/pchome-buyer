import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pchome.api.routers import auth, checkouts, events, jobs, products
from tests.support.isolated_container import build_isolated_container


@pytest.fixture
def container(tmp_path, monkeypatch):
    """組出一個完全隔離的 Container：不碰真實 products.json/checkouts.json/auth_state.json"""
    return build_isolated_container(tmp_path, monkeypatch)


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
    ):
        fastapi_app.include_router(router)
    return fastapi_app


@pytest.fixture
def client(app):
    return TestClient(app)
