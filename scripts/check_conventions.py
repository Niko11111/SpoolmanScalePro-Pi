#!/usr/bin/env python3
"""Counts what the house rules forbid. Every rule must stand at zero.

The project started clean, so there is no baseline of old debt to freeze:
a finding is a failure. An exception is not a quiet edit to a number but a
line in ALLOWED below, with the reason next to it.

Run through scripts/check.sh, locally and in CI. --verbose lists every
finding; without it, the rules with findings and their first few lines.
"""

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FUNCTION_MAX_LINES = 50
FUNCTION_MAX_PARAMS = 5
NESTING_MAX = 3
FILE_MAX_LINES = 1000
SHOWN_PER_RULE = 5

# Written as a code point so this file does not contain the character.
EM_DASH = chr(0x2014)

# (rule, file) pairs that may break a rule, each with its reason.
ALLOWED = {
    # A meter's width is only known at run time; set through the CSSOM.
    ("style_in_js", "static/js/view_status.js"),
    # The job thread is the outer boundary: a crash there must be logged and
    # turned into a failed job, whatever it was.
    ("broad_except", "spoolmanscale_pro/jobs.py"),
}

# German words written without their umlaut, the mistake rule
# "ascii_umlauts" looks for in the German catalog.
ASCII_UMLAUT_WORDS = re.compile(
    r"\b(fuer|ueber|zurueck|loeschen|moechte|koennen|muessen|waehle|waehlen|"
    r"aendern|geaendert|oeffnen|schliessen|groesse|gross|laeuft|naechste|"
    r"spaeter|frueher|pruefe|pruefen|faehrt|haengt|zaehlt|uebernehmen)\b",
    re.IGNORECASE)


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / line for line in out.splitlines() if (ROOT / line).is_file()]


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


# ---- Python -----------------------------------------------------------------

BLOCKS = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.AsyncFor, ast.AsyncWith)


def _is_elif(parent: ast.AST, child: ast.AST) -> bool:
    """An elif is an If inside the orelse of an If; it reads as the same
    level, not one deeper."""
    return isinstance(parent, ast.If) and isinstance(child, ast.If) and parent.orelse == [child]


def _depth(node: ast.AST, level: int = 0) -> int:
    deepest = level
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        nested = isinstance(child, BLOCKS) and not _is_elif(node, child)
        inner = level + 1 if nested else level
        deepest = max(deepest, _depth(child, inner))
    return deepest


def check_function(fn: ast.AST, where: str, add) -> None:
    length = fn.end_lineno - fn.lineno + 1
    if length > FUNCTION_MAX_LINES:
        add("function_too_long", f"{where}:{fn.lineno} {fn.name} ({length} lines)")
    params = [a.arg for a in fn.args.args + fn.args.kwonlyargs if a.arg not in ("self", "cls")]
    if len(params) > FUNCTION_MAX_PARAMS:
        add("too_many_params", f"{where}:{fn.lineno} {fn.name} ({len(params)})")
    depth = _depth(fn)
    if depth > NESTING_MAX:
        add("nesting_too_deep", f"{where}:{fn.lineno} {fn.name} ({depth} levels)")


def check_except(handler: ast.ExceptHandler, lines: list[str], where: str, add) -> None:
    if handler.type is None:
        add("bare_except", f"{where}:{handler.lineno}")
    elif isinstance(handler.type, ast.Name) and handler.type.id in ("Exception", "BaseException"):
        add("broad_except", f"{where}:{handler.lineno}")
    body = handler.body
    if len(body) == 1 and isinstance(body[0], ast.Pass) and "#" not in lines[body[0].lineno - 1]:
        add("silent_except", f"{where}:{handler.lineno} (pass without a comment saying why)")


def check_call(call: ast.Call, where: str, add) -> None:
    for kw in call.keywords:
        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            add("shell_true", f"{where}:{call.lineno}")
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in ("system", "popen") and \
            isinstance(func.value, ast.Name) and func.value.id == "os":
        add("shell_true", f"{where}:{call.lineno} os.{func.attr}")


def check_python(path: Path, add) -> None:
    where = rel(path)
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=where)
    except SyntaxError as e:
        add("syntax", f"{where}:{e.lineno} {e.msg}")
        return
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check_function(node, where, add)
        elif isinstance(node, ast.ExceptHandler):
            check_except(node, lines, where, add)
        elif isinstance(node, ast.Call):
            check_call(node, where, add)


def check_pyflakes(py_files: list[Path], add) -> None:
    done = subprocess.run([sys.executable, "-m", "pyflakes", *map(str, py_files)],
                          capture_output=True, text=True)
    if done.returncode not in (0, 1):
        add("pyflakes", "pyflakes is not installed: pip install -r requirements-dev.txt")
        return
    for line in done.stdout.splitlines():
        add("pyflakes", line.replace(str(ROOT) + "/", ""))


