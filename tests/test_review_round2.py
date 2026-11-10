"""Second independent boundary review (docs/BLOCKER_REVIEW_2026-11-10.md, findings B1-B5), plus an empty draft
report that could still reach full_support (B6). Every test here failed at b2de604 (docs/red/15_*.RED.log).

Exit 1 means 'gaps found' and is never produced by a crash. A SERV label or acceptance can never be set by a caller.
"""
import json
import os
import subprocess
import sys

import pytest

from contract_audit import cli, inputs, reconcile
from contract_audit.audit import build_audit
from contract_audit.inputs import InputError, is_finite_number, validate_case, validate_catalog
from contract_audit.serv import attach_advisory, parse_interpretation
from conftest import DATA

CATALOG = DATA / "catalog.json"
CASE = DATA / "cases" / "c01_supported_called.json"
QUOTE_D = "measure cardiac size on radiographs"           # verbatim in SRC-SYN-D (tool of OB-4)
QUOTE_A = "flag nodule-like findings on chest-xr studies"  # verbatim in SRC-SYN-A, not in SRC-SYN-D


def run(*args):
    env = {k: v for k, v in os.environ.items() if k != "SERV_API_KEY"}
    env["PYTHONPATH"] = str(DATA.parent / "src")
    return subprocess.run([sys.executable, "-m", "contract_audit", "audit", *map(str, args)],
                          capture_output=True, text=True, env=env, cwd=str(DATA.parent))


def with_extra(tmp_path, base, raw_value):
    """Copy a fixture file and add one extra top-level key whose JSON text is written verbatim."""
    text = base.read_text(encoding="utf-8").rstrip()
    assert text.endswith("}")
    p = tmp_path / base.name
    p.write_text(text[:-1] + f', "zz_extra": {raw_value}}}', encoding="utf-8")
    return p


# ---- B1: a huge integer literal is bad input (exit 2) on every Python version, never a ValueError traceback ----
@pytest.mark.parametrize("digits", [5000, 400])  # 5000 trips CPython's own 4300-digit limit (3.9.14+, 3.11+)
@pytest.mark.parametrize("which", ["case", "catalog"])
def test_huge_integer_literal_is_bad_input_not_a_crash(tmp_path, digits, which):
    big = with_extra(tmp_path, CASE if which == "case" else CATALOG, "9" * digits)
    r = run("--catalog", CATALOG, "--case", big) if which == "case" else run("--catalog", big, "--case", CASE)
    assert r.returncode == 2, r.stderr[-300:]
    assert "Traceback" not in r.stderr and "digits" in r.stderr


def test_negative_huge_integer_inside_a_list_is_bad_input(tmp_path):
    r = run("--catalog", CATALOG, "--case", with_extra(tmp_path, CASE, "[1, -" + "9" * 400 + "]"))
    assert r.returncode == 2 and "Traceback" not in r.stderr


def test_integer_at_the_digit_limit_is_still_read(tmp_path):
    r = run("--catalog", CATALOG, "--case", with_extra(tmp_path, CASE, "9" * inputs.MAX_INT_DIGITS))
    assert r.returncode == 0, r.stderr[-300:]


def test_any_value_error_from_the_json_parser_is_an_input_error(monkeypatch):
    def boom(*args, **kwargs):
        raise ValueError("Exceeds the limit (4300 digits) for integer string conversion")
    monkeypatch.setattr(inputs.json, "loads", boom)
    with pytest.raises(InputError, match="digits"):
        inputs.load_case(CASE)


# ---- B2: integers beyond float range never raise OverflowError ----
@pytest.mark.parametrize("value", [10 ** 400, -(10 ** 400), 10 ** 309])
def test_int_beyond_float_range_is_not_a_finite_number_and_does_not_raise(value):
    assert is_finite_number(value) is False


@pytest.mark.parametrize("value", [0, -3, 10 ** 300, 2.5])
def test_ordinary_numbers_are_still_finite(value):
    assert is_finite_number(value) is True


def numeric_tool(catalog, clone, spec):
    cat = clone(catalog)
    tool = next(t for t in cat["tools"] if t["tool_id"] == "SYN-NODULE-1")
    tool["required_args"] = ["study_id", "scale_factor"]
    tool["args_schema"] = {"study_id": {"type": "study_id"}, "scale_factor": spec}
    return cat


