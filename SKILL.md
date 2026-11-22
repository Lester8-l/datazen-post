---
name: datazen-post
description: 把一篇文章、新聞、報告、政策、MPF 制度或一個念頭，做成 Data Zen 品牌的 1080×1350 圖卡（IG 輪播 或 客戶懶人包），一套視覺語言兩個出口。內建 8 款版型（封面／宣言／數字／明細／清單／對照／收尾／懶人包）、三層翻譯法、8 類懶人包題材、圖片生成與角色場景指引、五支檢查（版面溢出、孤字、對比度、來源、合規）同出 PNG／PDF。當用戶說「出 IG 貼文」「做個 carousel」「變成 IG 圖」「做插畫輪播」「出懶人包」「發俾客人」「講下 MPF」「把呢篇文章變成圖」時使用。**流程第一步一律先確認模式（IG／懶人包）。**
agent_created: true
---

# Data Zen 圖卡 · 一套視覺，兩個出口

> 北極星：**以極客邏輯抽乾水份，以沉靜內在安頓人心。**
> 視覺定位：**數據霧**——霧是氣氛，刻度是態度。遠看安靜，近看一直被量度。

兩個模式共用同一套 tokens、霧層、字體、檢查腳本，只差內容規則與是否需要來源：

| 模式 | 張數 | 受眾 | 目的 | 額外要求 |
|---|---|---|---|---|
| **A · `ig`** | 6–9 | 陌生人 | 停手、收藏、轉發 | 封面 + 收尾 |
| **B · `pack`** | 1 或 3 | 已認識的客戶 | 開一場對話 | 每張卡都要 `.src` 來源＋免責 |

---

## 第 0 步：先確認模式（不可跳過）

「出一張圖」不是足夠清楚的指令。IG 與懶人包的**內容規則、合規強度、版型、
配文寫法全部不同**，寫錯就整份重做。

用戶一提出要求，先判斷：

- 講明「IG」「carousel」「貼文」「輪播」→ 模式 A，不用問。
- 講明「俾客人」「WhatsApp」「懶人包」「分享呢單新聞」→ 模式 B，不用問。
- **兩者都沒講** → 用目前環境的提問工具問一次，確認這是給陌生人看的（IG），還是發給特定客戶的（懶人包）。
- 模式 B 但沒講題材 → 再問一題：哪一類？（見 `references/types-library.md` 的 8 類）

其餘分叉（結尾軟性／引導、素材來源）一次問完，不要逐個問。

---

## 工作流程（兩段式）

> **預設先交文字稿及畫面構想，等確認後再生成圖片和排版。**
> 用戶明確要求直接出圖，或已確認文案同整體方向，就進入第二段。

### 第一段：文字稿

1. **讀輸入**。模式 B 要抽出可核實的事實並標明來源與日期；
   來源不明的（「據悉／消息指／網上流傳」）**當場刪掉**，不要留給他抓。
   只給題目 → 先查（WebSearch／WebFetch），把來源列出來讓他確認。
2. **跑框架**：模式 B 用三層翻譯（發生咩事 → 點解關你事 → 你可以點做），
   見 `references/content-framework.md`；模式 A 用「一句立場 + 一個數字 + 一個動作」。
3. **選版型及畫面**。見 `references/layouts.md`。同款不連續，每三張要有一張有數據。有圖嘅卡加一行 `[畫面]`，寫清楚場景、角色動作同文字留白。涉及人物或吉祥物時，讀 `references/brand.md` 第六節。
4. **寫文字稿並交付**（`文字稿.md`），按目前環境提供可開啟的檔案連結，**停下來等確認**。
   格式見下節。這一步不碰 HTML。
5. **順手自檢**：對照「合規與來源」掃一次，有禁詞或來源不全就當場改。

### 第二段：確認後開工

