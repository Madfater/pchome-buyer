# CLAUDE.md

PChome 24h 限量商品搶購工具：Playwright 自動化，主介面是 web 控制面板（React + Vite 前端、FastAPI 後端）。每個商品是一張可獨立啟動的 job 卡；同一開賣時間的 job 在執行期合併成一個 run-group（一個瀏覽器、一次批次輪詢、一次結帳）。

## 目錄結構

```
backend/    # Python 後端，獨立 src-layout 專案（backend/pyproject.toml、backend/src/pchome、backend/tests）
frontend/   # React + Vite 前端
e2e/        # 跨前後端的 e2e 測試（留在根目錄，用 backend 的 venv 執行，見下方指令）
data/       # 執行期舊版 JSON 檔（gitignored，一次性 migration 來源）
docs/       # 專案文件
docker-compose.yml   # build context 為 repo 根目錄，dockerfile 指到 backend/Dockerfile
```

## 指令

後端是 `backend/` 底下的獨立 src-layout 專案（`backend/pyproject.toml`/`backend/uv.lock`，套件在 `backend/src/pchome`），以下後端指令都要在 `backend/` 目錄下執行。

```bash
cd backend
uv sync                                 # 後端依賴（含 editable 安裝 pchome 本身）
uv run playwright install chromium      # 裝瀏覽器（一次）
cd ..
npm --prefix frontend install           # 前端依賴
npm --prefix frontend run build         # 前端 build（FastAPI 服務面板前必跑）

cd backend && uv run pchome [--port 9000] [--host 0.0.0.0]   # 面板 http://127.0.0.1:8787
npm --prefix frontend run dev           # 前端開發（另開終端，proxy /api 到 :8787）

# 檢查（改完必跑對應項；pytest 以 fake 隔離、不碰真瀏覽器/網路，測不到的行為改動仍要實跑驗證）
cd backend && uv run pytest                        # 改了 pchome/ 任何 Python 必跑（覆蓋 core/services/api 大部分模組，2 秒內跑完；tests/unit + tests/integration 都會跑到）
cd backend && uv run lint-imports                  # 改了 pchome/ 任何 Python 必跑（api/services/core 分層契約）
cd backend && uv run --with pyright pyright src/pchome   # 改了 Python 必跑
cd backend && uv run ruff format .                 # 改了 Python 必跑（格式化）
npm --prefix frontend run lint          # 改了前端必跑（oxlint）
npm --prefix frontend run format        # 改了前端必跑（格式化，prettier）
npm --prefix frontend run build         # 改了前端必跑（含 tsc 型別檢查）
npm --prefix frontend run test          # 改了 frontend/src 必跑（Vitest + React Testing Library）

# e2e（真實瀏覽器打真實 FastAPI server；不在 uv run pytest 預設範圍，需先 npm run build）
npm --prefix frontend run build && cd backend && PYTHONPATH=. uv run pytest ../e2e   # 只涵蓋不啟動 job 的 UI 流程，見 e2e/conftest.py 開頭註解
```

## 致命不變量（違反會 silent fail 或花冤枉錢，改碼前逐條核對）

