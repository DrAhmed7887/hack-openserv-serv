"""Reconcile a draft report against per-obligation coverage and receipts.

Output is a verdict and an action label per statement. The reconciler never writes report text.
"""
from __future__ import annotations

_CLAIM_ACTION = {
    "supported_omitted": "run_tool_or_remove",
    "unsupported": "remove_or_disclose",
    "uncertain": "qualify_or_remove",
    "supported_called": "remove_until_valid_receipt",
}
_OK = ("supported_by_receipt", "limitation_disclosed")


def _statement_verdict(obligations, statement):
    ob = obligations.get(statement["obligation_id"])
    if ob is None:
        return {"outcome": "unknown_obligation", "action": "remove_statement"}
    if statement["kind"] == "discloses_not_assessed":
        return {"outcome": "limitation_disclosed", "action": None}
    if statement["kind"] != "claims_assessed":
        return {"outcome": "invalid_statement", "action": "remove_statement"}
    if not ob["full_support"]:
        return {"outcome": "unsupported_claim", "action": _CLAIM_ACTION[ob["disposition"]]}
    if statement["cites_receipt"] == ob["receipt_id"]:
        return {"outcome": "supported_by_receipt", "action": None}
    return {"outcome": "receipt_mismatch", "action": "cite_valid_receipt"}


def reconcile_report(obligations, draft_report):
    statements = {s["statement_id"]: _statement_verdict(obligations, s) for s in draft_report["statements"]}
    mentioned = {s["obligation_id"] for s in draft_report["statements"]}
    gaps = {oid: "add_limitation_statement" for oid, ob in obligations.items()
            if not ob["full_support"] and oid not in mentioned}
    consistent = not gaps and all(v["outcome"] in _OK for v in statements.values())
    return {"statements": statements, "report_gaps": gaps, "report_consistent": consistent}
