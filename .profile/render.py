#!/usr/bin/env python3
"""Render the profile through one deterministic Windows/Python 3.13 pipeline."""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import cairo
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / ".profile"
TEMPLATE_PATH = PROFILE_DIR / "profile.svg.tpl"
DATA_PATH = PROFILE_DIR / "profile.json"
CANVAS = (975, 460)
TIMEZONE = ZoneInfo("America/Sao_Paulo")
ASCII_VIEWPORT = (0, 18, 365, 420)
INFO_X = 385
FONT_FAMILY = "Consolas"
FONT_SIZE = 16

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


TYPING_CHUNKS = (
    (6, 16), (3, 8), (4,), (3,), (7, 17), (8, 22),
    (6, 18), (9, 20, 31), (8, 19), (7, 16), (7, 17), (8, 17, 23),
)


def parse_iso_date(value: str, variable_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{variable_name} must use YYYY-MM-DD; received {value!r}.") from error


def current_profile_date(render_date: str | None = None) -> date:
    value = render_date if render_date is not None else os.environ.get("PROFILE_RENDER_DATE")
    return parse_iso_date(value, "PROFILE_RENDER_DATE") if value else datetime.now(TIMEZONE).date()


def calculate_age(birth_date: date, on_date: date) -> int:
    if birth_date > on_date:
        raise ValueError("PROFILE_BIRTH_DATE cannot be in the future relative to the render date.")
    years = on_date.year - birth_date.year
    try:
        anniversary = birth_date.replace(year=on_date.year)
    except ValueError:  # 29 February celebrates on 28 February in non-leap years.
        anniversary = date(on_date.year, 2, 28)
    return years - (on_date < anniversary)


def birth_date_from_environment(value: str | None = None) -> date:
    raw = value if value is not None else os.environ.get("PROFILE_BIRTH_DATE")
    if not raw:
        raise ValueError("PROFILE_BIRTH_DATE is required (YYYY-MM-DD) and must not be committed to the repository.")
    return parse_iso_date(raw, "PROFILE_BIRTH_DATE")


def load_data() -> dict[str, str]:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    required = {"name", "os", "wm", "shell", "editor", "kernel", "focus", "languages_programming", "languages_real", "web", "instagram", "mail"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"profile.json is missing required keys: {', '.join(sorted(missing))}")
    return {key: str(value) for key, value in data.items()}


def _text(x: int, y: int, text: str, class_name: str = "") -> str:
    css = f' class="{class_name}"' if class_name else ""
    return f'<text x="{x}" y="{y}"{css}>{html.escape(text)}</text>'


def ascii_markup(visible_lines: int, glitch: bool = False) -> str:
    rendered = []
    for index, line in enumerate(ASCII_LINES[:visible_lines]):
        x = -50 + (2 if glitch and index in (8, 9) else -1 if glitch and index in (13, 14) else 0)
        rendered.append(_text(x, 35 + index * 20, line, "primary"))
    return "\n    ".join(rendered)


def information_rows(data: dict[str, str], age: int) -> list[tuple[int, str]]:
    return [
        (40, data["name"]), (60, "──────"), (90, f"OS: {data['os']}"), (110, f"Uptime: {age} years"),
        (130, f"WM: {data['wm']}"), (150, f"Shell: {data['shell']}"), (170, f"Editor: {data['editor']}"),
        (190, f"Kernel: {data['kernel']}"), (210, f"Focus: {data['focus']}"),
        (250, f"Languages.Programming: {data['languages_programming']}"), (270, f"Languages.Real: {data['languages_real']}"),
        (320, "Contact"), (340, "──────"), (370, f"Web: {data['web']}"),
        (390, f"Instagram: {data['instagram']}"), (410, f"Mail: {data['mail']}"),
    ]


def profile_fields(data: dict[str, str], age: int) -> tuple[ProfileField, ...]:
    return (
        ProfileField("OS", data["os"], 90),
        ProfileField("Uptime", f"{age} years", 110),
        ProfileField("WM", data["wm"], 130),
        ProfileField("Shell", data["shell"], 150),
        ProfileField("Editor", data["editor"], 170),
        ProfileField("Kernel", data["kernel"], 190),
        ProfileField("Focus", data["focus"], 210),
        ProfileField("Languages.Programming", data["languages_programming"], 250),
        ProfileField("Languages.Real", data["languages_real"], 270),
        ProfileField("Web", data["web"], 370),
        ProfileField("Instagram", data["instagram"], 390),
        ProfileField("Mail", data["mail"], 410),
    )


def typing_prefix_lengths(value: str, chunks: tuple[int, ...]) -> tuple[int, ...]:
    """Return increasing deterministic burst endpoints, always ending at the full value."""
    endpoints: list[int] = []
    for chunk in chunks:
        endpoint = min(len(value), chunk)
        if not endpoints or endpoint > endpoints[-1]:
            endpoints.append(endpoint)
    if not endpoints or endpoints[-1] != len(value):
        endpoints.append(len(value))
    return tuple(endpoints)


def typing_prefixes(value: str, chunks: tuple[int, ...]) -> tuple[str, ...]:
    return tuple(value[:length] for length in typing_prefix_lengths(value, chunks))


def ascii_lines_for_step(step: int, total_steps: int) -> int:
    milestones = (9, 12, 15, 18, len(ASCII_LINES))
    if total_steps <= 1:
        return milestones[-1]
    index = min(len(milestones) - 1, (step * len(milestones)) // total_steps)
    return milestones[index]


def build_timeline(data: dict[str, str], age: int) -> tuple[AnimationState, ...]:
    fields = profile_fields(data, age)
    states = [
        AnimationState(100, len(ASCII_LINES), header_chars=len(data["name"]), header_separator=True, completed_fields=len(fields), contact_visible=True),
        AnimationState(70, 0),
        AnimationState(55, 3, header_chars=3, cursor_visible=True, cursor_header=True),
        AnimationState(55, 6, header_chars=len(data["name"]), cursor_visible=True, cursor_header=True),
        AnimationState(55, 9, header_chars=len(data["name"]), header_separator=True),
    ]
    typed_states: list[AnimationState] = []
    completed = 0
    for index, field in enumerate(fields):
        for endpoint in typing_prefix_lengths(field.value, TYPING_CHUNKS[index]):
            typed_states.append(AnimationState(50, 0, header_chars=len(data["name"]), header_separator=True, completed_fields=completed, active_field=index, active_chars=endpoint, contact_visible=index >= 9, cursor_visible=True, cursor_field=index))
        completed += 1
    total = len(typed_states)
    for index, state in enumerate(typed_states):
        states.append(AnimationState(**{**state.__dict__, "ascii_lines": ascii_lines_for_step(index, total)}))
    mail_index = len(fields) - 1
    states.extend((
        AnimationState(60, len(ASCII_LINES), header_chars=len(data["name"]), header_separator=True, completed_fields=len(fields), contact_visible=True),
        AnimationState(60, len(ASCII_LINES), header_chars=len(data["name"]), header_separator=True, completed_fields=len(fields), contact_visible=True, cursor_visible=True, cursor_field=mail_index),
        AnimationState(110, len(ASCII_LINES), header_chars=len(data["name"]), header_separator=True, completed_fields=len(fields), contact_visible=True),
        AnimationState(40, len(ASCII_LINES), header_chars=len(data["name"]), header_separator=True, completed_fields=len(fields), contact_visible=True, glitch=True),
        AnimationState(220, len(ASCII_LINES), header_chars=len(data["name"]), header_separator=True, completed_fields=len(fields), contact_visible=True),
    ))
    return tuple(states)


def visible_info_rows(data: dict[str, str], age: int, groups: int) -> list[tuple[int, str]]:
    ends = (2, 4, 6, 8, 9, 10, 11, 16)
    count = ends[max(0, min(groups, 8) - 1)] if groups else 0
    return information_rows(data, age)[:count]


def info_markup(data: dict[str, str], age: int, groups: int) -> str:
    chunks = []
    for y, row in visible_info_rows(data, age, groups):
        if ": " in row:
            key, value = row.split(": ", 1)
            chunks.append(f'<text x="{INFO_X}" y="{y}"><tspan class="key">{html.escape(key)}</tspan><tspan class="primary">: </tspan><tspan class="value">{html.escape(value)}</tspan></text>')
        elif row == "──────":
            chunks.append(_text(INFO_X, y, row, "muted"))
        else:
            chunks.append(_text(INFO_X, y, row, "primary"))
    return "\n    ".join(chunks)


def strict_template(template: str, values: dict[str, str]) -> str:
    expected = set(re.findall(r"\{\{([A-Z_]+)\}\}", template))
    if expected != set(values):
        raise ValueError(f"template placeholders mismatch; expected {sorted(expected)}, supplied {sorted(values)}")
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    if re.search(r"\{\{[A-Z_]+\}\}", template):
        raise ValueError("unresolved placeholder in rendered SVG")
    return template


def build_svg(theme_name: str, data: dict[str, str], age: int) -> str:
    if theme_name not in THEMES:
        raise ValueError(f"unknown theme: {theme_name}")
    values = dict(THEMES[theme_name])
    values.update({"ASCII_MARKUP": ascii_markup(len(ASCII_LINES)), "INFO_MARKUP": info_markup(data, age, 8)})
    return strict_template(TEMPLATE_PATH.read_text(encoding="utf-8"), values)


def _color(hex_value: str) -> tuple[float, float, float]:
    return tuple(int(hex_value[index:index + 2], 16) / 255 for index in (1, 3, 5))


def _rounded_rect(context: cairo.Context) -> None:
    radius, width, height = 14, *CANVAS
    context.new_sub_path()
    context.arc(width - radius, radius, radius, -1.5708, 0)
    context.arc(width - radius, height - radius, radius, 0, 1.5708)
    context.arc(radius, height - radius, radius, 1.5708, 3.1416)
    context.arc(radius, radius, radius, 3.1416, 4.7124)
    context.close_path()


def _draw_text(context: cairo.Context, x: int, y: int, value: str, color: str) -> None:
    context.set_source_rgb(*_color(color))
    context.move_to(x, y)
    context.show_text(value)


def _draw_field(context: cairo.Context, field: ProfileField, value: str, theme: dict[str, str]) -> float:
    _draw_text(context, INFO_X, field.y, field.key, theme["KEY"])
    key_width = context.text_extents(field.key).x_advance
    _draw_text(context, int(INFO_X + key_width), field.y, ": ", theme["PRIMARY"])
    value_x = INFO_X + key_width + context.text_extents(": ").x_advance
    _draw_text(context, int(value_x), field.y, value, theme["VALUE"])
    return value_x + context.text_extents(value).x_advance


def _draw_cursor(context: cairo.Context, x: float, baseline: int, color: str) -> None:
    context.set_source_rgb(*_color(color))
    context.rectangle(x + 2, baseline - 14, max(3, context.text_extents("M").x_advance * 0.42), 15)
    context.fill()


def cursor_coordinates(context: cairo.Context, data: dict[str, str], age: int, state: AnimationState) -> tuple[float, int] | None:
    if not state.cursor_visible:
        return None
    if state.cursor_header:
        return INFO_X + context.text_extents(data["name"][:state.header_chars]).x_advance, 40
    if state.cursor_field is None:
        return None
    field = profile_fields(data, age)[state.cursor_field]
    prefix = field.value[:state.active_chars] if state.active_field == state.cursor_field else field.value
    value_x = INFO_X + context.text_extents(field.key).x_advance + context.text_extents(": ").x_advance
    return value_x + context.text_extents(prefix).x_advance, field.y


def render_frame(theme_name: str, data: dict[str, str], age: int, state: AnimationState | None = None) -> Image.Image:
    """The sole rasterization implementation used locally and in Windows CI."""
    theme = THEMES[theme_name]
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, *CANVAS)
    context = cairo.Context(surface)
    context.set_operator(cairo.OPERATOR_CLEAR)
    context.paint()
    context.set_operator(cairo.OPERATOR_OVER)
    _rounded_rect(context)
    context.set_source_rgb(*_color(theme["BACKGROUND"]))
    context.fill_preserve()
    context.set_source_rgb(*_color(theme["BORDER"]))
    context.set_line_width(1)
    context.stroke()
    context.select_font_face(FONT_FAMILY, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    context.set_font_size(FONT_SIZE)

    state = state or build_timeline(data, age)[0]
    context.save()
    context.rectangle(*ASCII_VIEWPORT)
    context.clip()
    for index, line in enumerate(ASCII_LINES[:state.ascii_lines]):
        x = -50 + (2 if state.glitch and index in (8, 9) else -1 if state.glitch and index in (13, 14) else 0)
        _draw_text(context, x, 35 + index * 20, line, theme["PRIMARY"])
    context.restore()

    if state.header_chars:
        _draw_text(context, INFO_X, 40, data["name"][:state.header_chars], theme["PRIMARY"])
    if state.header_separator:
        _draw_text(context, INFO_X, 60, "──────", theme["MUTED"])

    fields = profile_fields(data, age)
    for field in fields[:state.completed_fields]:
        _draw_field(context, field, field.value, theme)
    if state.contact_visible:
        _draw_text(context, INFO_X, 320, "Contact", theme["PRIMARY"])
        _draw_text(context, INFO_X, 340, "──────", theme["MUTED"])

    cursor_x: float | None = None
    cursor_y = 0
    cursor_color = theme["VALUE"]
    if state.active_field is not None:
        field = fields[state.active_field]
        cursor_x = _draw_field(context, field, field.value[:state.active_chars], theme)
        cursor_y = field.y
    coordinates = cursor_coordinates(context, data, age, state)
    if coordinates is not None:
        cursor_x, cursor_y = coordinates
        if state.cursor_header:
            cursor_color = theme["PRIMARY"]
    if state.cursor_visible and cursor_x is not None:
        _draw_cursor(context, cursor_x, cursor_y, cursor_color)

    png = BytesIO()
    surface.write_to_png(png)
    return Image.open(png).convert("RGBA")


def save_gif(frames: list[Image.Image], output: Path, durations: tuple[int, ...]) -> None:
    if len(frames) != len(durations):
        raise ValueError("GIF frame and duration counts must match")
    transparent_index = 47
    paletted = []
    for frame in frames:
        rgba = frame.convert("RGBA")
        alpha = rgba.getchannel("A")
        panel_background = rgba.getpixel((500, 440))[:3]
        rgb = Image.new("RGB", CANVAS, panel_background)
        rgb.paste(rgba.convert("RGB"), mask=alpha)
        indexed = rgb.quantize(colors=47, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        pixels = list(indexed.getdata())
        indexed.putdata([transparent_index if opacity == 0 else pixel for pixel, opacity in zip(pixels, alpha.getdata())])
        indexed.info["transparency"] = transparent_index
        paletted.append(indexed)
    paletted[0].save(output, format="GIF", save_all=True, append_images=paletted[1:], duration=durations, disposal=2, optimize=True, transparency=transparent_index)


def render(output_root: Path, birth_date: date, render_date: date, keep_frames: bool = False) -> None:
    data, age = load_data(), calculate_age(birth_date, render_date)
    output_root.mkdir(parents=True, exist_ok=True)
    states = build_timeline(data, age)
    frame_root: tempfile.TemporaryDirectory[str] | None = None
    if keep_frames:
        frames_dir = PROFILE_DIR / "build"
        if frames_dir.exists():
            shutil.rmtree(frames_dir)
        frames_dir.mkdir(parents=True)
    else:
        frame_root = tempfile.TemporaryDirectory(prefix="phpont-profile-")
        frames_dir = Path(frame_root.name)
    try:
        for theme_name in THEMES:
            (output_root / f"{theme_name}_mode.svg").write_text(build_svg(theme_name, data, age), encoding="utf-8", newline="\n")
            frames = []
            for index, state in enumerate(states):
                frame = render_frame(theme_name, data, age, state)
                frames.append(frame)
                if keep_frames:
                    frame.save(frames_dir / f"{theme_name}-{index:02d}.png")
            save_gif(frames, output_root / f"{theme_name}_mode.gif", tuple(state.duration for state in states))
    finally:
        if frame_root is not None:
            frame_root.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--keep-frames", action="store_true", help="write diagnostic PNG frames to .profile/build")
    args = parser.parse_args()
    try:
        render(args.output_root.resolve(), birth_date_from_environment(), current_profile_date(), args.keep_frames)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"render failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
