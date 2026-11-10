import importlib.util
import json
import re

from conftest import DATA

ROOT = DATA.parent
HTML = ROOT / "mock" / "index.html"


def builder():
    spec = importlib.util.spec_from_file_location("build_mock", ROOT / "scripts" / "build_mock.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def embedded():
    m = re.search(r'<script type="application/json" id="mock-data">(.*?)</script>', HTML.read_text(encoding="utf-8"), re.S)
    return json.loads(m.group(1))


def test_embedded_data_is_exactly_what_the_offline_modules_produce():
    assert embedded() == builder().payload()


def test_page_is_labelled_a_replay_that_calls_no_server_and_names_all_five_screens():
    text = HTML.read_text(encoding="utf-8")
    assert "REPLAY OF REAL OUTPUT" in text and "This page calls no server" in text
    for step in ("catalog", "study", "coverage", "repair", "export"):
        assert f'id="step-{step}"' in text


def test_mock_makes_no_network_requests_and_loads_nothing_external():
    text = HTML.read_text(encoding="utf-8")
    assert not re.search(r"https?://", text)
    for api in ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "<img", "<link", "src="):
        assert api not in text


def test_serv_appears_only_as_recorded_advice_that_cannot_change_the_result():
    text = HTML.read_text(encoding="utf-8")
    assert "step_trace" not in text and "recorded live run" in text and "SERV cannot change it" in text
    p = builder().payload()
    uncertain = {k for k, o in p["audit"]["obligations"].items() if o["disposition"] == "uncertain"}
    assert set(p["serv_recorded"]) and set(p["serv_recorded"]) <= uncertain
    rec = json.loads((ROOT / "docs" / "serv_run" / "c07_combined.json").read_text(encoding="utf-8"))
    for oid, r in p["serv_recorded"].items():
        assert (r["verdict"], r["quote"]) == (rec["serv_advisory"][oid]["verdict"], rec["serv_advisory"][oid]["quote"])
    # the recorded answer quotes no study type, so the current rules do not accept it
    assert p["serv_recorded"]["OB-4"]["accepted_now"] is False
    assert p["serv_recorded"]["OB-4"]["reasons_now"] == ["quote_does_not_name_modality"]


def test_every_number_on_the_first_screen_comes_from_the_committed_eval_results():
    adv = json.loads((ROOT / "eval" / "results" / "adversarial_v1.json").read_text(encoding="utf-8"))
    v2 = json.loads((ROOT / "eval" / "results" / "serv_batch_v2.json").read_text(encoding="utf-8"))["summary"]
    e = builder().payload()["eval"]
    assert (e["broken"], e["flagged_right"], e["passed_as_complete"]) == (
        adv["broken"]["n"], adv["broken"]["right_reason"], adv["broken"]["false_full_support"])
    assert (e["clean"], e["clean_passed"]) == (adv["clean"]["n"], adv["clean"]["full_support"])
    assert (e["serv_over"], e["serv_over_of"], e["serv_over_accepted"]) == (
        v2["over_reach"]["n"], v2["over_reach"]["of"], v2["over_reach"]["accepted_now"])
    assert (e["serv_accepted"], e["serv_accepted_right"]) == (
        v2["accepted_advice_now"]["n"], v2["accepted_advice_now"]["match_designed"])


def test_payload_is_labelled_fixture_and_synthetic():
    p = builder().payload()
    assert p["audit"]["synthetic"] is True and p["audit"]["serv"]["executed"] is False
    assert p["audit"]["case_id"] == "c07_combined"


# ---- routing: the URL hash and the visible step stay in step (history/back/forward), and every
# reconciler outcome has a label. Behaviour is checked by running the mock's real script in node. ----
import shutil
import subprocess

import pytest

from contract_audit.reconcile import ACTIONS, OUTCOMES, reconcile_report

HARNESS = ROOT / "tests" / "mock_harness.js"


def routing(scenarios):
    out = subprocess.run(["node", str(HARNESS), str(HTML), json.dumps(scenarios)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


@needs_node
def test_clicking_a_step_updates_the_url_hash():
    [steps] = routing([{"initial": "", "actions": [{"click": "coverage"}, {"click": "repair"}]}])
    assert [s["visible"] for s in steps] == [["catalog"], ["coverage"], ["repair"]]
    assert [s["hash"] for s in steps][1:] == ["#coverage", "#repair"]


@needs_node
def test_back_and_forward_show_the_step_in_the_url():
    [steps] = routing([{"initial": "#study", "actions": [{"hash": "#coverage"}, {"hash": "#study"}, {"hash": "#export"}]}])
    assert [s["visible"] for s in steps] == [["study"], ["coverage"], ["study"], ["export"]]


@needs_node
@pytest.mark.parametrize("bad", ["#", "#nope", "#__proto__", "#constructor", "#catalog%20", "#../x"])
def test_an_unknown_hash_falls_back_to_the_first_step_and_exactly_one_step_is_visible(bad):
    [steps] = routing([{"initial": bad, "actions": [{"hash": "#coverage"}, {"hash": bad}]}])
    assert [s["visible"] for s in steps] == [["catalog"], ["coverage"], ["catalog"]]


@needs_node
def test_clicking_the_current_step_is_harmless():
    [steps] = routing([{"initial": "#repair", "actions": [{"click": "repair"}]}])
    assert [s["visible"] for s in steps] == [["repair"], ["repair"]]


def test_mock_has_a_hashchange_handler():
    assert "hashchange" in HTML.read_text(encoding="utf-8")


def mock_map(name):
    text = HTML.read_text(encoding="utf-8")
    block = re.search(r"var " + name + r" = \{(.*?)\};", text, re.S).group(1)
    return set(re.findall(r"(\w+):", block))


def test_every_reconciler_outcome_and_action_has_a_label_in_the_mock():
    assert mock_map("OUTCOME") == set(OUTCOMES)
    assert set(ACTIONS) <= mock_map("ACTION")


def test_the_declared_outcome_and_action_sets_are_exactly_what_the_reconciler_emits():
    def ob(disposition, full, rids=()):
        return {"disposition": disposition, "full_support": full, "receipt_id": rids[0] if rids else None,
                "receipt_ids": list(rids)}
    obligations = {"A": ob("supported_called", True, ("R",)), "B": ob("supported_omitted", False),
                   "C": ob("unsupported", False), "D": ob("uncertain", False),
                   "E": ob("supported_called", False)}
    seen = []
    for oid in obligations:
        for kind, cite in (("claims_assessed", "R"), ("claims_assessed", None), ("discloses_not_assessed", None),
                           ("bogus", None)):
            seen.append(reconcile_report(obligations, {"statements": [
                {"statement_id": "S", "obligation_id": oid, "kind": kind, "cites_receipt": cite}]})["statements"]["S"])
    seen.append(reconcile_report(obligations, {"statements": [
        {"statement_id": "S", "obligation_id": "ZZ", "kind": "claims_assessed", "cites_receipt": None}]})["statements"]["S"])
    assert {v["outcome"] for v in seen} == set(OUTCOMES)
    gap_actions = {"add_limitation_statement", "add_cited_claim"}  # report_gaps actions, not statement actions
    assert {v["action"] for v in seen if v["action"]} | gap_actions == set(ACTIONS)
