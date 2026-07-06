# Architecture 導航地圖

> **本檔是導航用描述，不是契約。** 與程式碼衝突時一律以程式碼為準；引用本檔的函式名/欄位名之前先 Grep 確認存在。發現過時請順手更新本檔（規則見 [40-maintenance.md](40-maintenance.md)）。
> **最後校準：2026-07-06**（CLI 移除：`pchome/cli.py` 的 `login`/`buy`/`web` 子指令全部拿掉，`main()` 改成無子指令直接解析 `--host`/`--port` 啟動網頁控制台；`ConsoleReporter`/`session.login_flow` 已刪除；尚未 commit）。距今超過 30 天或經歷大型 refactor 後，引用前應抽查校準。
> 致命不變量不在本檔——在 CLAUDE.md，那份才是不能違反的。

`main.py` 是薄入口 → `pchome/cli.py`（唯一功能是啟動 uvicorn 服務網頁控制台）。分層如下。

## `pchome/core/` — 領域邏輯（不碰 FastAPI、不碰持久化）

- **`config.py`** — `.env` 載入（現在只放 `MONGO_URI`/`MONGO_DB` 這類啟動前必須知道的連線資訊）、API endpoint URL、輪詢/重試出廠預設常數（`DEFAULT_INTERVAL_SECS`/`DEFAULT_LEAD_SECS`/`FAST_POLL_WINDOW_SECS`/`SLOW_POLL_FACTOR`/`RESYNC_SECS`/`DEFAULT_MAX_RETRIES`/`DEFAULT_RETRY_DELAY_SECS`）、`AUTH_STATE_FILE` / `PRODUCTS_FILE` / `CHECKOUTS_FILE` / `LEGACY_ENV_FILE` 路徑。CVC/AUTO_PAY 已不在這裡（搬去 `services/settings_store.py`）。
- **`jsapi.py`** — 瀏覽器端 JS 片段：`JSONP_JS`（共用 JSONP helper；URL 中的 `{CB}` 會被替換成一次性 callback 名）與 `ADD_TO_CART_JS`（批次加購物車：snapup fetch 以 `Promise.all` 平行，cart-modify 嚴格逐一序列——原因見 CLAUDE.md 不變量）。
- **`timing.py`** — `now_ms()`、`parse_sale_time()`（會 raise `ValueError`）、`get_server_offset()`（伺服器−本機時鐘差，RTT 中點補償）。
- **`reporter.py`** — `Reporter` 抽象（`log` / `progress` / `product_status` / `phase`）；web 用 `GroupReporter`（在 `services/job_service.py`，推 SSE）。core 模組永不直接 `print()`。`phase()` 回報 run-group 生命週期給 service 層（預設 no-op）。
- **`cancel.py`** — `JobCancelled` + `cancellable_sleep()`；web job 以 `threading.Event` 在每個等待點檢查停止。
- **`membership.py`** — `GroupMembership`：run-group 的執行緒安全可變成員集。監控期間可加入/離開；加購前 `freeze()` 鎖定名單（之後 `add()` 回傳 `False`）。
- **`session.py`** — auth-state 存檔/存在檢查、`check_session(page)`（載入購物車頁偵測是否被導向登入；snapup/cart modify 不需登入——登入只在結帳時強制，所以這步在監控開始前跑）、`check_session_standalone()`（短命 headless 瀏覽器，給 auth status endpoint 用）。
- **`monitor.py`** — `wait_for_sale(..., *, fast_poll_window_secs=, slow_poll_factor=, resync_secs=)`：以 `interval` ±50% 隨機化輪詢 `prod/button` API（JSONP，所有商品一次批次呼叫）取 `ButtonType`（`ForSale` / `NotReady` / `SoldOut`）。每圈重讀 `membership.active_ids()`（動態進出）；成員空了 raise `JobCancelled`。伺服器時間開始時取一次、每 `resync_secs`（預設 60）秒重新校正；同週期對 `ecssl-cart.pchome.com.tw` 發 `no-cors` fetch 保持 TLS 連線暖機。有 sale time 時以 `interval*slow_poll_factor`（預設 4）慢輪詢，開賣前 `fast_poll_window_secs`（預設 15）秒切全速。這三個參數原本是模組常數，現在是 keyword-only 參數（預設值＝原常數），由 `runner.py` 從 `JobConfig` 傳入——面板的設定視窗可調整。
- **`product_info.py`** — `resolve_store_codes()`：批次 prod-API 查每個商品的真實 store code（`Store` 欄位）供購物車 `RS` 參數用，含 in-memory cache。cache 在 `runner.py` 監控前暖機（晚加入者在 `job_service.start()` 暖）；查詢失敗 fallback 到 ID 前綴但不寫入 cache。`fetch_product_meta()`：另一支獨立函式，新增商品時呼叫一次，抓同一個 `prod` API 但擴大 `fields`（Name/Price/Pic/isSpec/isETicket/isPreOrder24h），純展示用途、不快取、失敗一律回傳 `None`（不可讓新增商品失敗）；不要跟 `resolve_store_codes` 共用快取或函式，語意不同。
- **`cart.py`** — `add_with_retry(..., *, max_retries=, retry_delay_secs=)` 回傳 `(success_ids, failed_ids, results)`，`results` 是結構化 `CartItemResult`（含 cart-modify 回應的 `PRODCOUNT`/`PRODTOTAL`）。每商品：`snapup` API（fetch）取得 MAC 授權碼（約 15 秒有效），緊接 `cart modify`（JSONP）帶上該 MAC；全部商品在一次 `page.evaluate` 內完成（snapup 平行、modify 序列）。若 `PRODCOUNT` 未隨逐次加入嚴格遞增會記 warning（clobber 偵測）。失敗最多嘗試 `max_retries`（預設 3，含首次；sold-out 不重試）次，重試間隔 `retry_delay_secs`（預設 0.3 秒）——原本是模組常數 `MAX_RETRIES`/`RETRY_DELAY_SECS`，現在是 keyword-only 參數，面板設定視窗可調整。
- **`checkout.py`** — `go_to_checkout(page, reporter, *, cvc="", auto_pay=False)` 回傳 `CheckoutInfo`：購物車 → payinfo 頁，`cvc` 非空時自動填入（多重 fallback selector），`auto_pay=True` 時自動點「確認付款」，並 best-effort 擷取訂單資訊（`_capture_payinfo`：selector 串接＋截斷 body 文字 fallback；擷取失敗絕不能中斷付款流程——payinfo 的 DOM selector 未經實地驗證，可能需要 live 調整）。`cvc`/`auto_pay` 原本是內部呼叫 `config.get_cvc()`/`is_auto_pay()`（讀 `.env`），現在是明確參數，由呼叫端（`runner.py`）從 `JobConfig` 傳入——core 模組維持不碰持久化。
- **`runner.py`** — `JobConfig` 除了 `product_ids`/`sale_ts`/`interval`/`lead`/`headless`，還有 `fast_poll_window_secs`/`slow_poll_factor`/`resync_secs`/`max_retries`/`retry_delay_secs`/`cvc`/`auto_pay`（皆有出廠預設值）。`run_snapup_job(JobConfig, reporter, membership=, checkout_lock=, cancel=, hold=)`：lead 睡眠 → 開瀏覽器 → session 檢查 → 監控（帶入 `cfg` 的輪詢調校參數）→ freeze membership → 加購重試（帶入 `cfg` 的重試參數）→ 結帳（帶入 `cfg.cvc`/`cfg.auto_pay`）→ `hold(result)`（保持瀏覽器開啟；以 pending `JobResult` 呼叫，讓 web 層在瀏覽器還開著時就持久化結帳紀錄）。回傳 `JobResult(status, success_ids, cart_results, checkout)`。

