"""Call argument VALUES are validated against the catalog's args_schema, not just key presence.

The catalog is fictional and the schema bounds below are engineering limits of synthetic mock tools.
They are not clinical thresholds and do not measure anything real.
"""
import pytest

from contract_audit.audit import build_audit
from contract_audit.calls import validate_calls


def only(result):
    assert len(result) == 1
    return result[0]


def call_with(catalog, case, clone, args):
    c = clone(case("c01_supported_called"))
    c["proposed_calls"][0]["args"] = args
    return c, only(validate_calls(catalog, c["study"], c["proposed_calls"]))


@pytest.mark.parametrize("value", [None, "", [], {}, -5, 1e9, 0, True, "SYN-STUDY-999", "syn-study-001",
                                   " SYN-STUDY-001", ["SYN-STUDY-001"], float("nan")])
def test_study_id_must_be_a_nonempty_string_equal_to_the_studys_id(catalog, case, clone, value):
    c, r = call_with(catalog, case, clone, {"study_id": value})
    assert r["status"] == "invalid" and "arg_invalid:study_id" in r["reasons"]
    assert build_audit(catalog, dict(c, receipts=c["receipts"]))["obligations"]["OB-1"]["full_support"] is False


def test_the_studys_own_id_is_still_valid(catalog, case, clone):
    _, r = call_with(catalog, case, clone, {"study_id": "SYN-STUDY-001"})
    assert r["status"] == "valid" and r["reasons"] == []


def test_a_tool_without_an_args_schema_cannot_be_called(catalog, case, clone):
    cat = clone(catalog)
    next(t for t in cat["tools"] if t["tool_id"] == "SYN-NODULE-1").pop("args_schema", None)
    c = case("c01_supported_called")
    r = only(validate_calls(cat, c["study"], c["proposed_calls"]))
    assert r["status"] == "invalid" and "args_schema_missing" in r["reasons"]


@pytest.mark.parametrize("extra", [{"extra": 1}, {"study_ID": "SYN-STUDY-001"}, {"": None}])
def test_arguments_outside_the_schema_are_refused(catalog, case, clone, extra):
    _, r = call_with(catalog, case, clone, dict({"study_id": "SYN-STUDY-001"}, **extra))
    key = next(iter(extra))
    assert r["status"] == "invalid" and f"unknown_arg:{key}" in r["reasons"]


def test_missing_required_arg_is_still_reported_alongside_a_bad_extra(catalog, case, clone):
    _, r = call_with(catalog, case, clone, {"other": 1})
    assert "missing_arg:study_id" in r["reasons"] and "unknown_arg:other" in r["reasons"]


# ---- numeric arguments: a synthetic engineering scale factor, range 0.5..4.0 (not a clinical value) ----
def with_numeric_tool(catalog, case, clone, value):
    cat, c = clone(catalog), clone(case("c01_supported_called"))
    tool = next(t for t in cat["tools"] if t["tool_id"] == "SYN-NODULE-1")
    tool["required_args"] = ["study_id", "scale_factor"]
    tool["args_schema"] = {"study_id": {"type": "study_id"},
                           "scale_factor": {"type": "number", "min": 0.5, "max": 4.0}}
    c["proposed_calls"][0]["args"] = {"study_id": "SYN-STUDY-001", "scale_factor": value}
    return cat, c, only(validate_calls(cat, c["study"], c["proposed_calls"]))


@pytest.mark.parametrize("value", [0.5, 1, 2.5, 4, 4.0])
def test_number_inside_its_bounds_is_valid(catalog, case, clone, value):
    _, _, r = with_numeric_tool(catalog, case, clone, value)
    assert r["status"] == "valid"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), True, False, "2", None, [],
                                   {}, 0.49, 4.01, -1, 1e9, 1e308])
def test_number_that_is_not_finite_numeric_or_in_bounds_is_invalid(catalog, case, clone, value):
    cat, c, r = with_numeric_tool(catalog, case, clone, value)
    assert r["status"] == "invalid" and "arg_invalid:scale_factor" in r["reasons"]
    assert build_audit(cat, c)["obligations"]["OB-1"]["full_support"] is False


# ---- list of quantities: items 0..10, at most 4 items, sum at most 12 (synthetic engineering limits) ----
def with_list_tool(catalog, case, clone, value):
    cat, c = clone(catalog), clone(case("c01_supported_called"))
    tool = next(t for t in cat["tools"] if t["tool_id"] == "SYN-NODULE-1")
    tool["required_args"] = ["study_id", "quantities"]
    tool["args_schema"] = {"study_id": {"type": "study_id"},
                           "quantities": {"type": "number_list", "max_items": 4, "item_min": 0,
                                          "item_max": 10, "max_total": 12}}
    c["proposed_calls"][0]["args"] = {"study_id": "SYN-STUDY-001", "quantities": value}
    return cat, c, only(validate_calls(cat, c["study"], c["proposed_calls"]))


@pytest.mark.parametrize("value", [[1], [0], [10, 2], [3, 3, 3, 3], [2.5, 2.5, 7], [12 - 10, 10]])
def test_list_inside_item_count_item_and_sum_bounds_is_valid(catalog, case, clone, value):
    _, _, r = with_list_tool(catalog, case, clone, value)
    assert r["status"] == "valid", r


@pytest.mark.parametrize("value", [
    [], "1,2", None, 5, {"a": 1},                       # not a non-empty list
    [1, 2, 3, 4, 5],                                    # too many items
    [-0.1], [10.5],                                     # item out of range
    [10, 2.5], [6, 6, 1], [10, 10],                     # sum above max_total (each item in range)
    [1, float("nan")], [float("inf")], [1, True], [1, "2"], [1, None], [[1]],   # malformed items
    [1e308, 1e308],                                     # sum overflows to infinity
])
def test_list_outside_its_bounds_or_malformed_is_invalid(catalog, case, clone, value):
    cat, c, r = with_list_tool(catalog, case, clone, value)
    assert r["status"] == "invalid" and "arg_invalid:quantities" in r["reasons"]
    assert build_audit(cat, c)["obligations"]["OB-1"]["full_support"] is False


def test_sum_that_overflows_is_invalid_even_with_huge_bounds(catalog, case, clone):
    cat, c, _ = with_list_tool(catalog, case, clone, [1])
    spec = next(t for t in cat["tools"] if t["tool_id"] == "SYN-NODULE-1")["args_schema"]["quantities"]
    spec.update(item_max=1.7e308, max_total=1.7e308)
    c["proposed_calls"][0]["args"]["quantities"] = [1.7e308, 1.7e308]
    r = only(validate_calls(cat, c["study"], c["proposed_calls"]))
    assert r["status"] == "invalid" and "arg_invalid:quantities" in r["reasons"]
