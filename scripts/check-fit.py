#!/usr/bin/env python3
"""
檢查懶人包的內容有沒有「裝唔落」（被 overflow:hidden 靜默裁切）或「太空」。

Usage:
    python check-fit.py pack.html
    python check-fit.py pack.html --chrome "C:\\...\\chrome.exe"
    python check-fit.py pack.html --empty 300     # 自訂「偏空」門檻（px）

原理：
    headless Chrome 開臨時頁，注入 JS 讀每張卡 .frame 的
    scrollHeight / clientHeight（溢出），以及
    內容底 → .src 來源區塊之間被 margin:auto 吸收的空白（留白）。

    為什麼要量而不是看圖？
    溢出被裁掉的往往是最後一行的下緣，肉眼在縮圖上幾乎看不出來——
    但發到 WhatsApp 客人一眼就看到斷字。

    ⚠ 版面設計必須遵守兩條，否則這支腳本量唔準：
      1. .card 用固定 height（1080×1350），.frame 用 height:100%。
      2. **不要給內容區塊（.blk）加 flex:1**。
         加了 flex:1，區塊會被撐滿，溢出永遠是 0，檢查形同虛設。
         要垂直居中請用 margin:auto，不是 flex:1。

退出碼：任何一張溢出或缺來源 → 1；正常 → 0。
"""
import argparse
import html as html_mod
import json
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _serve  # noqa: E402

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

PROBE = r"""
(function(){
  function finish(p){ var e=document.createElement('pre'); e.id='__fit'; e.textContent=JSON.stringify(p); e.style.display='none'; document.body.appendChild(e); }
  function run(){
    var rows=[];
    document.querySelectorAll('.card').forEach(function(c){
      var f=c.querySelector('.frame');
      if(!f) return;
      var blocks=[...f.querySelectorAll('.blk')].map(function(b){
        return { cls:(b.className||'').replace('blk','').trim(), h:Math.round(b.getBoundingClientRect().height) };
      });
      // 留白 = 內容底 → .src 頂 之間被 margin:auto 吸收的空白
      var src=f.querySelector('.src');
      var gap=null;
      var bottom=0;
      [].forEach.call(f.children,function(k){
        if(k===src) return;
        var r=k.getBoundingClientRect();
        if(r.height>0) bottom=Math.max(bottom,r.bottom);
      });
      if(src){
        gap=Math.round(src.getBoundingClientRect().top-bottom);
      }else{
        // IG 模式冇 .src：量最後一個區塊底 → frame 底的空白
        gap=Math.round(f.getBoundingClientRect().bottom-bottom);
      }
      rows.push({
        f: c.dataset.filename || 'card',
        sh: f.scrollHeight,
        ch: f.clientHeight,
        over: f.scrollHeight - f.clientHeight,
        gap: gap,
        src: !!src,
        blocks: blocks
      });
    });
    finish(rows);
  }
  if(document.fonts&&document.fonts.ready){ document.fonts.ready.then(function(){setTimeout(run,1400);}); }
  else { setTimeout(run,2800); }
})();
"""


def find_browser(explicit=None):
    if explicit:
        return explicit
    for p in CHROME_CANDIDATES:
        if pathlib.Path(p).exists():
            return p
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        f = shutil.which(name)
        if f:
            return f
    home = pathlib.Path.home() / ".agent-browser" / "browsers"
    if home.exists():
        for exe in home.glob("chrome-*/chrome.exe"):
            return str(exe)
    raise SystemExit("找不到 Chrome / Edge，請用 --chrome <path> 指定。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--chrome", default=None)
    ap.add_argument("--wait", type=int, default=18000)
    ap.add_argument("--tolerance", type=int, default=2, help="容許的溢出像素")
    ap.add_argument("--empty", type=int, default=300, help="留白超過幾 px 就提示偏空")
    ap.add_argument("--require-src", action="store_true",
                    help="要求每張卡都有 .src 來源區塊（客戶懶人包模式必開）")
    args = ap.parse_args()

    src = pathlib.Path(args.html).resolve()
    if not src.exists():
        raise SystemExit(f"檔案不存在：{src}")
    browser = find_browser(args.chrome)

    html = src.read_text(encoding="utf-8")
    html = html.replace("</body>", "<script>" + PROBE + "</script></body>", 1)

    # 走臨時 http server：file:// 下字型會被 CORS 擋，量到的高度係錯的
    tmp = src.parent / "_fit_probe.html"
    tmp.write_text(html, encoding="utf-8")
    try:
        with _serve.serve(src.parent) as base:
            r = subprocess.run([
                browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                "--window-size=1200,2200", f"--virtual-time-budget={args.wait}",
                "--dump-dom", _serve.url(base, tmp, src.parent),
            ], capture_output=True, text=True)
            dom = r.stdout or ""
    finally:
        tmp.unlink(missing_ok=True)

    m = re.search(r'<pre id="__fit"[^>]*>(.*?)</pre>', dom, re.S)
    if not m:
        print("⚠ 取不到量測結果（頁面可能沒載入完）")
        sys.exit(2)
    rows = json.loads(html_mod.unescape(m.group(1)))
    if not rows:
        print("⚠ 找不到 .card / .frame 結構，請確認這是本 skill 產出的 HTML。")
        sys.exit(2)

    print(f"{'卡片':<20}{'內容高':>8}{'可用高':>8}{'溢出':>8}{'留白':>8}  狀態")
    print("-" * 62)
    bad, empty, nosrc = [], [], []
    for r in rows:
        over, gap = r["over"], r.get("gap")
        if over > args.tolerance:
            status, note = "✗ 溢出", f"多出 {over}px"
            bad.append(r["f"])
        elif args.require_src and not r.get("src"):
            status, note = "✗ 缺來源", "沒有 .src 區塊"
            nosrc.append(r["f"])
        elif gap is not None and gap > args.empty:
            status, note = "△ 偏空", "封面／少內容頁正常，內頁要留意"
            empty.append(r["f"])
        else:
            status, note = "✓", ""
        gap_s = "—" if gap is None else str(gap)
        print(f"{r['f']:<20}{r['sh']:>8}{r['ch']:>8}{over:>8}{gap_s:>8}  {status} {note}")
        if r.get("blocks"):
            print("      區塊高度：" + " / ".join(f"{b['cls'] or '-'} {b['h']}" for b in r["blocks"]))

    print()
    if bad:
        print(f"✗ {len(bad)} 張溢出，會被 overflow:hidden 裁掉：{bad}")
        print("  修法：減字、精簡要點至三條、或把該區塊字級降一級。")
        sys.exit(1)
    if nosrc:
        print(f"✗ {len(nosrc)} 張沒有來源區塊：{nosrc}（來源是這類內容的執照，不可省）")
        sys.exit(1)
    if not args.require_src:
        print("  （未開 --require-src：IG 模式不要求 .src）")
    print("✓ 全部裝得下，沒有裁切。")
    if empty:
        print(f"  △ 留白較多：{empty}——封面與「所以呢」頁正常，若係內容頁可考慮放大字級。")


if __name__ == "__main__":
    main()
