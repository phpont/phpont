#!/usr/bin/env python3
"""Create a Windows-friendly local review page for generated profile assets."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / ".profile" / "preview"
ASSETS = ("dark_mode.svg", "light_mode.svg", "dark_mode.gif", "light_mode.gif")
FRAME_SELECTION = (0, 1, 2, 5, 13, 18, 22, 27, 30, 32, 33)


def write_contact_sheet(theme: str) -> Path:
    source = ROOT / f"{theme}_mode.gif"
    with Image.open(source) as image:
        cards = []
        for frame_number in FRAME_SELECTION:
            image.seek(frame_number)
            cards.append(image.convert("RGBA").resize((488, 230)))
    background = (13, 17, 23, 255) if theme == "dark" else (246, 248, 250, 255)
    foreground = (201, 209, 217, 255) if theme == "dark" else (36, 41, 47, 255)
    rows = (len(cards) + 1) // 2
    sheet = Image.new("RGBA", (976, rows * 230), background)
    draw = ImageDraw.Draw(sheet)
    for index, card in enumerate(cards):
        x, y = (index % 2) * 488, (index // 2) * 230
        sheet.alpha_composite(card, (x, y))
        draw.rectangle((x, y, x + 72, y + 18), fill=background)
        draw.text((x + 5, y + 3), f"frame {FRAME_SELECTION[index]}", fill=foreground)
    output = PREVIEW / f"{theme}-frames.png"
    sheet.convert("RGB").save(output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--open", action="store_true", help="open the generated preview with the Windows default browser")
    args = parser.parse_args()
    missing = [asset for asset in ASSETS if not (ROOT / asset).is_file()]
    if missing:
        raise SystemExit("render the profile first; missing: " + ", ".join(missing))
    PREVIEW.mkdir(parents=True, exist_ok=True)
    write_contact_sheet("dark")
    write_contact_sheet("light")
    picture = '''<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../dark_mode.gif">
  <source media="(prefers-color-scheme: light)" srcset="../../light_mode.gif">
  <img src="../../dark_mode.gif" alt="README picture runtime">
</picture>'''
    html = f'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>phpont profile preview</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;font:14px/1.4 system-ui,sans-serif}}section{{padding:28px}}h1{{font-size:18px;margin:0 0 16px}}h2{{font-size:14px;margin:28px 0 12px}}img{{display:block;width:100%;height:auto;border-radius:8px}}.dark{{background:#0d1117;color:#c9d1d9}}.light{{background:#fff;color:#24292f}}.desktop{{max-width:896px;margin:auto}}.mobile{{max-width:390px;margin:auto}}.sheet{{max-width:976px;margin:auto}}.note{{max-width:896px;margin:0 auto 16px;color:inherit;opacity:.8}}
</style>
<section class="dark"><div class="desktop"><h1>Dark static SVG — desktop width</h1><img src="../../dark_mode.svg" alt="Dark static profile"></div><div class="mobile"><h2>Dark static SVG — reduced width</h2><img src="../../dark_mode.svg" alt="Dark static profile at reduced width"></div></section>
<section class="light"><div class="desktop"><h1>Light static SVG — desktop width</h1><img src="../../light_mode.svg" alt="Light static profile"></div><div class="mobile"><h2>Light static SVG — reduced width</h2><img src="../../light_mode.svg" alt="Light static profile at reduced width"></div></section>
<section class="dark"><div class="desktop"><h1>Dark GIF — desktop width</h1><img src="../../dark_mode.gif" alt="Dark animated profile"></div><div class="mobile"><h2>Dark GIF — reduced width</h2><img src="../../dark_mode.gif" alt="Dark animated profile at reduced width"></div></section>
<section class="light"><div class="desktop"><h1>Light GIF — desktop width</h1><img src="../../light_mode.gif" alt="Light animated profile"></div><div class="mobile"><h2>Light GIF — reduced width</h2><img src="../../light_mode.gif" alt="Light animated profile at reduced width"></div></section>
<section class="dark"><div class="desktop"><h1>README picture runtime — browser-selected theme</h1><p class="note">This is the actual README picture markup. Its theme follows the browser preference; the explicit dark/light sections above are the visual comparison reference.</p>{picture}</div></section>
<section class="dark"><div class="sheet"><h1>Dark GIF typing timeline</h1><p class="note">Complete, reset, phpont, OS partial, configuration middle, Languages partial, Contact, Mail partial, final blink, glitch and static final.</p><img src="dark-frames.png" alt="Dark GIF typing timeline contact sheet"></div></section>
<section class="light"><div class="sheet"><h1>Light GIF typing timeline</h1><p class="note">Complete, reset, phpont, OS partial, configuration middle, Languages partial, Contact, Mail partial, final blink, glitch and static final.</p><img src="light-frames.png" alt="Light GIF typing timeline contact sheet"></div></section>
</html>'''
    output = PREVIEW / "index.html"
    output.write_text(html, encoding="utf-8", newline="\n")
    if args.open:
        if os.name != "nt":
            raise SystemExit("--open is supported only on Windows; open the printed path manually.")
        os.startfile(output)  # type: ignore[attr-defined]
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
