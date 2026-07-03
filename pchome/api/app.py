"""FastAPI 應用組裝：服務注入、掛載 API routers 與前端靜態檔"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from ..core.config import PROJECT_ROOT
from .deps import build_container
from .routers import auth, checkouts, events, jobs, products

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


def create_app(dist_dir: Path = FRONTEND_DIST) -> FastAPI:
    app = FastAPI(title="PChome 搶購控制台")
    app.state.container = build_container()

    for router in (products.router, jobs.router, auth.router, checkouts.router, events.router):
        app.include_router(router)

    # API 路由先註冊；前端建置產物掛在根路徑接住其餘請求
    if (dist_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="ui")
    else:
        @app.get("/")
        def index_missing():
            return PlainTextResponse(
                "前端尚未建置：請在 frontend/ 執行 `npm install && npm run build`，"
                "或開發時使用 `npm run dev`（Vite dev server 會代理 /api）",
                status_code=503,
            )

    return app
