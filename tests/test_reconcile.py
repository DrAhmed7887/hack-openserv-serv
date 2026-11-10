import pytest

from contract_audit.coverage import assess_obligations
from contract_audit.reconcile import reconcile_report
from test_coverage import CASES


def reconcile(catalog, c):
    obligations, _ = assess_obligations(catalog, c["study"], c["proposed_calls"], c["receipts"])
    return reconcile_report(obligations, c["draft_report"])


@pytest.mark.parametrize("case_id", CASES)
def test_statements_and_gaps_match_hand_written_expectations(catalog, case, expected, case_id):
    result, exp = reconcile(catalog, case(case_id)), expected(case_id)
    assert result["statements"] == exp["statements"]
    assert result["report_gaps"] == exp["report_gaps"]


def test_report_is_consistent_only_when_every_claim_has_its_receipt_and_no_gaps(catalog, case):
    assert reconcile(catalog, case("c01_supported_called"))["report_consistent"] is True
    assert reconcile(catalog, case("c03_unsupported"))["report_consistent"] is True  # disclosed limitation
    assert reconcile(catalog, case("c02_supported_omitted"))["report_consistent"] is False
    assert reconcile(catalog, case("c07_combined"))["report_consistent"] is False


def test_claim_without_citation_on_fully_supported_obligation_is_flagged(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["draft_report"]["statements"][0]["cites_receipt"] = None
    r = reconcile(catalog, c)
    assert r["statements"]["ST-1"] == {"outcome": "receipt_mismatch", "action": "cite_valid_receipt"}
    assert r["report_consistent"] is False


def test_claim_citing_another_receipt_is_flagged(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["draft_report"]["statements"][0]["cites_receipt"] = "RCPT-OTHER"
    assert reconcile(catalog, c)["statements"]["ST-1"]["outcome"] == "receipt_mismatch"


def test_statement_about_unknown_obligation_is_flagged(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["draft_report"]["statements"][0]["obligation_id"] = "OB-99"
    r = reconcile(catalog, c)
    assert r["statements"]["ST-1"] == {"outcome": "unknown_obligation", "action": "remove_statement"}
    # OB-1 is now unmentioned. Fully supported or not, the report must address it (review round 2, B6).
    assert r["report_gaps"] == {"OB-1": "add_cited_claim"}


def test_obligation_with_no_statement_and_no_full_support_is_a_gap(catalog, case, clone):
    c = clone(case("c02_supported_omitted"))
    c["draft_report"]["statements"] = []
    r = reconcile(catalog, c)
    assert r["report_gaps"] == {"OB-2": "add_limitation_statement"}


def test_unsupported_claim_is_never_rewritten_by_the_reconciler(catalog, case):
    r = reconcile(catalog, case("c02_supported_omitted"))
    assert set(r["statements"]["ST-1"]) == {"outcome", "action"}  # action label only, no generated text


# ---- a limitation disclosure contradicts an obligation that is fully supported ----
def as_disclosure(c, index=0):
    st = c["draft_report"]["statements"][index]
    st.update(kind="discloses_not_assessed", cites_receipt=None)
    return c


def test_disclosing_not_assessed_on_a_fully_supported_obligation_is_a_contradiction(catalog, case, clone):
    r = reconcile(catalog, as_disclosure(clone(case("c01_supported_called"))))
    assert r["statements"]["ST-1"] == {"outcome": "disclosure_contradicts_support",
                                       "action": "replace_with_cited_claim"}
    assert r["report_consistent"] is False


@pytest.mark.parametrize("case_id", ["c02_supported_omitted", "c03_unsupported", "c04_uncertain_source_insufficient",
                                     "c05_missing_receipt", "c06_execution_failure"])
def test_disclosure_on_an_obligation_without_full_support_stays_accepted(catalog, case, clone, case_id):
    r = reconcile(catalog, as_disclosure(clone(case(case_id))))
    assert r["statements"]["ST-1"] == {"outcome": "limitation_disclosed", "action": None}
    assert r["report_consistent"] is True


def test_disclosure_beside_a_valid_cited_claim_still_flags_the_disclosure(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["draft_report"]["statements"].append(
        {"statement_id": "ST-2", "obligation_id": "OB-1", "kind": "discloses_not_assessed",
         "cites_receipt": None, "text": "x"})
    r = reconcile(catalog, c)
    assert r["statements"]["ST-1"]["outcome"] == "supported_by_receipt"
    assert r["statements"]["ST-2"]["outcome"] == "disclosure_contradicts_support"
    assert r["report_consistent"] is False
