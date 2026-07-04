# Architecture 導航地圖

> **本檔是導航用描述，不是契約。** 與程式碼衝突時一律以程式碼為準；引用本檔的函式名/欄位名之前先 Grep 確認存在。發現過時請順手更新本檔（規則見 [40-maintenance.md](40-maintenance.md)）。
> **最後校準：2026-07-04**（對應 commit 672aadd）。距今超過 30 天或經歷大型 refactor 後，引用前應抽查校準。
> 致命不變量不在本檔——在 CLAUDE.md，那份才是不能違反的。

`main.py` 是薄入口 → `pchome/cli.py`。分層如下。

## `pchome/core/` — 領域邏輯（不碰 FastAPI、不碰持久化）

- **`config.py`** — `.env` 載入、API endpoint URL、輪詢常數、`AUTH_STATE_FILE` / `PRODUCTS_FILE` / `CHECKOUTS_FILE` 路徑、`get_cvc()` / `is_auto_pay()`。
- **`jsapi.py`** — 瀏覽器端 JS 片段：`JSONP_JS`（共用 JSONP helper；URL 中的 `{CB}` 會被替換成一次性 callback 名）與 `ADD_TO_CART_JS`（批次加購物車：snapup fetch 以 `Promise.all` 平行，cart-modify 嚴格逐一序列——原因見 CLAUDE.md 不變量）。
- **`timing.py`** — `now_ms()`、`parse_sale_time()`（會 raise `ValueError`）、`get_server_offset()`（伺服器−本機時鐘差，RTT 中點補償）。
- **`reporter.py`** — `Reporter` 抽象（`log` / `progress` / `product_status` / `phase`）；CLI 用 `ConsoleReporter`，web 用 `GroupReporter`（在 `services/job_service.py`，推 SSE）。core 模組永不直接 `print()`。`phase()` 回報 run-group 生命週期給 service 層（預設 no-op）。
- **`cancel.py`** — `JobCancelled` + `cancellable_sleep()`；web job 以 `threading.Event` 在每個等待點檢查停止。
- **`membership.py`** — `GroupMembership`：run-group 的執行緒安全可變成員集。監控期間可加入/離開；加購前 `freeze()` 鎖定名單（之後 `add()` 回傳 `False`）。
- **`session.py`** — `login_flow(wait_for_user)`（有頭瀏覽器，CLI 專用）、auth-state 存檔/存在檢查、`check_session(page)`（載入購物車頁偵測是否被導向登入；snapup/cart modify 不需登入——登入只在結帳時強制，所以這步在監控開始前跑）、`check_session_standalone()`（短命 headless 瀏覽器，給 auth status endpoint 用）。
- **`monitor.py`** — `wait_for_sale()`：以 `interval` ±50% 隨機化輪詢 `prod/button` API（JSONP，所有商品一次批次呼叫）取 `ButtonType`（`ForSale` / `NotReady` / `SoldOut`）。每圈重讀 `membership.active_ids()`（動態進出）；成員空了 raise `JobCancelled`。伺服器時間開始時取一次、每 60 秒重新校正；每 60 秒對 `ecssl-cart.pchome.com.tw` 發 `no-cors` fetch 保持 TLS 連線暖機。有 sale time 時以 `interval*4` 慢輪詢，開賣前 15 秒切全速。
- **`product_info.py`** — `resolve_store_codes()`：批次 prod-API 查每個商品的真實 store code（`Store` 欄位）供購物車 `RS` 參數用，含 in-memory cache。cache 在 `runner.py` 監控前暖機（晚加入者在 `job_service.start()` 暖）；查詢失敗 fallback 到 ID 前綴但不寫入 cache。
- **`cart.py`** — `add_with_retry()` 回傳 `(success_ids, failed_ids, results)`，`results` 是結構化 `CartItemResult`（含 cart-modify 回應的 `PRODCOUNT`/`PRODTOTAL`）。每商品：`snapup` API（fetch）取得 MAC 授權碼（約 15 秒有效），緊接 `cart modify`（JSONP）帶上該 MAC；全部商品在一次 `page.evaluate` 內完成（snapup 平行、modify 序列）。若 `PRODCOUNT` 未隨逐次加入嚴格遞增會記 warning（clobber 偵測）。失敗最多嘗試 3 次（含首次；sold-out 不重試）。
- **`checkout.py`** — `go_to_checkout()` 回傳 `CheckoutInfo`：購物車 → payinfo 頁，自動填 CVC（多重 fallback selector），`AUTO_PAY=true` 時自動點「確認付款」，並 best-effort 擷取訂單資訊（`_capture_payinfo`：selector 串接＋截斷 body 文字 fallback；擷取失敗絕不能中斷付款流程——payinfo 的 DOM selector 未經實地驗證，可能需要 live 調整）。
- **`runner.py`** — `run_snapup_job(JobConfig, reporter, membership=, checkout_lock=, cancel=, hold=)`：lead 睡眠 → 開瀏覽器 → session 檢查 → 監控 → freeze membership → 加購重試 → 結帳 → `hold(result)`（保持瀏覽器開啟；以 pending `JobResult` 呼叫，讓 web 層在瀏覽器還開著時就持久化結帳紀錄）。回傳 `JobResult(status, success_ids, cart_results, checkout)`。CLI 不傳 membership（由 `cfg.product_ids` 建靜態的）。

