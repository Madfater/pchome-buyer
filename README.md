# PChome 24h 搶購工具

使用 Playwright 瀏覽器自動化，監控 PChome 24h 商品開賣狀態，自動加入購物車並結帳。主要介面是網頁控制台（React + FastAPI），支援部署在遠端伺服器。

## 安裝

```bash
# 本機開發需要一個可連線的 PostgreSQL
docker run -d -p 127.0.0.1:5432:5432 -e POSTGRES_USER=pchome -e POSTGRES_PASSWORD=pchome -e POSTGRES_DB=pchome_buyer -v pchome-pg-data:/var/lib/postgresql/data postgres:16-alpine

# 後端依賴（backend/ 是獨立的 src-layout 專案）
cd backend
uv sync

# 安裝 Playwright 瀏覽器（首次）
uv run playwright install chromium
cd ..

# 前端建置（首次與前端有更新時）
npm --prefix frontend install
npm --prefix frontend run build
```

## 設定

建立 `.env` 檔案（參考 `.env.example`），只需要 PostgreSQL 連線字串（SQLAlchemy URL）：

```env
DATABASE_URL=postgresql+psycopg://pchome:pchome@localhost:5432/pchome_buyer
```

資料表在啟動時自動建立。docker-compose 部署可用 `POSTGRES_PASSWORD` 環境變數覆寫資料庫密碼（預設 `pchome`，資料庫不對外 publish port）。

信用卡安全碼（CVC）、是否自動確認付款（AUTO_PAY）、搶購輪詢時機等參數改在控制台右上角 ⚙「設定」視窗調整，存在 PostgreSQL，不再透過 `.env` 設定。

## 使用方式（網頁控制台）

```bash
cd backend
uv run pchome                    # http://127.0.0.1:8787
uv run pchome --port 9000
uv run pchome --host 0.0.0.0     # 遠端部署（見下方安全性說明）
```

1. **登入**：按右上角 ⚙「設定」開啟設定視窗，在「登入」區塊貼上登入憑證：
   - 用瀏覽器擴充功能（Cookie-Editor、EditThisCookie 等）在已登入的 PChome 分頁匯出 cookie JSON 貼上。
   - 匯入後可按「檢查 session」實測有效性。
   - 同一個視窗還有「付款」（CVC/AUTO_PAY）、「搶購時機」（輪詢間隔/lead time/加速視窗等）、「進階」（重試次數/延遲）三個 section。
2. **新增任務**：按「＋ 新增任務」，貼上商品頁網址（如 `https://24h.pchome.com.tw/prod/DGCQ39-A900JESMM`）或商品編號，選填開始監測時間（留空 = 立即監控）。
3. **啟動**：每張卡片各自有「開始」；勾選多張卡片可批次「啟動選取／取消選取」。開賣時間相同的任務啟動後併為同一組（卡片同色標示）——一起監控、一起加入購物車、一次結帳。
4. **付款**：結帳頁就緒後瀏覽器保持開啟（headless），同時寫入結帳紀錄；`AUTO_PAY=true` 會自動點擊「確認付款」，否則需在卡片按「結束」前手動處理（遠端無視窗，建議開 AUTO_PAY）。
5. **結帳紀錄**：每組結帳留下一張紀錄卡，「查看詳情」可看每件商品的加車結果、購物車金額、結帳頁資訊與日誌；「標記完成」後可用「清除已完成」整理。

### 前端開發

```bash
cd backend && uv run pchome            # 終端 1：後端 API
npm --prefix frontend run dev          # 終端 2：Vite dev server（自動代理 /api）
```

### 安全性

控制台**本身沒有認證機制**。預設只綁 `127.0.0.1`；以 `--host 0.0.0.0` 部署到遠端時，請務必用反向代理（nginx basic auth、Cloudflare Access、VPN 等）保護存取——信用卡安全碼與登入 session 皆存在 PostgreSQL（由設定視窗管理），這些才是實際需要被保護的憑證。
