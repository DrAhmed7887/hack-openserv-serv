"""Characterisation test: the committed fixtures are exactly what data/build_fixtures.py writes.

It passes on first run by design (it guards drift in fixed data, not new behaviour).
"""
import importlib.util
import json

from conftest import DATA


def load_builder():
    spec = importlib.util.spec_from_file_location("build_fixtures", DATA / "build_fixtures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_catalog_file_matches_builder():
    mod = load_builder()
    assert json.loads((DATA / "catalog.json").read_text(encoding="utf-8")) == mod.catalog()


def test_case_files_match_builder():
    mod = load_builder()
    for c in mod.CASES:
        assert json.loads((DATA / "cases" / f"{c['case_id']}.json").read_text(encoding="utf-8")) == c


def test_every_case_has_an_expected_file_and_vice_versa():
    cases = {p.stem for p in (DATA / "cases").glob("*.json")}
    expected = {p.stem for p in (DATA / "expected").glob("*.json")}
    assert cases == expected and len(cases) == 7
