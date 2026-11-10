"""Committed evidence and docs must not carry local paths, private links or credentials.

Failures name file and line only, never the matched text, so a failing run cannot leak it into a log.
"""
import importlib.util
import re

from conftest import DATA

ROOT = DATA.parent
SCANNED = ("docs", "README.md", "mock", "data", "scripts", ".github")
SUFFIXES = {".md", ".log", ".html", ".json", ".py", ".sh", ".yml", ".txt"}
SELF = {"scripts/scrub_paths.py"}  # its regexes spell out the patterns
FORBIDDEN = [
    ("local user path", re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+")),
    ("temp path", re.compile(r"/(?:private/)?var/folders/|pytest-of-(?!<user>)")),
    ("private link", re.compile(r"(?:drive|docs)\.google\.com|notion\.(?:so|site)|file:///")),
    ("credential", re.compile(r"Bearer\s+[A-Za-z0-9._-]{8,}|\bsk-[A-Za-z0-9]{16,}|\bghp_[A-Za-z0-9]{20,}")),
]


def scanned_files():
    for name in SCANNED:
        base = ROOT / name
        paths = [base] if base.is_file() else sorted(base.rglob("*"))
        for p in paths:
            if (p.is_file() and p.suffix in SUFFIXES and "__pycache__" not in p.parts
                    and p.relative_to(ROOT).as_posix() not in SELF):
                yield p


def test_no_local_paths_private_links_or_credentials_in_committed_text():
    hits = []
    for path in scanned_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            hits += [f"{path.relative_to(ROOT)}:{number} ({label})"
                     for label, pattern in FORBIDDEN if pattern.search(line)]
    assert hits == []


def scrub():
    spec = importlib.util.spec_from_file_location("scrub_paths", ROOT / "scripts" / "scrub_paths.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.scrub


def test_scrub_replaces_repo_home_and_temp_paths():
    text = ("/work/repo/tests/x.py /Users/someone/.cache/y "
            "/private/var/folders/ab/cdef/T/pytest-of-someone/pytest-0/t0/a.json")
    out = scrub()(text, "/work/repo")
    assert out == "<repo>/tests/x.py <home>/.cache/y <tmp>"
    assert "someone" not in out