## `pchome/services/` — 應用層（狀態、執行緒、持久化）

- **`event_bus.py`** — `EventBus` 把事件扇出到各 SSE 訂閱者 queue（滿了就丟棄）。
- **`product_store.py`** — `ProductStore`，`[{id, sale_time}]` 持久化到 `products.json`。
- **`checkout_store.py`** — `CheckoutRecordStore`，結帳紀錄持久化到 `checkouts.json`（新的在前；`clear_completed()` 只移除 `completed: true`）。
- **`product_id.py`** — `parse_product_ref()`：接受商品頁 URL（`…/prod/<ID>`）或裸 ID；single source of truth（前端只為輸入預覽複製了 regex）。
- **`auth_service.py`** — 遠端部署用 cookie 匯入：`import_auth(payload)` 自動判別 Playwright storage_state JSON vs 瀏覽器擴充套件 cookie 陣列（Cookie-Editor / EditThisCookie；轉換 `expirationDate`→`expires`、正規化 `sameSite`、丟棄擴充套件專屬欄位）後寫入 `auth_state.json`。`status(live=)` 可選跑 `check_session_standalone()`（debounce 30 秒，只在使用者明確操作時）。
- **`job_service.py`** — job/run-group 模型：
  - **Job** = 一張商品卡，狀態 `idle → queued → monitoring → forsale → carted → awaiting_payment → success`，分支 `soldout / cart_failed / failed / session_expired / not_logged_in`（sticky），cancel → `idle`（可重啟）。
  - **RunGroup** = 執行期實體，`gid = <sale_time-slug>#<seq>`，phase `pending → lead_wait → checking_session → monitoring → carting → checkout → holding → closed`。一組一執行緒一瀏覽器（sync Playwright 不能跑在 asyncio loop 上）。
  - `start(pids)`：按 sale_time 分桶；有活著且處於可加入 phase 的 group 就加入（`membership.add()`；回傳 `False` = 剛 freeze → 開新 group），否則開新 group。`cancel(pids)`：移除成員（group 空了 → cancel event 關瀏覽器）；`holding` 中的 group 則是 release（關瀏覽器）。
  - **全域 checkout lock** 串行化各 group 的加購→結帳階段（PChome 購物車是帳號全域的）。
  - `_hold()` 在 block 之前先寫結帳紀錄，所以瀏覽器還開著時面板就看得到；release hold 時標記 completed。

## `pchome/api/` — FastAPI

- **`deps.py`** — `Container`（store/checkout_store/bus/jobs/auth 單例）在 `create_app()` 建立，經 `request.app.state.container` 取用；`Container.state()` 是所有 mutating route 回傳的完整快照。
- **`routers/`** — `products.py`（以 URL/ID 新增、刪除）、`jobs.py`（`POST /api/jobs/start|cancel`，body `{pids: []}`）、`auth.py`（`POST /api/auth/import`、`GET /api/auth/status?live=`）、`checkouts.py`（標記完成、清除已完成）、`events.py`（`GET /api/state`、`GET /api/events` SSE——sync generator；每個訂閱分頁佔一條 threadpool 執行緒，1–2 個分頁可接受）。
- **`app.py`** — `create_app()`：先掛 routers，再把 `frontend/dist` mount 到 `/`（`StaticFiles(html=True)`）；前端沒 build 時回 503 提示。
- SSE 事件型別：`log`、`progress`、`job`（每卡 `{pid, state, info, gid}`）、`group`（`{gid, phase, member_pids}`；`closed` 表示移除）、`checkout`（`{record}`）。

