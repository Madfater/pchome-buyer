# 派工 Prompt 模板

> 用法：挑對應型態，複製整段填空（`<>` 是填空處），作為 Agent 工具的 `prompt`。`subagent_type` 與 `model` 依標註；規則出處見 [10-model-dispatch.md](10-model-dispatch.md)。
> 若派 `verifier` / `deep-reviewer` 回報「Agent type not found」（agent 定義是本 session 才安裝的）：改派 `general-purpose`、`model` 照定義檔設、prompt 開頭貼上 `docs/claude/agents/` 對應檔的規則內文（詳見 10-model-dispatch.md 教訓紀錄）。
> 通則：驗收條件寫「可判定的事實」，不寫「做好做滿」這種形容詞。回報合約每份模板已內建，別刪。

## 1. 搜尋 / 定位（subagent_type: `Explore`，model 省略即可）

```
在這個 repo 找出：<要找什麼，例如「job 狀態機的所有狀態轉移發生的位置」>。
動機：<為什麼找，例如「我要加一個 paused 狀態，需要知道所有要改的點」>。
搜尋廣度：<medium / very thorough>。
已知線索：<檔名、關鍵字、或「無」>。
回報格式：條列每個相關位置為「檔案:行號 — 一句話說明它做什麼」；最後一段講整體結構的結論。
不要貼程式碼原文，不要超過 300 字。若找不到，回報你搜過哪些關鍵字與目錄。
```

## 2. 實作（subagent_type: `general-purpose`，model: `sonnet`）

```
任務：實作 <功能一句話>。
動機：<為什麼要這個，遇到岔路時往這個目的取捨>。
範圍：改 <檔案/模組>；除此之外的檔案不要動。
必守約束：先讀 CLAUDE.md 的「致命不變量」；另外 <本任務特別要注意的點，或「無」>。
做法提示：<已知的方向；沒有就寫「自行判斷，但動手前先讀 docs/claude/architecture.md 對應段落」>。
驗收條件（完成的定義）：
1. <可判定條件，例：POST /api/jobs/pause 對 monitoring 中的 job 回 200 且 state 變 paused>
2. <...>
3. CLAUDE.md「指令」區塊「檢查」段中對應本次改動的每一項 gate 都跑過且乾淨（照該段註解判斷哪些必跑，逐項列出結果）。
回報格式：改了哪些檔案（檔案:行號區間）、每項驗收條件的實測結果與證據、遺留問題。
不要貼大段程式碼。任何驗收條件沒過就如實回報失敗輸出，不要宣稱完成。
```

## 3. 重構（subagent_type: `general-purpose`，model: `sonnet`）

```
任務：重構 <對象>，目標是 <例如「把 X 從 Y 模組抽出，讓 Z 不再依賴 FastAPI」>。
動機：<為什麼>。
行為不變是硬約束：對外行為、API 契約、持久化格式都不得改變。
必守：CLAUDE.md 致命不變量；不順手做無關清理；不改公開介面除非任務明說。
驗收條件：
1. <結構性事實，例：pchome/core/ 內不再 import fastapi（用 grep 驗證）>
2. CLAUDE.md「指令」區塊「檢查」段中對應本次改動的每一項 gate 都跑過且乾淨（逐項列出結果）。
3. <行為不變的驗法，例：實跑 cd backend && uv run pchome 並 curl /api/state 回傳結構與重構前一致>
回報格式：移動/改名清單（舊路徑 → 新路徑）、驗收逐條結果與證據、你注意到但沒動的技術債（至多三條）。
```

## 4. 研究 / 網路查證（subagent_type: `general-purpose`，model: `sonnet`；查 Claude Code/API 本身用 `claude-code-guide`）

```
問題：<要回答什麼>。
動機：<答案會被用來做什麼決定>。
要求：用官方文件/一手來源，每個結論附來源 URL；區分「文件明說」與「你的推論」。
查不到就回「查不到」並列出查過的來源——不要編。
長篇整理寫到 <scratchpad 或指定路徑>，回報只給：每個問題一段結論＋來源＋信心（高/中/低）。
```

## 5. 審查 / 第二意見（subagent_type: `deep-reviewer`，model 已內建 opus）

```
請對抗審查以下結論／方案：
結論：<被審對象，一兩句>。
背景：<最小必要背景；不要複述你的推理過程，讓審查者自己建立事實>。
相關位置：<檔案:行號 清單>。
特別要戳的面向：<例如「併發下 membership freeze 與 cancel 的競態」，或「無，全面審」>。
回報依你的內建格式（結論/信心/依據/排除的替代解釋/會改變判斷的證據）。
```

### 驗收派工（subagent_type: `verifier`，任何交付完成後必派）

```
請驗收以下交付，逐條判定：
交付說明：<一句話，只說「什麼」不說「怎麼做出來的」>。
驗收條件：
1. <與派工時完全相同的條件——原樣複製，不要改寫>
2. <...>
限制：<例如「不可觸發真實結帳」；無則寫「遵守 CLAUDE.md 不變量」>。
回報依你的內建格式（總判定 + 逐條 PASS/FAIL + 證據）。
```

## 教訓紀錄

（踩坑後依 [40-maintenance.md](40-maintenance.md) 格式追加於此）
