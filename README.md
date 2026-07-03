# PChome 24h 搶購工具

使用 Playwright 瀏覽器自動化，監控 PChome 24h 商品開賣狀態，自動加入購物車並結帳。主要介面是網頁控制台（React + FastAPI），CLI 為輔助工具，支援部署在遠端伺服器。

## 功能

- **網頁控制台**：任務卡片網格管理，每張卡可獨立開始/取消，checkbox 勾選批次操作
- 貼上商品頁**網址**即可新增任務（自動解析商品編號），可指定開始監測時間
- 開賣時間相同的任務啟動後自動併組：一個瀏覽器、一次批次輪詢、一次結帳（監控中仍可加入/退出）
- **結帳紀錄**：每次結帳留下紀錄卡片，可查看加車結果（件數/金額）、結帳頁擷取資訊與執行日誌
- **遠端部署**：登入改為貼上/上傳 cookie（storage_state 或瀏覽器擴充功能匯出格式），伺服器不需開視窗
- 透過 `prod/button` API 即時偵測商品開賣狀態（`ForSale` / `NotReady` / `SoldOut`），多商品併行查詢
- 透過 `snapup` + `cart modify` API 直接加入購物車（不需操作頁面按鈕），多商品並行加入
- 啟動時預檢登入 session 是否有效，過期立即提示重新登入
- 指定開賣時間時：距開賣超過 5 分鐘先睡眠等待，開賣前 15 秒才全速輪詢
- 自動填寫信用卡安全碼 (CVC) 並可選自動付款

## 安裝

```bash
# 後端依賴
uv sync

# 安裝 Playwright 瀏覽器（首次）
uv run playwright install chromium

# 前端建置（首次與前端有更新時）
npm --prefix frontend install
npm --prefix frontend run build
```

## 設定

建立 `.env` 檔案（參考 `.env.example`）：

```env
# 信用卡安全碼 (CVC/CVV)
CVC=123

# 是否自動確認付款（設為 true 則自動點擊「確認付款」；遠端部署建議開啟）
AUTO_PAY=false
```

## 使用方式（網頁控制台）

```bash
uv run python main.py web                    # http://127.0.0.1:8787
uv run python main.py web --port 9000
uv run python main.py web --host 0.0.0.0     # 遠端部署（見下方安全性說明）
```

1. **登入**：按「登入」開啟匯入視窗，貼上登入憑證：
   - 在本機執行 `uv run python main.py login`（開瀏覽器手動登入），把產生的 `auth_state.json` 內容貼上或上傳；或
   - 用瀏覽器擴充功能（Cookie-Editor、EditThisCookie 等）在已登入的 PChome 分頁匯出 cookie JSON 貼上。
   - 匯入後可按「檢查 session」實測有效性。
2. **新增任務**：按「＋ 新增任務」，貼上商品頁網址（如 `https://24h.pchome.com.tw/prod/DGCQ39-A900JESMM`）或商品編號，選填開始監測時間（留空 = 立即監控）。
3. **啟動**：每張卡片各自有「開始」；勾選多張卡片可批次「啟動選取／取消選取」。開賣時間相同的任務啟動後併為同一組（卡片同色標示）——一起監控、一起加入購物車、一次結帳。
4. **付款**：結帳頁就緒後瀏覽器保持開啟（headless），同時寫入結帳紀錄；`AUTO_PAY=true` 會自動點擊「確認付款」，否則需在卡片按「結束」前手動處理（遠端無視窗，建議開 AUTO_PAY）。
5. **結帳紀錄**：每組結帳留下一張紀錄卡，「查看詳情」可看每件商品的加車結果、購物車金額、結帳頁資訊與日誌；「標記完成」後可用「清除已完成」整理。

### 前端開發

```bash
uv run python main.py web              # 終端 1：後端 API
npm --prefix frontend run dev          # 終端 2：Vite dev server（自動代理 /api）
```

### 安全性

控制台**本身沒有認證機制**。預設只綁 `127.0.0.1`；以 `--host 0.0.0.0` 部署到遠端時，請務必用反向代理（nginx basic auth、Cloudflare Access、VPN 等）保護存取——`.env` 裡有信用卡安全碼、`auth_state.json` 是你的登入身分。

## 使用方式（CLI，輔助）

