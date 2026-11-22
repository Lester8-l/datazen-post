#!/usr/bin/env python3
"""
懶人包合規守門員：掃描**可見文字**，攔截違規與越界表述。

Usage:
    python check-compliance.py pack.html
    python check-compliance.py pack.html --strict     # 連 WARN 也視為失敗

為什麼懶人包也要跑這支：
    題材是「新聞／資訊」，但你的身份是持牌顧問。
    只要卡片上出現「穩賺」「包賠」「保證回報」，或把醫療資訊寫成醫療建議、
    把市場資訊寫成投資建議，責任一樣落在你身上。
    排版好看救不了用字違規，所以這支是硬門檻。

退出碼：有 ERROR → 1；只有 WARN → 0（除非 --strict）；乾淨 → 0。
"""
import argparse
import html as html_mod
import pathlib
import re
import sys

# ── 一律禁止的詞（無條件）──
BANNED = [
    (r"穩賺|稳赚",                        "承諾獲利，屬違規表述"),
    (r"必賺|必赚|一定賺|一定赚|保證賺|保证赚|包賺|包赚|必升|肯定升",  "承諾獲利／升值，屬違規表述"),
    (r"零風險|零风险|無風險|无风险|冇風險|絕無風險|绝无风险",  "「零風險」不可用於金融保險產品"),
    (r"像定存|似定存|等同定存|如同定存",      "不得與銀行存款混淆"),
    (r"等同儲蓄|等同储蓄|儲蓄替代品|储蓄替代品|取代儲蓄|取代储蓄",         "不得宣稱為儲蓄替代品"),
    (r"包賠|包赔|全賠|全赔|100%\s*[賠赔]|必定[賠赔]|一定[賠赔]|必[賠赔]", "理賠不得寫成必然結果"),
    (r"保本保息|保證保本|保证保本|保本增值",          "不得承諾保本"),
    (r"唔會蝕|不會虧損|不会亏损|穩陣必勝|稳阵必胜|包賺唔蝕|包赚唔蚀",     "不得承諾不虧損"),
    (r"最好|第一|全港最|市場上唯一|市场上唯一|世界上最好", "不得作絕對化或唯一性宣稱"),
    (r"保證(治好|醫好|痊癒|根治|斷尾)|保证(治好|医好|痊愈|根治|断尾)",       "不得宣稱療效或康復保證"),
    (r"食(咗|左)?(呢|這|这)(個|隻|个|只)就(好|冇事)",   "不得寫成療效承諾"),
    (r"政府(保證|保证|包底|一定|必定)",            "不得作政策保證式表述"),
]

# ── 有條件的規則：(觸發詞, 同卡必須存在的字樣, 說明) ──
CONDITIONAL = [
    (
        r"預期(回報|收益|現金價值|價值|紅利|派息)|潛在(回報|收益)|非保證紅利|預期利益|预期(回报|收益|现金价值|价值|红利|派息)|潜在(回报|收益)|非保证红利|预期利益",
        r"非保證|非保证",
        "出現預期／潛在利益，但沒有標示「非保證」",
    ),
    (
        r"回報率|派息率|年化|過往表現|歷史回報|過去.*回報|年均增長|回报率|过往表现|历史回报|过去.*回报|年均增长",
        r"過往(表現)?不代表(將來|未來)|过往(表现)?不代表(将来|未来)",
        "出現回報率／過往數據，但沒有標註「過往表現不代表將來」",
    ),
    (
        r"保證(回報|收益|利潤|增長|升值|賺)|保證.*回報|保证(回报|收益|利润|增长|升值|赚)|保证.*回报",
        None,   # 直接違規
        "「保證」與收益詞連用，構成保證回報表述",
    ),
    (
        r"股票|基金|ETF|債券|外匯|加密貨幣|虛擬資產|強積金|投資組合|债券|外汇|加密货币|虚拟资产|强积金|投资组合",
        r"投資(涉及|帶有|附帶)?風險|價格可升可跌|可升可跌|投资(涉及|带有|附带)?风险|价格可升可跌",
        "提到投資產品／市場，但同卡沒有風險警示（建議補「投資涉及風險」）",
    ),
    (
        r"住院|手術|癌症|確診|病徵|症狀|藥物|治療|手术|确诊|病症|症状|药物|治疗",
        r"不構成[^。；]{0,14}建議|並非(醫療|醫學|專業)建議|請諮詢(醫生|醫護|家庭醫生)|不能代替(醫生|專業)|不构成[^。；]{0,14}建议|并非(医疗|医学|专业)建议|请咨询(医生|医护|家庭医生)|不能代替(医生|专业)",
        "涉及疾病／治療內容，但同卡沒有「不構成醫療建議」的提示",
    ),
]

# ── 每張卡都必須有的免責聲明（任一命中即可）──
REQUIRED_IN_CARD = [
    (r"僅供(參考|資訊|分享)|資料僅供|內容僅供|不構成(任何)?[^。；]{0,10}建議|以(正式)?保單條款為準|並非(專業|醫療|投資|法律)建議|仅供(参考|资讯|分享)|资料仅供|内容仅供|不构成(任何)?[^。；]{0,10}建议|以(正式)?保单条款为准|并非(专业|医疗|投资|法律)建议",
     "缺少免責聲明。每張卡都要有一句，例如「資料僅供參考，不構成任何投資／醫療建議」。"),
]