## `pchome/services/` — 應用層（狀態、執行緒、持久化）

- **`mongo.py`** — 共用 `get_db()`：懶初始化一個 `pymongo.MongoClient`（`serverSelectionTimeoutMS=5000`，連不到 Mongo 快點噴錯而不是卡 30 秒）。目前只有 `settings_store.py` 用；未來 `product_store.py`/`checkout_store.py`/`auth_service.py` 遷移到 Mongo 時共用同一個 client，見 [50-letter.md](50-letter.md)。
- **`settings_store.py`** — `SettingsStore(db=None)`：CVC/AUTO_PAY/輪詢與重試調校參數的持久化，MongoDB `settings` collection 單一文件（`_id="singleton"`）。`get()`/`update(partial)`（`update` 做欄位邊界驗證，違反丟 `ValueError`）。建構時用 `update_one(..., upsert=True)` 確保文件存在；真的觸發 insert 時才做一次性 `.env`（`config.LEGACY_ENV_FILE`）migration，讀舊版 `CVC`/`AUTO_PAY` 塞進去（手動 KEY=VALUE 解析，不靠 python-dotenv）。不需要 `threading.Lock`——`MongoClient` 本身執行緒安全，跟其他檔案型 store 不同。測試一律用 `db=mongomock.MongoClient()[...]` 注入假 db，見 `tests/support/isolated_container.py`。
- **`event_bus.py`** — `EventBus` 把事件扇出到各 SSE 訂閱者 queue（滿了就丟棄）。
- **`product_store.py`** — `ProductStore`，`[{id, sale_time, meta}]` 持久化到 `products.json`；`meta` 是選填的商品展示資訊 dict（`fetch_product_meta()` 的回傳值），純資訊用途，舊資料沒有這個 key 時下游一律用 `item.get("meta", {})` 容錯讀取，不會拋例外。
- **`checkout_store.py`** — `CheckoutRecordStore`，結帳紀錄持久化到 `checkouts.json`（新的在前；`clear_completed()` 只移除 `completed: true`）。
- **`product_id.py`** — `parse_product_ref()`：接受商品頁 URL（`…/prod/<ID>`）或裸 ID；single source of truth（前端只為輸入預覽複製了 regex）。
- **`auth_service.py`** — 遠端部署用 cookie 匯入：`import_auth(payload)` 自動判別 Playwright storage_state JSON vs 瀏覽器擴充套件 cookie 陣列（Cookie-Editor / EditThisCookie；轉換 `expirationDate`→`expires`、正規化 `sameSite`、丟棄擴充套件專屬欄位）後寫入 `auth_state.json`。`status(live=)` 可選跑 `check_session_standalone()`（debounce 30 秒，只在使用者明確操作時）。
- **`job_service.py`** — job/run-group 模型：
  - **Job** = 一張商品卡，狀態 `idle → queued → monitoring → forsale → carted → awaiting_payment → success`，分支 `soldout / cart_failed / failed / session_expired / not_logged_in`（sticky），cancel → `idle`（可重啟）。
  - **RunGroup** = 執行期實體，`gid = <sale_time-slug>#<seq>`，phase `pending → lead_wait → checking_session → monitoring → carting → checkout → holding → closed`。一組一執行緒一瀏覽器（sync Playwright 不能跑在 asyncio loop 上）。
  - `start(pids)`：按 sale_time 分桶；有活著且處於可加入 phase 的 group 就加入（`membership.add()`；回傳 `False` = 剛 freeze → 開新 group），否則開新 group。`cancel(pids)`：移除成員（group 空了 → cancel event 關瀏覽器）；`holding` 中的 group 則是 release（關瀏覽器）。
  - **全域 checkout lock** 串行化各 group 的加購→結帳階段（PChome 購物車是帳號全域的）。
  - `_hold()` 在 block 之前先寫結帳紀錄，所以瀏覽器還開著時面板就看得到；release hold 時標記 completed。
  - `JobService.__init__` 多吃一個 `settings: SettingsStore`；`_run()` 建 `JobConfig` 前先 `self.settings.get()`，把 interval/lead/輪詢調校/重試/CVC/AUTO_PAY 全部帶進去（run-group 啟動當下讀一次，執行期間不重讀）。這是這次設定視窗改動順便修的既有缺口——web job 以前完全接觸不到 `DEFAULT_INTERVAL_SECS`/`DEFAULT_LEAD_SECS`。

