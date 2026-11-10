#!/usr/bin/env python3
"""Embeds the real offline audit of fixture case c07 into mock/index.html, plus the recorded live SERV answer
for it (docs/serv_run/, re-scored under the current rules) and the eval headline (eval/results/). No network.

Run: python3 scripts/build_mock.py   (rewrites the mock-data block in place)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from contract_audit.audit import build_audit  # noqa: E402
from contract_audit.catalog import entry_reasons  # noqa: E402
from contract_audit.inputs import load_case, load_catalog  # noqa: E402
from contract_audit.serv import attach_advisory  # noqa: E402

CASE_ID = "c07_combined"
RECORDED_RUN = "10 Nov 2026, 10:47 UTC"  # docs/SERV_RUN.md


def recorded_serv(catalog, audit):
    """The live SERV answer recorded for this case, and whether the CURRENT rules accept it. Sends nothing."""
    rec = json.loads((ROOT / "docs" / "serv_run" / f"{CASE_ID}.json").read_text(encoding="utf-8"))
    out = {}
    for oid, adv in sorted(rec.get("serv_advisory", {}).items()):
        interp = {"fixture": True, "verdict": adv["verdict"], "quote": adv["quote"], "reasons": []}
        now = attach_advisory(audit, oid, interp, catalog)["serv_advisory"][oid]
        out[oid] = {"model": rec["serv"]["model"], "run": RECORDED_RUN, "verdict": adv["verdict"],
                    "quote": adv["quote"], "accepted_now": now["accepted"], "reasons_now": now["reasons"]}
    return out


def eval_headline():
    adv = json.loads((ROOT / "eval" / "results" / "adversarial_v1.json").read_text(encoding="utf-8"))
    v2 = json.loads((ROOT / "eval" / "results" / "serv_batch_v2.json").read_text(encoding="utf-8"))["summary"]
    return {"broken": adv["broken"]["n"], "flagged_right": adv["broken"]["right_reason"],
            "passed_as_complete": adv["broken"]["false_full_support"],
            "clean": adv["clean"]["n"], "clean_passed": adv["clean"]["full_support"],
            "serv_over": v2["over_reach"]["n"], "serv_over_of": v2["over_reach"]["of"],
            "serv_over_accepted": v2["over_reach"]["accepted_now"],
            "serv_accepted": v2["accepted_advice_now"]["n"], "serv_accepted_right": v2["accepted_advice_now"]["match_designed"],
            "guard_held": v2["guard"]["disposition_unchanged"], "guard_of": v2["guard"]["answered"]}
BLOCK = re.compile(r'(<script type="application/json" id="mock-data">)(.*?)(</script>)', re.S)


def payload():
    catalog = load_catalog(ROOT / "data" / "catalog.json")
    case = load_case(ROOT / "data" / "cases" / f"{CASE_ID}.json")
    audit = build_audit(catalog, case)
    texts = {s["statement_id"]: s for s in case["draft_report"]["statements"]}
    return {
        "catalog": [{"tool_id": t["tool_id"], "finding_class": t["finding_class"], "modality": t["modality"],
                     "source_id": t["source_id"], "quote": t["quote"],
                     "status": "not confirmed" if entry_reasons(catalog, t) else "confirmed",
                     "reasons": entry_reasons(catalog, t)} for t in catalog["tools"]],
        "study": case["study"],
        "calls": [dict(c, **audit["calls"][c["call_id"]]) for c in case["proposed_calls"]],
        "receipts": [{"receipt_id": r["receipt_id"], "call_id": r["call_id"], "status": r["status"]}
                     for r in case["receipts"]],
        "statements": [dict(texts[sid], **v) for sid, v in sorted(audit["statements"].items())],
        "audit": audit,
        "serv_recorded": recorded_serv(catalog, audit),
        "eval": eval_headline(),
    }


def main():
    html_path = ROOT / "mock" / "index.html"
    html = html_path.read_text(encoding="utf-8")
    data = json.dumps(payload(), indent=1, sort_keys=True).replace("</", "<\\/")
    html_path.write_text(BLOCK.sub(lambda m: m.group(1) + "\n" + data + "\n" + m.group(3), html, count=1),
                         encoding="utf-8")
    print("mock/index.html updated from", CASE_ID)


if __name__ == "__main__":
    main()
