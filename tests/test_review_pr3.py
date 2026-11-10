"""Independent review of PR #3 (10 Nov 2026, code-reviewer agent): four verified findings, each reproduced first.

F1  an unhashable spec type crashed the catalog loader (exit 1, traceback), outside the exit-6 guard
F2  attach_advisory kept a non-string quote in an accepted advisory when the verdict was not supported/unsupported
F3  attach_advisory tied the catalog to the audit by catalog_id only: a different catalog with the same id passed
F4  common negations ("is unable to", "fails to", "wasn't", "Unsupported:") were not in the word list
"""
import copy
import hashlib
import json
import os
import subprocess
import sys

import pytest

from contract_audit import cli
from contract_audit.audit import build_audit
from contract_audit.catalog import entry_reasons
from contract_audit.inputs import InputError, validate_catalog
from contract_audit.serv import attach_advisory
from conftest import DATA

CATALOG = DATA / "catalog.json"
CASE = DATA / "cases" / "c01_supported_called.json"


def run(*args):
    env = {k: v for k, v in os.environ.items() if k != "SERV_API_KEY"}
    env["PYTHONPATH"] = str(DATA.parent / "src")
    return subprocess.run([sys.executable, "-m", "contract_audit", "audit", *map(str, args)],
                          capture_output=True, text=True, env=env, cwd=str(DATA.parent))


# ---- F1 ----
@pytest.mark.parametrize("bad_type", [[], {}, ["study_id"], 7, None])
def test_spec_type_that_is_not_a_string_is_an_input_error(catalog, clone, bad_type):
    cat = clone(catalog)
    cat["tools"][0]["args_schema"]["study_id"]["type"] = bad_type
    with pytest.raises(InputError, match="type"):
        validate_catalog(cat)


def test_unhashable_spec_type_in_a_file_exits_two_without_a_traceback(tmp_path):
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    cat["tools"][0]["args_schema"]["study_id"]["type"] = []
    p = tmp_path / "catalog.json"
    p.write_text(json.dumps(cat), encoding="utf-8")
    r = run("--catalog", p, "--case", CASE)
    assert r.returncode == 2 and "Traceback" not in r.stderr, r.stderr[-300:]


def test_unexpected_error_while_loading_is_exit_six_not_one(monkeypatch, capsys):
    def boom(path):
        raise RuntimeError("synthetic loader failure")
    monkeypatch.setattr(cli, "load_catalog", boom)
    code = cli.main(["audit", "--catalog", str(CATALOG), "--case", str(CASE), "--fail-on-gaps"])
    out, err = capsys.readouterr()
    assert code == cli.EXIT_INTERNAL_ERROR and out == "" and "internal error" in err


# ---- F2 ----
def audit4(catalog, case):
    return build_audit(catalog, case("c04_uncertain_source_insufficient"))


@pytest.mark.parametrize("quote", [{1}, 5, ["a"], {"q": "x"}, float("nan"), True])
@pytest.mark.parametrize("verdict", ["uncertain", None, "supported"])
def test_a_quote_that_is_not_a_string_is_refused_for_every_verdict(catalog, case, verdict, quote):
    interp = {"fixture": True, "verdict": verdict, "quote": quote, "reasons": []}
    with pytest.raises(ValueError, match="quote"):
        attach_advisory(audit4(catalog, case), "OB-4", interp, catalog)


# ---- F3 ----
def test_audit_records_the_digest_of_the_catalog_it_was_built_from(catalog, case):
    canonical = json.dumps(catalog, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert audit4(catalog, case)["catalog_sha256"] == hashlib.sha256(canonical).hexdigest()


@pytest.mark.parametrize("edit", ["source text and hash", "source text only", "tool quote"])
def test_a_different_catalog_with_the_same_id_is_refused(catalog, case, clone, edit):
    forged = clone(catalog)
    src = forged["sources"]["SRC-SYN-D"]
    if edit == "tool quote":
        next(t for t in forged["tools"] if t["tool_id"] == "SYN-CARDIAC-1")["quote"] = "measure cardiac size"
    else:
        src["text"] += " FORGED quote sentence here."
        if edit == "source text and hash":
            src["sha256"] = hashlib.sha256(src["text"].encode("utf-8")).hexdigest()
    interp = {"fixture": True, "verdict": "supported", "quote": "FORGED quote sentence here", "reasons": []}
    with pytest.raises(ValueError, match="catalog"):
        attach_advisory(audit4(catalog, case), "OB-4", interp, forged)


def test_the_same_catalog_reloaded_still_attaches(catalog, case):
    reloaded = json.loads(CATALOG.read_text(encoding="utf-8"))
    interp = {"fixture": True, "verdict": "unsupported", "quote": "measure cardiac size on radiographs", "reasons": []}
    out = attach_advisory(audit4(catalog, case), "OB-4", interp, copy.deepcopy(reloaded))
    assert out["serv_advisory"]["OB-4"]["accepted"] is True


# ---- F4 ----
QUOTE = "flag nodule-like findings on chest-xr studies"


@pytest.mark.parametrize("lead", [
    "Tool SYN-NODULE-1 wasn't built to", "Tool SYN-NODULE-1 is unable to", "Tool SYN-NODULE-1 fails to",
    "Tool SYN-NODULE-1 lacks the ability to", "Unsupported:", "Tool SYN-NODULE-1 shouldn't be used to",
    "Tool SYN-NODULE-1 couldn't", "Tool SYN-NODULE-1 hasn't been cleared to",
])
def test_more_negation_phrasings_are_not_confirmed(catalog, clone, lead):
    cat = clone(catalog)
    tool = next(t for t in cat["tools"] if t["tool_id"] == "SYN-NODULE-1")
    src = cat["sources"][tool["source_id"]]
    src["text"] = f"{lead} {QUOTE}."
    src["sha256"] = hashlib.sha256(src["text"].encode("utf-8")).hexdigest()
    assert "negation_near_quote" in entry_reasons(cat, tool)