```bash
# 登入：開瀏覽器手動登入，儲存 session 至 auth_state.json
# （遠端部署時，這個檔案的內容就是控制台「登入」視窗要貼的憑證）
uv run python main.py login

# 搶購單一商品
uv run python main.py buy DGCQ39-A900JESMM

# 搶購多個商品（同時監控，全部加入購物車後結帳）
uv run python main.py buy DGCQ39-A900JESMM DGCQ39-A900I4PN6

# 無頭模式（不顯示瀏覽器視窗）
uv run python main.py buy DGCQ39-A900JESMM --headless

# 自訂輪詢間隔（預設 0.5 秒，實際會在 0.5x~1.5x 間隨機）
uv run python main.py buy DGCQ39-A900JESMM --interval 0.3

# 指定開賣時間：距開賣超過 5 分鐘會先睡眠，開賣前 5 分鐘自動開始監控，
# 前 15 秒才全速輪詢（之前以 4 倍間隔慢速輪詢）
uv run python main.py buy DGCQ39-A900JESMM --sale-time "2026-03-06 12:00"

# 調整提前啟動監控的秒數（預設 300 秒 = 5 分鐘）
uv run python main.py buy DGCQ39-A900JESMM --sale-time "2026-03-06 12:00" --lead 600

# 背景執行
nohup uv run python main.py buy DGCQ39-A900JESMM --sale-time "2026-03-06 12:00" --headless > buy.log 2>&1 &
```

## 搶購流程

```
匯入登入憑證 → session 預檢 → 監控商品狀態 → 開賣 → snapup API 取得授權碼
→ cart modify API 加入購物車（多商品並行） → 前往結帳 → 自動填 CVC → 確認付款
```

1. **預檢階段**：前往購物車頁確認 session 有效，過期立即報錯（避免開賣瞬間才發現）
2. **監控階段**：透過 `prod/button` API 併行查詢所有商品的 `ButtonType`；只在啟動時對時一次（之後用本機時間推算），並每 60 秒預熱與購物車主機的 TLS 連線。此階段成員可動態加入/退出
3. **加入購物車**：成員凍結後呼叫 `snapup` API 取得 MAC 授權碼（效期僅 15 秒），緊接透過 JSONP 呼叫 `cart modify` API；多商品在瀏覽器內以 `Promise.all` 並行，失敗自動重試 3 次（售完不重試）
4. **結帳階段**：自動導向付款頁面，填入 CVC，擷取訂單資訊寫入結帳紀錄，可選自動點擊「確認付款」

## 已知限制

- 帳號購物車是全域的，「加車→結帳」階段以全域鎖序列化：兩組開賣時間過近時，後一組會等前一組結帳完成。
- 網頁控制台的任務以 headless 瀏覽器執行：`AUTO_PAY=false` 時遠端使用者無法手動付款，建議遠端部署開啟 `AUTO_PAY`。
- 結帳頁訂單資訊的擷取是 best-effort（頁面結構可能改版），擷取失敗不影響付款流程，紀錄中仍保留頁面原始文字。

## 專案結構

```
pchome-buyer/
├── main.py                    # 入口（轉呼叫 pchome.cli）
├── pchome/
│   ├── cli.py                 # login / buy / web 子指令（輔助介面）
│   ├── core/                  # 領域邏輯（無 FastAPI、無持久化）
│   │   ├── config.py          # 環境變數、API 端點、常數
│   │   ├── jsapi.py           # 瀏覽器端 JS 片段（JSONP、批次加車）
│   │   ├── timing.py          # 時間戳、開賣時間解析、伺服器對時
│   │   ├── reporter.py        # 輸出抽象（終端機 / SSE）
│   │   ├── cancel.py          # 任務取消機制
│   │   ├── membership.py      # run-group 動態成員集（加車前凍結）
│   │   ├── session.py         # 登入、session 儲存與檢查
│   │   ├── monitor.py         # 開賣輪詢監控
│   │   ├── cart.py            # 加入購物車 + 重試（結構化結果）
│   │   ├── checkout.py        # 結帳、填 CVC、自動付款、訂單資訊擷取
│   │   └── runner.py          # 完整搶購流程協調（CLI / web 共用）
│   ├── services/              # 應用層（狀態、執行緒、持久化）
│   │   ├── job_service.py     # job / run-group 管理（併組、取消、結帳紀錄）
│   │   ├── auth_service.py    # cookie / storage_state 匯入與 session 檢查
│   │   ├── product_store.py   # products.json 持久化
│   │   ├── checkout_store.py  # checkouts.json 持久化
│   │   ├── product_id.py      # 商品網址 / 編號解析
│   │   └── event_bus.py       # SSE 事件廣播
│   └── api/                   # FastAPI
│       ├── app.py             # 應用組裝、服務前端建置產物
│       ├── deps.py            # 服務單例注入
│       └── routers/           # products / jobs / auth / checkouts / events(SSE)
├── frontend/                  # React + TypeScript + Vite
│   ├── src/components/        # 卡片網格、dialog、結帳紀錄、日誌面板
│   ├── src/state.tsx          # 全域狀態（useReducer + SSE）
│   └── vite.config.ts         # dev server 代理 /api
├── auth_state.json            # 登入狀態（自動產生，已 gitignore）
├── products.json              # 任務清單（自動產生，已 gitignore）
├── checkouts.json             # 結帳紀錄（自動產生，已 gitignore）
├── .env                       # 環境變數（CVC、AUTO_PAY，已 gitignore）
├── pyproject.toml             # 專案設定
└── uv.lock                    # 依賴鎖定
```