# ── 不該出現在圖上的敏感資料 ──
SENSITIVE = [
    (r"\b[A-Z]{1,2}\d{6}\(\d\)\b", "疑似香港身份證號碼"),
    (r"\b\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b", "疑似信用卡／銀行卡號"),
    (r"\bP\d{8,}\b|\b[A-Z]{2}\d{7,}\b", "疑似保單號碼"),
]

# ── 建議改進（不阻斷交付）──
WARNINGS = [
    (r"確診即賠", "「確診即賠」易被理解為任何確診均賠，建議改為「符合保單定義下可獲賠償」"),
    (r"實報實銷(?!.*合理)", "「實報實銷」宜補上「合理及慣常費用」的界定"),
    (r"[^\d]保證[^\d]", "出現「保證」二字，請確認僅用於既有條款術語（如「保證現金價值」）"),
    (r"100\s*%", "出現 100%，請確認不是對理賠或回報的絕對化描述"),
    (r"專家(指出|表示|建議)|有醫生(指出|表示)", "「專家／醫生」宜寫明身份與來源，否則屬匿名權威"),
    (r"最快|最平|最抵|最筍", "絕對化比較用語，建議改為較溫和的描述"),
]

CARD_SPLIT = re.compile(r'<div[^>]*class="card[^"]*"[^>]*data-filename="([^"]+)"')


def strip_html(s: str) -> str:
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_mod.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def cards_of(raw: str):
    parts = CARD_SPLIT.split(raw)
    if len(parts) < 3:
        return [("（整份文件）", strip_html(raw))]
    out = []
    for i in range(1, len(parts), 2):
        out.append((parts[i], strip_html(parts[i + 1])))
    return out


def context(text: str, m: re.Match, span: int = 14) -> str:
    a = max(0, m.start() - span)
    b = min(len(text), m.end() + span)
    return ("…" if a else "") + text[a:b] + ("…" if b < len(text) else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--strict", action="store_true", help="把 WARN 也視為失敗")
    ap.add_argument("--mode", choices=["auto", "ig", "pack"], default="auto",
                    help="auto = 讀 DZ_CONFIG.mode。ig 模式不要求每張卡都有免責句")
    args = ap.parse_args()

    path = pathlib.Path(args.html).resolve()
    if not path.exists():
        raise SystemExit(f"檔案不存在：{path}")
    raw = path.read_text(encoding="utf-8")
    cards = cards_of(raw)

    mode = args.mode
    if mode == "auto":
        m = re.search(r"mode\s*:\s*['\"](ig|pack)['\"]", raw)
        mode = m.group(1) if m else "pack"

    print(f"掃描 {path.name}　共 {len(cards)} 張卡　模式：{mode}\n")
    if mode == "ig":
        print("  （IG 模式：不要求每張卡都有免責句；禁詞與風險警示照驗）\n")
    errors, warns = [], []

    for name, text in cards:
        for pat, msg in BANNED:
            for m in re.finditer(pat, text):
                errors.append((name, msg, context(text, m)))
        for trig, fix, msg in CONDITIONAL:
            for m in re.finditer(trig, text):
                if fix is None:
                    errors.append((name, msg, context(text, m)))
                elif not re.search(fix, text):
                    # IG 模式：把「投資／醫療風險提示」降為提示。
                    # 理由：IG 卡短，提示可以放配文；強制上卡會令每張都變成小字廣告。
                    (warns if mode == "ig" else errors).append((name, msg, context(text, m)))
        for pat, msg in ([] if mode == "ig" else REQUIRED_IN_CARD):
            if not re.search(pat, text):
                errors.append((name, msg, "（整張卡）"))
        for pat, msg in SENSITIVE:
            for m in re.finditer(pat, text):
                errors.append((name, msg, context(text, m)))
        for pat, msg in WARNINGS:
            for m in re.finditer(pat, text):
                warns.append((name, msg, context(text, m)))

    def dump(title, rows, mark):
        if not rows:
            return
        print(f"{mark} {title}（{len(rows)}）")
        for name, msg, ctx in rows:
            print(f"   [{name}] {msg}")
            print(f"        ↳ {ctx}")
        print()

    dump("必須修正", errors, "✗")
    dump("建議檢查", warns, "△")

    if errors:
        print(f"✗ 合規檢查不通過（{len(errors)} 項錯誤）。這份懶人包不可交付。")
        print("  修法：改寫用字，或補上「非保證」「過往表現不代表將來」「投資涉及風險」等標示。")
        sys.exit(1)
    if warns and args.strict:
        print(f"✗ --strict 模式下 {len(warns)} 項提醒視為失敗。")
        sys.exit(1)
    print("✓ 合規檢查通過。")
    if warns:
        print("  提醒：上面 △ 項目仍值得人工確認一次。")


if __name__ == "__main__":
    main()
