"""Render labeled PNG excerpts from the verified Markdown fixtures using Pillow."""
from pathlib import Path
import hashlib
import re

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT_CANDIDATES = ["/System/Library/Fonts/Menlo.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]
font_path = next((p for p in FONT_CANDIDATES if Path(p).exists()), None)
font = ImageFont.truetype(font_path, 19) if font_path else ImageFont.load_default(size=19)
title_font = ImageFont.truetype(font_path, 27) if font_path else ImageFont.load_default(size=27)
width, padding, line_height = 1200, 44, 29


def render(name, fixture):
    content = fixture.read_text(encoding="utf-8")
    selected, section, warnings = [], "", 0
    for line in content.splitlines():
        if line.startswith("### "):
            section = line[4:]
        if section == "Recommendations":
            continue
        if section == "Inputs and assumptions" and line.startswith("- ") and not any(k in line for k in ("applied:", "defaulted fields:")):
            continue
        if section == "Warnings" and line.startswith("- "):
            warnings += 1
            if warnings > 2:
                continue
        selected.append(re.sub(r"\\([\\`*_{}\[\]()#+!|~])", r"\1", line))
    draw = ImageDraw.Draw(Image.new("RGB", (width, 100)))
    rows = []
    for line in selected:
        remaining = line
        while draw.textlength(remaining, font=font) > width - 2 * padding:
            cut = len(remaining)
            while draw.textlength(remaining[:cut], font=font) > width - 2 * padding:
                cut -= 1
            space = remaining.rfind(" ", 0, cut)
            cut = space if space > 0 else cut
            rows.append(remaining[:cut])
            remaining = remaining[cut:].lstrip()
        rows.append(remaining)
    image = Image.new("RGB", (width, 165 + line_height * len(rows)), "#fafbfc")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 104), fill="#17392e")
    draw.text((padding, 20), "TrainCost CI | " + name, fill="white", font=title_font)
    draw.text((padding, 63), "Local fixture excerpt. Not a GitHub screenshot.", fill="#d9e8df", font=font)
    y = 125
    for row in rows:
        draw.text((padding, y), row, fill="#15242d", font=font)
        y += line_height
    digest = hashlib.sha256(fixture.read_bytes()).hexdigest()[:16]
    draw.text((padding, y + 6), "Source SHA-256: " + digest + " | Full Markdown linked in demo docs", fill="#475b67", font=font)
    dest = ROOT / "docs/assets" / (name + "-report.png")
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest)
    print(f"Rendered {dest.relative_to(ROOT)} ({image.width}x{image.height})")


for name, filename in (("risk", "expected-report.md"), ("missing", "expected-missing-report.md"), ("invalid", "expected-invalid-report.md")):
    render(name, ROOT / "examples/pytorch-demo" / filename)