## `pchome/api/` — FastAPI

- **`deps.py`** — `Container`（store/checkout_store/bus/jobs/auth/settings 單例）在 `create_app()` 建立，經 `request.app.state.container` 取用；`Container.state()` 是所有 mutating route 回傳的完整快照（不含 settings——`/api/settings` 是獨立端點，不在 `/api/state` 快照裡）。
- **`routers/`** — `products.py`（以 URL/ID 新增、刪除；新增時同步呼叫 `fetch_product_meta()` 存進 `meta`，失敗不影響新增；`GET /api/products/preview?ref=` 唯讀查詢，新增前預覽商品資訊用，不寫入 store）、`jobs.py`（`POST /api/jobs/start|cancel`，body `{pids: []}`）、`auth.py`（`POST /api/auth/import`、`GET /api/auth/status?live=`）、`checkouts.py`（標記完成、清除已完成）、`events.py`（`GET /api/state`、`GET /api/events` SSE——sync generator；每個訂閱分頁佔一條 threadpool 執行緒，1–2 個分頁可接受）、`settings.py`（`GET /api/settings`、`PATCH /api/settings` body 為 pydantic 全 optional 欄位，`exclude_unset=True` 後交給 `SettingsStore.update()`；驗證失敗 400）。
- **`app.py`** — `create_app()`：先掛 routers，再把 `frontend/dist` mount 到 `/`（`StaticFiles(html=True)`）；前端沒 build 時回 503 提示。
- SSE 事件型別：`log`、`progress`、`job`（每卡 `{pid, state, info, gid}`）、`group`（`{gid, phase, member_pids}`；`closed` 表示移除）、`checkout`（`{record}`）。

