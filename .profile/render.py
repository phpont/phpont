#!/usr/bin/env python3
"""Generate deterministic static and declarative-vector profile SVG assets."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / ".profile"
TEMPLATE_PATH = PROFILE_DIR / "templates" / "profile.svg.tpl"
DATA_PATH = PROFILE_DIR / "profile.json"
CANVAS = (975, 460)
TIMEZONE = ZoneInfo("America/Sao_Paulo")
INFO_X = 380
FONT_SIZE = 17
PAGES_BASE_URL = "https://phpont.github.io/phpont"

# The original profile skull, preserved character-for-character as its source text.
ASCII_LINES = (
    "                      :::!~!!!!!:.                   ",
    "                  .xUHWH!! !!?M88WHX:.             ",
    "                .X*#M@$!!  !X!M$$$$$$WWx:.         ",
    "               :!!!!!!?H! :!$!$$$$$$$$$$8X:        ",
    "              !!~  ~:~!! :~!$!#$$$$$$$$$$8X:       ",
    "             :!~::!H!    ~.U$X!?R$$$$$$$$MM!      ",
    "             ~!~!!!!~~ .:XW$$$U!!?$$$$$$RMM!       ",
    "               !:~~~ .:!M\"T#$$$$WX??#MRRMMM!       ",
    "               ~?WuxiW*`   `\"#$$$$8!!!!??!!!      ",
    "             :X- M$$$$       `\"T#$T~!8$WUXU~      ",
    "            :%`  ~#$$$m:        ~!~ ?$$$$$$       ",
    "          :!`.-   ~T$$$$8xx.  .xWW- ~\"\"##*\"       ",
    ".....   -~~:<` !    ~?T#$$@@W@*?$$      /`        ",
    "W$@@M!!! .!~~ !!     .:XUW$W!~ `\"~:    :          ",
    "#\"~~`.:x%`!!  !H:   !WM$$$$Ti.: .!WUn+!`         ",
    ":::~:!!`:X~ .: ?H.!u \"$$$B$$$!W:U!T$$M~          ",
    ".~~   :X@!.-~   ?@WTWo(\"*$$$W$TH$! `            ",
    "Wi.~!X$?!-~    : ?$$$B$Wu(\"**$RM!               ",
    "$R@i.~~ !     :   ~$$$$$B$$en:``                ",
    "?MXT@Wx.~    :     ~\"##*$$$$M~                  ",
)
THEMES = {
    "dark": {"BACKGROUND": "#161b22", "BORDER": "#30363d", "PRIMARY": "#c9d1d9", "MUTED": "#8b949e", "KEY": "#ffa657", "VALUE": "#a5d6ff"},
    "light": {"BACKGROUND": "#f6f8fa", "BORDER": "#d0d7de", "PRIMARY": "#24292f", "MUTED": "#57606a", "KEY": "#953800", "VALUE": "#0a3069"},
}


@dataclass(frozen=True)
class ProfileField:
    key: str
    value: str
    y: int


@dataclass(frozen=True)
class AnimationState:
    duration: int
    ascii_lines: int
    header_chars: int = 0
    header_separator: bool = False
    completed_fields: int = 0
    active_field: int | None = None
    active_chars: int = 0
    contact_visible: bool = False
    cursor_visible: bool = False
    cursor_field: int | None = None
    cursor_header: bool = False
    glitch: bool = False


TYPING_CHUNKS = ((6, 16), (3, 8), (4,), (3,), (7, 17), (8, 22), (6, 18), (9, 20, 31), (8, 19), (7, 16), (7, 17), (8, 17, 23))
README_TEMPLATE = '''<picture>
  <source media="(prefers-color-scheme: dark)" srcset="{pages_base}/profile-dark.svg?v={dark_hash}">
  <source media="(prefers-color-scheme: light)" srcset="{pages_base}/profile-light.svg?v={light_hash}">
  <img alt="phpont profile terminal: Full Stack Developer focused on Web Security and Rust, using Debian, Niri and zsh." src="dark_mode.svg" width="975" height="460">
</picture>
'''
PAGES_INDEX = '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>phpont profile SVG diagnostics</title>
<style>*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,sans-serif;background:#0d1117;color:#c9d1d9}.light{background:#fff;color:#24292f}section{padding:28px}.wrap{max-width:976px;margin:auto}h1{font-size:20px;margin:0 0 16px}h2{font-size:15px;margin:28px 0 10px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}figure{margin:0}figcaption{font-weight:600;margin:0 0 8px}img{display:block;width:100%;height:auto;border-radius:8px}.narrow{max-width:390px}</style>
<section><div class="wrap"><h1>Animated dark</h1><img src="profile-dark.svg" alt="Animated dark profile SVG"><div class="narrow"><h2>Reduced width</h2><img src="profile-dark.svg" alt="Animated dark profile SVG at reduced width"></div></div></section>
<section class="light"><div class="wrap"><h1>Animated light</h1><img src="profile-light.svg" alt="Animated light profile SVG"><div class="narrow"><h2>Reduced width</h2><img src="profile-light.svg" alt="Animated light profile SVG at reduced width"></div></div></section>
<section><div class="wrap"><h1>Static dark / light</h1><div class="grid"><figure><figcaption>Static dark</figcaption><img src="static-dark.svg" alt="Static dark profile SVG"></figure><figure><figcaption>Static light</figcaption><img src="static-light.svg" alt="Static light profile SVG"></figure></div></div></section>
<section class="light"><div class="wrap"><h1>Compatibility probe</h1><img src="compatibility.svg" alt="Declarative SVG animation compatibility probe"></div></section>
</html>
'''


def parse_iso_date(value: str, variable_name: str) -> date:
    try: return date.fromisoformat(value)
    except ValueError as error: raise ValueError(f"{variable_name} must use YYYY-MM-DD; received {value!r}.") from error


def current_profile_date(render_date: str | None = None) -> date:
    value = render_date if render_date is not None else os.environ.get("PROFILE_RENDER_DATE")
    return parse_iso_date(value, "PROFILE_RENDER_DATE") if value else datetime.now(TIMEZONE).date()


def calculate_age(birth_date: date, on_date: date) -> int:
    if birth_date > on_date: raise ValueError("PROFILE_BIRTH_DATE cannot be in the future relative to the render date.")
    years = on_date.year - birth_date.year
    try: anniversary = birth_date.replace(year=on_date.year)
    except ValueError: anniversary = date(on_date.year, 2, 28)
    return years - (on_date < anniversary)


def birth_date_from_environment(value: str | None = None) -> date:
    raw = value if value is not None else os.environ.get("PROFILE_BIRTH_DATE")
    if not raw: raise ValueError("PROFILE_BIRTH_DATE is required (YYYY-MM-DD) and must not be committed to the repository.")
    return parse_iso_date(raw, "PROFILE_BIRTH_DATE")


def load_data() -> dict[str, str]:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    required = {"name", "os", "wm", "shell", "editor", "kernel", "focus", "languages_programming", "languages_real", "web", "instagram", "mail"}
    missing = required - data.keys()
    if missing: raise ValueError(f"profile.json is missing required keys: {', '.join(sorted(missing))}")
    return {key: str(value) for key, value in data.items()}


def fields(data: dict[str, str], age: int) -> tuple[ProfileField, ...]:
    return (
        ProfileField("OS", data["os"], 90), ProfileField("Uptime", f"{age} years", 110), ProfileField("WM", data["wm"], 130), ProfileField("Shell", data["shell"], 150),
        ProfileField("Editor", data["editor"], 170), ProfileField("Kernel", data["kernel"], 190), ProfileField("Focus", data["focus"], 210),
        ProfileField("Languages.Programming", data["languages_programming"], 250), ProfileField("Languages.Real", data["languages_real"], 270),
        ProfileField("Web", data["web"], 370), ProfileField("Instagram", data["instagram"], 390), ProfileField("Mail", data["mail"], 410),
    )


def typing_prefix_lengths(value: str, chunks: tuple[int, ...]) -> tuple[int, ...]:
    endpoints: list[int] = []
    for chunk in chunks:
        endpoint = min(len(value), chunk)
        if not endpoints or endpoint > endpoints[-1]: endpoints.append(endpoint)
    if not endpoints or endpoints[-1] != len(value): endpoints.append(len(value))
    return tuple(endpoints)


def typing_prefixes(value: str, chunks: tuple[int, ...]) -> tuple[str, ...]: return tuple(value[:length] for length in typing_prefix_lengths(value, chunks))


def ascii_lines_for_step(step: int, total_steps: int) -> int:
    milestones = (9, 12, 15, 18, len(ASCII_LINES))
    return milestones[min(len(milestones) - 1, (step * len(milestones)) // max(total_steps, 1))]


def build_timeline(data: dict[str, str], age: int) -> tuple[AnimationState, ...]:
    profile_fields = fields(data, age)
    states = [AnimationState(100, len(ASCII_LINES), len(data["name"]), True, len(profile_fields), contact_visible=True), AnimationState(70, 0), AnimationState(55, 3, 3, cursor_visible=True, cursor_header=True), AnimationState(55, 6, len(data["name"]), cursor_visible=True, cursor_header=True), AnimationState(55, 9, len(data["name"]), True)]
    typed, completed = [], 0
    for index, field in enumerate(profile_fields):
        for endpoint in typing_prefix_lengths(field.value, TYPING_CHUNKS[index]): typed.append(AnimationState(50, 0, len(data["name"]), True, completed, index, endpoint, index >= 9, True, index))
        completed += 1
    states.extend(AnimationState(**{**state.__dict__, "ascii_lines": ascii_lines_for_step(index, len(typed))}) for index, state in enumerate(typed))
    mail_index = len(profile_fields) - 1
    states.extend((AnimationState(60, len(ASCII_LINES), len(data["name"]), True, len(profile_fields), contact_visible=True), AnimationState(60, len(ASCII_LINES), len(data["name"]), True, len(profile_fields), contact_visible=True, cursor_visible=True, cursor_field=mail_index), AnimationState(110, len(ASCII_LINES), len(data["name"]), True, len(profile_fields), contact_visible=True), AnimationState(40, len(ASCII_LINES), len(data["name"]), True, len(profile_fields), contact_visible=True, glitch=True), AnimationState(220, len(ASCII_LINES), len(data["name"]), True, len(profile_fields), contact_visible=True)))
    return tuple(states)


def text(x: float, y: int, value: str, class_name: str = "") -> str:
    return f'<text x="{x:g}" y="{y}"{f" class=\"{class_name}\"" if class_name else ""}>{html.escape(value)}</text>'


def field_markup(field: ProfileField, value: str) -> str: return f'<text x="{INFO_X}" y="{field.y}"><tspan class="key">{html.escape(field.key)}</tspan><tspan class="primary">: </tspan><tspan class="value">{html.escape(value)}</tspan></text>'


def ascii_markup(visible_lines: int, glitch: bool = False, reusable: bool = False) -> str:
    result = []
    for index in range(visible_lines):
        if reusable and not (glitch and index in (8, 9, 13, 14)): result.append(f'<use href="#ascii-line-{index}"/>')
        else:
            shift = 2 if glitch and index in (8, 9) else -1 if glitch and index in (13, 14) else 0
            result.append(text(-50 + shift, 35 + index * 20, ASCII_LINES[index], "primary"))
    return "\n      ".join(result)


def content_markup(data: dict[str, str], age: int, state: AnimationState, reusable_ascii: bool = False) -> str:
    chunks = []
    if state.ascii_lines: chunks.append(f'<g clip-path="url(#ascii-viewport)">{ascii_markup(state.ascii_lines, state.glitch, reusable_ascii)}</g>')
    if state.header_chars: chunks.append(text(INFO_X, 40, data["name"][:state.header_chars], "primary"))
    if state.header_separator: chunks.append(text(INFO_X, 60, "──────", "muted"))
    profile_fields = fields(data, age)
    chunks.extend(field_markup(field, field.value) for field in profile_fields[:state.completed_fields])
    if state.contact_visible: chunks.extend((text(INFO_X, 320, "Contact", "primary"), text(INFO_X, 340, "──────", "muted")))
    if state.active_field is not None:
        active = profile_fields[state.active_field]
        chunks.append(field_markup(active, active.value[:state.active_chars]))
    if state.cursor_visible:
        if state.cursor_header: cursor_x, baseline, color = INFO_X + len(data["name"][:state.header_chars]) * FONT_SIZE * .6, 40, "cursor-primary"
        else:
            active = profile_fields[state.cursor_field or 0]; prefix = active.value[:state.active_chars] if state.active_field == state.cursor_field else active.value
            cursor_x, baseline, color = INFO_X + (len(active.key) + 2 + len(prefix)) * FONT_SIZE * .6, active.y, "cursor-value"
        chunks.append(f'<rect class="{color}" x="{cursor_x + 2:.2f}" y="{baseline - 14}" width="6" height="15"/>')
    return "\n    ".join(chunks)


def strict_template(template: str, values: dict[str, str]) -> str:
    expected = set(re.findall(r"\{\{([A-Z_]+)\}\}", template))
    if expected != set(values): raise ValueError(f"template placeholders mismatch; expected {sorted(expected)}, supplied {sorted(values)}")
    for key, value in values.items(): template = template.replace("{{" + key + "}}", value)
    return template


def document(theme_name: str, body: str) -> str:
    values = dict(THEMES[theme_name]); values.update({"FONT_SIZE": str(FONT_SIZE), "BODY": body})
    return strict_template(TEMPLATE_PATH.read_text(encoding="utf-8"), values)


def final_state(data: dict[str, str], age: int) -> AnimationState: return AnimationState(0, len(ASCII_LINES), len(data["name"]), True, len(fields(data, age)), contact_visible=True)


def static_svg(theme_name: str, data: dict[str, str], age: int) -> str: return document(theme_name, f'<defs><clipPath id="ascii-viewport"><rect x="0" y="18" width="365" height="420"/></clipPath></defs>\n  <g id="final-state" data-final-state="true">\n    <rect x="0" y="0" width="975" height="460" rx="14" class="panel"/>\n    {content_markup(data, age, final_state(data, age))}\n  </g>')


def animated_svg(theme_name: str, data: dict[str, str], age: int) -> str:
    definitions = "\n      ".join(f'<text id="ascii-line-{index}" x="-50" y="{35 + index * 20}" class="primary">{html.escape(line)}</text>' for index, line in enumerate(ASCII_LINES))
    states, start = [], 100
    for index, state in enumerate(build_timeline(data, age)):
        glitch_attribute = ' data-glitch="true"' if state.glitch else ""
        states.append(f'<g id="state-{index:02d}" data-animation-state="{index}"{glitch_attribute} visibility="hidden"><set attributeName="visibility" to="visible" begin="{start}ms" dur="{state.duration}ms" fill="remove"/><use href="#panel"/>{content_markup(data, age, state, True)}</g>')
        start += state.duration
    body = f'''<defs><clipPath id="ascii-viewport"><rect x="0" y="18" width="365" height="420"/></clipPath><g id="panel"><rect x="0" y="0" width="975" height="460" rx="14" class="panel"/></g><g id="ascii-lines">{definitions}</g></defs>
  <g id="final-state" data-final-state="true"><use href="#panel"/>{content_markup(data, age, final_state(data, age), True)}</g>
  <g id="animation-overlay" data-animation-overlay="true" visibility="hidden" data-duration-ms="{start}"><set attributeName="visibility" to="visible" begin="100ms" dur="{start - 100}ms" fill="remove"/>{''.join(states)}</g>'''
    return document(theme_name, body)


def compatibility_svg() -> str:
    body = '''<g id="final-state" data-final-state="true"><rect x="0" y="0" width="975" height="460" rx="14" class="panel"/><text x="64" y="120" class="primary">phpont</text><text x="64" y="170"><tspan class="key">OS</tspan><tspan class="primary">: </tspan><tspan class="value">Debian GNU/Linux</tspan></text></g>
  <g id="animation-overlay" data-animation-overlay="true" visibility="hidden" data-duration-ms="1100"><set attributeName="visibility" to="visible" begin="100ms" dur="1000ms" fill="remove"/><g visibility="hidden"><set attributeName="visibility" to="visible" begin="100ms" dur="180ms" fill="remove"/><rect x="0" y="0" width="975" height="460" rx="14" class="panel"/></g><g visibility="hidden"><set attributeName="visibility" to="visible" begin="280ms" dur="240ms" fill="remove"/><rect x="0" y="0" width="975" height="460" rx="14" class="panel"/><text x="64" y="120" class="primary">phpont</text><text x="64" y="170"><tspan class="key">OS</tspan><tspan class="primary">: </tspan><tspan class="value">Debian</tspan></text><rect x="168" y="156" width="6" height="15" class="cursor-value"/></g><g visibility="hidden"><set attributeName="visibility" to="visible" begin="520ms" dur="280ms" fill="remove"/><rect x="0" y="0" width="975" height="460" rx="14" class="panel"/><text x="64" y="120" class="primary">phpont</text><text x="64" y="170"><tspan class="key">OS</tspan><tspan class="primary">: </tspan><tspan class="value">Debian GNU/Linux</tspan></text><rect x="270" y="156" width="6" height="15" class="cursor-value"/></g><g visibility="hidden"><set attributeName="visibility" to="visible" begin="800ms" dur="300ms" fill="remove"/><rect x="0" y="0" width="975" height="460" rx="14" class="panel"/><text x="64" y="120" class="primary">phpont</text><text x="64" y="170"><tspan class="key">OS</tspan><tspan class="primary">: </tspan><tspan class="value">Debian GNU/Linux</tspan></text></g></g>'''
    return document("dark", body)


def short_hash(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def readme_text(dark_hash: str, light_hash: str) -> str: return README_TEMPLATE.format(pages_base=PAGES_BASE_URL, dark_hash=dark_hash, light_hash=light_hash)


def render(output_root: Path, birth_date: date, render_date: date) -> None:
    data, age = load_data(), calculate_age(birth_date, render_date); output_root.mkdir(parents=True, exist_ok=True); docs = output_root / "docs"; docs.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        static = static_svg(theme, data, age)
        (output_root / f"{theme}_mode.svg").write_text(static, encoding="utf-8", newline="\n")
        (docs / f"static-{theme}.svg").write_text(static, encoding="utf-8", newline="\n")
        (docs / f"profile-{theme}.svg").write_text(animated_svg(theme, data, age), encoding="utf-8", newline="\n")
    (docs / "compatibility.svg").write_text(compatibility_svg(), encoding="utf-8", newline="\n")
    (docs / ".nojekyll").write_text("", encoding="utf-8")
    (docs / "index.html").write_text(PAGES_INDEX, encoding="utf-8", newline="\n")
    (output_root / "README.md").write_text(readme_text(short_hash(docs / "profile-dark.svg"), short_hash(docs / "profile-light.svg")), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--output-root", type=Path, default=ROOT); args = parser.parse_args()
    try: render(args.output_root.resolve(), birth_date_from_environment(), current_profile_date())
    except (OSError, ValueError, json.JSONDecodeError) as error: print(f"render failed: {error}", file=sys.stderr); return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
