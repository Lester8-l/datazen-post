#!/usr/bin/env python3
"""
把 deck HTML 逐張卡輸出成 1080×1350 PNG。

用法:
    python export-png.py deck.html                    # -> deck 同層 out/
    python export-png.py deck.html --out out/ --scale 2

做法:
    起臨時 http server（見 _serve.py），逐張卡寫一個臨時頁，只顯示第 N 張，
    再用 headless Chrome 截圖。

    ⚠ 為什麼唔用 file:// ？
    file:// 下 @font-face 是 CORS 受限資源，Chrome 會靜默拒絕載入，
    字型退回系統字——手寫體會整批消失，而畫面「睇落正常」。
    走 http://127.0.0.1 就冇這個問題，字型由 skill 內附的 TTF 直出。
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

ISOLATE = """
<style>
  html,body{margin:0!important;padding:0!important;background:#fff!important;overflow:hidden!important}
  .toolbar,.controls,.btn-edit,.btn-pdf,.hint,[data-noexport]{display:none!important}
  .deck{display:block!important;gap:0!important;margin:0!important;padding:0!important;max-width:none!important}
  .card-wrap{display:none!important}
  .card-wrap:nth-of-type(%d){display:block!important;margin:0!important;padding:0!important;gap:0!important}
  .card{box-shadow:none!important;margin:0!important}
</style>
</head>"""


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--out", default=None, help="輸出目錄（預設 deck 同層 out/）")
    ap.add_argument("--chrome", default=None)
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1350)
    ap.add_argument("--scale", type=int, default=1, help="device scale factor，2 = 2160×2700 高清")
    ap.add_argument("--wait", type=int, default=15000)
    args = ap.parse_args()

    deck_path = pathlib.Path(args.deck).resolve()
    if not deck_path.exists():
        raise SystemExit(f"檔案不存在：{deck_path}")
    root = deck_path.parent
    out_dir = pathlib.Path(args.out).resolve() if args.out else root / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    # 臨時頁必須在 server root（deck 同層）之下，否則 http 取不到
    tmp_dir = root / ".dz_tmp"
    tmp_dir.mkdir(exist_ok=True)

    browser = find_browser(args.chrome)
    html = deck_path.read_text(encoding="utf-8")
    names = CARD_RE.findall(html)
    if not names:
        raise SystemExit("找不到任何 data-filename 卡片，請確認 deck HTML 結構。")

    print(f"browser : {browser}")
    print(f"cards   : {len(names)} -> {names}")

    failures = []
    with _serve.serve(root) as base:
        for i, name in enumerate(names, start=1):
            page = tmp_dir / f"{i:02d}.html"
            page.write_text(html.replace("</head>", ISOLATE % i, 1), encoding="utf-8")
            png = out_dir / f"{name}.png"
            cmd = [
                browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                "--run-all-compositor-stages-before-draw",
                f"--force-device-scale-factor={args.scale}",
                f"--window-size={args.width},{args.height}",
                f"--virtual-time-budget={args.wait}",
                f"--screenshot={png}",
                _serve.url(base, page, root),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            ok = png.exists() and png.stat().st_size > 2000
            kb = png.stat().st_size // 1024 if png.exists() else 0
            print(f"  {'OK  ' if ok else 'FAIL'} {name}.png  {kb}KB")
            if not ok:
                failures.append(name)
                if r.stderr:
                    print("       ", r.stderr.strip()[-200:])

        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n完成：{len(names) - len(failures)}/{len(names)} 張 -> {out_dir}")
    if failures:
        print("失敗：", failures)
        sys.exit(1)


if __name__ == "__main__":
    main()