## `frontend/` — React + TypeScript + Vite

- 依賴只有 react/react-dom；原生 `<dialog>`；純 CSS（`src/styles.css`，light/dark 用 `prefers-color-scheme`）。
- `src/state.tsx` — 單一 `useReducer` context，鏡像 `/api/state` + SSE 增量；`useSse` 在（重新）連線時重抓快照以修復漏掉的事件。`src/api.ts` — fetch 包裝（mutation 回傳完整快照）。`src/types.ts` — 後端契約型別＋label map。
- `src/components/` — `TopBar`（auth 徽章 + `LoginDialog` cookie 貼上/上傳）、`ProductGrid`（勾選＋批次列＋`AddProductDialog` URL/ID＋datetime）、`ProductCard`（依狀態顯示 開始/取消/結束，group 色條以 sale_time 為 key）、`CheckoutGrid`/`CheckoutDetailDialog`（購物車結果表、payinfo 擷取、log 尾巴、標記完成/清除已完成）、`LogPanel`（可按 group 過濾）。
- Vite dev server 把 `/api` proxy 到 `127.0.0.1:8787`（`vite.config.ts`）。

## `tests/` — 純邏輯測試（`uv run pytest`，192 個測試）

- 不碰真實瀏覽器/網路/檔案系統：`test_timing.py`、`test_product_id.py`、`test_membership.py`、`test_cancel.py`、`test_event_bus.py`、`test_config.py`、`test_cli_helpers.py`。
- 檔案系統類用 `tmp_path` 隔離：`test_product_store.py`、`test_checkout_store.py`；`test_auth_service.py`、`test_session.py` 額外用 `monkeypatch` 換掉 `AUTH_STATE_FILE`，絕不寫真實 `auth_state.json`。
- 網路類用 fake：`test_product_info.py`（monkeypatch `_fetch_stores`／`urllib.request.urlopen`，涵蓋 RS 查詢/快取/fallback 語意——保護 CLAUDE.md 不變量 #2）、`test_cart.py`（`FakePage.evaluate()` 回放批次結果，涵蓋 `add_with_retry` 重試/售完/PRODCOUNT 未遞增警告——不變量 #3/#6）。
- 碰 Playwright `page` 的模組改用「符合介面的 fake page/locator」隔離，不啟動真實瀏覽器：`test_monitor.py`（`wait_for_sale` 的輪詢/開賣判定/慢速→全速切換/動態成員加減）、`test_checkout.py`（`go_to_checkout` 的 CVC 填寫/AUTO_PAY 點擊/payinfo 擷取，含擷取失敗不可中斷付款流程——不變量 #10）、`test_runner.py`（`run_snapup_job` 的未登入早退路徑、`_wait_until_lead`、`_log_header`）。
- `test_session.py` 進一步用「符合 `sync_playwright()` 回傳形狀的 fake `p`/`chromium`/`browser`/`context`/`page`」（`FakeSyncPlaywright` 等）monkeypatch 掉 `session.sync_playwright` 本身，涵蓋 `check_session`（登入導轉判斷）、`login_flow`（導頁→點登入→等待→`save_auth_state`→關瀏覽器的順序與副作用）、`check_session_standalone`（無 auth state 時完全不啟動 Playwright；有 auth state 時以 `headless=True`／`storage_state=AUTH_STATE_FILE` 建 context 並委派給 `check_session`；`browser.close()` 在 `check_session` 拋例外時仍會執行——`try/finally` 語意）。全專案已無「非要真開瀏覽器不可才能測」的核心模組。
- `test_job_service.py` 用假 `run_snapup_job`（monkeypatch，卡在 `cancel.wait()` 模擬監控中）測 run-group 的 join/skip/cancel/holding 語意；執行緒測試用 `threading.Event` 同步，不靠 `sleep` 賭時序。
- **`test_api_*.py`**（`test_api_products.py`/`test_api_jobs.py`/`test_api_auth.py`/`test_api_checkouts.py`/`test_api_events.py`）用 FastAPI `TestClient`（`conftest.py` 的 `client`/`container`/`app` fixture，`dev` 依賴新增 `httpx`）打完整 routers，驗證狀態碼與 `Container.state()` 快照形狀；`container` fixture 把 `ProductStore`/`CheckoutRecordStore`/`AUTH_STATE_FILE` 全部指向 `tmp_path`，**不透過 `create_app()`/`build_container()`**（那兩者會綁定專案根目錄的真實 `products.json`/`checkouts.json`/`auth_state.json`）。
  - 教訓：`AUTH_STATE_FILE` 在 `auth_service.py` 與 `session.py` 是各自獨立 `import` 的模組級名稱，只 monkeypatch 其中一個會讓 `has_auth_state()` 仍讀到真實檔案——`conftest.py` 的 `container` fixture 兩邊都換。
  - **`GET /api/events`（SSE）刻意不測**：`StreamingResponse` 的同步 generator 卡在 `queue.get(timeout=15)`，用 `TestClient.stream()` 消費時無法可靠地立即取消底層執行緒，實測會讓整個 `uv run pytest`（必跑 CI gate）掛住超過 2 分鐘——別再嘗試用 TestClient 測這支 endpoint，只測 `GET /api/state`。
