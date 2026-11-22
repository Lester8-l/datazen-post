#!/usr/bin/env python3
"""Embed complete editable font faces and a compact first-export copy.

Normally use: python scripts/build-embed-fonts.py deck.html
Use --extra to include planned terms in the compact copy.
Use --face FAMILY WEIGHT FONT_FILE FACE_INDEX to add a local face.
Use --only-faces for a custom deck that already defines its font roles.
"""
import argparse
import base64
from dataclasses import dataclass
from html.parser import HTMLParser
from importlib.util import find_spec
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

SKILL = Path(__file__).resolve().parent.parent
FONT_DIR = SKILL / "assets" / "fonts"
ALWAYS = "".join(chr(codepoint) for codepoint in range(32, 127)) + "　、。！？；：「」『』（）《》〈〉…—·＋－×÷％‰°→０１２３４５６７８９"
FLAVOR = "woff2" if find_spec("brotli") else "woff"
FONT_TAG = re.compile(
    r'<(?P<tag>script|style)\b[^>]*\bid=["\']dz-(?:fonts|edit-fonts|font-plan|font-legacy)["\'][^>]*>.*?</(?P=tag)>',
    re.S | re.I,
)
EXISTING_EDITOR = re.compile(r'<script id="dz-editor-runtime"[^>]*>.*?</script>', re.S)


@dataclass(frozen=True)
class Face:
    family: str
    weight: int
    file: Path
    index: int = 0


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = False
        self.segments = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = False

    def handle_data(self, data):
        if not self.hidden:
            self.segments.append(data)


def visible_text(document):
    reader = VisibleText()
    reader.feed(document)
    return "".join(reader.segments)


def desktop_face(family, query, weight):
    windows = os.environ.get("WINDIR")
    if windows and query.startswith("Noto Serif"):
        for name in ("NotoSerifTC-VF.ttf", "NotoSerifHK-VF.ttf"):
            path = Path(windows) / "Fonts" / name
            if path.is_file():
                return Face(family, weight, path)
    matcher = shutil.which("fc-match")
    if not matcher:
        return None
    result = subprocess.run(
        [matcher, "-f", "%{family}\n%{file}\n%{index}\n", query],
        capture_output=True, text=True, check=False,
    )
    lines = result.stdout.splitlines()
    if len(lines) == 3 and query.split(":")[0].casefold() in lines[0].casefold():
        return Face(family, weight, Path(lines[1]), int(lines[2]))
    return None


def default_faces():
    faces = [
        Face("Iansui Local", 400, FONT_DIR / "iansui.ttf"),
        Face("LXGW Local", 400, FONT_DIR / "lxgw-wenkai-tc.ttf"),
    ]
    desktop = [
        ("Noto Serif TC", "Noto Serif CJK TC:style=Regular", 400),
        ("Noto Serif TC", "Noto Serif CJK TC:style=Bold", 700),
        ("JetBrains Mono", "JetBrains Mono", 400),
        ("Cormorant Garamond", "Cormorant Garamond", 400),
    ]
    faces.extend(face for family, query, weight in desktop if (face := desktop_face(family, query, weight)))
    return faces


def font_object(face):
    font = TTFont(face.file, fontNumber=face.index, recalcTimestamp=False)
    if "fvar" in font:
        axes = {axis.axisTag for axis in font["fvar"].axes}
        if "wght" in axes:
            instantiateVariableFont(font, {"wght": face.weight}, inplace=True)
    return font


def serialise(font):
    font.flavor = FLAVOR
    stream = io.BytesIO()
    font.save(stream)
    return stream.getvalue()


def declaration(face, data):
    family = json.dumps(face.family, ensure_ascii=False)
    b64 = base64.b64encode(data).decode("ascii")
    return ('@font-face{font-family:%s;font-weight:%d;font-display:block;'
            'src:url(data:font/%s;base64,%s) format("%s")}' %
            (family, face.weight, FLAVOR, b64, FLAVOR))


