# 維護協議（改 CLAUDE.md 或 docs/claude/ 之前先讀這份）

## 權限分級

**可以自行改（改完在回報中提一句即可）**：
- [architecture.md](architecture.md)：發現與程式碼不符 → 順手更正該段，並更新檔頭「最後校準」日期。
- 各檔末尾的「教訓紀錄」段：只准追加（格式見下）。
- [30-delegation-templates.md](30-delegation-templates.md)：模板措辭微調、補新任務型態的模板。
- `docs/claude/agents/*.md` 的 prompt 內文（frontmatter 除外）；改完必須 `cp docs/claude/agents/*.md .claude/agents/` 同步。

**動之前必須先問使用者**：
- CLAUDE.md 的「致命不變量」：增删改任何一條。
- [10-model-dispatch.md](10-model-dispatch.md) 的派工門檻、模型選擇表、升降級路徑。
- [20-judgment-rubrics.md](20-judgment-rubrics.md) 的任何 rubric 本文。
- agent 定義檔的 frontmatter（model / effort / disallowedTools）。
- **刪除**任何檔案或任何規則（教訓紀錄的精簡除外，見下）。
- 覺得某條規則在當前情境不適用 → 那是例外不是修訂：照 R3 問使用者，或執行後把例外記進教訓紀錄，**不要直接改規則**。

## 硬規則：改前備份

改任何既有制度檔前：`cp <檔案> /home/madfater/.claude/backups/<檔名>.$(date +%F).bak`。git 裡有也一樣做——備份成本近零，弄壞制度檔的成本很高。

## 教訓寫回

踩坑（規則沒擋住的錯、規則本身誤導、發現新的環境事實）→ 當個 session 就寫，不要「之後再記」：
- 位置：與該坑最相關的檔案末尾「## 教訓紀錄」段；跨檔的寫進 [00-diagnosis.md](00-diagnosis.md)。
- 格式（一行一條）：`- YYYY-MM-DD | 症狀: <一句> | 根因: <一句> | 規則: <以後怎麼做，一句>`
- 只記「會再發生的」。一次性的手滑不記。
- 同一個教訓不要同時寫進正文和教訓紀錄（2026-07-06 整理時發現三條重複）：正文放「規則一句話＋指向紀錄」，紀錄放完整的症狀/根因/規則。
- 會隨程式碼漂移的具體數字（測試數、行數）只寫在 architecture.md 檔頭校準行一處，其他地方用相對描述或引用。
- 與本專案程式碼無關、屬於使用者偏好或環境的事實 → 寫進 auto-memory（`~/.claude/projects/-home-madfater-pchome-buyer/memory/`），不要塞這裡。

## 精簡協議（防膨脹）

- 任一檔案的教訓紀錄超過 **15 條**、或檔案超過 **250 行** → 觸發精簡：把重複教訓合併、把已驗證多次的教訓「升格」為正文規則（升格進受保護區段要先問使用者）、刪掉敘事只留規則。
- CLAUDE.md 超過 **6KB** → 檢查是否有描述性內容混進來了，移回 architecture.md。
- 精簡也是「改既有檔」：先備份。

## 同步義務

- 改了 `docs/claude/agents/` → 立刻 `cp` 到 `.claude/agents/`（`.claude/` 被 gitignore，正本永遠在 docs/claude/agents/）。
- 改了 docs/claude/ 任何檔 → 提醒使用者 commit（遵守「使用者要求才 commit」的預設；只提醒，不擅自 commit）。
- 檔案間互相引用的路徑改了 → grep `docs/claude` 與該檔名，把所有引用一起改。