- 尚未覆蓋且不打算補：`GET /api/events` 串流本身（見上）、前端 TypeScript（無測試框架，需另外評估要不要引入）。

## 教訓紀錄

（踩坑後依 [40-maintenance.md](40-maintenance.md) 格式追加於此）

- 2026-07-05 | 症狀: 幫 FastAPI routers 補測試時，`GET /api/auth/status` 明明用 `monkeypatch` 換了 `AUTH_STATE_FILE` 卻仍回報專案根目錄真實 `auth_state.json` 存在 | 根因: `AUTH_STATE_FILE` 在 `services/auth_service.py` 與 `core/session.py` 是各自獨立 `from .config import AUTH_STATE_FILE` 出來的模組級名稱，`has_auth_state()`/`check_session_standalone()` 走 `session.py` 那份，只 patch `auth_service` 那份不會生效 | 規則: 任何要隔離 `AUTH_STATE_FILE` 的測試，兩個模組的綁定都要 monkeypatch（見 `tests/conftest.py` 的 `container` fixture）。
- 2026-07-05 | 症狀: 想用 `TestClient.stream()` 測 `GET /api/events`（SSE），實跑後 `uv run pytest` 整個掛住超過 2 分鐘、`timeout` 包裝也攔不住 | 根因: `events.py` 的 SSE generator 是同步函式卡在 `queue.get(timeout=15)`，交給 starlette 丟到 threadpool 執行；`TestClient` 提前結束 `with client.stream()` 區塊時無法可靠取消該背景執行緒 | 規則: 不要用 `TestClient` 測真正的串流 endpoint，只測回傳快照的 `GET /api/state`；SSE 串流本身留給實跑（開瀏覽器連 `/api/events` 觀察）驗證。
- 2026-07-05 | 症狀: 幫 `login_flow` 補測試時只各自斷言「goto 發生過」「click 發生過」「wait_for_user 發生過」「save_auth_state 發生過」，fresh-context verifier 用 mutation testing（把原始碼 `wait_for_user()`/`save_auth_state()` 呼叫順序對調）發現測試仍全過——證明「各自發生過一次」測不出「順序錯了」這種 bug | 根因: 各項副作用記在各自獨立的變數（`waited`/`page.clicked`/`browser.closed`），沒有共用一份按時間序記錄的 log | 規則: 測「A 必須發生在 B 之前」這種順序不變量時，把所有相關 fake 物件的呼叫都 append 進同一份共用 `calls: list[str]`，最後斷言整個序列（例：`assert calls == ["goto","click","wait","save","close"]`），不要只斷言各自的旗標；懷疑測試是否測到位時，親自對原始碼做一次小 mutation 重跑測試確認會紅，比只看測試綠燈可靠。
- 2026-07-05 | 症狀: 手動對 `session.py` 做 mutation-testing（改順序→測試紅→改回原樣→測試卻仍然紅，明明 `diff` 確認檔案內容已跟原始一模一樣）| 根因: 在同一秒內快速「寫入 mutated 版本→跑 pytest→寫回原版→再跑 pytest」，`__pycache__/*.pyc` 的 mtime-based 快取失效判斷在同一秒窗口內可能誤判為快取仍有效，導致還在跑舊的 mutated bytecode | 規則: 手動 mutation-testing 時，每次改完原始碼、跑 pytest 前，先 `find . -name "__pycache__" -exec rm -rf {} +` 清快取，或用 `python -B`（不寫入 bytecode），否則會出現「明明改回去了、測試卻還是紅」的假警報，白白懷疑錯地方。
