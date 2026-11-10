"""Per-obligation coverage: supported+called, supported but omitted, unsupported, uncertain."""
from __future__ import annotations

from .calls import validate_calls
from .catalog import resolve_capability
from .receipts import check_receipt


_STATUS_PRIORITY = ("invalid", "failed", "missing")  # worst first


def _unique(items):
    return list(dict.fromkeys(items))


def _conflicting_tools(checks):
    """Tools whose valid receipts disagree on the output digest: two runs, two answers, no way to pick."""
    digests = {}
    for _, r in checks:
        if r["status"] == "valid":
            digests.setdefault(r["tool_id"], set()).add(r["output_sha256"])
    return sorted(t for t, d in digests.items() if len(d) > 1)


def _receipt_summary(checks):
    """Aggregate over every valid call of one obligation: (status, reasons). All must be valid, and agree."""
    statuses = [r["status"] for _, r in checks]
    reasons = _unique(x for _, r in checks if r["status"] != "valid" for x in r["reasons"])
    for status in _STATUS_PRIORITY:
        if status in statuses:
            return status, reasons
    if _conflicting_tools(checks):
        return "invalid", ["conflicting_outputs"]
    return "valid", []


def _call_entry(call_result, receipt):
    """One submitted call and its receipt relation. Calls that are not valid have no receipt relation."""
    return {"call_id": call_result["call_id"], "status": call_result["status"],
            "receipt_id": receipt["receipt_id"] if receipt else None,
            "receipt_status": receipt["status"] if receipt else "not_applicable",
            "reasons": list(receipt["reasons"] if receipt else call_result["reasons"])}


def assess_obligations(catalog, study, calls, receipts):
    """Return ({obligation_id: assessment}, call_results).

    full_support is true only for supported_called where EVERY valid call has a valid receipt and the
    receipts do not conflict. Nothing else sets it. Every call proposed for the obligation is listed under
    "calls" with its own receipt relation; no call or receipt is dropped.
    """
    call_results = validate_calls(catalog, study, calls)
    status_by_id = {r["call_id"]: r for r in call_results}
    assessments = {}
    for ob in study["obligations"]:
        oid = ob["obligation_id"]
        cap = resolve_capability(catalog, study["modality"], ob["finding_class"])
        own = [c for c in calls if c["obligation_id"] == oid]
        valid = [c for c in own if status_by_id[c["call_id"]]["status"] == "valid"]
        a = {"capability": cap["capability"], "tool_id": cap["tool_id"], "call_id": None,
             "receipt_id": None, "receipt_ids": [], "receipt_status": "not_applicable", "full_support": False,
             "reasons": list(cap["reasons"]), "calls": []}
        checks = [(c, check_receipt(c, receipts)) for c in valid] if cap["capability"] == "supported" else []
        check_of = {c["call_id"]: r for c, r in checks}
        a["calls"] = [_call_entry(status_by_id[c["call_id"]], check_of.get(c["call_id"])) for c in own]
        if checks:
            status, reasons = _receipt_summary(checks)
            a.update(disposition="supported_called", call_id=checks[0][0]["call_id"],
                     receipt_id=checks[0][1]["receipt_id"], receipt_status=status,
                     receipt_ids=[r["receipt_id"] for _, r in checks if r["status"] == "valid"],
                     full_support=status == "valid")
            a["reasons"] += reasons
        elif cap["capability"] == "supported":
            a["disposition"] = "supported_omitted"
            if own:
                a["reasons"].append("call_invalid")
        else:
            a["disposition"] = cap["capability"]
        assessments[oid] = a
    return assessments, call_results
