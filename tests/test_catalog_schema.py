"""The catalog's args_schema is validated at the boundary: unbounded or malformed specs never load."""
import json

import pytest

from contract_audit.calls import validate_calls
from contract_audit.inputs import InputError, load_catalog, validate_catalog

NUM = {"type": "number", "min": 0.5, "max": 4.0}
LST = {"type": "number_list", "max_items": 4, "item_min": 0, "item_max": 10, "max_total": 12}


def tool0(cat):
    return cat["tools"][0]


def set_schema(extra):
    def f(cat):
        t = tool0(cat)
        t["args_schema"] = dict({"study_id": {"type": "study_id"}}, **extra)
    return f


def drop_key(key):
    return lambda cat: tool0(cat).pop(key)


BAD = {
    "required_args missing": (drop_key("required_args"), "required_args"),
    "args_schema missing": (drop_key("args_schema"), "args_schema"),
    "args_schema is list": (lambda c: tool0(c).update(args_schema=[]), "args_schema"),
    "args_schema null": (lambda c: tool0(c).update(args_schema=None), "args_schema"),
    "spec is string": (set_schema({"x": "number"}), "x"),
    "spec unknown type": (set_schema({"x": {"type": "regex"}}), "type"),
    "spec no type": (set_schema({"x": {}}), "type"),
    "required arg not in schema": (lambda c: tool0(c).update(required_args=["study_id", "ghost"]), "ghost"),
    "number no min": (set_schema({"x": {"type": "number", "max": 4}}), "min"),
    "number no max": (set_schema({"x": {"type": "number", "min": 0}}), "max"),
    "number nan bound": (set_schema({"x": dict(NUM, min=float("nan"))}), "min"),
    "number inf bound": (set_schema({"x": dict(NUM, max=float("inf"))}), "max"),
    "number bool bound": (set_schema({"x": dict(NUM, min=True)}), "min"),
    "number string bound": (set_schema({"x": dict(NUM, max="4")}), "max"),
    "number min above max": (set_schema({"x": dict(NUM, min=5, max=1)}), "min"),
    "list no max_total": (set_schema({"x": {k: v for k, v in LST.items() if k != "max_total"}}), "max_total"),
    "list no item_max": (set_schema({"x": {k: v for k, v in LST.items() if k != "item_max"}}), "item_max"),
    "list max_items zero": (set_schema({"x": dict(LST, max_items=0)}), "max_items"),
    "list max_items bool": (set_schema({"x": dict(LST, max_items=True)}), "max_items"),
    "list max_items float": (set_schema({"x": dict(LST, max_items=2.5)}), "max_items"),
    "list nan total": (set_schema({"x": dict(LST, max_total=float("nan"))}), "max_total"),
    "list item_min above item_max": (set_schema({"x": dict(LST, item_min=11)}), "item_min"),
    "study_id spec with extra keys": (set_schema({"study_id": {"type": "study_id", "min": 1}}), "study_id"),
}


@pytest.mark.parametrize("name", sorted(BAD))
def test_malformed_args_schema_is_an_input_error(catalog, clone, name):
    mutate, needle = BAD[name]
    cat = clone(catalog)
    mutate(cat)
    with pytest.raises(InputError, match=needle):
        validate_catalog(cat)


def test_malformed_schema_from_a_file_is_an_input_error(catalog, clone, tmp_path):
    cat = clone(catalog)
    del tool0(cat)["required_args"]
    p = tmp_path / "cat.json"
    p.write_text(json.dumps(cat), encoding="utf-8")
    with pytest.raises(InputError, match="required_args"):
        load_catalog(p)


@pytest.mark.parametrize("spec", [{"type": "number"}, {"type": "number", "min": 0}, {"type": "number_list"},
                                  {"type": "number", "min": float("nan"), "max": 1}, "number", None])
def test_validate_calls_fails_closed_on_a_malformed_spec_without_crashing(catalog, case, clone, spec):
    cat, c = clone(catalog), clone(case("c01_supported_called"))
    t = next(t for t in cat["tools"] if t["tool_id"] == "SYN-NODULE-1")
    t["required_args"] = ["study_id", "x"]
    t["args_schema"] = {"study_id": {"type": "study_id"}, "x": spec}
    c["proposed_calls"][0]["args"] = {"study_id": "SYN-STUDY-001", "x": 1}
    r = validate_calls(cat, c["study"], c["proposed_calls"])[0]
    assert r["status"] == "invalid" and "arg_invalid:x" in r["reasons"]


def test_shipped_catalog_still_loads(catalog):
    validate_catalog(catalog)