1. **JSONP-only**：PChome 的 `prod/button` 與 `cart modify` 是 JSONP-only（跨域、無 CORS），必須經 `page.evaluate` 注入 `<script>`（`core/jsapi.py` 的 `JSONP_JS`）呼叫，不能用 `fetch`。`snapup` 和 `datetime` 有 CORS，直接 `fetch`。
2. **RS 必須查、不能拆**：cart-modify 的 `RS`（store code）必須來自 `product_info.resolve_store_codes()`，絕不能從商品 ID 前綴拆（例：`DBAJ8S-A900AJDA7` 屬於 `DBAJ8U`）。RS 錯了 cart-modify 照樣回成功，但購物車頁載入時 PChome 會默默丟掉該商品。ID+`-000` 只用在 `TI` 欄位。
3. **cart-modify 嚴格序列**：PChome 購物車寫入是整車 last-write-wins，並行 modify 會互相覆蓋只剩一件。snapup 可平行，modify 必須逐一序列（`ADD_TO_CART_JS`）。
4. **MAC 只有約 15 秒有效** → membership 在加購前 `freeze()`；`carting` phase 之後絕不可變動 group 的商品集合。
5. **一個輪詢迴圈**：多商品用一次批次 `prod/button` 呼叫同時監控，不是一商品一頁。
6. `PRODCOUNT`/`PRODTOTAL` 是該次加入後的**整車累計**，不是單品數量/價格。
7. **會花真錢**：`AUTO_PAY=true` 會自動點確認付款，任何測試不可跑到真實結帳。CVC 與登入 session 皆存 MongoDB（設定視窗管理；本機舊 `.env`/`auth_state.json` 可能殘留作一次性 migration 來源）——不讀進對話、不印出、不外傳；回傳這些欄位一律先 redact。
8. web job 一律 headless（遠端部署）；`AUTO_PAY=false` 時遠端無法手動付款——遠端部署建議 `AUTO_PAY=true`。
9. 面板**無認證層**：預設綁 127.0.0.1；`--host 0.0.0.0` 需靠反向代理保護（basic auth/VPN/Cloudflare Access）。
10. checkout 的 payinfo 擷取是 best-effort：擷取失敗絕不能中斷付款流程（selector 未經實地驗證）。
11. sync Playwright 不能跑在 asyncio loop 上 → 一個 run-group 一條執行緒一個瀏覽器；**全域 checkout lock** 串行化加購→結帳（購物車是帳號全域的）。

## 文件路由（按需讀，不用全讀）

| 時機 | 讀 |
|---|---|
| 要改任何程式碼、找檔案位置之前 | [docs/claude/architecture.md](docs/claude/architecture.md)（導航地圖；以程式碼為準） |
| 任務要大量讀檔/掃 repo/查網頁/批次改檔 | [docs/claude/10-model-dispatch.md](docs/claude/10-model-dispatch.md)（派工守則，含授權聲明） |
| 判斷要不要升級模型/算不算完成/該不該問使用者/是不是方向錯了 | [docs/claude/20-judgment-rubrics.md](docs/claude/20-judgment-rubrics.md) |
| 要派 subagent 時抄模板 | [docs/claude/30-delegation-templates.md](docs/claude/30-delegation-templates.md) |
| 要修改 CLAUDE.md 或 docs/claude/ 任何檔案 | [docs/claude/40-maintenance.md](docs/claude/40-maintenance.md)（先讀再改） |
| session 開始接手不熟的狀況 | [docs/claude/50-letter.md](docs/claude/50-letter.md) |
| 想知道這套制度為什麼長這樣 | [docs/claude/00-diagnosis.md](docs/claude/00-diagnosis.md) |

**每個 session 的底線**（詳細判準在 20-judgment-rubrics.md）：改 Python 在 `backend/` 底下跑 pyright＋`uv run pytest`、改前端跑 lint+build（動到 `frontend/src` 另跑 `npm run test`）；行為改動要被實際執行過才算完成；驗收派 fresh-context agent，不自驗；教訓寫回對應檔案的「教訓紀錄」段。

## 環境

本機開發需要一個可連線的 MongoDB（`docker run -d -p 127.0.0.1:27017:27017 -v pchome-mongo-data:/data/db mongo:4.4`；釘 4.4 是因為 5.0+ 要求 CPU 支援 AVX，部署機沒有）。
`.env`（見 `.env.example`）只放 `MONGO_URI`/`MONGO_DB` 連線資訊；CVC/AUTO_PAY 與搶購時機/進階調校參數改在面板齒輪圖示的「設定」視窗管理，存 MongoDB（細節見 architecture.md）。
執行期資料（商品/結帳/登入 session）皆存 MongoDB；根目錄舊版 `products.json`/`checkouts.json`/`auth_state.json`（均 gitignore）僅供一次性搬移，之後可留可刪。
本機是 Fedora WSL2：`playwright install-deps` 會失敗，缺系統依賴改用 `dnf`。
**push 到 master ＝ 自動部署遠端實例**（可能帶真憑證與 `AUTO_PAY=true`）——push 前確認使用者要的是部署；細節見 50-letter.md 第 1 件事。
