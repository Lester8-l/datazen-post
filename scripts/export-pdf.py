#!/usr/bin/env python3
"""
把卡片 HTML 匯出成多頁 PDF（每張卡一頁，保留 4:5 比例）。

Usage:
    python export-pdf.py pack.html [--out <file.pdf>] [--chrome <chrome.exe>]
    python export-pdf.py pack.html --a4          # 改為 A4 直向（打印用）

How it works:
    注入 @page 規則把紙張尺寸設成跟卡片一樣（預設 1080×1350），
    再叫 headless Chrome 直接 --print-to-pdf。
    因為紙張比例 = 卡片比例，每張卡剛好落一頁，唔會被切開。

    為什麼要獨立一支：
    - PNG 適合 WhatsApp 預覽（縮略圖唔會被裁），PDF 適合
      ① 用電腦睇放大細節 ② 打印 ③ 存檔歸檔 ④ 轉發俾要用電腦開嘅客戶。
    - print-to-pdf 出嘅文字係**可選取、可搜尋**的向量文字，
      唔係圖片，所以檔案細、放大唔起格、可以 Ctrl+F。

Requirements:
    headless Chrome 或 Edge，會自動偵測常見路徑，可用 --chrome 覆寫。
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _serve  # noqa: E402

CARD_RE = re.compile(r'data-filename="([^"]+)"')

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def find_browser(explicit=None):
    if explicit:
        return explicit
    for p in CHROME_CANDIDATES:
        if pathlib.Path(p).exists():
            return p
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    home = pathlib.Path.home() / ".agent-browser" / "browsers"
    if home.exists():
        for exe in home.glob("chrome-*/chrome.exe"):
            return str(exe)
    raise SystemExit("找不到 Chrome / Edge，請用 --chrome <path> 指定。")


# 打印用樣式：只保留卡片、移除工具列、每卡一頁
PRINT_CSS = """
@page {{ size: {w}px {h}px; margin: 0; }}
html,body{{margin:0 !important;padding:0 !important;background:#fff !important;}}
.toolbar,.controls,.card-label,.ovf,.btn{{display:none !important;}}
.deck{{display:block !important;max-width:none !important;margin:0 !important;gap:0 !important;}}
.card-wrap{{display:block !important;margin:0 !important;padding:0 !important;}}
.card-wrap.overflow .card{{outline:4px solid #B23A2F;}}  /* 溢出可見，避免靜默印出斷版 */
/* 每張卡一頁。最後一張唔加 break-after，否則會多出一頁空白。 */
.card{{
  width:{w}px !important;height:{h}px !important;margin:0 !important;
  page-break-after:always;break-after:page;
  box-shadow:none !important;border-radius:0 !important;
}}
.card:last-of-type{{page-break-after:auto;break-after:auto;}}
"""

# A4 210×297mm；@page 留 10mm 邊距 → 內容區 190×277mm = 718×1047px @96dpi
A4_CONTENT_PX = 718

# A4 打印樣式：**等比縮放整張卡**，不是改卡片尺寸。
#
# ⚠ 這裡連踩四個坑才對，改動前務必讀完：
#
# 坑 1：原本寫成 .card{{width:794px;height:992px}}，整份 A4 PDF 爛掉。
#   卡片內部所有字級、內距、行高都是為 1080×1350 設計的固定 px，
#   把容器縮到 794 寬而字級沒跟著縮，內容立刻被 overflow:hidden 裁掉一大截。
#   → 必須保持原尺寸，用 zoom 整體縮放。
#
# 坑 2：transform:scale() 不行——transform 只是視覺變換，
#   卡片的**佈局寬度仍是 1080px**，比可打印寬度（718px）寬，
#   Chrome 列印偵測到內容超寬就啟動整頁 shrink-to-fit，於是再縮一次（718→423px）。
#   → 改用 zoom（Chrome 原生），它會實際改變元素的佈局尺寸。
#
# 坑 3：html,body{{width:auto}} 也不行。
#   **@page margin 只決定「哪一帶印不出來」，不會縮小 CSS 的 layout viewport**。
#   A4 的 layout viewport 仍是整頁寬 794px，而可打印寬度只有 718px；
#   body 寬 794px > 718px，Chrome 照樣啟動整頁縮放（718→638px，比例 718/794）。
#   → html,body 寬度必須**明確設成內容區寬度（{w}px）**，而不是 auto。
#   這樣「內容寬度 = 可打印寬度」，Chrome 沒有超寬就不會整頁縮放。
#
# 坑 4：模板自己有一段 @media print，裡面寫死 html,body{{width:1080px}}。
#   所以本檔案每個關鍵屬性都帶 !important——目的是**壓過**模板的 @media print，
#   不是跟它疊加。改這裡的規則時，記得保持 !important。
#
# 驗證方法（改完一定要做，用 pymupdf 讀 PDF 量）：
#   ① 量「最大字級」：正確值 = 模板字級 × scale（例：封面大標 80px × 0.665 = 53.2px）。
#      **這是最可靠的指標**，不受卡片 padding 影響。
#   ② 若要量卡片像素尺寸，務必量 **.card 的邊界，不是 .frame**——
#      .card 有 60px padding，內層 .frame 才是你看到的那塊底色／深色區。
#      量 .frame 會得到 (1080−120)×scale = 638px，看起來像縮放失敗，
#      但那其實是對的（卡片本體是 718px，只是四周有縮放後的 40px padding）。
#      實測紀錄：.card = 718px、.frame = 638px、x 起點 = 38(page margin) + 40(padding) = 78px。
A4_CSS = """
@page {{ size: A4 portrait; margin: 10mm; }}
html,body{{margin:0 !important;padding:0 !important;background:#fff !important;
          width:{w}px !important;max-width:{w}px !important;}}
.toolbar,.controls,.card-label,.ovf,.btn{{display:none !important;}}
.deck{{display:block !important;width:{w}px !important;max-width:{w}px !important;
       margin:0 !important;gap:0 !important;}}
/* 外層容器 = 縮放後的實際尺寸，一頁一張卡 */
.card-wrap{{
  display:block !important;
  width:{w}px !important;height:{h}px !important;
  margin:0 auto !important;padding:0 !important;
  overflow:hidden;
  page-break-after:always;break-after:page;
}}
.card-wrap:last-child{{page-break-after:auto;break-after:auto;}}
/* 卡片保持原設計尺寸，用 zoom 整體等比縮放。
   zoom 會實際改變佈局尺寸（transform 不會），這是這條規則能生效的關鍵。 */
.card{{
  width:{cw}px !important;height:{ch}px !important;
  margin:0 !important;
  zoom:{scale} !important;
  box-shadow:none !important;border-radius:0 !important;
}}
.card-wrap.overflow .card{{outline:4px solid #B23A2F;}}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--out", default=None, help="輸出 PDF 路徑（預設與 HTML 同層同名）")
    ap.add_argument("--chrome", default=None)
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1350)
    ap.add_argument("--a4", action="store_true",
                    help="輸出 A4 直向（210×297mm）——打印用，卡片會置中留白邊")
    args = ap.parse_args()

    deck_path = pathlib.Path(args.deck).resolve()
    if not deck_path.exists():
        raise SystemExit(f"檔案不存在：{deck_path}")

    names = CARD_RE.findall(deck_path.read_text(encoding="utf-8"))
    if not names:
        raise SystemExit("找不到任何 data-filename 卡片，請確認 HTML 結構。")

    out = pathlib.Path(args.out).resolve() if args.out else deck_path.with_suffix(".pdf")
    # --out 指到目錄時自動補檔名：否則 Chrome 唔會寫檔，
    # 而目錄本身 size > 2000 bytes，會令下面嘅驗證誤判成功。
    if out.is_dir():
        out = out / (deck_path.stem + ("-A4.pdf" if args.a4 else ".pdf"))
    out.parent.mkdir(parents=True, exist_ok=True)

    browser = find_browser(args.chrome)
    html = deck_path.read_text(encoding="utf-8")

    if args.a4:
        # A4 打印：等比縮放整張卡塞進 A4 內容區（不要改 .card 尺寸，原因見 A4_CSS 註解）
        scale = A4_CONTENT_PX / args.width
        css = A4_CSS.format(
            scale=f"{scale:.5f}",
            w=round(args.width * scale),
            h=round(args.height * scale),
            cw=args.width,
            ch=args.height,
        )
        print(f"縮放    : {scale:.3f}（{args.width}×{args.height} → "
              f"{round(args.width * scale)}×{round(args.height * scale)}px）")
    else:
        css = PRINT_CSS.format(w=args.width, h=args.height)

    # A4 專用：移除 viewport meta。
    # <meta name="viewport" content="width=device-width"> 是手機版排版用的，
    # 但在列印時它會改變 Chrome 計算 layout viewport 的方式（改用裝置寬度再縮放去適應紙張），
    # 造成額外的整頁縮放——實測卡片被無形縮小約 11%（718px 印出來只剩 637px）。
    if args.a4:
        html = re.sub(r'<meta[^>]*name=["\']viewport["\'][^>]*>', '', html, flags=re.I)

    print_html = html.replace("</head>", f"<style>{css}</style></head>", 1)

    # 走臨時 http server：file:// 下字型會被 CORS 擋，PDF 會用系統字
    tmp = deck_path.parent / "_pdf_page.html"
    tmp.write_text(print_html, encoding="utf-8")
    try:
        with _serve.serve(deck_path.parent) as base:
            cmd = [
                browser, "--headless=new", "--disable-gpu",
                "--no-pdf-header-footer",
                "--virtual-time-budget=15000",
                f"--print-to-pdf={out}",
                _serve.url(base, tmp, deck_path.parent),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        tmp.unlink(missing_ok=True)

    if not out.is_file() or out.stat().st_size < 2000:
        print("✗ 匯出失敗。")
        if r.stderr:
            print(r.stderr.strip()[-400:])
        sys.exit(1)

    # 驗證頁數是否等於卡片數——頁數不符通常代表卡片高度有偏差
    size_kb = out.stat().st_size // 1024
    pages = None
    try:
        import pymupdf  # 有的話順便驗頁數
        pages = pymupdf.open(str(out)).page_count
    except Exception:
        pass

    mode = "A4 直向（打印用）" if args.a4 else f"{args.width}×{args.height}（4:5，螢幕用）"
    print(f"browser : {browser}")
    print(f"紙張    : {mode}")
    print(f"卡片    : {len(names)} -> {names}")
    print(f"輸出    : {out}  {size_kb}KB" + (f"  {pages} 頁" if pages else ""))

    if pages is not None and pages != len(names):
        print(f"⚠ 頁數（{pages}）與卡片數（{len(names)}）不符。")
        print("  多數是 .card 高度在打印樣式下被撐開，或內容溢出。")
        print("  請先跑 check-fit.py，確認沒有溢出。")
        sys.exit(1)

    print("✓ 完成。")


if __name__ == "__main__":
    main()
