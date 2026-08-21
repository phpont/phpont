#!/usr/bin/env python3
"""Regression tests for the canonical Windows profile renderer and typing timeline."""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import cairo
from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ASSET_NAMES = ("dark_mode.svg", "light_mode.svg", "dark_mode.gif", "light_mode.gif")


def validate_svg(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    assert root.tag.endswith("svg")
    assert root.attrib == {"width": "975", "height": "460", "viewBox": "0 0 975 460", "role": "img", "aria-labelledby": "title description"}
    rect = next(element for element in root.iter() if element.tag.endswith("rect"))
    assert rect.attrib["width"] == "975" and rect.attrib["height"] == "460" and rect.attrib["rx"] == "14"
    lowered = text.lower()
    assert "<script" not in lowered and "javascript:" not in lowered and "foreignobject" not in lowered
    assert not re.search(r"(?:href|src)=[\"'][^\"']*https?://", text, re.I)
    assert "\ufffd" not in text and "█" not in text and "Windows 11" not in text
    for expected in ("Debian GNU/Linux", "WM", "Niri", "Shell", "zsh", "Full Stack Development", "Web Security, Rust", "Languages.Programming", "Languages.Real", "phpont.github.io", "@paulohpontarolo"):
        assert expected in text, expected
    for forbidden in ("Windows 11", "Host", "Languages.Computer", "Projects", "GitHub Stats", "access granted", "initializing"):
        assert forbidden.lower() not in lowered, forbidden


def gif_frames(path: Path) -> tuple[list[Image.Image], list[int], int | None]:
    with Image.open(path) as image:
        frames, durations = [], []
        for index in range(image.n_frames):
            image.seek(index)
            frames.append(image.convert("RGBA").copy())
            durations.append(image.info.get("duration", 0))
        return frames, durations, image.info.get("loop")


def validate_gif(path: Path) -> tuple[list[Image.Image], list[int]]:
    frames, durations, loop = gif_frames(path)
    assert frames[0].size == render.CANVAS
    assert 28 <= len(frames) <= 40
    assert loop is None, "GIF must not carry an infinite/repeating loop extension"
    assert 1700 <= sum(durations) <= 2400, sum(durations)
    assert ImageChops.difference(frames[0].convert("RGB"), frames[-1].convert("RGB")).getbbox() is None
    assert path.stat().st_size <= 1_000_000
    return frames, durations


def foreground_count(image: Image.Image, box: tuple[int, int, int, int], background: str) -> int:
    color = tuple(int(background[index:index + 2], 16) for index in (1, 3, 5))
    return sum(pixel[:3] != color for pixel in image.crop(box).getdata())


class ProfileTests(unittest.TestCase):
    def test_age_boundaries_and_leap_year(self) -> None:
        born = date(2000, 9, 8)
        self.assertEqual(render.calculate_age(born, date(2026, 9, 7)), 25)
        self.assertEqual(render.calculate_age(born, date(2026, 9, 8)), 26)
        self.assertEqual(render.calculate_age(born, date(2026, 9, 9)), 26)
        self.assertEqual(render.calculate_age(born, date(2027, 1, 1)), 26)
        leap_born = date(2004, 2, 29)
        self.assertEqual(render.calculate_age(leap_born, date(2025, 2, 27)), 20)
        self.assertEqual(render.calculate_age(leap_born, date(2025, 2, 28)), 21)
        self.assertEqual(render.calculate_age(leap_born, date(2024, 2, 29)), 20)

    def test_original_ascii_is_literal(self) -> None:
        self.assertEqual(len(render.ASCII_LINES), 20)
        self.assertEqual(render.ASCII_LINES[0], "                      :::!~!!!!!:.                   ")
        self.assertEqual(render.ASCII_LINES[-1], "?MXT@Wx.~    :     ~\"##*$$$$M~                  ")
        self.assertEqual(hashlib.sha256("\n".join(render.ASCII_LINES).encode()).hexdigest(), "2652ce820194908f6ac6ef4b6dc2748d13f3e5d5a08ce6762b4872be80f15a0b")

    def test_typing_prefixes_are_monotonic_and_complete(self) -> None:
        data, fields = render.load_data(), render.profile_fields(render.load_data(), 19)
        self.assertEqual(data["os"], "Debian GNU/Linux")
        for field, chunks in zip(fields, render.TYPING_CHUNKS):
            prefixes = render.typing_prefixes(field.value, chunks)
            self.assertEqual(prefixes[-1], field.value)
            self.assertEqual(tuple(sorted(map(len, prefixes))), tuple(map(len, prefixes)))
            self.assertEqual(len(set(prefixes)), len(prefixes))
            self.assertTrue(all(field.value.startswith(prefix) for prefix in prefixes))

    def test_timeline_cursor_typing_and_glitch_rules(self) -> None:
        data, age = render.load_data(), 19
        timeline = render.build_timeline(data, age)
        self.assertTrue(28 <= len(timeline) <= 40)
        self.assertTrue(1700 <= sum(state.duration for state in timeline) <= 2400)
        self.assertFalse(timeline[0].cursor_visible)
        self.assertFalse(timeline[-1].cursor_visible)
        self.assertEqual(sum(state.glitch for state in timeline), 1)
        self.assertGreaterEqual(sum(state.cursor_visible for state in timeline), 20)
        self.assertTrue(any(not state.cursor_visible for state in timeline[-6:-3]))
        self.assertTrue(any(state.cursor_visible for state in timeline[-6:-3]))
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, *render.CANVAS)
        context = cairo.Context(surface)
        context.select_font_face(render.FONT_FAMILY, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(render.FONT_SIZE)
        for state in timeline:
            if state.cursor_visible:
                position = render.cursor_coordinates(context, data, age, state)
                self.assertIsNotNone(position)
                x, y = position
                self.assertGreater(x, render.INFO_X)
                self.assertLess(x, render.CANVAS[0] - 5)
                self.assertGreaterEqual(y, 40)
                self.assertNotEqual(state.cursor_field, None) if not state.cursor_header else None
                self.assertFalse(state.glitch)

    def test_canonical_render_visual_guards(self) -> None:
        data, age = render.load_data(), 19
        for theme_name, theme in render.THEMES.items():
            frame = render.render_frame(theme_name, data, age)
            self.assertEqual(frame.size, render.CANVAS)
            self.assertGreater(foreground_count(frame, (0, 18, 365, 438), theme["BACKGROUND"]), 800, theme_name)
            self.assertGreater(foreground_count(frame, (385, 20, 950, 430), theme["BACKGROUND"]), 800, theme_name)
            self.assertLess(foreground_count(frame, (366, 20, 384, 430), theme["BACKGROUND"]), 20, theme_name)
            self.assertEqual(frame.getpixel((0, 0))[3], 0, theme_name)
            self.assertGreater(frame.getpixel((14, 0))[3], 0, theme_name)
            self.assertNotEqual(ImageStat.Stat(frame.crop((0, 18, 365, 438)).convert("RGB")).sum, (0.0, 0.0, 0.0), theme_name)

    def test_rendered_assets_determinism_parity_and_no_build_side_effect(self) -> None:
        build_path = ROOT / ".profile" / "build"
        self.assertFalse(build_path.exists(), "tests must begin without persistent frame output")
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            birth, today = date(2000, 9, 8), date(2026, 9, 7)
            render.render(Path(first_dir), birth, today)
            render.render(Path(second_dir), birth, today)
            self.assertFalse(build_path.exists(), "default render must not write .profile/build")
            for name in ASSET_NAMES:
                first, second = Path(first_dir) / name, Path(second_dir) / name
                self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest(), name)
            for name in ASSET_NAMES[:2]:
                validate_svg(Path(first_dir) / name)
            timeline = render.build_timeline(render.load_data(), render.calculate_age(birth, today))
            glitch_index = next(index for index, state in enumerate(timeline) if state.glitch)
            for theme_name in render.THEMES:
                frames, _ = validate_gif(Path(first_dir) / f"{theme_name}_mode.gif")
                expected = render.render_frame(theme_name, render.load_data(), render.calculate_age(birth, today))
                backdrop = Image.new("RGBA", render.CANVAS, (255, 255, 255, 255))
                actual_rgb, expected_rgb = backdrop.copy(), backdrop.copy()
                actual_rgb.alpha_composite(frames[-1])
                expected_rgb.alpha_composite(expected)
                mean_delta = ImageStat.Stat(ImageChops.difference(actual_rgb.convert("RGB"), expected_rgb.convert("RGB"))).mean
                self.assertLess(max(mean_delta), 4.0, f"{theme_name} final GIF frame visual drift: {mean_delta}")
                glitch_bbox = ImageChops.difference(frames[glitch_index - 1].convert("RGB"), frames[glitch_index].convert("RGB")).getbbox()
                self.assertIsNotNone(glitch_bbox)
                self.assertLessEqual(glitch_bbox[2], 365, f"{theme_name} glitch escaped ASCII region")

    def test_environment_requires_birth_date(self) -> None:
        prior = os.environ.pop("PROFILE_BIRTH_DATE", None)
        try:
            with self.assertRaisesRegex(ValueError, "PROFILE_BIRTH_DATE is required"):
                render.birth_date_from_environment()
        finally:
            if prior is not None:
                os.environ["PROFILE_BIRTH_DATE"] = prior


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-generated", action="store_true", help="also validate versioned assets in the repository root")
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProfileTests))
    if args.check_generated and result.wasSuccessful():
        try:
            for name in ASSET_NAMES[:2]:
                validate_svg(ROOT / name)
            for name in ASSET_NAMES[2:]:
                validate_gif(ROOT / name)
            with tempfile.TemporaryDirectory() as generated_dir:
                render.render(Path(generated_dir), render.birth_date_from_environment(), render.current_profile_date())
                for name in ASSET_NAMES:
                    assert hashlib.sha256((ROOT / name).read_bytes()).digest() == hashlib.sha256((Path(generated_dir) / name).read_bytes()).digest(), f"generated root artifact drift: {name}"
        except (AssertionError, OSError, ET.ParseError) as error:
            print(f"generated asset validation failed: {error}", file=sys.stderr)
            return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
