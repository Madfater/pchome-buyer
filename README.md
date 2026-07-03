# PChome 24h 搶購腳本

使用 Playwright 瀏覽器自動化，監控 PChome 24h 商品開賣狀態，自動加入購物車並結帳。

## 功能

- 自動登入並儲存 session（cookie / localStorage）
- 透過 `prod/button` API 即時偵測商品開賣狀態（`ForSale` / `NotReady` / `SoldOut`）
- 支援同時監控多個商品，併行查詢狀態
- 透過 `snapup` + `cart modify` API 直接加入購物車（不需操作頁面按鈕），多商品並行加入
- 啟動時預檢登入 session 是否有效，過期立即提示重新登入
- 支援 `--sale-time` 分段輪詢：開賣前 15 秒才全速輪詢，降低被封鎖風險
- 自動填寫信用卡安全碼 (CVC) 並可選自動付款
- 排程腳本支援在開賣前 5 分鐘自動啟動

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

## 使用方式

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

# 指定開賣時間：開賣前 15 秒才全速輪詢，之前以 4 倍間隔慢速輪詢
uv run python main.py buy DGCQ39-A900JESMM --sale-time "2026-03-06 12:00"
```

### 3. 排程搶購

使用 `schedule.sh` 在指定開賣時間前 5 分鐘自動啟動監控：

```bash
# 基本用法
./schedule.sh "2026-03-06 12:00" DGCQ39-A900IGZAX DGCQ39-A900JRDBJ

# 搭配 headless 模式
./schedule.sh "2026-03-06 12:00" DGCQ39-A900IGZAX --headless

# 背景執行
nohup ./schedule.sh "2026-03-06 12:00" DGCQ39-A900IGZAX > buy.log 2>&1 &
```

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
├── main.py          # 主程式
├── schedule.sh      # 排程腳本
├── auth_state.json  # 登入狀態（自動產生，已 gitignore）
├── .env             # 環境變數（CVC、AUTO_PAY）
├── pyproject.toml   # 專案設定
└── uv.lock          # 依賴鎖定
```
