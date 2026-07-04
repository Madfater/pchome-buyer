# Harness 診斷（制度依據）

> 2026-07-04 由 Fable 5 盤點本環境後寫成。這份是後面所有制度檔的依據：每條規則都在修這裡的某個問題。
> 環境事實：Claude Code on WSL2 (Fedora)、無 MCP server、無自訂 agent（本次補上）、`.claude/` 被 gitignore、專案無測試套件、唯一自動 gate 是 `pyright` + `oxlint` + `tsc`（藏在 frontend build 裡）。

## 第 1 名：大輸出直接灌進主對話（最漏 token）

**症狀**：主對話自己 Read 整個大檔（`uv.lock` 60KB、`auth_state.json` 27KB）、`cat` build log、WebFetch 整頁、用 playwright 抓整頁 DOM。一次工具結果就吃掉幾千 token，session 後半開始遺忘早期指示、觸發 context 摘要後品質再降一級。

**自我檢測**：呼叫工具前問「這個結果我需要全文，還是只需要結論？」只需要結論 → 就不該讓全文進 context。

**修法**（已制度化於 [10-model-dispatch.md](10-model-dispatch.md)）：
- 預估要讀 >5 個檔案或 >800 行、或輸出量不可控（build log、網頁、爬蟲）→ 派 subagent，只收結論與 `檔案:行號`。
- 主對話 Read 大檔一律帶 `offset`/`limit`；Bash 長輸出導到 scratchpad 檔案再 grep/tail。
- 絕不 Read：`uv.lock`、`auth_state.json`、`frontend/dist/`、`node_modules/`、`.venv/`。

## 第 2 名：CLAUDE.md 把「不變量」和「描述」混寫（最易被過時內容誤導）

**症狀**：舊版 CLAUDE.md 12KB，每個 session 全文載入。其中致命不變量（違反會 silent fail，如 RS store code）和描述性細節（函式簽名、欄位名）混在一起。描述性內容程式碼一改就過時，弱模型會把它當事實直接引用而不去驗證；而且 12KB 稀釋了真正不能違反的那幾條。

**自我檢測**：引用 CLAUDE.md/architecture.md 的具體函式簽名或欄位前，先 Grep 確認它還存在。

**修法**（已實施於本次重寫）：
- CLAUDE.md 只留三種內容：指令、致命不變量、文件路由。
- 描述性架構移到 [architecture.md](architecture.md)，檔頭標「導航用，與程式碼衝突時以程式碼為準」＋最後校準日期。
- 過時就順手修（規則見 [40-maintenance.md](40-maintenance.md)）。

## 第 3 名：無測試套件 →「完成」沒有機器判準（最易出錯）

**症狀**：本專案零測試。pyright/oxlint/tsc 只擋型別錯，行為正確性（JSONP 呼叫方式、cart clobber、MAC 15 秒時效、時序邏輯）完全沒有自動驗證。弱模型的典型失敗模式：改完、型別過了、就宣稱成功——但行為根本沒被執行過。

**加重因素**：這個工具會花真錢（`AUTO_PAY=true` 會真的付款），所以「跑跑看驗證」也不能隨便跑完整流程。

**自我檢測**：回報「完成」前問「這段改動的行為，被什麼東西實際執行過？」答案是「沒有」→ 還沒完成。

**修法**：
- 完成定義與必跑清單制度化於 [20-judgment-rubrics.md](20-judgment-rubrics.md) R2。
- 驗收一律派 fresh-context verifier agent，不自驗（[10-model-dispatch.md](10-model-dispatch.md) §驗證）。
- 根本解是補純邏輯測試（`timing`、`product_id`、`membership`、`auth_service` 的 cookie 轉換）——建議寫在 [50-letter.md](50-letter.md)。

## 教訓紀錄

（踩坑後依 [40-maintenance.md](40-maintenance.md) 格式追加於此）
