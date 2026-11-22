#!/usr/bin/env python3
"""
把 deck 用到的字，子集化成極小的 WOFF2，內嵌成 `window.__EMBED_CSS`。

為什麼需要這一步？
    HTML 內建「匯出 PNG」按鈕走 html-to-image（把 DOM 序列化成 SVG 再畫到 canvas）。
    用 SVG 圖片渲染時，頁面已載入的字型不會被繼承——必須把字型檔本身
    以 data URI 塞進 SVG，否則整張圖會變成系統字。

    但 Iansui（8.2MB）與霞鶩文楷（13MB）原檔編碼成 base64 要 100 秒以上。
    所以：只保留 deck 真正用到的字 → 通常 100–200 字 → 20–60KB，出圖由 28 秒變 0.2 秒。

用法:
    python build-embed-fonts.py deck.html              # 就地注入 <script id="dz-fonts">
    python build-embed-fonts.py deck.html --dry-run    # 只報告字數與大小
    python build-embed-fonts.py deck.html --extra 常用字…

注意:
    子集只覆蓋**出圖當刻**的字。改了字又加了新字，重跑這支腳本即可。
    （按鈕出圖失敗或見到系統字，就是漏了這一步。）
"""
import argparse
import base64
import io
import pathlib
import re
import sys

SKILL = pathlib.Path(__file__).resolve().parent.parent
FONT_DIR = SKILL / "assets" / "fonts"
FONTS = [
    ("Iansui Local", "iansui.ttf"),
    ("LXGW Local", "lxgw-wenkai-tc.ttf"),
]

# 一定帶上的字符：ASCII、常用標點、數字符號
ALWAYS = (
    "".join(chr(c) for c in range(0x20, 0x7F))
    + "　、。！？；：「」『』（）《》〈〉…—－·～＋－×÷％‰°"
    + "0123456789０１２３４５６７８９"
    + "壹貳參肆伍陸柒捌玖拾佰仟萬億"
)

TAG = re.compile(r"<[^>]+>")
BLOCK = re.compile(r"<(script|style)\b.*?</\1>", re.S)


def visible_text(html: str) -> str:
    s = BLOCK.sub(" ", html)
    s = TAG.sub(" ", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return s


def subset_woff2(ttf: pathlib.Path, chars: str) -> bytes:
    from fontTools import subset as ftsubset

    opts = ftsubset.Options()
    opts.flavor = "woff2"
    opts.layout_features = []      # 卡片只排中文與基本數字，不需要 OT 特性
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    opts.recalc_bounds = True

    font = ftsubset.load_font(str(ttf), opts)
    sub = ftsubset.Subsetter(options=opts)
    sub.populate(text=chars)
    sub.subset(font)

    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--extra", default="", help="額外保證收錄的字（例如你打算改用的詞）")
    args = ap.parse_args()

    deck = pathlib.Path(args.deck).resolve()
    if not deck.exists():
        raise SystemExit(f"檔案不存在：{deck}")
    html = deck.read_text(encoding="utf-8")

    text = visible_text(html) + ALWAYS + args.extra
    chars = "".join(sorted(set(text)))
    print(f"deck    : {deck.name}")
    print(f"字集    : {len(chars)} 個不同字符")

    css_parts = []
    total = 0
    for family, fname in FONTS:
        src = FONT_DIR / fname
        if not src.exists():
            raise SystemExit(f"缺字型檔：{src}")
        data = subset_woff2(src, chars)
        total += len(data)
        b64 = base64.b64encode(data).decode()
        print(f"  {family:<14} {fname:<22} {len(data)/1024:6.1f} KB")
        css_parts.append(
            '@font-face{font-family:"%s";src:url(data:font/woff2;base64,%s) format("woff2")}'
            % (family, b64)
        )

    css = "".join(css_parts)
    print(f"合計    : {total/1024:.1f} KB（base64 後 {len(css)/1024:.1f} KB）")

    if args.dry_run:
        return

    snippet = '<script id="dz-fonts">window.__EMBED_CSS=' + repr(css).replace("'", '"', 2) + ";</script>"
    # 用 JSON 方式安全嵌入
    import json
    snippet = '<script id="dz-fonts">window.__EMBED_CSS=' + json.dumps(css) + ";</script>"

    existing = re.search(r'<script id="dz-fonts">.*?</script>', html, re.S)
    if existing:
        html = html[: existing.start()] + snippet + html[existing.end():]
        action = "更新"
    else:
        html = html.replace("</body>", snippet + "\n</body>", 1)
        action = "注入"

    deck.write_text(html, encoding="utf-8")
    print(f"✓ {action} <script id=\"dz-fonts\"> 完成")


if __name__ == "__main__":
    main()
