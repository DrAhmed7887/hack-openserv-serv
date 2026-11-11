import itertools
import json

import pytest

from contract_audit.audit import build_audit
from test_coverage import CASES


@pytest.mark.parametrize("case_id", CASES)
def test_audit_matches_hand_written_expectations(catalog, case, expected, case_id):
    a, exp = build_audit(catalog, case(case_id)), expected(case_id)
    assert a["completeness"] == exp["completeness"]
    assert {k: {"disposition": v["disposition"], "receipt_status": v["receipt_status"],
                "full_support": v["full_support"]} for k, v in a["obligations"].items()} == exp["obligations"]
    assert {k: v["status"] for k, v in a["calls"].items()} == exp["calls"]
    assert a["statements"] == exp["statements"]
    assert a["report_gaps"] == exp["report_gaps"]


def test_audit_is_byte_identical_across_runs(catalog, case):
    one = json.dumps(build_audit(catalog, case("c07_combined")), sort_keys=True)
    two = json.dumps(build_audit(catalog, case("c07_combined")), sort_keys=True)
    assert one == two


def test_audit_labels_synthetic_signed_rules_and_serv_not_run(catalog, case):
    a = build_audit(catalog, case("c01_supported_called"))
    assert a["synthetic"] is True
    assert a["signoff"]["status"] == "engineering_rules_signed"
    assert a["signoff"]["catalog"] == "fictional, unsigned"
    assert a["serv"] == {"status": "not_run", "executed": False, "fixture": False}
    text = json.dumps(a)
    assert "SERV result" not in text
    assert "step_trace" not in text


def test_summary_counts_the_four_dispositions(catalog, case):
    s = build_audit(catalog, case("c07_combined"))["summary"]
    assert s["by_disposition"] == {"supported_called": 3, "supported_omitted": 1,
                                   "unsupported": 1, "uncertain": 1}
    assert s["fully_supported"] == 1 and s["obligations"] == 6


def test_full_support_never_reported_without_a_valid_receipt_for_every_obligation(catalog, case):
    """Property over every subset of each fixture case's receipts: no full_support without a valid receipt."""
    for case_id in CASES:
        base = case(case_id)
        receipts = base["receipts"]
        for r in range(len(receipts) + 1):
            for keep in itertools.combinations(range(len(receipts)), r):
                c = json.loads(json.dumps(base))
                c["receipts"] = [receipts[i] for i in keep]
                a = build_audit(catalog, c)
                if a["completeness"] == "full_support":
                    assert all(o["full_support"] and o["receipt_status"] == "valid"
                               and o["disposition"] == "supported_called"
                               for o in a["obligations"].values()), (case_id, keep)


def test_study_with_no_obligations_is_never_full_support(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["study"]["obligations"] = []
    c["proposed_calls"], c["receipts"], c["draft_report"]["statements"] = [], [], []
    a = build_audit(catalog, c)
    assert a["completeness"] == "gaps_found"
    assert a["summary"]["obligations"] == 0
