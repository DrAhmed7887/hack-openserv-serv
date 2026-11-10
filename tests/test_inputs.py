import json

import pytest

from contract_audit.inputs import InputError, load_case, load_catalog
from conftest import DATA


def write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_shipped_fixtures_load():
    assert load_catalog(DATA / "catalog.json")["catalog_id"] == "SYN-CATALOG-001"
    assert load_case(DATA / "cases" / "c01_supported_called.json")["case_id"] == "c01_supported_called"


def test_missing_file_is_a_clear_error(tmp_path):
    with pytest.raises(InputError, match="cannot read"):
        load_case(tmp_path / "nope.json")


def test_invalid_json_is_a_clear_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(InputError, match="not valid JSON"):
        load_case(p)


def test_case_not_marked_synthetic_is_refused(tmp_path, case, clone):
    c = clone(case("c01_supported_called"))
    c["synthetic"] = False
    with pytest.raises(InputError, match="synthetic"):
        load_case(write(tmp_path, "c.json", c))


def test_case_without_synthetic_flag_is_refused(tmp_path, case, clone):
    c = clone(case("c01_supported_called"))
    del c["synthetic"]
    with pytest.raises(InputError, match="synthetic"):
        load_case(write(tmp_path, "c.json", c))


def test_catalog_not_marked_synthetic_is_refused(tmp_path, catalog, clone):
    c = clone(catalog)
    c["synthetic"] = False
    with pytest.raises(InputError, match="synthetic"):
        load_catalog(write(tmp_path, "cat.json", c))


def test_case_missing_required_key_is_named(tmp_path, case, clone):
    c = clone(case("c01_supported_called"))
    del c["receipts"]
    with pytest.raises(InputError, match="receipts"):
        load_case(write(tmp_path, "c.json", c))


def test_tool_entry_missing_key_is_named(tmp_path, catalog, clone):
    c = clone(catalog)
    del c["tools"][0]["quote"]
    with pytest.raises(InputError, match="quote"):
        load_catalog(write(tmp_path, "cat.json", c))


def test_non_object_top_level_is_refused(tmp_path):
    p = tmp_path / "list.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(InputError, match="object"):
        load_case(p)
