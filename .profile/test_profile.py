#!/usr/bin/env python3
"""Structural regression tests for static and declarative SVG profile assets."""
from __future__ import annotations
import argparse, hashlib, os, re, sys, tempfile, unittest
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import render  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STATIC = ("dark_mode.svg", "light_mode.svg")
ANIMATED = ("docs/profile-dark.svg", "docs/profile-light.svg", "docs/compatibility.svg")
ALL_GENERATED = STATIC + ANIMATED + ("docs/static-dark.svg", "docs/static-light.svg", "docs/.nojekyll", "docs/index.html", "README.md")
EXPECTED = ("phpont", "Debian GNU/Linux", "Uptime", "Niri", "zsh", "Neovim, VS Code", "Full Stack Development", "Web Security, Rust", "Languages.Programming", "Languages.Real", "phpont.github.io", "@paulohpontarolo", "paulohponta@gmail.com")

def local(tag: str) -> str: return tag.rsplit("}", 1)[-1]
def read_svg(path: Path) -> tuple[ET.Element, str]:
    source = path.read_text(encoding="utf-8"); return ET.fromstring(source), source
def all_text(element: ET.Element) -> str: return "".join(element.itertext())

def validate_common(path: Path, animated: bool) -> None:
    root, source = read_svg(path); lowered = source.lower()
    assert local(root.tag) == "svg" and root.attrib["width"] == "975" and root.attrib["height"] == "460" and root.attrib["viewBox"] == "0 0 975 460"
    for forbidden in ("<script", "javascript:", "foreignobject", "<image", "data:image", ".woff", ".ttf", ".otf", "repeatcount=\"indefinite\"", "windows 11", ".gif"):
        assert forbidden not in lowered, forbidden
    assert not re.search(r"(?:href|src)=[\"'][^\"']*https?://", source, re.I)
    expected_content = ("phpont", "Debian GNU/Linux") if path.name == "compatibility.svg" else EXPECTED
    for expected in expected_content: assert expected in source, expected
    final = next(element for element in root.iter() if element.attrib.get("id") == "final-state")
    assert final.attrib.get("visibility") != "hidden" and "cursor-" not in ET.tostring(final, encoding="unicode")
    if animated:
        overlay = next(element for element in root.iter() if element.attrib.get("id") == "animation-overlay")
        duration = int(overlay.attrib["data-duration-ms"])
        assert overlay.attrib.get("visibility") == "hidden" and (800 <= duration <= 1200 if path.name == "compatibility.svg" else 1700 <= duration <= 2400)
        assert sum(local(element.tag) == "set" for element in root.iter()) > 1
        if "compatibility" not in path.name: assert sum(element.attrib.get("data-glitch") == "true" for element in root.iter()) == 1
    else: assert not any(local(element.tag) in {"set", "animate"} for element in root.iter())

def validate_text(source: str, animated: bool, filename: str = "asset.svg") -> None:
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / filename; path.write_text(source, encoding="utf-8"); validate_common(path, animated)

