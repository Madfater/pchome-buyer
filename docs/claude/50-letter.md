# 給未來 session 的信

> 2026-07-04，Fable 5 在建立這套制度的 session 末尾寫下。讀者是之後接手的每一個模型。

## 三件使用者沒問、但你該知道的事

### 1.（已完成，2026-07-04）這個專案最大的槓桿曾是「補一套純邏輯測試」，而且很便宜

已於 2026-07-04 另一 session 完成：`uv add --dev pytest`，`tests/` 覆蓋 `core/timing.py`（`parse_sale_time` 各種格式與錯誤輸入）、`services/product_id.py`（URL/裸 ID 解析）、`core/membership.py`（join/leave/freeze 語意）、`services/auth_service.py`（cookie 格式轉換 + `AUTH_STATE_FILE` 用 monkeypatch 隔離、絕不寫真實檔案）。45 個測試，`uv run pytest` 綠燈，`pyright` 也過。以後改這四個模組先跑 `uv run pytest`，比派 agent 實跑便宜很多——R2 的驗證成本因此下降。細節見 [architecture.md](architecture.md) 的 `tests/` 段。

### 2. 這個工具花真錢，而且錢的入口比你以為的多

`AUTO_PAY=true` ＋ 真 CVC 在 `.env` ＋ 真登入 session 在 `auth_state.json`。這代表：跑 `main.py web` 起服務本身安全，但只要有 job 走到 checkout 就可能真的付款。實跑驗證的安全邊界是：**可以**啟動服務、加商品、看狀態機、甚至用不存在的商品 ID 觀察失敗路徑；**絕不可以**讓真實可買商品的 job 跑進 carting/checkout phase。測試用的商品 ID 不存在時 API 會走失敗分支，這是安全的驗證路徑。另外 `auth_state.json`（repo 根目錄，27KB）是活的登入憑證：不要 Read 進對話、不要出現在 diff、log、或任何外傳內容裡。

### 3. 失敗時先懷疑「PChome 契約漂移」，再懷疑 regression

這個專案的對手是一個沒有 API 文件、隨時可能改版的電商網站。JSONP endpoint、button API 的欄位、payinfo 頁的 DOM selector（本來就標註未驗證）都可能無預警改變。所以當「昨天還能跑的東西今天壞了」而 git log 沒有相關改動時，第一假設應該是外部契約變了，不是找程式碼的 regression。驗證方式：用 playwright-cli skill 實地打開對應頁面/endpoint 看現在長什麼樣，把新契約寫回 [architecture.md](architecture.md) 與教訓紀錄。反過來說，改壞的如果是自己這邊，錯誤通常在 git diff 裡——先 diff 再猜。

## 這套制度最可能的退化方式與預防

1. **規則被逐 session 侵蝕**——每個 session 都覺得「這次情況特殊，跳過派工/驗收沒關係」，三個月後制度名存實亡。預防：例外必須留痕（教訓紀錄），改規則必須問使用者（[40-maintenance.md](40-maintenance.md)）。如果你正想跳過某條規則，那一刻就是該寫教訓紀錄的時刻。
2. **architecture.md 過時後反而變成誤導源**——比沒有文件更糟。預防：檔頭校準日期＋「引用前 grep 驗證」＋發現不符順手修。如果連續兩次發現它跟程式碼不符，別零星修補，派一個 agent 整段重校。
3. **文件膨脹到沒人讀**——教訓越積越多，弱模型載入成本上升就開始跳過不讀，等於回到沒有制度。預防：40-maintenance.md 的精簡門檻（15 條/250 行/CLAUDE.md 6KB）是硬觸發，到了就執行。
4. **過度儀式化**——三行能解決的事也走全套派工＋驗收，使用者嫌煩之後整套被棄用。預防：10-model-dispatch.md 的反儀式化條款與 R3 反例是制度的一部分，不是可選項。制度的目的是省 token 和防錯，當它開始浪費 token，就是在違反自己。

## 環境備忘

- `~/.claude/settings.json` 目前是 `"model": "claude-fable-5[1m]"`——那是建立制度的特殊 session 用的。之後的日常 model 由使用者自己設；不要因為看到這行就以為自己是 Fable。
- 派工時 `model` 參數可用：`haiku` / `sonnet` / `opus`（清單裡沒有 `fable` 就當它不存在）。effort 只能設在 agent 定義檔 frontmatter。
- auto-memory（`~/.claude/projects/-home-madfater-pchome-buyer/memory/`）已有 [fedora-wsl-environment.md]：Fedora WSL2、`playwright install-deps` 會失敗要用 `dnf`、uv 在 `~/.local/bin`。使用者偏好類的新發現寫去那裡，專案制度類的寫回 docs/claude/。
- `.claude/` 整個被 gitignore：`verifier`、`deep-reviewer` 兩個 agent 定義的正本在 `docs/claude/agents/`，換機器後 `cp docs/claude/agents/*.md .claude/agents/` 重建。

## 未完成交接

- 2026-07-06 | **CLI 移除計畫**：使用者提到之後要把 `main.py`/`cli.py` 的 `login`/`buy` 指令整個拿掉，只留 web 服務當唯一入口——目標是 `uv run main.py`（不帶任何子指令）就直接啟動 web 服務，取代現在還要多打一個 `web` 子指令。這次的設定視窗改動（CVC/AUTO_PAY/輪詢調校移入 MongoDB `settings` collection）刻意跳過 `cli.py` 的搶購流程改動：`cmd_buy` 沒接 `SettingsStore`，`checkout.py` 的 `cvc`/`auto_pay` 對 CLI `buy` 會永遠拿到 `JobConfig` 的出廠預設值（`cvc=""`/`auto_pay=False`）。之後真的執行 CLI 移除工程時要一併處理：`cli.py`、`test_cli_helpers.py`、README/docs 提到 CLI 的地方，並把 `main()` 改成無子指令時直接呼叫現在 `cmd_web` 那段邏輯。
- 2026-07-06 | **Mongo 化其他 store**：這次只把 settings 搬進 MongoDB（`pchome/services/settings_store.py` + `mongo.py`）；`ProductStore`/`CheckoutRecordStore`/`AuthService` 目前仍是 `products.json`/`checkouts.json`/`auth_state.json` 檔案。使用者提到之後有計畫也遷過去——`pchome/services/mongo.py` 的 `get_db()` 共用 client 存取點就是為了讓那次遷移直接重用，不用重新設計連線層。

（2026-07-04 制度建立 session：A–G 與收尾全部完成，經 opus 對抗審查修正 5 處。若你因中斷接手，先跑收尾三步：對抗審查、read-back、給使用者總結。）