## `frontend/` — React + TypeScript + Vite

- 依賴只有 react/react-dom；原生 `<dialog>`；純 CSS（`src/styles.css`，light/dark 用 `prefers-color-scheme`）。
- `src/state.tsx` — 單一 `useReducer` context，鏡像 `/api/state` + SSE 增量；`useSse` 在（重新）連線時重抓快照以修復漏掉的事件。`src/api.ts` — fetch 包裝（mutation 回傳完整快照）。`src/types.ts` — 後端契約型別＋label map。
- `src/components/` — `TopBar`（auth 徽章 + 齒輪圖示按鈕開 `SettingsDialog`，取代原本的獨立「登入」按鈕）、`SettingsDialog`（`wide` dialog，四個 section：登入用 `LoginSettingsSection`、付款＝CVC/AUTO_PAY、搶購時機＝interval/lead/fast_poll_window/slow_poll_factor/resync、進階＝max_retries/retry_delay；每個 section 各自 `fetchSettings()`/`updateSettings()`，各自的「儲存」按鈕只送出該 section 自己的欄位，避免跨 section 或跨分頁同時儲存時互相覆蓋）、`LoginSettingsSection`（cookie 貼上/上傳＋檢查 session，從舊的 `LoginDialog` 抽出、拿掉 `Dialog` 包裝，只在 `SettingsDialog` 裡用）、`ProductGrid`（勾選＋批次列＋`AddProductDialog` URL/ID＋datetime，貼上後 debounce 呼叫 `GET /api/products/preview` 顯示縮圖/名稱/價格預覽卡）、`ProductCard`（縮圖/名稱/價格/規格徽章 + 依狀態顯示 開始/取消/結束，group 色條以 sale_time 為 key；`name`/`image`/`price`/`is_spec` 等欄位缺省時 fallback 顯示商品編號，不佔位空白）、`CheckoutGrid`/`CheckoutDetailDialog`（購物車結果表、payinfo 擷取、log 尾巴、標記完成/清除已完成）、`LogPanel`（可按 group 過濾）。
- Vite dev server 把 `/api` proxy 到 `127.0.0.1:8787`（`vite.config.ts`）。
- **測試**（`npm --prefix frontend run test`，Vitest + React Testing Library，100 個測試，`vitest.config.ts` + `src/test-setup.ts`）：每個元件/模組旁邊 `*.test.ts(x)` 共存；`state.tsx` 的 `reducer`/`initialState` 為了可測性改為 `export`（原本模組私有）。API 層一律 `vi.mock('../api')`＋`vi.mock('../toast')`＋`vi.mock('../state')`（只 mock 用到的 hook）隔離，不接真實 fetch／不啟真實 SSE。
  - 教訓：jsdom 沒實作 `<dialog>` 的 `showModal()`/`close()`（只有 `open` 屬性），`test-setup.ts` 補了最小 polyfill（`showModal` 設 `open` 屬性、`close` 移除屬性並 dispatch `close` 事件）；沒有這段 polyfill 任何用到 `components/Dialog.tsx` 的元件測試都會噴 `showModal is not a function`。
  - 教訓：沒開 `vitest.config.ts` 的 `test.globals: true`（刻意用明確 `import` 避免污染 ambient 型別），導致 `@testing-library/react` 靠偵測 global `afterEach` 才會註冊的自動 cleanup 不會生效——每個 render 出的 DOM 會累積到下一個 `it()`，出現「same text 找到兩個節點」的假錯誤。`test-setup.ts` 手動 `afterEach(() => cleanup())` 補上。
  - 教訓：`userEvent.type()` 把 `{`/`[` 當成特殊按鍵語法解析（例：輸入 `{"cookies": []}` 會噴 `Expected repeat modifier...`），貼 JSON payload 一律改用 `fireEvent.change(el, { target: { value } })`，不要用 `user.type()`。