6. **選擇及準備圖片**。見 [`references/images.md`](references/images.md)。新場景、人物新動作、角色互動或滿版敘事插畫，呼叫圖片生成工具。有合適嘅既有素材或以資訊為主嘅卡，直接排版。角色出場時把固定參考圖交畀圖片工具，續頁可加已確認嘅無字封面底圖。先做封面樣稿適用於用戶想先睇方向嘅情況。方向已確認就接住完成餘頁。
7. **以模板生成 HTML**。複製 `assets/template.html` 的完整結構與 `<style>`，
   按選中的卡**逐塊保留**（沒選中的整塊刪掉，連 `.card-wrap` 一起）。
   轉換規則：
   - 文字稿的 `｜` → `<br>`
   - 每卡第一行的「版型：cover」→ 對應 `data-type="cover"`
   - 設定區的帳號 → `DZ_CONFIG.handle`、關鍵字 → `keywords`
   - 標準霧底用 `v2` / `v3` 隔頁轉變漸層。滿版插畫用同一套色溫同光線，按每頁分鏡安排留白。
   - 將核對過嘅底圖嵌入 HTML，確保預覽及匯出可載入。標題、數字、圖表、來源及免責用排版層製作，保留精確文字同刻度。
8. **執行字型子集腳本**，讓 HTML 嘅「匯出 PNG」按鈕載入正確字型。
   ```bash
   python scripts/build-embed-fonts.py <deck.html>
   ```
9. **用以下腳本逐項檢查同出圖**。
   ```bash
   python scripts/check-fit.py      <deck.html>              # 溢出裁切（模式 B 加 --require-src）
   python scripts/check-orphans.py  <deck.html>              # 孤字 + 結構破損
   python scripts/check-compliance.py <deck.html>            # 禁詞、警示、免責
   python scripts/check-source.py   <deck.html>              # 只看模式 B：來源與日期
   python scripts/export-png.py     <deck.html> --out out/   # 出圖
   python scripts/check-contrast.py out/                     # 白字對比度（出圖後才量）
   ```
   修正所有檢查發現嘅問題。瀏覽器匯出受環境限制時，可用同一份資料和字型重現版面，核對成品嘅字框、對比、尺寸及內容，並如實交代驗證結果。
10. **檢視原尺寸同手機縮圖**。逐張核對斷行、裁切、角色比例同局部對比。數字同單位要對齊，圖表嘅長度、零點及刻度要同試算一致。
11. **交付可開啟嘅 HTML 同 PNG**。HTML 用於預覽同改字，模式 B 另出 4:5 存檔版同 A4 打印版 PDF。
    ```bash
    python scripts/export-pdf.py <deck.html> --out out/pack.pdf           # 4:5 存檔
    python scripts/export-pdf.py <deck.html> --a4 --out out/pack-A4.pdf   # 打印
    ```
    附一句「發圖前建議口頭再講一次重點，圖是輔助不是代替對話。」

---

## 文字稿格式

````markdown
# 圖卡文字稿

## 基本設定
- 模式：A IG ／ B 客戶懶人包
- 主題：保單重複保障
- 帳號：lesterleung_07
- 關鍵字：重複, 冗餘, 減法
- 日期：2026.10

## 來源（模式 B 必填）
- 機構：【待補：原文出處】
- 日期：2026.10

---
## 卡 01 · 版型 cover
- [top-r] POLICY AUDIT · 2026.10
- [book] 《保單說明》
- [hand] 你真正需要嘅
- [title] 其實只有三行
- [lbl] 3　危疾 · 醫療 · 退休
- [meta] 3 POLICIES · 47 CLAUSES · 11 DUPLICATED

## 卡 02 · 版型 number
- [kicker] OVERLAP RATIO
- [bignum] 34%
- [numcap] 你嘅保額，有三成四係重複嘅
- [lg] 66% 有效保障 ｜ 34% 重複
````

規則：
- **一行一顆 `-`**，方括號內是 class 或位置提示。
- **`｜` = 換行**。用戶在該處加／刪就能控制斷行，不必理解 HTML。
- 每張卡第一行寫 **`- 版型：xxx`**，他能直接換版型。
- **寫稿時就對照字數預算**（`references/brand.md` 第七節），超出的行他改稿時看不到問題。
- 模式 B 的事實每條 ≤ 30 字，標題 ≤ 20 字。