@pytest.mark.parametrize("spec", [
    {"type": "number", "min": 10 ** 400, "max": 10 ** 401},
    {"type": "number", "min": 0, "max": 10 ** 400},
    {"type": "number_list", "max_items": 2, "item_min": 0, "item_max": 10 ** 400, "max_total": 1},
])
def test_catalog_bound_beyond_float_range_is_an_input_error(catalog, clone, spec):
    with pytest.raises(InputError, match="finite number"):
        validate_catalog(numeric_tool(catalog, clone, spec))


@pytest.mark.parametrize("spec,value", [
    ({"type": "number", "min": 0.5, "max": 4.0}, 10 ** 400),
    ({"type": "number_list", "max_items": 4, "item_min": 0, "item_max": 10, "max_total": 12}, [1, 10 ** 400]),
])
def test_call_argument_beyond_float_range_is_invalid_not_a_crash(catalog, case, clone, spec, value):
    cat, c = numeric_tool(catalog, clone, spec), clone(case("c01_supported_called"))
    c["proposed_calls"][0]["args"] = {"study_id": "SYN-STUDY-001", "scale_factor": value}
    a = build_audit(cat, c)
    assert a["calls"]["CALL-1"] == {"status": "invalid", "reasons": ["arg_invalid:scale_factor"]}
    assert a["obligations"]["OB-1"]["full_support"] is False


# ---- B3: a string that is not UTF-8 text (a lone surrogate escape) is bad input, never a crash ----
def test_lone_surrogate_in_a_catalog_source_text_is_an_input_error(catalog, clone):
    cat = clone(catalog)
    cat["sources"]["SRC-SYN-A"]["text"] += "\ud800"
    with pytest.raises(InputError, match="surrogate"):
        validate_catalog(cat)


@pytest.mark.parametrize("where", ["statement text", "dict key"])
def test_lone_surrogate_anywhere_in_a_case_is_an_input_error(case, clone, where):
    c = clone(case("c01_supported_called"))
    if where == "statement text":
        c["draft_report"]["statements"][0]["text"] = "ok \udfff"
    else:
        c["study"]["\ud800"] = 1
    with pytest.raises(InputError, match="surrogate"):
        validate_case(c)


def test_lone_surrogate_escape_in_a_catalog_file_exits_two_without_a_traceback(tmp_path):
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    cat["sources"]["SRC-SYN-A"]["text"] += "\ud800"
    p = tmp_path / "catalog.json"
    p.write_text(json.dumps(cat), encoding="utf-8")  # ensure_ascii writes the \ud800 escape: a valid UTF-8 file
    r = run("--catalog", p, "--case", CASE)
    assert r.returncode == 2, r.stderr[-300:]
    assert "Traceback" not in r.stderr and "surrogate" in r.stderr


