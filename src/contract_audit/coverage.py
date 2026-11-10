"""Per-obligation coverage: supported+called, supported but omitted, unsupported, uncertain."""
from __future__ import annotations

from .calls import validate_calls
from .catalog import resolve_capability
from .receipts import check_receipt


def assess_obligations(catalog, study, calls, receipts):
    """Return ({obligation_id: assessment}, call_results).

    full_support is true only for supported_called with a valid receipt. Nothing else sets it.
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
             "receipt_id": None, "receipt_status": "not_applicable", "full_support": False,
             "reasons": list(cap["reasons"])}
        if cap["capability"] == "supported" and valid:
            call = valid[0]
            receipt = check_receipt(call, receipts)
            a.update(disposition="supported_called", call_id=call["call_id"],
                     receipt_id=receipt["receipt_id"], receipt_status=receipt["status"],
                     full_support=receipt["status"] == "valid")
            a["reasons"] += [] if receipt["status"] == "valid" else receipt["reasons"]
        elif cap["capability"] == "supported":
            a["disposition"] = "supported_omitted"
            if own:
                a["reasons"].append("call_invalid")
        else:
            a["disposition"] = cap["capability"]
        assessments[oid] = a
    return assessments, call_results