class ProfileTests(unittest.TestCase):
    def test_age_boundaries_and_leap_year(self) -> None:
        born = date(2000, 9, 8)
        self.assertEqual(render.calculate_age(born, date(2026, 9, 7)), 25); self.assertEqual(render.calculate_age(born, date(2026, 9, 8)), 26); self.assertEqual(render.calculate_age(born, date(2026, 9, 9)), 26); self.assertEqual(render.calculate_age(born, date(2027, 1, 1)), 26); self.assertEqual(render.calculate_age(date(2004, 2, 29), date(2025, 2, 28)), 21)
    def test_original_ascii_and_typing_are_preserved(self) -> None:
        self.assertEqual(len(render.ASCII_LINES), 20); self.assertEqual(render.ASCII_LINES[0], "                      :::!~!!!!!:.                   "); self.assertEqual(render.ASCII_LINES[-1], "?MXT@Wx.~    :     ~\"##*$$$$M~                  "); self.assertEqual(hashlib.sha256("\n".join(render.ASCII_LINES).encode()).hexdigest(), "2652ce820194908f6ac6ef4b6dc2748d13f3e5d5a08ce6762b4872be80f15a0b")
        for field, chunks in zip(render.fields(render.load_data(), 19), render.TYPING_CHUNKS):
            prefixes = render.typing_prefixes(field.value, chunks); self.assertEqual(prefixes[-1], field.value); self.assertEqual(tuple(sorted(map(len, prefixes))), tuple(map(len, prefixes)))
    def test_timeline_cursor_and_glitch_rules(self) -> None:
        timeline = render.build_timeline(render.load_data(), 19); self.assertTrue(28 <= len(timeline) <= 40); self.assertTrue(1700 <= sum(state.duration for state in timeline) <= 2400); self.assertFalse(timeline[0].cursor_visible); self.assertFalse(timeline[-1].cursor_visible); self.assertEqual(sum(state.glitch for state in timeline), 1); self.assertGreater(sum(state.cursor_visible for state in timeline), 20)
    def test_svg_structure_animation_and_fail_safe(self) -> None:
        data, age = render.load_data(), 19
        for theme in render.THEMES:
            validate_text(render.static_svg(theme, data, age), False); animated = render.animated_svg(theme, data, age); validate_text(animated, True)
            root = ET.fromstring(animated)
            for parent in root.iter():
                for child in list(parent):
                    if local(child.tag) in {"set", "animate"}: parent.remove(child)
            final = next(element for element in root.iter() if element.attrib.get("id") == "final-state")
            for expected in EXPECTED: self.assertIn(expected, all_text(final))
            self.assertNotIn("cursor-", ET.tostring(final, encoding="unicode"))
        validate_text(render.compatibility_svg(), True, "compatibility.svg")
    def test_deterministic_render_and_no_raster_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            birth, today = date(2000, 9, 8), date(2026, 8, 21); render.render(Path(first), birth, today); render.render(Path(second), birth, today)
            for name in ALL_GENERATED: self.assertEqual((Path(first) / name).read_bytes(), (Path(second) / name).read_bytes(), name)
            for name in STATIC: validate_common(Path(first) / name, False)
            for name in ("docs/static-dark.svg", "docs/static-light.svg"): validate_common(Path(first) / name, False)
            for name in ANIMATED: validate_common(Path(first) / name, True)
            for name in ("docs/profile-dark.svg", "docs/profile-light.svg"): self.assertLess((Path(first) / name).stat().st_size, 150_000)
            readme = (Path(first) / "README.md").read_text(encoding="utf-8"); self.assertIn(render.PAGES_BASE_URL, readme); self.assertNotIn(".gif", readme.lower()); self.assertRegex(readme, r"\?v=[0-9a-f]{12}")
    def test_environment_requires_birth_date(self) -> None:
        prior = os.environ.pop("PROFILE_BIRTH_DATE", None)
        try:
            with self.assertRaisesRegex(ValueError, "PROFILE_BIRTH_DATE is required"): render.birth_date_from_environment()
        finally:
            if prior is not None: os.environ["PROFILE_BIRTH_DATE"] = prior

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--check-generated", action="store_true"); args = parser.parse_args(); result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProfileTests))
    if args.check_generated and result.wasSuccessful():
        try:
            for name in STATIC: validate_common(ROOT / name, False)
            for name in ANIMATED: validate_common(ROOT / name, True)
            for name in ("docs/static-dark.svg", "docs/static-light.svg"): validate_common(ROOT / name, False)
            for legacy in ("dark_mode.gif", "light_mode.gif"): assert not (ROOT / legacy).exists(), legacy
            for source in (ROOT / "README.md", ROOT / "requirements.txt", ROOT / ".profile" / "render.py", ROOT / ".profile" / "preview.py"):
                lowered = source.read_text(encoding="utf-8").lower()
                assert ".gif" not in lowered and "pillow" not in lowered and "pycairo" not in lowered, source
            with tempfile.TemporaryDirectory() as temp:
                render.render(Path(temp), render.birth_date_from_environment(), render.current_profile_date())
                for name in ALL_GENERATED: assert (ROOT / name).read_bytes() == (Path(temp) / name).read_bytes(), name
        except (AssertionError, OSError, ET.ParseError) as error: print(f"generated asset validation failed: {error}", file=sys.stderr); return 1
    return 0 if result.wasSuccessful() else 1
if __name__ == "__main__": raise SystemExit(main())