# ---- hardening: an unexpected internal error has its own exit code, never 1 ('gaps found'), and hides nothing ----
def test_unexpected_error_while_building_the_audit_is_not_reported_as_gaps(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise RuntimeError("synthetic internal failure \ud800")
    monkeypatch.setattr(cli, "build_audit", boom)
    code = cli.main(["audit", "--catalog", str(CATALOG), "--case", str(CASE), "--fail-on-gaps"])
    out, err = capsys.readouterr()
    assert code == cli.EXIT_INTERNAL_ERROR == 6
    assert out == "" and "internal error" in err and "not a finding" in err
    assert "Traceback" in err and "RuntimeError: synthetic internal failure \\ud800" in err  # escaped, printable


# ---- B4: the SERV status block is whitelisted and copied ----
@pytest.mark.parametrize("status", ["serv_confirmed", "executed", "fixture", "", "NOT_RUN"])
def test_serv_status_outside_the_not_run_states_is_refused(catalog, case, status):
    with pytest.raises(ValueError, match="serv"):
        build_audit(catalog, case("c01_supported_called"),
                    serv={"status": status, "executed": False, "fixture": False})


def test_serv_block_with_extra_keys_is_refused(catalog, case):
    with pytest.raises(ValueError, match="serv"):
        build_audit(catalog, case("c01_supported_called"),
                    serv={"status": "not_run", "executed": False, "fixture": False, "verdict": "supported"})


def test_serv_block_is_copied_not_aliased(catalog, case):
    blk = {"status": "not_configured", "executed": False, "fixture": False}
    a = build_audit(catalog, case("c01_supported_called"), serv=blk)
    blk.update(status="executed", executed=True)
    assert a["serv"] == {"status": "not_configured", "executed": False, "fixture": False}


# ---- B5: attach_advisory recomputes acceptance against the obligation's own catalog source ----
def fixture_interp(catalog, verdict="supported", quote=QUOTE_D, source="SRC-SYN-D"):
    content = json.dumps({"verdict": verdict, "quote": quote})
    response = {"fixture": True, "choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
    return parse_interpretation(response, catalog["sources"][source]["text"])


def audit4(catalog, case):
    return build_audit(catalog, case("c04_uncertain_source_insufficient"))


def advisory(catalog, case, interp):
    return attach_advisory(audit4(catalog, case), "OB-4", interp, catalog)["serv_advisory"]["OB-4"]


def test_a_correct_advisory_is_still_accepted(catalog, case):
    adv = advisory(catalog, case, fixture_interp(catalog))
    # the quote is verbatim but does not name chest-xr, so since the relevance rule it is not accepted as support
    assert adv["accepted"] is False and adv["reasons"] == ["quote_does_not_name_modality"]
    assert adv["human_confirmation_required"] is True


def test_caller_set_acceptance_is_recomputed_not_trusted(catalog, case):
    forged = {"fixture": True, "executed": False, "verdict": "supported", "quote": "x", "accepted": True,
              "reasons": []}
    adv = advisory(catalog, case, forged)
    assert adv["accepted"] is False and "quote_too_short" in adv["reasons"]


def test_quote_is_checked_against_the_obligations_own_source(catalog, case):
    parsed_elsewhere = fixture_interp(catalog, quote=QUOTE_A, source="SRC-SYN-A")
    assert parsed_elsewhere["accepted"] is True  # accepted against the wrong source text
    adv = advisory(catalog, case, parsed_elsewhere)
    assert adv["accepted"] is False and "quote_not_in_source" in adv["reasons"]


def test_caller_reasons_can_only_make_acceptance_stricter(catalog, case):
    adv = advisory(catalog, case, dict(fixture_interp(catalog), reasons=["finish_reason_not_stop"], accepted=True))
    assert adv["accepted"] is False and adv["reasons"][0] == "finish_reason_not_stop"


@pytest.mark.parametrize("verdict", ["CONFIRMED", "Supported", "", 1])
def test_verdict_outside_the_schema_is_refused(catalog, case, verdict):
    with pytest.raises(ValueError, match="verdict"):
        advisory(catalog, case, dict(fixture_interp(catalog), verdict=verdict))


@pytest.mark.parametrize("drop", ["verdict", "quote", "reasons"])
def test_missing_interpretation_key_is_a_value_error_not_a_key_error(catalog, case, drop):
    interp = fixture_interp(catalog)
    del interp[drop]
    with pytest.raises(ValueError, match=drop):
        advisory(catalog, case, interp)


def test_unknown_obligation_is_a_value_error_not_a_key_error(catalog, case):
    with pytest.raises(ValueError, match="OB-99"):
        attach_advisory(audit4(catalog, case), "OB-99", fixture_interp(catalog), catalog)


def test_catalog_must_be_the_one_the_audit_was_built_from(catalog, case, clone):
    other = clone(catalog)
    other["catalog_id"] = "SYN-OTHER-CATALOG"
    with pytest.raises(ValueError, match="catalog"):
        attach_advisory(audit4(catalog, case), "OB-4", fixture_interp(catalog), other)


# ---- B6: a report must address every obligation; an empty report cannot reach full_support ----
def test_empty_report_is_not_complete_even_when_every_obligation_is_fully_supported(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    assert build_audit(catalog, c)["completeness"] == "full_support"
    c["draft_report"]["statements"] = []
    a = build_audit(catalog, c)
    assert a["completeness"] == "gaps_found"
    assert a["report_gaps"] == {"OB-1": "add_cited_claim"}
    assert a["obligations"]["OB-1"]["full_support"] is True  # the tool evidence itself is unchanged


def test_add_cited_claim_is_a_declared_action():
    assert "add_cited_claim" in reconcile.ACTIONS