---

## 合規與來源（交付前必守）

### 來源（模式 B，`check-source.py` exit 1）
- 每一張卡都要有 `.src`，**包括封面**——圖會被單獨截圖轉發。
- 格式：`資料來源：〈機構全名〉｜YYYY.MM`。連結放配文，不印在圖上。
- 一律攔截：`據悉／據了解／消息指／網上流傳／聽講／朋友講／傳聞`。
- 不得改寫數字。

### 用字（兩個模式都適用，`check-compliance.py` exit 1）
- **禁止詞**：保證、穩賺、零風險、必賺、一定賺、像定存、等同儲蓄、包賠、全賠、
  100% 賠、保本、最好、第一、全港最、市場上唯一。
- **非保證利益**：出現「預期／潛在」收益 → 同卡須有「非保證」。
- **過往績效**：出現回報率／年化 → 同句須標「過往表現不代表將來」。
- **投資題材**：同卡須有「投資涉及風險」。
- **醫療題材**：同卡須有「不構成醫療建議」。
- **每張懶人包卡都要有免責**。
- **不得出現客戶姓名、身份證號、保單號、完整地址**（兩個模式都不行）。

題材禁區見 `references/content-framework.md` 第五節。

---

## 交付後：讓他自己改

模板已內建三個入口：

| 入口 | 怎麼用 |
|---|---|
| **✎ 編輯文字** | 點下去就能直接改卡片上的字；內容超出會跳紅字警示 |
| 帳號／關鍵字欄位 | 改帳號、加減關鍵字，即時上色 |
| 直接改 HTML | 搜尋 `data-filename`，改 `.frame` 裡的文字 |

**HTML 有「⤓ 匯出 PNG」按鈕**，一次匯出全部卡片。

它走 `html-to-image`（DOM → SVG foreignObject → canvas），**不是 html2canvas**：
html2canvas 不支援 `filter: blur()`，會把霧畫成一片死色；
foreignObject 由同一個引擎渲染，所以模糊、漸層、混色全部保真
（實測與命令行出圖平均誤差 1.1/255）。

⚠ 按鈕能用，前提是**先跑過 `build-embed-fonts.py`**：
SVG 當圖片渲染時繼承不到頁面已載入的字型，必須把字型檔以 data URI 塞進去。
沒有 `window.__EMBED_CSS` 就會 fallback 去即時編碼 21MB 原檔 —— 實測 **106 秒**，
完成後每張 0.2 秒。所以交付前一定要跑那支腳本，並在改字之後重跑。

---

## 常見坑

### 1. 字型（最陰險的一個）
**`file://` 下 `@font-face` 是 CORS 受限資源，Chrome 會靜默拒絕載入。**
結果：Iansui（8.2MB）與霞鶩文楷（13MB）根本沒載入，出圖用系統字，
但畫面「看起來正常」——手寫體整批消失，而沒有人會發現。

所以 `export-png.py`／`export-pdf.py`／`check-fit.py`／`check-orphans.py`
**一律起一個臨時 http server**（`scripts/_serve.py`），把 `/fonts/` alias 到
`assets/fonts/`。改這幾支腳本時不要退回 `file://`。

### 2. 對比度
霧是中間調。白字壓上去很容易只得 3.x:1，在手機上糊。
`check-contrast.py` 量的是排除文字後的底色分佈：
**中位 < 4.5:1 就 fail**。修法是把霧壓深（改 `--mist-1..5`）或加重 `.scrim`，
**不是**加粗、不是描邊、不是加陰影。

### 3. `flex:1` 會毀掉溢出檢測
`.blk` 加了 `flex:1` 會被撐滿，`check-fit.py` 永遠量到溢出 0，內容爆了也測不到。
要垂直居中用 `margin:auto` 或 `justify-content:center`。

### 4. 孤字
斷行時某行剛好超出，會有一個字被擠到下一行。此時溢出是 0、留白也正常，
只有 `check-orphans.py` 抓得到。兩支都要跑。

### 5. 中文寬字距
`.12em` 以上的字距在中文細字上等於毀掉可讀性。寬字距只留給拉丁字母的 mono label。