## `tests/` — 純邏輯測試（`uv run pytest`，205 個測試）

- 不碰真實瀏覽器/網路/檔案系統：`test_timing.py`、`test_product_id.py`、`test_membership.py`、`test_cancel.py`、`test_event_bus.py`、`test_cli_helpers.py`。
- 檔案系統類用 `tmp_path` 隔離：`test_product_store.py`、`test_checkout_store.py`；`test_auth_service.py`、`test_session.py` 額外用 `monkeypatch` 換掉 `AUTH_STATE_FILE`，絕不寫真實 `auth_state.json`。
- `test_settings_store.py` 用 `mongomock.MongoClient()` 假 db 隔離，涵蓋預設值/get-update 往返/邊界驗證/`.env` 一次性 migration；**每個測試都必須 monkeypatch `settings_store.LEGACY_ENV_FILE` 指到不存在的路徑**（見下方教訓紀錄——沒隔離會讀到專案根目錄真實 `.env` 的 CVC）。`test_api_settings.py` 走 `conftest.py` 的 `client` fixture（走 `build_isolated_container`，已內建這個隔離）。
- `test_api_products.py` 的 `conftest.py` `container`/`app`/`client` fixture 群另外掛了一個 autouse fixture `no_network_product_meta`，預設把 `products.py` 的 `fetch_product_meta` monkeypatch 成回傳 `None`——`POST /api/products` 新增時會呼叫真實網路查商品展示資訊，測試預設不打真網路；需要驗證 meta 實際寫入行為的測試會自行覆寫這個 monkeypatch。
- 網路類用 fake：`test_product_info.py`（monkeypatch `_fetch_stores`／`urllib.request.urlopen`，涵蓋 RS 查詢/快取/fallback 語意——保護 CLAUDE.md 不變量 #2；同檔另涵蓋 `fetch_product_meta` 的成功解析/缺欄位/查無商品/逾時例外，一律優雅回傳 `None` 不外拋）、`test_cart.py`（`FakePage.evaluate()` 回放批次結果，涵蓋 `add_with_retry` 重試/售完/PRODCOUNT 未遞增警告——不變量 #3/#6）。
- 碰 Playwright `page` 的模組改用「符合介面的 fake page/locator」隔離，不啟動真實瀏覽器：`test_monitor.py`（`wait_for_sale` 的輪詢/開賣判定/慢速→全速切換/動態成員加減）、`test_checkout.py`（`go_to_checkout` 的 CVC 填寫/AUTO_PAY 點擊/payinfo 擷取，含擷取失敗不可中斷付款流程——不變量 #10）、`test_runner.py`（`run_snapup_job` 的未登入早退路徑、`_wait_until_lead`、`_log_header`）。
- `test_session.py` 進一步用「符合 `sync_playwright()` 回傳形狀的 fake `p`/`chromium`/`browser`/`context`/`page`」（`FakeSyncPlaywright` 等）monkeypatch 掉 `session.sync_playwright` 本身，涵蓋 `check_session`（登入導轉判斷）、`check_session_standalone`（無 auth state 時完全不啟動 Playwright；有 auth state 時以 `headless=True`／`storage_state=AUTH_STATE_FILE` 建 context 並委派給 `check_session`；`browser.close()` 在 `check_session` 拋例外時仍會執行——`try/finally` 語意）。全專案已無「非要真開瀏覽器不可才能測」的核心模組。
- `test_job_service.py` 用假 `run_snapup_job`（monkeypatch，卡在 `cancel.wait()` 模擬監控中）測 run-group 的 join/skip/cancel/holding 語意；執行緒測試用 `threading.Event` 同步，不靠 `sleep` 賭時序。
- **`test_api_*.py`**（`test_api_products.py`/`test_api_jobs.py`/`test_api_auth.py`/`test_api_checkouts.py`/`test_api_events.py`）用 FastAPI `TestClient`（`conftest.py` 的 `client`/`container`/`app` fixture，`dev` 依賴新增 `httpx`）打完整 routers，驗證狀態碼與 `Container.state()` 快照形狀；`container` fixture 把 `ProductStore`/`CheckoutRecordStore`/`AUTH_STATE_FILE` 全部指向 `tmp_path`，**不透過 `create_app()`/`build_container()`**（那兩者會綁定專案根目錄的真實 `products.json`/`checkouts.json`/`auth_state.json`）。
  - 教訓：`AUTH_STATE_FILE` 在 `auth_service.py` 與 `session.py` 是各自獨立 `import` 的模組級名稱，只 monkeypatch 其中一個會讓 `has_auth_state()` 仍讀到真實檔案——`conftest.py` 的 `container` fixture 兩邊都換。
  - **`GET /api/events`（SSE）刻意不測**：`StreamingResponse` 的同步 generator 卡在 `queue.get(timeout=15)`，用 `TestClient.stream()` 消費時無法可靠地立即取消底層執行緒，實測會讓整個 `uv run pytest`（必跑 CI gate）掛住超過 2 分鐘——別再嘗試用 TestClient 測這支 endpoint，只測 `GET /api/state`。
