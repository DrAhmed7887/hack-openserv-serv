#!/usr/bin/env python3
"""Embeds the real offline audit of fixture case c07 into mock/index.html. No network, no SERV.

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

CASE_ID = "c07_combined"
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
