#!/usr/bin/env python3
"""
對比度守門員：白字壓在霧上，到底睇唔睇得清？

用法:
    python check-contrast.py out/                 # 量一個資料夾內所有 PNG
    python check-contrast.py out/01-cover.png ...  # 或指定檔案

原理:
    1. 讀 PNG 每個像素的相對亮度（WCAG 定義）。
    2. 排除近白像素（L > 0.62）＝文字本身，剩返的就是「底色」。
    3. 取底色的 p50（中位）與 p98（最亮的 2%，即霧心）。
    4. 用白字（#FFFDF8）計對比：
         對比 = (1.05) / (L + 0.05)
    5. 中位 < --min（預設 4.5）→ 正文不合格，exit 1。
       p98 < --min-large（預設 3.0）→ 若該處有大字則仍可接受，只警告。

為什麼要量？
    「感覺睇得清」係不可靠的。中明度的水彩霧，肉眼覺得「柔和、有氣氛」，
    實際對比可能只有 3.6:1 —— 手機細字就開始糊。
    人的眼睛會適應低對比，數字不會。
"""
import argparse
import pathlib
import sys

try:
    from PIL import Image
    import numpy as np
except ImportError:
    raise SystemExit("需要 pillow 同 numpy：pip install pillow numpy")


def srgb_to_lin(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def analyse(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    lum = 0.2126 * srgb_to_lin(a[:, :, 0]) \
        + 0.7152 * srgb_to_lin(a[:, :, 1]) \
        + 0.0722 * srgb_to_lin(a[:, :, 2])
    bg = lum[lum < 0.62]
    if bg.size < 1000:
        return None
    p50, p98 = np.percentile(bg, [50, 98])
    cr = lambda l: 1.05 / (l + 0.05)  # noqa: E731
    return float(p50), float(p98), float(cr(p50)), float(cr(p98))


def collect(paths):
    files = []
    for p in paths:
        p = pathlib.Path(p)
        if p.is_dir():
            files += sorted(p.glob("*.png"))
        elif p.suffix.lower() == ".png":
            files.append(p)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="PNG 檔案或資料夾")
    ap.add_argument("--min", type=float, default=4.5, help="正文最低對比（WCAG AA）")
    ap.add_argument("--min-large", type=float, default=3.0, help="大字最低對比")
    args = ap.parse_args()

    files = collect(args.paths)
    if not files:
        raise SystemExit("找不到 PNG。先跑 export-png.py。")

    print(f"{'卡片':<26}{'底色 L(p50)':>12}{'霧心 L(p98)':>12}{'正文對比':>10}{'霧心對比':>10}")
    print("-" * 74)
    bad, warn = [], []
    for f in files:
        r = analyse(f)
        if r is None:
            print(f"{f.stem:<26}{'—':>12}{'—':>12}{'—':>10}{'—':>10}  （幾乎全白，跳過）")
            continue
        p50, p98, c50, c98 = r
        flag = ""
        if c50 < args.min:
            flag = " ✗ 正文太淡"
            bad.append(f.stem)
        elif c98 < args.min_large:
            flag = " △ 霧心偏亮"
            warn.append(f.stem)
        else:
            flag = " ✓"
        print(f"{f.stem:<26}{p50:>12.3f}{p98:>12.3f}{c50:>9.2f}:1{c98:>9.2f}:1{flag}")

    print()
    if bad:
        print(f"✗ {len(bad)} 張正文對比不足 {args.min}:1：{bad}")
        print("  修法：霧底壓深、把 scrim 加重、或提高文字透明度／字級。不要靠加粗硬撐。")
        sys.exit(1)
    print(f"✓ 全部過關（正文 ≥ {args.min}:1）。")
    if warn:
        print(f"  △ 霧心偏亮（<{args.min_large}:1）：{warn}——該處只可以放 100px 以上的大字。")


if __name__ == "__main__":
    main()
