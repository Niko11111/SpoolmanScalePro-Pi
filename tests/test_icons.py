"""Button icons (static/js/icons.js): every button gets its content from
label() or labelForText(), every mapped key is a real text, every mapped
icon is drawn, and icon_data.js matches tools/build_icons.py."""

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "static" / "js"

_spec = importlib.util.spec_from_file_location("build_icons", ROOT / "tools" / "build_icons.py")
build_icons = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_icons)

# The first argument after a button's attributes: its content.
BUTTON = re.compile(r'el\("button", \{[^}]*\},\s*([A-Za-z.]+)')
LINK_BUTTON = re.compile(r'el\("a", \{[^}]*class: "linkbtn"[^}]*\},\s*([A-Za-z.]+)')
ALLOWED_CONTENT = {"label", "labelForText", "SSPro.label", "SSPro.labelForText",
                   "nextLabel",  # page_setup.js: navRow() is handed label("setup.next")
                   "icon"}  # icons.js iconButton(): an icon alone, named by aria-label


def action_icons() -> dict[str, str]:
    block = re.search(r"const ACTION_ICONS = \{(.*?)\n  \};", (JS / "icons.js").read_text(), re.S).group(1)
    return dict(re.findall(r'"([a-z_.]+)": "([a-z_]+)"', block))


def drawn_icons() -> set[str]:
    return set(re.findall(r'^  "([a-z_]+)": \[', (JS / "icon_data.js").read_text(), re.M))


def catalog_keys(lang: str) -> set[str]:
    return set(re.findall(r'^\s*"([^"]+)":', (ROOT / "static" / "i18n" / f"{lang}.js").read_text(), re.M))


def buttons_without_icon(name: str, text: str) -> list[str]:
    found = [m for pattern in (BUTTON, LINK_BUTTON) for m in pattern.finditer(text)]
    return [f"{name}:{text.count(chr(10), 0, m.start()) + 1} {m.group(1)}"
            for m in found if m.group(1) not in ALLOWED_CONTENT]


def test_every_button_is_built_with_its_icon():
    offenders = [o for f in sorted(JS.glob("*.js")) for o in buttons_without_icon(f.name, f.read_text())]
    assert offenders == []


def test_every_mapped_icon_is_drawn():
    missing = {key: name for key, name in action_icons().items() if name not in drawn_icons()}
    assert missing == {}


def test_every_mapped_key_is_a_text_in_both_languages():
    keys = set(action_icons())
    assert keys - catalog_keys("de") == set()
    assert keys - catalog_keys("en") == set()


def test_icon_data_matches_the_builder():
    assert drawn_icons() == set(build_icons.ICONS)


def test_icon_data_has_only_drawing_elements():
    text = (JS / "icon_data.js").read_text()
    for line in re.findall(r'^  "[a-z_]+": (\[.*\]),$', text, re.M):
        for tag, attrs in json.loads(line):
            assert tag in build_icons.DRAWING
            assert all(build_icons.keep(tag, k, v) for k, v in attrs.items())