### 6. 硃紅濫用
`#C2553B` 只標「重複／冗餘／問題」。一張卡最多兩處。
用成裝飾色，品牌就從「診斷」變成「配色」。

### 7. 關鍵字上色範圍
`applyKeywords()` 會跳過 `.top / .meta / .src / .hd / .no / .cd / .cta` 等。
新增版型時如果有「不該被上色」的區塊，記得加進 `skip` 那行。

### 8. 匯出按鈕出系統字
按鈕出圖時字型是空的 → 你漏了 `build-embed-fonts.py`，或者改完字沒有重跑。
子集只覆蓋**跑腳本當刻**的字；新增的字要再跑一次。

### 9. PDF 檔案大小
`.grain`（SVG 顆粒）在 `--print-to-pdf` 下會被光柵化成巨大點陣圖：
實測 8 頁 **225MB**。`@media print` 已把它關掉，降到 **9MB**。
改模板時不要把那行刪掉。

### 10. 文案語氣
粵語口語（「你嘅」「唔係」「係」）。不要寫成書面報告。
手寫體只放一句話；整段用手寫會顯得隨便，也傷可讀性。

### 11. 封面漏 `cover` class（檢查工具捉唔到）
`.cover .hand`／`.cover .title` 靠 **card 元素上嘅 `cover` class** 生效。
漏咗會令 138px／88px 大字縮成細字，而 `check-fit` 唔會報錯。
**每次出圖都要做縮圖總覽目視一次**，唔好只靠工具。

### 12. 關鍵字被 inline 拆行
自動上色嘅 `<em class="hl kw">` 會斷成「受／益人」孤字。
加 `em.hl.kw{white-space:nowrap}` 一勞永逸。

### 13. 多版型輪播嘅置中
`.blk{flex:0 0 auto; margin:auto}` ＋ `.ruler{margin-top:0}`，
先可以又置中、又畀 `check-fit` 量到真實溢出。

> 更多實戰伏位（附量到嘅數字同修復前後對照）見 **`references/playbook.md`**。

---

## 檔案

- `assets/template.html` — 主模板：8 款版型 + 霧的六層 + 刻度尺 + 設定區 + 編輯模式 + 列印 CSS。
- `assets/fonts/` — Iansui、霞鶩文楷（本地檔，出圖靠它們）。
- `assets/characters/` — 固定角色參考圖嘅預設位置，使用規則見 `references/brand.md` 第六節。
- `scripts/_serve.py` — 臨時 http server ＋ `/fonts/` alias。**所有要開瀏覽器的腳本都經它。**
- `scripts/check-fit.py` — 溢出與留白（`--require-src` 給模式 B）。
- `scripts/check-orphans.py` — 孤字與結構破損。
- `scripts/check-contrast.py` — 白字對比度（出圖後量 PNG）。
- `scripts/build-embed-fonts.py` — 把 deck 用到的字子集化成 WOFF2，內嵌成 `__EMBED_CSS`
  （約 380 字 → 325KB；匯出按鈕靠它，否則要等 106 秒）。
- `scripts/check-compliance.py` — 禁詞、非保證標示、投資／醫療警示、免責。
- `scripts/check-source.py` — 來源與日期（模式 B 專屬）。
- `scripts/export-png.py` — headless Chrome 出 1080×1350 PNG。
- `scripts/export-pdf.py` — 多頁 PDF；`--a4` 轉打印版。
- `references/brand.md` — **品牌與視覺規則。改設計前先讀。**
- `references/playbook.md` — **實操手冊：真實出圖中過嘅伏、修復數字、模板維護與合規原則。**
- `references/layouts.md` — 8 款版型與選版規則。
- `references/images.md` — 出圖時機、固定角色參考、完整場景、圖文留白及 MPF 輪播分鏡。
- `references/content-framework.md` — 三層翻譯法、標題公式、來源規範、題材禁區。
- `references/types-library.md` — 8 類懶人包的角度、合規注意、建議來源。
- `references/topic-library.md` — 10 個常見題材的切入角度。
