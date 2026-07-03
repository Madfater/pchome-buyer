"""FastAPI 路由：狀態查詢、商品管理、登入、job 控制與 SSE 事件流"""

import json
import queue
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from ..config import PRODUCTS_FILE
from ..timing import parse_sale_time
from .jobs import EventBus, JobManager
from .store import ProductStore

STATIC_DIR = Path(__file__).parent / "static"


class ProductIn(BaseModel):
    id: str
    sale_time: str = ""


def create_app() -> FastAPI:
    store = ProductStore(PRODUCTS_FILE)
    manager = JobManager(store)
    app = FastAPI(title="PChome 搶購控制台")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/state")
    def state():
        return manager.state()

    @app.post("/api/products")
    def add_product(p: ProductIn):
        pid = p.id.strip()
        sale_time = p.sale_time.strip()
        if not pid or "-" not in pid:
            raise HTTPException(400, "商品編號格式錯誤（如 DGCQ39-A900JESMM）")
        if sale_time:
            try:
                parse_sale_time(sale_time)
            except ValueError as e:
                raise HTTPException(400, str(e))
        store.add(pid, sale_time)
        return manager.state()

    @app.delete("/api/products/{pid}")
    def remove_product(pid: str):
        store.remove(pid)
        return manager.state()

    @app.post("/api/login/start")
    def login_start():
        started = manager.start_login()
        return {"started": started}

    @app.post("/api/login/save")
    def login_save():
        manager.save_login()
        return {"ok": True}

    @app.post("/api/jobs/start")
    def jobs_start():
        if not store.list():
            raise HTTPException(400, "尚未新增任何商品")
        return {"started": manager.start_all()}

    @app.post("/api/jobs/{gid}/stop")
    def job_stop(gid: str):
        if not manager.stop(gid):
            raise HTTPException(404, f"找不到 job: {gid}")
        return {"ok": True}

    @app.get("/api/events")
    def events():
        return StreamingResponse(_sse_stream(manager.bus), media_type="text/event-stream")

    return app


def _sse_stream(bus: EventBus):
    """同步 generator（starlette 會丟到 threadpool 迭代），15 秒無事件送 keepalive"""
    q = bus.subscribe()
    try:
        yield "retry: 2000\n\n"
        while True:
            try:
                event = q.get(timeout=15)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    finally:
        bus.unsubscribe(q)
