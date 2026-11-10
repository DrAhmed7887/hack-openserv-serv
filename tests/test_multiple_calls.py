"""Several calls on one obligation: every call and receipt relation is represented, and any non-valid
receipt on a valid call keeps the obligation out of full support (fail closed)."""
import pytest

from contract_audit.audit import build_audit
from contract_audit.receipts import output_digest
from contract_audit.reconcile import reconcile_report


def second_call(c, clone, receipt=None, args=None, tool_id=None):
    call = clone(c["proposed_calls"][0])
    call["call_id"] = "CALL-2"
    if args is not None:
        call["args"] = args
    if tool_id:
        call["tool_id"] = tool_id
    c["proposed_calls"].append(call)
    if receipt is not None:
        base = clone(c["receipts"][0])
        base.update(call_id="CALL-2", receipt_id="RCPT-2")
        base.update(receipt)
        if "output" in receipt and "output_sha256" not in receipt:
            base["output_sha256"] = output_digest(base["output"])
        c["receipts"].append(base)
    return c


def ob(catalog, c):
    return build_audit(catalog, c)["obligations"]["OB-1"]


def by_call(o):
    return {e["call_id"]: e for e in o["calls"]}


def test_single_call_shape_is_unchanged_and_lists_its_relation(catalog, case):
    o = ob(catalog, case("c01_supported_called"))
    assert o["call_id"] == "CALL-1" and o["receipt_id"] == "RCPT-1" and o["receipt_ids"] == ["RCPT-1"]
    assert o["calls"] == [{"call_id": "CALL-1", "status": "valid", "receipt_id": "RCPT-1",
                           "receipt_status": "valid", "reasons": []}]


def test_a_later_valid_call_without_a_receipt_blocks_full_support(catalog, case, clone):
    o = ob(catalog, second_call(clone(case("c01_supported_called")), clone))
    assert o["full_support"] is False and o["receipt_status"] == "missing"
    assert by_call(o)["CALL-1"]["receipt_status"] == "valid"
    assert by_call(o)["CALL-2"]["receipt_status"] == "missing" and "no_receipt" in by_call(o)["CALL-2"]["reasons"]
    assert "no_receipt" in o["reasons"]


def test_a_later_valid_call_with_a_failed_receipt_blocks_full_support(catalog, case, clone):
    c = second_call(clone(case("c01_supported_called")), clone,
                    {"status": "error", "output": {"result_code": "MOCK-ERROR", "region_id": "R-002"}})
    o = ob(catalog, c)
    assert o["full_support"] is False and o["receipt_status"] == "failed"
    assert by_call(o)["CALL-2"]["receipt_status"] == "failed"


def test_an_earlier_unreceipted_call_does_not_hide_a_later_valid_receipt(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["receipts"] = []
    c = second_call(c, clone)
    c["receipts"] = [dict(case("c01_supported_called")["receipts"][0], call_id="CALL-2", receipt_id="RCPT-2")]
    o = ob(catalog, c)
    assert o["full_support"] is False and o["receipt_status"] == "missing"
    assert by_call(o)["CALL-2"]["receipt_id"] == "RCPT-2" and by_call(o)["CALL-2"]["receipt_status"] == "valid"
    assert o["receipt_ids"] == ["RCPT-2"]


def test_two_valid_calls_with_identical_outputs_are_full_support_and_both_listed(catalog, case, clone):
    c = second_call(clone(case("c01_supported_called")), clone, {})
    o = ob(catalog, c)
    assert o["full_support"] is True and o["receipt_status"] == "valid"
    assert o["receipt_ids"] == ["RCPT-1", "RCPT-2"] and len(o["calls"]) == 2


def test_two_valid_receipts_from_one_tool_with_different_outputs_conflict(catalog, case, clone):
    c = second_call(clone(case("c01_supported_called")), clone,
                    {"output": {"result_code": "MOCK-OK", "region_id": "R-777"}})
    o = ob(catalog, c)
    assert o["full_support"] is False and o["receipt_status"] == "invalid"
    assert "conflicting_outputs" in o["reasons"]
    assert o["receipt_ids"] == ["RCPT-1", "RCPT-2"]  # neither output is dropped


def test_an_extra_invalid_call_is_listed_but_does_not_remove_support(catalog, case, clone):
    c = second_call(clone(case("c01_supported_called")), clone, args={})
    o = ob(catalog, c)
    assert o["full_support"] is True
    assert by_call(o)["CALL-2"]["status"] == "invalid" and by_call(o)["CALL-2"]["receipt_status"] == "not_applicable"
    assert "missing_arg:study_id" in by_call(o)["CALL-2"]["reasons"]


def test_unsupported_obligation_still_lists_its_invalid_call(catalog, case):
    o = build_audit(catalog, case("c03_unsupported"))["obligations"]["OB-3"]
    assert [e["status"] for e in o["calls"]] == ["invalid"] and o["receipt_ids"] == []


@pytest.mark.parametrize("cite,outcome", [("RCPT-1", "supported_by_receipt"), ("RCPT-2", "supported_by_receipt"),
                                          ("RCPT-9", "receipt_mismatch"), (None, "receipt_mismatch")])
def test_a_claim_may_cite_any_valid_receipt_of_its_obligation(catalog, case, clone, cite, outcome):
    c = second_call(clone(case("c01_supported_called")), clone, {})
    c["draft_report"]["statements"][0]["cites_receipt"] = cite
    a = build_audit(catalog, c)
    assert a["statements"]["ST-1"]["outcome"] == outcome
