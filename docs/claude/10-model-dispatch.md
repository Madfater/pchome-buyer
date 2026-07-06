# 模型調度守則

> 使用者制定於 2026-07-04。**授權聲明：本檔即為使用者的常設授權——符合下列門檻的派工「視同使用者要求」，不需再徵詢，也不受「未經要求不派 agent」的預設限制。** 反之，未達門檻就不要派（見 §反儀式化）。

## 原則：指揮官不下場

主對話的 context 是最貴的資源，只放**決策所需的結論**。大量讀取、掃 repo、查網頁、批次改檔一律派 subagent，主對話只收結論。

**必須派工的門檻**（任一成立就派）：
- 預估要讀 **>5 個檔案** 或 **>800 行**才能回答的問題。
- 輸出量不可控的操作：build/測試的完整 log、WebFetch 網頁、爬蟲/playwright 抓頁。
- 對 **>3 個檔案**套用同一種已知模式的批次修改。
- 開放式研究（「查一下 X 怎麼做」「比較 A/B 方案」）。
- 驗收（預設派；唯一豁免見下方「輕量豁免」）。

**反儀式化**（任一成立就不派、直接做）：
- 主對話兩三個工具呼叫內能完成、且每個結果可控（單檔小修、跑一個指令看 exit code、Grep 一個符號）。
- 已經知道確切檔案與確切改法。
- 派工說明寫起來比直接做還長。

**輕量豁免**（驗收唯一的例外，兩條同時成立才適用）：改動無執行面（純文件/註解/log 字串），且主對話三個工具呼叫內可自證（例如 grep 確認改到位）。此時可自驗，但回報必須註明「輕量豁免，自驗」。任何碰到程式行為的改動不適用。

## 環境事實（2026-07-04 驗證、2026-07-06 複驗，來源：code.claude.com/docs/en/sub-agents.md）

- `Agent` 工具內建 subagent_type：`general-purpose`（全工具）、`Explore`（唯讀搜尋）、`Plan`（規劃）、`claude`（同 general-purpose 的 catch-all）、`claude-code-guide`（查 Claude Code/API 文件）。另有本專案自訂的 `verifier`、`deep-reviewer`（見 §附錄），可直接派。
- `Agent` 呼叫可帶 `model` 參數逐次覆寫：`haiku` / `sonnet` / `opus`（`fable` 只在特殊 session 存在，列表沒有就當不存在）。
- **effort 不能逐次指定**，只能寫在 agent 定義檔 frontmatter（`effort: low|medium|high|xhigh|max`）。所以需要高 effort 的工作請用 `verifier` / `deep-reviewer` 這類定義檔 agent，而不是對 general-purpose 幻想 effort 參數。
- agent 定義檔在 `.claude/agents/*.md`（被 gitignore，換機器要重建：`cp docs/claude/agents/*.md .claude/agents/`）。
- 用 `SendMessage` 可以延續已跑過的 agent（保留它的 context）；重新 `Agent` 則是冷啟動。追問用前者。

## 模型選擇表（顯式指定，不要省略 model 參數）

| 任務性質 | model | 例子 |
|---|---|---|
| 機械性、模式已知、低歧義 | `haiku` | 把已驗證的修法批次套到多個檔案；格式轉換；大量 grep 結果彙整 |
| 預設：搜尋、實作、重構、研究、驗收 | `sonnet` | 找某行為的實作位置；照規格實作一個 endpoint；跑 verifier |
| 高風險判斷、審查、除錯纏鬥、第二意見 | `opus` | 併發/時序 bug 分析；架構取捨；對 sonnet 兩次失敗的子任務接手 |

## 派工三件套（每個 prompt 必含，模板見 30-delegation-templates.md）

1. **目標與動機**：要什麼、為什麼要（讓 agent 遇到岔路能自行取捨）。
2. **驗收條件**：可機器判定或可逐條核對的完成標準。
3. **回報格式**：明確規定回什麼、不回什麼。

## 回報合約（寫進每個派工 prompt）

- 只回**結論**與 `檔案:行號`，不要貼大段程式碼或原文。
- 長產物（報告、diff、抓下來的資料）寫到檔案，回傳路徑。
- 回報上限約 300 字；超過表示沒消化完，先消化再回。
- 失敗要回：試了什麼、卡在哪、原始錯誤訊息（這條例外，錯誤訊息要完整）。

## 升降級路徑

- `haiku` 錯一次 → 直接升 `sonnet` 重派，不重試。
- `sonnet` 在**同一個子任務**連錯兩次 → 帶完整失敗軌跡（兩次的做法＋錯誤輸出）升 `opus`。不帶軌跡的升級等於重新猜。
- `opus` 也解不了 → 停，整理現況問使用者（見 20-judgment-rubrics.md R3）。
- 解出來的模式（確定的修法、確定的規則）→ 降回 `haiku` 批次套用，prompt 裡附一個已完成的範例當樣板。
- **同一件事最多重試兩輪**。第三輪前必須換方法或換模型，判準見 20-judgment-rubrics.md R4。

## 驗證不自驗

寫的人不能當驗的人——自驗會繼承同一套盲點。

- **檔案落地**：派 fresh-context `verifier` read-back：檔案存在、內容涵蓋驗收條件各項、內鏈路徑有效。
- **程式碼**：優先跑檢查與測試（pyright / lint / build / 有測試就跑測試）；行為改動要 `verifier` 實跑受影響流程（本專案注意 CLAUDE.md 不變量 7：不可跑到真實結帳）。
- **高風險判斷**（架構決策、難 bug 的根因結論）：派 `deep-reviewer` 第二意見；或同題派兩個 agent 各自解、比對答案後擇優。兩者結論衝突時不要自己當裁判硬選——把分歧點列出來問使用者或再派第三個 agent 針對分歧點驗證。
- 驗收 agent 的 prompt 只給驗收條件，**不給實作過程的敘事**（避免被帶風向）。
- **驗收鏈有終點**：`verifier` / `deep-reviewer` 的回報直接採用，不再對驗收報告派驗收。對其結論有疑慮 → 派第二意見比對，不是再疊一層。

## 附錄：自訂 agent 定義

正本在 `docs/claude/agents/`（進版控），安裝到 `.claude/agents/` 才生效。修改時**先改正本再複製過去**，不要直接改 `.claude/agents/`。

```bash
cp docs/claude/agents/*.md .claude/agents/
```

## 教訓紀錄

- 2026-07-04 | 症狀: 剛 cp 進 `.claude/agents/` 的 agent 立刻派工報「Agent type not found」 | 根因: agent 清單在 session 啟動時載入，session 中新增不生效（下個 session 起即正常，已多次驗證） | 規則: 當前 session 要用剛裝的 agent 時，改派 `general-purpose` 並在 prompt 開頭貼上該定義檔的規則內文、`model` 參數照定義檔設（effort 無法補，接受差異）。