def codepoint_ranges(points):
    groups = []
    for point in sorted(points):
        if groups and groups[-1][1] + 1 == point:
            groups[-1][1] = point
        else:
            groups.append([point, point])
    return groups


def font_bank(document, faces, extra=""):
    chars = "".join(sorted(set(visible_text(document) + ALWAYS + extra)))
    full_css = []
    compact_css = []
    coverage = {}
    for face in faces:
        if not face.file.is_file():
            raise FileNotFoundError(f"缺字型檔案：{face.file}")
        font = font_object(face)
        points = set(font.getBestCmap() or {})
        if not points:
            raise ValueError(f"字型冇有效字集：{face.file}")
        coverage.setdefault(face.family.lower(), set()).update(points)
        full = serialise(font)
        full_css.append(declaration(face, full))
        options = subset.Options()
        options.flavor = FLAVOR
        options.name_IDs = ["*"]
        options.drop_tables += ["FFTM"]
        small = subset.Subsetter(options=options)
        small.populate(text=chars)
        small.subset(font)
        compact = serialise(font)
        compact_css.append(declaration(face, compact))
        font.close()
        print(f"{face.family} {face.weight}: {len(points):,} 字元，完整 {len(full):,} bytes，精簡 {len(compact):,} bytes")
    return "\n".join(full_css), {
        "compactChars": chars,
        "compactCSS": "\n".join(compact_css),
        "coverage": {family: codepoint_ranges(points) for family, points in coverage.items()},
    }


def embed(document, faces, extra="", overrides=""):
    document = FONT_TAG.sub("", document)
    css, plan = font_bank(document, faces, extra)
    payload = json.dumps(plan, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    tags = (
        f'<style id="dz-edit-fonts">{css}\n{overrides}</style>\n'
        f'<script type="application/json" id="dz-font-plan">{payload}</script>\n'
        '<script id="dz-font-legacy">window.__EMBED_CSS='
        'Array.from(document.getElementById("dz-edit-fonts").sheet.cssRules)'
        '.filter(rule=>rule.type===CSSRule.FONT_FACE_RULE).map(rule=>rule.cssText).join("\\n");</script>\n'
    )
    if "</head>" not in document:
        raise ValueError("HTML 需要有 </head>。")
    document = document.replace("</head>", tags + "</head>", 1)
    if EXISTING_EDITOR.search(document):
        source = (SKILL / "assets" / "text-editor.js").read_text(encoding="utf-8")
        block = '<script id="dz-editor-runtime">\n' + source + '</script>'
        document = EXISTING_EDITOR.sub(lambda _: block, document, count=1)
    return document


def default_overrides(faces):
    families = {face.family for face in faces}
    serif = '"Noto Serif TC","LXGW Local",serif' if "Noto Serif TC" in families else '"LXGW Local",serif'
    mono = ('"JetBrains Mono",' if "JetBrains Mono" in families else "ui-monospace,") + '"LXGW Local",monospace'
    digits = ('"Cormorant Garamond",' if "Cormorant Garamond" in families else "") + serif
    return (
        ":root{" + f'--serif:{serif};--soft:"LXGW Local",{serif};'
        f'--hand:"Iansui Local","LXGW Local",{serif};--sans:{serif};--mono:{mono};--en:{digits}' + "}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--extra", default="")
    parser.add_argument("--face", action="append", nargs=4, default=[], metavar=("FAMILY", "WEIGHT", "FILE", "INDEX"))
    parser.add_argument("--only-faces", action="store_true")
    args = parser.parse_args()
    faces = [] if args.only_faces else default_faces()
    indexed = {(face.family, face.weight): face for face in faces}
    for family, weight, file, index in args.face:
        face = Face(family, int(weight), Path(file), int(index))
        indexed[(face.family, face.weight)] = face
    faces = list(indexed.values())
    if not faces:
        parser.error("至少提供一套完整字型。")
    html = args.deck.read_text(encoding="utf-8")
    output = embed(html, faces, args.extra, "" if args.only_faces else default_overrides(faces))
    if not args.dry_run:
        args.deck.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()