- `tests/support/isolated_container.py` — `build_isolated_container(tmp_path, monkeypatch)`：把「組一個完全隔離的 `Container`（換掉兩份 `AUTH_STATE_FILE`、store 全指到 `tmp_path`）」這段邏輯抽出來，`tests/conftest.py` 的 `container` fixture 與 `e2e/conftest.py` 的 `container` fixture 都呼叫它，避免兩處重複維護同一段隔離邏輯。
- 尚未覆蓋且不打算補：`GET /api/events` 串流本身（見上）。

## `e2e/` — 真實瀏覽器測試（`uv run pytest e2e`，9 個測試，不在 `uv run pytest` 預設範圍）

- 不屬於 `pyproject.toml` 的 `testpaths = ["tests"]`，所以預設 `uv run pytest` 不會跑到；要跑必須明確 `uv run pytest e2e`，且需要先 `npm --prefix frontend run build`（`frontend/dist` 不存在會 `pytest.skip`）。
- **範圍刻意限縮，只測不會啟動 job 的 UI 流程**：新增/編輯/刪除商品（單筆＋批次）、登入憑證匯入（含失敗訊息）、checkout 列表顯示/標記完成/清除已完成。**完全不點「開始」/「啟動選取」**——那會在背景執行緒真的呼叫 `core/runner.py` 的 `run_snapup_job`，可能觸發真實網路查詢甚至真的開另一個 Playwright 瀏覽器連真實 PChome（CLAUDE.md 不變量 #7 的紅線）。同理也不點「檢查 session」（live 登入檢查）——只有在已匯入 auth_state 且 30 秒 debounce 過期時才會真的開 headless 瀏覽器連真實網域，e2e 完全不觸碰這顆按鈕。這是使用者在 2026-07-05 明確做的取捨（見 `e2e/conftest.py` 檔頭註解）。
- `e2e/conftest.py` 的 `live_server` fixture：組一個真實的 `FastAPI` app（掛 routers + `frontend/dist` 靜態檔），在背景執行緒跑 `uvicorn.Server`（`socket.bind(("127.0.0.1", 0))` 探測空閒 port，輪詢 `server.started` 直到啟動完成或逾時），yield `(base_url, container)`——回傳 `container` 讓測試能直接呼叫 `container.store.add()`/`container.checkout_store.add()` 預先寫入資料（例如結帳紀錄），不必透過真的加車流程才能測 checkout 列表 UI。
- `page`/`browser` fixture：直接用 `playwright.sync_api.sync_playwright()`（專案主依賴，非新增），headless chromium，每個測試獨立 `new_context()`。
- 教訓：Playwright 的 `get_by_role`/`get_by_text` 預設是子字串比對，`"新增"` 會連 `"＋ 新增任務"` 一起命中（strict mode violation）；同一段文字常在畫面上出現兩次（group 標題 + 卡片內文，例如 `"立即監控"`）。前者用 `exact=True` 排除，後者用 `.first` 或改抓更精確的容器。

