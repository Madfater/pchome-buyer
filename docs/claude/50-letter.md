# 給未來 session 的信

> 2026-07-04 由 Fable 5 建立制度時寫下，2026-07-06 檢查更新。讀者是之後接手的每一個模型。

## 三件使用者沒問、但你該知道的事

### 1. push 到 master ＝ 部署到遠端，不是備份動作

`.github/workflows/ci-cd.yml`：push master → CI 跑全套檢查（backend：pytest＋pyright＋`ruff format --check`；frontend：lint＋`prettier --check`＋build＋test）→ 全綠後打 Dockhand webhook 自動重新部署遠端實例。這有兩個後果：（a）遠端實例可能帶著真登入 session 與 `AUTO_PAY=true` 在跑，push 是對外動作，凡 push 前先確認使用者要的是部署；（b）CI 的 format 檢查是 `--check` 模式——本地沒跑 `ruff format` / `npm run format` 就 push，CI 會紅。部署細節見 [architecture.md](architecture.md) §部署。

### 2. 這個工具花真錢，而且錢與憑證的入口比你以為的多

入口清單：MongoDB `settings` collection 裡的真 CVC＋`AUTO_PAY`（面板設定視窗管理）、本機舊 `.env` 可能殘留的 legacy CVC、`auth_state.json`（repo 根目錄，活的登入 session）、`GET /api/settings`（回傳 `cvc` 欄位——手動 curl 驗證先 redact 再看，別直接印原始 JSON）。測試或腳本要建 `SettingsRepository` 一律走 `tests/support/isolated_container.py`，否則它的 `.env` migration 會讀到真實 CVC。實跑驗證的安全邊界：**可以**啟動服務、加商品、看狀態機、用不存在的商品 ID 觀察失敗路徑；**絕不可以**讓真實可買商品的 job 跑進 carting/checkout phase。`auth_state.json` 不要 Read 進對話、不要出現在 diff、log、或任何外傳內容裡。

### 3. 失敗時先懷疑「PChome 契約漂移」，再懷疑 regression

這個專案的對手是一個沒有 API 文件、隨時可能改版的電商網站。JSONP endpoint、button API 的欄位、payinfo 頁的 DOM selector（本來就標註未驗證）都可能無預警改變。所以當「昨天還能跑的東西今天壞了」而 git log 沒有相關改動時，第一假設應該是外部契約變了，不是找程式碼的 regression。驗證方式：用 playwright-cli skill 實地打開對應頁面/endpoint 看現在長什麼樣，把新契約寫回 [architecture.md](architecture.md) 與教訓紀錄。反過來說，改壞的如果是自己這邊，錯誤通常在 git diff 裡——先 diff 再猜。

## 這套制度最可能的退化方式與預防

1. **規則被逐 session 侵蝕**——每個 session 都覺得「這次情況特殊，跳過派工/驗收沒關係」，三個月後制度名存實亡。預防：例外必須留痕（教訓紀錄），改規則必須問使用者（[40-maintenance.md](40-maintenance.md)）。如果你正想跳過某條規則，那一刻就是該寫教訓紀錄的時刻。
2. **architecture.md 過時後反而變成誤導源**——比沒有文件更糟。預防：檔頭校準日期＋「引用前 grep 驗證」＋發現不符順手修。如果連續兩次發現它跟程式碼不符，別零星修補，派一個 agent 整段重校。
3. **文件膨脹到沒人讀**——教訓越積越多，弱模型載入成本上升就開始跳過不讀，等於回到沒有制度。預防：40-maintenance.md 的精簡門檻（15 條/250 行/CLAUDE.md 6KB）是硬觸發，到了就執行。
4. **過度儀式化**——三行能解決的事也走全套派工＋驗收，使用者嫌煩之後整套被棄用。預防：10-model-dispatch.md 的反儀式化條款與 R3 反例是制度的一部分，不是可選項。制度的目的是省 token 和防錯，當它開始浪費 token，就是在違反自己。

## 環境備忘

- `~/.claude/settings.json` 的 `model` 欄位由使用者自己管理，隨時會換。不要假設自己是哪個模型——照制度做事，制度不依賴主模型等級。
- 派工時 `model` 參數可用：`haiku` / `sonnet` / `opus`（清單裡沒有 `fable` 就當它不存在）。effort 只能設在 agent 定義檔 frontmatter。
- auto-memory（`~/.claude/projects/-home-madfater-pchome-buyer/memory/`）已有 [fedora-wsl-environment.md]：Fedora WSL2、`playwright install-deps` 會失敗要用 `dnf`、uv 在 `~/.local/bin`。使用者偏好類的新發現寫去那裡，專案制度類的寫回 docs/claude/。
- `.claude/` 整個被 gitignore：`verifier`、`deep-reviewer` 兩個 agent 定義的正本在 `docs/claude/agents/`，換機器後 `cp docs/claude/agents/*.md .claude/agents/` 重建。

## 未完成交接
