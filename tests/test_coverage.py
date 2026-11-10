import pytest

from contract_audit.coverage import assess_obligations

CASES = ["c01_supported_called", "c02_supported_omitted", "c03_unsupported",
         "c04_uncertain_source_insufficient", "c05_missing_receipt", "c06_execution_failure",
         "c07_combined"]


def assess(catalog, c):
    return assess_obligations(catalog, c["study"], c["proposed_calls"], c["receipts"])


@pytest.mark.parametrize("case_id", CASES)
def test_obligations_match_hand_written_expectations(catalog, case, expected, case_id):
    c, exp = case(case_id), expected(case_id)
    obligations, _ = assess(catalog, c)
    actual = {k: {"disposition": v["disposition"], "receipt_status": v["receipt_status"],
                  "full_support": v["full_support"]} for k, v in obligations.items()}
    assert actual == exp["obligations"]


@pytest.mark.parametrize("case_id", CASES)
def test_call_statuses_match_hand_written_expectations(catalog, case, expected, case_id):
    c, exp = case(case_id), expected(case_id)
    _, calls = assess(catalog, c)
    assert {x["call_id"]: x["status"] for x in calls} == exp["calls"]


def test_removing_receipt_removes_full_support(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["receipts"] = []
    ob = assess(catalog, c)[0]["OB-1"]
    assert ob["disposition"] == "supported_called"
    assert ob["receipt_status"] == "missing"
    assert ob["full_support"] is False


def test_invalid_call_does_not_count_as_called(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["proposed_calls"][0]["args"] = {}
    ob = assess(catalog, c)[0]["OB-1"]
    assert ob["disposition"] == "supported_omitted"
    assert "call_invalid" in ob["reasons"]
    assert ob["full_support"] is False


def test_removed_capability_with_call_and_receipt_is_unsupported_not_full(catalog, case, clone):
    cat, c = clone(catalog), case("c01_supported_called")
    cat["tools"] = [t for t in cat["tools"] if t["tool_id"] != "SYN-NODULE-1"]
    ob = assess(cat, c)[0]["OB-1"]
    assert ob["disposition"] == "unsupported"
    assert ob["full_support"] is False


def test_uncertain_capability_never_full_even_with_valid_receipt(catalog, case):
    ob = assess(catalog, case("c04_uncertain_source_insufficient"))[0]["OB-4"]
    assert ob["disposition"] == "uncertain"
    assert ob["full_support"] is False