## 教訓紀錄

（踩坑後依 [40-maintenance.md](40-maintenance.md) 格式追加於此）

- 2026-07-05 | 症狀: 幫 FastAPI routers 補測試時，`GET /api/auth/status` 明明用 `monkeypatch` 換了 `AUTH_STATE_FILE` 卻仍回報專案根目錄真實 `auth_state.json` 存在 | 根因: `AUTH_STATE_FILE` 在 `services/auth_service.py` 與 `core/session.py` 是各自獨立 `from .config import AUTH_STATE_FILE` 出來的模組級名稱，`has_auth_state()`/`check_session_standalone()` 走 `session.py` 那份，只 patch `auth_service` 那份不會生效 | 規則: 任何要隔離 `AUTH_STATE_FILE` 的測試，兩個模組的綁定都要 monkeypatch（見 `tests/conftest.py` 的 `container` fixture）。
- 2026-07-05 | 症狀: 想用 `TestClient.stream()` 測 `GET /api/events`（SSE），實跑後 `uv run pytest` 整個掛住超過 2 分鐘、`timeout` 包裝也攔不住 | 根因: `events.py` 的 SSE generator 是同步函式卡在 `queue.get(timeout=15)`，交給 starlette 丟到 threadpool 執行；`TestClient` 提前結束 `with client.stream()` 區塊時無法可靠取消該背景執行緒 | 規則: 不要用 `TestClient` 測真正的串流 endpoint，只測回傳快照的 `GET /api/state`；SSE 串流本身留給實跑（開瀏覽器連 `/api/events` 觀察）驗證。
- 2026-07-05 | 症狀: 幫 `login_flow` 補測試時只各自斷言「goto 發生過」「click 發生過」「wait_for_user 發生過」「save_auth_state 發生過」，fresh-context verifier 用 mutation testing（把原始碼 `wait_for_user()`/`save_auth_state()` 呼叫順序對調）發現測試仍全過——證明「各自發生過一次」測不出「順序錯了」這種 bug | 根因: 各項副作用記在各自獨立的變數（`waited`/`page.clicked`/`browser.closed`），沒有共用一份按時間序記錄的 log | 規則: 測「A 必須發生在 B 之前」這種順序不變量時，把所有相關 fake 物件的呼叫都 append 進同一份共用 `calls: list[str]`，最後斷言整個序列（例：`assert calls == ["goto","click","wait","save","close"]`），不要只斷言各自的旗標；懷疑測試是否測到位時，親自對原始碼做一次小 mutation 重跑測試確認會紅，比只看測試綠燈可靠。
- 2026-07-05 | 症狀: 手動對 `session.py` 做 mutation-testing（改順序→測試紅→改回原樣→測試卻仍然紅，明明 `diff` 確認檔案內容已跟原始一模一樣）| 根因: 在同一秒內快速「寫入 mutated 版本→跑 pytest→寫回原版→再跑 pytest」，`__pycache__/*.pyc` 的 mtime-based 快取失效判斷在同一秒窗口內可能誤判為快取仍有效，導致還在跑舊的 mutated bytecode | 規則: 手動 mutation-testing 時，每次改完原始碼、跑 pytest 前，先 `find . -name "__pycache__" -exec rm -rf {} +` 清快取，或用 `python -B`（不寫入 bytecode），否則會出現「明明改回去了、測試卻還是紅」的假警報，白白懷疑錯地方。
- 2026-07-05 | 症狀: 補 `components/Dialog.tsx` 的元件測試時，任何觸發 `open` 從 false→true 的 render 都噴 `TypeError: el.showModal is not a function` | 根因: jsdom（vitest 預設環境）沒有實作 `HTMLDialogElement.showModal()`/`close()`，只認得 `open` 屬性 | 規則: `src/test-setup.ts` 補了最小 polyfill；任何新測試環境（例如換掉 jsdom）都要先確認這兩個方法有沒有被實作。
- 2026-07-05 | 症狀: 同一個 `*.test.tsx` 檔案裡，第二個以後的 `it()` 常常「找到兩個相同節點」而失敗，即使每個 `it()` 都各自 `render()` 一次 | 根因: `vitest.config.ts` 沒開 `test.globals: true`（刻意用明確 import 避免 ambient 型別污染），而 `@testing-library/react` 的自動 cleanup 是靠偵測 global `afterEach` 才註冊，沒偵測到就完全不會清理，DOM 在測試間累積 | 規則: 手動 import cleanup：`test-setup.ts` 裡 `import { afterEach } from 'vitest'; import { cleanup } from '@testing-library/react'; afterEach(() => cleanup())`。
- 2026-07-05 | 症狀: `userEvent.type(textarea, '{"cookies": []}')` 噴 `Expected repeat modifier or release modifier or "}"` | 根因: `userEvent.type()` 把字串裡的 `{`/`[` 解析成特殊按鍵語法（例如 `{enter}`），JSON 內容天生充滿這些字元 | 規則: 貼 JSON/含大括號內容一律用 `fireEvent.change(el, { target: { value } })`，不要用 `user.type()`。
- 2026-07-05 | 症狀: e2e 測試裡 `page.get_by_role("button", name="新增").click()` 噴 strict mode violation，命中「＋ 新增任務」跟「新增」兩顆按鈕 | 根因: Playwright 的 accessible-name 比對預設是子字串，不是精確相等 | 規則: 兩顆按鈕文字有包含關係時，短的那顆（或容易被包含的那顆）加 `exact=True`；同一段文字在畫面上合法地出現兩次（例如 group 標題與卡片內文都顯示 `"立即監控"`）時用 `.first`，而不是想辦法讓文字唯一。
- 2026-07-06 | 症狀: 幫 `SettingsStore` 補測試（含 `uv run pytest` 跑到的預設值測試）、以及手動實跑 `curl /api/settings` 驗證 API 時，兩次都把專案根目錄真實 `.env` 的 CVC 印進了對話 | 根因: `SettingsStore` 建構時的一次性 `.env` migration 讀的是 `config.LEGACY_ENV_FILE`（預設指向真實 `PROJECT_ROOT/.env`），測試/手動實跑若沒有明確把這個路徑換成不存在的假路徑，就會在本機這種已經有真實 `.env` 的開發環境讀到真實 CVC | 規則: 任何建構 `SettingsStore` 的地方（測試 fixture、手動實跑用的暫時 script）一律先確認 `LEGACY_ENV_FILE` 已被换成假路徑（`tests/support/isolated_container.py`/`tests/test_settings_store.py`/`tests/test_job_service.py` 已加上）；手動實跑若會呼叫任何回傳 `cvc` 欄位的 API，輸出前一律先 redact 該欄位再看，不要直接印原始 JSON。
