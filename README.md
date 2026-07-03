# PChome 24h 搶購腳本

使用 Playwright 瀏覽器自動化，監控 PChome 24h 商品開賣狀態，自動加入購物車並結帳。提供 CLI 與網頁控制台兩種操作方式。

## 功能

- 自動登入並儲存 session（cookie / localStorage）
- 透過 `prod/button` API 即時偵測商品開賣狀態（`ForSale` / `NotReady` / `SoldOut`）
- 支援同時監控多個商品，併行查詢狀態
- 透過 `snapup` + `cart modify` API 直接加入購物車（不需操作頁面按鈕），多商品並行加入
- 啟動時預檢登入 session 是否有效，過期立即提示重新登入
- 支援 `--sale-time`：距開賣超過 5 分鐘先睡眠等待（`--lead` 可調），開賣前 15 秒才全速輪詢
- 自動填寫信用卡安全碼 (CVC) 並可選自動付款
- 網頁控制台：卡片式管理多個商品，同開賣時間的商品一起結帳、不同時間分開結帳

## 安裝

```bash
# 安裝依賴
uv sync

# 安裝 Playwright 瀏覽器
uv run playwright install chromium
```

## 設定

建立 `.env` 檔案：

```env
# 信用卡安全碼 (CVC/CVV)
CVC=123

# 是否自動確認付款（設為 true 則自動點擊「確認付款」）
AUTO_PAY=false
```

## 使用方式（CLI）

### 1. 登入

首次使用需先登入，儲存 session：

```bash
uv run python main.py login
```

會開啟瀏覽器，手動完成登入後按 Enter 儲存 session 至 `auth_state.json`。

### 2. 搶購

```bash
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

## 使用方式（網頁控制台）

```bash
uv run python main.py web          # http://127.0.0.1:8787
uv run python main.py web --port 9000
```

- **登入**：按「登入」會彈出真實瀏覽器視窗，手動登入完成後回控制台按「完成登入，儲存 session」。
- **新增商品**：輸入商品編號與開賣時間（可留空 = 立即監控），每個商品一張卡片。
- **分組結帳**：開賣時間相同的商品自動歸為同一組（卡片同色標示）——一起監控、一起加入購物車、一次結帳；不同開賣時間是獨立任務、分開結帳。
- **啟動**：按「全部啟動」依分組啟動任務，卡片與日誌透過 SSE 即時更新。
- **付款**：結帳頁就緒後會保留瀏覽器視窗讓你手動確認付款（`AUTO_PAY=true` 則自動點擊），完成後在控制台按「結束」關閉瀏覽器。

### 已知限制

- 帳號購物車是全域的，「加車→結帳」階段以全域鎖序列化：兩組開賣時間過近時，後一組會等前一組結帳完成。
- 網頁登入與付款確認依賴本機有頭瀏覽器（WSL 需 WSLg）；遠端存取需另外加畫面串流，目前不支援。
- 控制台只綁 `127.0.0.1`，請勿改綁對外介面（無任何驗證機制）。

## 搶購流程

```
登入 → session 預檢 → 監控商品狀態 → 開賣 → snapup API 取得授權碼
→ cart modify API 加入購物車（多商品並行） → 前往結帳 → 自動填 CVC → 確認付款
```

1. **預檢階段**：前往購物車頁確認 session 有效，過期立即報錯（避免開賣瞬間才發現）
2. **監控階段**：透過 `prod/button` API 併行查詢所有商品的 `ButtonType`；只在啟動時對時一次（之後用本機時間推算），並每 60 秒預熱與購物車主機的 TLS 連線
3. **加入購物車**：呼叫 `snapup` API 取得 MAC 授權碼（效期僅 15 秒），緊接透過 JSONP 呼叫 `cart modify` API；多商品在瀏覽器內以 `Promise.all` 並行，失敗自動重試 3 次（售完不重試）
4. **結帳階段**：自動導向付款頁面，填入 CVC，可選自動點擊「確認付款」

## 商品 ID 取得方式

從 PChome 24h 商品頁面 URL 取得：

```
https://24h.pchome.com.tw/prod/DGCQ39-A900JESMM
                                 ^^^^^^^^^^^^^^^^^^
                                 這就是商品 ID
```

## 專案結構

```
pchome-buyer/
├── main.py              # 入口（轉呼叫 pchome.cli）
├── pchome/
│   ├── config.py        # 環境變數、API 端點、常數
│   ├── jsapi.py         # 瀏覽器端 JS 片段（JSONP、批次加車）
│   ├── timing.py        # 時間戳、開賣時間解析、伺服器對時
│   ├── reporter.py      # 輸出抽象（終端機 / 網頁）
│   ├── cancel.py        # 任務取消機制
│   ├── session.py       # 登入、session 儲存與檢查
│   ├── monitor.py       # 開賣輪詢監控
│   ├── cart.py          # 加入購物車 + 重試
│   ├── checkout.py      # 結帳、填 CVC、自動付款
│   ├── runner.py        # 完整搶購流程協調（CLI / web 共用）
│   ├── cli.py           # login / buy / web 子指令
│   └── web/
│       ├── store.py     # products.json 持久化
│       ├── jobs.py      # 分組 job 管理、SSE 事件廣播
│       ├── app.py       # FastAPI 路由
│       └── static/index.html  # 卡片網格 UI
├── auth_state.json      # 登入狀態（自動產生，已 gitignore）
├── products.json        # 網頁控制台的商品清單（自動產生）
├── .env                 # 環境變數（CVC、AUTO_PAY）
├── pyproject.toml       # 專案設定
└── uv.lock              # 依賴鎖定
```
