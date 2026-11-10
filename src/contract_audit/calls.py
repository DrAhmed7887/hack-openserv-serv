"""Validation of proposed (mock) tool calls against the catalog and the study."""
from __future__ import annotations

import math
from collections import Counter

from .catalog import entry_reasons
from .inputs import is_finite_number


def _number_list_ok(spec, value):
    """Non-empty list, bounded count, every item a finite number in range, finite sum within max_total."""
    if not isinstance(value, list) or not 1 <= len(value) <= spec["max_items"]:
        return False
    if not all(is_finite_number(v) and spec["item_min"] <= v <= spec["item_max"] for v in value):
        return False
    try:
        total = math.fsum(value)
    except OverflowError:
        return False
    return total <= spec["max_total"]


def _arg_reasons(name, spec, value, study):
    """Reasons one argument value is not acceptable under its schema spec. Unknown spec types fail closed."""
    kind = spec.get("type") if isinstance(spec, dict) else None
    try:
        if kind == "study_id":
            ok = isinstance(value, str) and bool(value) and value == study["study_id"]
        elif kind == "number":
            ok = is_finite_number(value) and spec["min"] <= value <= spec["max"]
        elif kind == "number_list":
            ok = _number_list_ok(spec, value)
        else:
            ok = False
    except (KeyError, TypeError):  # a malformed spec reached us without the catalog loader: fail closed
        ok = False
    return [] if ok else [f"arg_invalid:{name}"]


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
            schema = tool.get("args_schema")
            args = call.get("args")
            if not isinstance(schema, dict):
                reasons.append("args_schema_missing")
            elif not isinstance(args, dict):
                reasons.append("args_not_object")
            else:
                for arg in tool["required_args"]:
                    if arg not in args:
                        reasons.append(f"missing_arg:{arg}")
                for arg, value in args.items():
                    if arg in schema:
                        reasons += _arg_reasons(arg, schema[arg], value, study)
                    else:
                        reasons.append(f"unknown_arg:{arg}")
        if reasons:
            results.append({"call_id": call["call_id"], "status": "invalid", "reasons": reasons})
            continue
        unconfirmed = entry_reasons(catalog, tool)
        status = "unconfirmed" if unconfirmed else "valid"
        results.append({"call_id": call["call_id"], "status": status, "reasons": unconfirmed})
    return results
