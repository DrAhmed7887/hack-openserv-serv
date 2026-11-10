"""Validation of proposed (mock) tool calls against the catalog and the study."""
from __future__ import annotations

from collections import Counter

from .catalog import entry_reasons


def validate_calls(catalog, study, calls):
    """One result per call, in input order: {call_id, status valid|invalid|unconfirmed, reasons}.

    invalid:     the call cannot be run as proposed (unknown tool/obligation, wrong modality or
                 finding class, missing args, duplicate id).
    unconfirmed: the call is well-formed but the catalog's source link for that tool is not confirmed.
    """
    tools = {t["tool_id"]: t for t in catalog["tools"]}
    obligations = {o["obligation_id"]: o for o in study["obligations"]}
    id_counts = Counter(c["call_id"] for c in calls)
    results = []
    for call in calls:
        reasons = []
        if id_counts[call["call_id"]] > 1:
            reasons.append("duplicate_call_id")
        tool = tools.get(call["tool_id"])
        obligation = obligations.get(call["obligation_id"])
        if tool is None:
            reasons.append("unknown_tool")
        if obligation is None:
            reasons.append("unknown_obligation")
        if tool is not None:
            if tool["modality"] != study["modality"]:
                reasons.append("modality_mismatch")
            if obligation is not None and tool["finding_class"] != obligation["finding_class"]:
                reasons.append("finding_class_mismatch")
            for arg in tool["required_args"]:
                if arg not in call.get("args", {}):
                    reasons.append(f"missing_arg:{arg}")
        if reasons:
            results.append({"call_id": call["call_id"], "status": "invalid", "reasons": reasons})
            continue
        unconfirmed = entry_reasons(catalog, tool)
        status = "unconfirmed" if unconfirmed else "valid"
        results.append({"call_id": call["call_id"], "status": status, "reasons": unconfirmed})
    return results