# ---- JavaScript, CSS, catalogs ------------------------------------------------

def check_js(path: Path, add) -> None:
    where = rel(path)
    text = path.read_text(encoding="utf-8")
    done = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
    if done.returncode != 0:
        add("syntax", f"{where}: {done.stderr.strip().splitlines()[0] if done.stderr else 'node --check failed'}")
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("//", "/*", "*")):
            continue  # a comment may name what the code must not do
        if "innerHTML" in line or "outerHTML" in line or "insertAdjacentHTML" in line:
            add("html_in_js", f"{where}:{n}")
        if re.search(r"\bfetch\(", line) and where != "static/js/core.js":
            add("fetch_outside_core", f"{where}:{n}")
        if re.search(r"#[0-9a-fA-F]{3,8}\b", line) and "/i18n/" not in where:
            add("color_in_js", f"{where}:{n}")
        if re.search(r"\.style\.|setAttribute\(\s*[\"']style", line):
            add("style_in_js", f"{where}:{n}")


def check_css(path: Path, add) -> None:
    where = rel(path)
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        code = line.split("/*")[0]
        if re.search(r"#[0-9a-fA-F]{3,8}\b", code) and not re.search(r"--[a-z0-9-]+\s*:", code):
            add("color_outside_tokens", f"{where}:{n}")


def _catalog(path: Path) -> dict:
    keys = {}
    for match in re.finditer(r'^\s*"([a-z0-9_.]+)":\s*"((?:[^"\\]|\\.)*)"', path.read_text(encoding="utf-8"), re.M):
        keys[match.group(1)] = match.group(2)
    return keys


def check_catalogs(js_files: list[Path], add) -> None:
    en = _catalog(ROOT / "static/i18n/en.js")
    de = _catalog(ROOT / "static/i18n/de.js")
    for key in sorted(set(en) - set(de)):
        add("i18n_missing_de", key)
    for key in sorted(set(de) - set(en)):
        add("i18n_missing_en", key)
    for key, text in de.items():
        if ASCII_UMLAUT_WORDS.search(text):
            add("ascii_umlauts", f"de: {key}")
    for path in js_files:
        if "/i18n/" in rel(path):
            continue
        for key in re.findall(r'\bt\(\s*"([a-z0-9_.]+)"', path.read_text(encoding="utf-8")):
            # "lang." + code: a key put together at run time, not checkable here.
            if key not in en and not key.endswith("."):
                add("i18n_unknown_key", f"{rel(path)}: {key}")


# ---- every file -----------------------------------------------------------------

def check_text_file(path: Path, add) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return  # an image or another binary file
    where = rel(path)
    if EM_DASH in text:
        add("em_dash", f"{where}:{text[:text.index(EM_DASH)].count(chr(10)) + 1}")
    lines = text.count("\n")
    if lines > FILE_MAX_LINES and path.name != "LICENSE":
        add("file_too_long", f"{where} ({lines} lines)")


def check_shell(path: Path, add) -> None:
    shell = "bash" if path.read_text(encoding="utf-8").startswith("#!/bin/bash") or \
        path.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash") else "sh"
    done = subprocess.run([shell, "-n", str(path)], capture_output=True, text=True)
    if done.returncode != 0:
        add("syntax", f"{rel(path)}: {done.stderr.strip()}")


def check_version(add) -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(-beta\.\d+)?", version):
        add("version_format", f"VERSION is '{version}', expected X.Y.Z or X.Y.Z-beta.N")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## {version}" not in changelog:
        add("version_without_changelog", f"CHANGELOG.md has no '## {version}' section")


def collect() -> dict[str, list[str]]:
    findings: dict[str, list[str]] = {}

    def add(rule: str, detail: str) -> None:
        file = detail.split(":")[0].split(" ")[0]
        if (rule, file) not in ALLOWED:
            findings.setdefault(rule, []).append(detail)

    files = tracked_files()
    py = [f for f in files if f.suffix == ".py"]
    js = [f for f in files if f.suffix == ".js"]
    for f in py:
        check_python(f, add)
    check_pyflakes(py, add)
    for f in js:
        check_js(f, add)
    for f in (f for f in files if f.suffix == ".css"):
        check_css(f, add)
    for f in (f for f in files if f.suffix == ".sh"):
        check_shell(f, add)
    for f in files:
        check_text_file(f, add)
    check_catalogs(js, add)
    check_version(add)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    findings = collect()
    if not findings:
        print("conventions: every rule at zero")
        return 0
    for rule, details in sorted(findings.items()):
        print(f"{rule}: {len(details)}")
        for d in details if args.verbose else details[:SHOWN_PER_RULE]:
            print(f"    {d}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
