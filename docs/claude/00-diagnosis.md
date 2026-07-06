# Harness 診斷（制度依據）

> 2026-07-04 由 Fable 5 盤點本環境後寫成，2026-07-06 檢查更新（原第 3 名「無測試套件」已解決並移除，換上實際踩過坑的新第 3 名）。這份是後面所有制度檔的依據：每條規則都在修這裡的某個問題。
> 環境事實（2026-07-06）：Claude Code on WSL2 (Fedora)、自訂 agent `verifier`/`deep-reviewer` 可用、`.claude/` 被 gitignore、測試套件齊備（pytest＋Vitest＋e2e，現況見 [architecture.md](architecture.md)）、gate 清單唯一正本是 CLAUDE.md「指令」區塊、push master 會自動部署遠端（見 architecture.md §部署）。

## 第 1 名：大輸出直接灌進主對話（最漏 token）

**症狀**：主對話自己 Read 整個大檔（`uv.lock` 60KB、`auth_state.json` 27KB）、`cat` build log、WebFetch 整頁、用 playwright 抓整頁 DOM。一次工具結果就吃掉幾千 token，session 後半開始遺忘早期指示、觸發 context 摘要後品質再降一級。

**自我檢測**：呼叫工具前問「這個結果我需要全文，還是只需要結論？」只需要結論 → 就不該讓全文進 context。

**修法**（已制度化於 [10-model-dispatch.md](10-model-dispatch.md)）：
- 預估要讀 >5 個檔案或 >800 行、或輸出量不可控（build log、網頁、爬蟲）→ 派 subagent，只收結論與 `檔案:行號`。
- 主對話 Read 大檔一律帶 `offset`/`limit`；Bash 長輸出導到 scratchpad 檔案再 grep/tail。
- 絕不 Read：`uv.lock`、`auth_state.json`、`frontend/dist/`、`node_modules/`、`.venv/`。

## 第 2 名：不變量與描述混寫、描述過時後被當事實引用（最易被誤導）

**症狀**：致命不變量（違反會 silent fail，如 RS store code）和描述性細節（函式簽名、欄位名）混在一起時，描述性內容程式碼一改就過時，弱模型會把它當事實直接引用而不去驗證；而且長文稀釋了真正不能違反的那幾條。

**自我檢測**：引用 CLAUDE.md/architecture.md 的具體函式簽名或欄位前，先 Grep 確認它還存在。

**修法**（已實施）：
- CLAUDE.md 只留三種內容：指令、致命不變量、文件路由。
- 描述性架構在 [architecture.md](architecture.md)，檔頭標「導航用，與程式碼衝突時以程式碼為準」＋最後校準日期。
- 過時就順手修（規則見 [40-maintenance.md](40-maintenance.md)）。

## 第 3 名：憑證與真錢從意想不到的出口洩進對話（後果最重）

**症狀**：這個 repo 的敏感面不只「別跑到結帳」。真 CVC 存在 MongoDB `settings` collection（舊 `.env` 可能殘留一份）、`auth_state.json` 是活的登入 session，而它們會從看似無害的操作洩出：`GET /api/settings` 回傳 `cvc` 欄位（手動 curl 驗證直接印 JSON 就洩了）、`SettingsStore` 建構時會讀真實 `.env` 做 migration（測試 fixture 沒隔離就把真 CVC 拉進測試輸出）。2026-07-06 已實際發生兩次（見下方教訓紀錄引用的 architecture.md 條目）。

**自我檢測**：任何會輸出設定值、環境變數、cookie、API 回應的指令，執行前問「輸出裡可能有 CVC 或登入憑證嗎？」可能 → 先過濾再看。

**修法**：
- CLAUDE.md 不變量 7：CVC/auth_state 不讀進對話、不印出、不外傳；回傳 CVC 的 API 輸出一律先 redact（例：`curl ... | jq 'del(.cvc)'` 或 `.cvc="***"`）。
- 測試/腳本要建 `SettingsStore` 一律走 `tests/support/isolated_container.py`（已內建 `LEGACY_ENV_FILE` 隔離）。
- 事發詳情記在 [architecture.md](architecture.md) 教訓紀錄 2026-07-06 條。

## 教訓紀錄

- 2026-07-06 | 症狀: 把 gate 清單去重複化、宣告 CLAUDE.md「檢查」段為唯一正本後，deep-reviewer 發現該正本自己的 pytest 觸發註解過時（只列 4 個模組，實際 tests/ 已覆蓋 23 檔）——照正本做反而會漏跑測試 | 根因: 指向正本前沒先驗證正本是最新的；觸發條件寫成「模組白名單」會隨測試擴充而漂移 | 規則: 宣告任何檔案為唯一正本前，先把正本本身校準一次；觸發條件盡量寫成不會漂移的形式（例：「改了 pchome/ 任何 Python 就跑」而非列舉模組）。
