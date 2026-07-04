"""前端 e2e 測試基礎設施：隔離 container + 真實 uvicorn server + 真實 Playwright 瀏覽器

刻意範圍限縮：只驅動不會啟動 job 的 UI 流程（新增/編輯/刪除商品、批次操作、登入匯入、
checkout 列表）。啟動 job 會在背景執行緒真的呼叫 core/runner.py 的 run_snapup_job，
可能觸發真實網路查詢甚至真的開另一個 Playwright 瀏覽器連真實 PChome——這些一律不測。

不屬於 `tests/`（testpaths），`uv run pytest` 預設不會跑到，須明確指定
`uv run pytest e2e`。需要 `frontend/dist` 已建置（`npm --prefix frontend run build`）。
"""

import socket
import threading
import time

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import sync_playwright

from pchome.api.routers import auth, checkouts, events, jobs, products
from pchome.core.config import PROJECT_ROOT
from tests.support.isolated_container import build_isolated_container

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@pytest.fixture
def container(tmp_path, monkeypatch):
    return build_isolated_container(tmp_path, monkeypatch)


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def live_server(container):
    """回傳 (base_url, container)：container 供測試直接預先寫入資料（例如 checkout 紀錄）"""
    if not (FRONTEND_DIST / "index.html").exists():
        pytest.skip("frontend/dist 未建置：先執行 npm --prefix frontend run build")

    app = FastAPI()
    app.state.container = container
    for router in (products.router, jobs.router, auth.router, checkouts.router, events.router):
        app.include_router(router)
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="ui")

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 5
    while not server.started and time.time() < deadline:
        time.sleep(0.02)
    if not server.started:
        raise RuntimeError("live_server 啟動逾時")

    try:
        yield f"http://127.0.0.1:{port}", container
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.fixture
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context()
    pg = ctx.new_page()
    yield pg
    ctx.close()
