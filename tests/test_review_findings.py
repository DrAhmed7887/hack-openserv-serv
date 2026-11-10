"""Regressions for the independent review (docs/G1_RESULTS.md, cycle 12). Each starts from a fixture and
mutates it; the invariant is that nothing malformed or weakly confirmed can reach full_support."""
import json

import pytest

from contract_audit.audit import build_audit
from contract_audit.inputs import InputError, load_case
from contract_audit.serv import (NotConfigured, ServClient, attach_advisory, load_config,
                                 parse_interpretation)


def tool(cat, tool_id):
    return next(t for t in cat["tools"] if t["tool_id"] == tool_id)


def disp(audit, oid="OB-1"):
    return audit["obligations"][oid]["disposition"]


# 1. confirmation must be tied to the entry's own modality and finding class
def test_empty_quote_and_terms_never_confirm(catalog, case, clone):
    cat, c = clone(catalog), clone(case("c01_supported_called"))
    cat["tools"].append({"tool_id": "EVIL", "finding_class": "fracture_like", "modality": "chest-xr",
                         "modality_term": "", "finding_term": "", "quote": "", "required_args": [], "args_schema": {},
                         "source_id": "SRC-SYN-A"})
    c["study"]["obligations"][0]["finding_class"] = "fracture_like"
    c["proposed_calls"][0]["tool_id"] = "EVIL"
    c["receipts"] = []
    a = build_audit(cat, c)
    assert disp(a) == "uncertain" and a["completeness"] == "gaps_found"


def test_finding_term_must_match_the_entrys_finding_class(catalog, clone):
    from contract_audit.catalog import resolve_capability
    cat = clone(catalog)
    tool(cat, "SYN-NODULE-1")["finding_class"] = "fracture_like"
    r = resolve_capability(cat, "chest-xr", "fracture_like")
    assert r["capability"] == "uncertain" and "finding_term_mismatch" in r["reasons"]


def test_modality_term_must_match_the_entrys_modality(catalog, clone):
    from contract_audit.catalog import resolve_capability
    cat = clone(catalog)
    tool(cat, "SYN-FRACTURE-1")["modality"] = "chest-xr"
    r = resolve_capability(cat, "chest-xr", "fracture_like")
    assert r["capability"] == "uncertain" and "modality_term_mismatch" in r["reasons"]


# 2. and 3. duplicate ids may not hide a statement or an obligation
def test_duplicate_statement_id_is_refused(catalog, case, clone):
    c = clone(case("c02_supported_omitted"))
    c["draft_report"]["statements"].append(
        {"statement_id": "ST-1", "obligation_id": "OB-2", "kind": "discloses_not_assessed", "cites_receipt": None, "text": "x"})
    with pytest.raises(InputError, match="duplicate statement_id"):
        build_audit(catalog, c)


def test_duplicate_obligation_id_is_refused(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["study"]["obligations"].insert(0, {"obligation_id": "OB-1", "finding_class": "fracture_like"})
    with pytest.raises(InputError, match="duplicate obligation_id"):
        build_audit(catalog, c)


# 4. a null receipt id must not match an uncited claim
def test_null_receipt_id_is_refused(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    c["receipts"][0]["receipt_id"] = None
    c["draft_report"]["statements"][0]["cites_receipt"] = None
    with pytest.raises(InputError, match="receipt_id"):
        build_audit(catalog, c)


def test_duplicate_receipt_id_is_refused(catalog, case, clone):
    c = clone(case("c07_combined"))
    c["receipts"][1]["receipt_id"] = c["receipts"][0]["receipt_id"]
    with pytest.raises(InputError, match="duplicate receipt_id"):
        build_audit(catalog, c)


# 5. args must be an object
@pytest.mark.parametrize("bad", ["xxstudy_idxx", ["study_id"], None, 7])
def test_args_that_is_not_an_object_is_refused(catalog, case, clone, bad):
    c = clone(case("c01_supported_called"))
    c["proposed_calls"][0]["args"] = bad
    with pytest.raises(InputError, match="args"):
        build_audit(catalog, c)


# 8. nested structure is validated at the boundary: InputError, never a traceback
def mutations():
    def drop(path):
        def f(c):
            node = c
            for k in path[:-1]:
                node = node[k]
            del node[path[-1]]
        return f

    def setv(path, value):
        def f(c):
            node = c
            for k in path[:-1]:
                node = node[k]
            node[path[-1]] = value
        return f
    return [
        ("calls null", setv(["proposed_calls"], None)),
        ("call missing id", drop(["proposed_calls", 0, "call_id"])),
        ("receipt missing executor", drop(["receipts", 0, "executor"])),
        ("obligation missing id", drop(["study", "obligations", 0, "obligation_id"])),
        ("statements null", setv(["draft_report", "statements"], None)),
        ("obligation id list", setv(["study", "obligations", 0, "obligation_id"], ["a"])),
        ("statement missing kind", drop(["draft_report", "statements", 0, "kind"])),
        ("statement missing cites", drop(["draft_report", "statements", 0, "cites_receipt"])),
        ("study is list", setv(["study"], [])),
        ("receipt output not object", setv(["receipts", 0, "output"], "x")),
    ]


@pytest.mark.parametrize("name,mutate", mutations(), ids=[m[0] for m in mutations()])
def test_malformed_case_is_an_input_error_not_a_crash(case, clone, tmp_path, name, mutate):
    c = clone(case("c01_supported_called"))
    mutate(c)
    p = tmp_path / "c.json"
    p.write_text(json.dumps(c), encoding="utf-8")
    with pytest.raises(InputError):
        load_case(p)


def test_malformed_catalog_is_an_input_error(catalog, clone, tmp_path):
    from contract_audit.inputs import load_catalog
    for mutate in (lambda c: c["sources"]["SRC-SYN-A"].update(text=None),
                   lambda c: c.update(tools={}),
                   lambda c: c["tools"][0].update(required_args="study_id"),
                   lambda c: c.update(sources=[])):
        cat = clone(catalog)
        mutate(cat)
        p = tmp_path / "cat.json"
        p.write_text(json.dumps(cat), encoding="utf-8")
        with pytest.raises(InputError):
            load_catalog(p)


# 6. SERV status labels cannot overstate
def test_attach_advisory_refuses_a_result_that_is_neither_fixture_nor_executed(catalog, case):
    a = build_audit(catalog, case("c04_uncertain_source_insufficient"))
    with pytest.raises(ValueError, match="neither fixture nor executed"):
        attach_advisory(a, "OB-4", parse_interpretation({}, "s"), catalog)


def test_client_requires_real_credentials_even_for_a_transport(catalog):
    with pytest.raises(NotConfigured):
        ServClient(None, transport=lambda r, c: {}, live=True)
    ServClient(load_config({"SERV_API_KEY": "test-not-a-real-key-123"}), transport=lambda r, c: {})


# 7. non-string quote
@pytest.mark.parametrize("quote", [5, ["a"], None, {"a": 1}])
def test_non_string_quote_is_rejected_not_a_crash(quote):
    content = json.dumps({"verdict": "supported", "quote": quote})
    r = parse_interpretation({"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}, "source")
    assert r["accepted"] is False and "quote_not_string" in r["reasons"]
