#!/usr/bin/env python3
"""
懶人包來源守門員：每一張卡都必須標明**可核實的來源與日期**。

Usage:
    python check-source.py pack.html
    python check-source.py pack.html --strict

為什麼這支腳本比排版檢查更重要：
    懶人包的本質是「幫客戶讀完原文、只留重點」。
    一旦省略來源，卡片就由「資訊摘要」變成「個人觀點」——
    客戶轉發出去，出事的是你的專業信譽；若內容牽涉理賠、投資、醫療，
    更可能構成不當陳述。所以來源不是裝飾，是這類內容的執照。

    同時攔截「據悉／消息指／網上流傳」這類**不可核實來源**：
    貼上這類字樣等於承認自己沒有查證，寧可不發。

檢查項目（每張卡都要有）：
    1. 存在 .src 來源區塊（不是隨便在正文寫「來源」兩個字就算）
    2. 來源區塊寫明機構／媒體名稱（≥4 字）
    3. 來源區塊標明日期（年 + 月，或完整年月日）
    4. 沒有「據悉／消息指／網上流傳」等不可核實字樣

退出碼：有 ERROR → 1；只有 WARN → 0（除非 --strict）；乾淨 → 0。
"""
import argparse
import html as html_mod
import pathlib
import re
import sys

# 卡片切分：抓 <div class="card ..." data-filename="...">
CARD_SPLIT = re.compile(r'<div[^>]*class="card[^"]*"[^>]*data-filename="([^"]+)"')

# 來源區塊（視覺元素）——容忍附加 class，如 class="src src-sm"
SRC_BLOCK = re.compile(r'class="[^"]*\bsrc\b[^"]*"', re.I)

# 來源關鍵字
SRC_KEY = re.compile(r'(資料來源|數據來源|來源|出處|Source|资料来源|数据来源|来源|出处)', re.I)

# 日期：2026.10.08 / 2026-10-08 / 2026年10月8日 / 2026年10月
DATE = re.compile(r'20\d{2}\s*[年.\-/]\s*\d{1,2}(?:\s*[月.\-/]\s*\d{1,2}\s*日?)?')

# 不可核實的來源字樣（一律擋）
UNVERIFIABLE = [
    (r'據悉|據了解|據報導指|消息指|網上流傳|網絡流傳|聽講|朋友講|有人話|傳聞|據傳'
     r'|据悉|据了解|据报导指|消息指|网上流传|网络流传|听讲|朋友讲|有人话|传闻|据传',
     '來源不可核實（「據悉／消息指／網上流傳」）。請找出原始出處，或不要發。'),
]

# 建議檢查（不阻斷）
WARNINGS = [
    (r'(來源|来源)\s*[：:]\s*(?![^｜|\n]{4,})',
     '來源似乎沒有寫明機構／媒體名稱，客戶無法核實。'),
    (r'(轉載|原文|詳見)\s*(?!https?://)',
     '提到原文但沒有附連結，建議在 WhatsApp 配文補上連結而非印在圖上。'),
    (r'研究(顯示|指出|發現)|調查(顯示|發現)|數據(顯示|指出)|研究(显示|指出|发现)|调查(显示|发现)|数据(显示|指出)',
     '出現「研究／調查／數據顯示」，請確認同一張卡有寫明來源機構與年份。'),
]


def strip_html(s: str) -> str:
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_mod.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def cards_of(raw: str):
    """回傳 [(卡片名, HTML, 可見文字)]；找不到卡片結構時整份當一張。"""
    parts = CARD_SPLIT.split(raw)
    if len(parts) < 3:
        return [("（整份文件）", raw, strip_html(raw))]
    out = []
    for i in range(1, len(parts), 2):
        out.append((parts[i], parts[i + 1], strip_html(parts[i + 1])))
    return out


def context(text: str, m: re.Match, span: int = 16) -> str:
    a = max(0, m.start() - span)
    b = min(len(text), m.end() + span)
    return ("…" if a else "") + text[a:b] + ("…" if b < len(text) else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--strict", action="store_true", help="把 WARN 也視為失敗")
    args = ap.parse_args()

    path = pathlib.Path(args.html).resolve()
    if not path.exists():
        raise SystemExit(f"檔案不存在：{path}")
    raw = path.read_text(encoding="utf-8")

    # IG 模式不需要每張卡有來源（那條規則只屬於客戶懶人包）。
    # 自動偵測 DZ_CONFIG.mode，避免在 IG deck 上誤報。
    m_mode = re.search(r"mode\s*:\s*['\"](ig|pack)['\"]", raw)
    if m_mode and m_mode.group(1) == "ig":
        print(f"{path.name}：IG 模式，不需要 .src 來源區塊，跳過。")
        return
    cards = cards_of(raw)

    print(f"掃描 {path.name}　共 {len(cards)} 張卡\n")
    errors, warns = [], []

    for name, body, text in cards:
        # 1) 要有 .src 視覺區塊
        if not SRC_BLOCK.search(body):
            errors.append((name, "缺少來源區塊（.src）。每張卡都要有，包括輪播的封面頁。", "（整張卡）"))
            continue
        # 2) 要有來源關鍵字
        if not SRC_KEY.search(text):
            errors.append((name, "來源區塊沒有寫「來源」字樣。", "（整張卡）"))
        # 3) 要有日期
        if not DATE.search(text):
            errors.append((name, "來源沒有標明日期（建議格式 2026.10；完整則 2026.10.08）。", "（整張卡）"))
        # 4) 不可核實來源
        for pat, msg in UNVERIFIABLE:
            if msg is None:
                continue
            for m in re.finditer(pat, text):
                errors.append((name, msg, context(text, m)))
        # 5) 建議改進
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
        print(f"✗ 來源檢查不通過（{len(errors)} 項）。這份懶人包不可交付。")
        print("  修法：補上「資料來源：<機構／媒體>｜<日期>」；不可核實的內容請刪掉。")
        sys.exit(1)
    if warns and args.strict:
        print(f"✗ --strict 模式下 {len(warns)} 項提醒視為失敗。")
        sys.exit(1)
    print("✓ 來源檢查通過：每張卡都有可核實的來源與日期。")
    if warns:
        print("  提醒：上面 △ 項目仍值得人工確認一次。")


if __name__ == "__main__":
    main()
