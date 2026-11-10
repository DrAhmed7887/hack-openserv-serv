"""Execution-receipt validation. A receipt is evidence that a mock tool ran, nothing more."""
from __future__ import annotations

import hashlib
import json

ACCEPTED_EXECUTORS = frozenset({"mock-tool"})


def output_digest(output):
    canonical = json.dumps(output, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def check_receipt(call, receipts):
    """Return {"status": valid|missing|failed|invalid, "receipt_id", "reasons"} for one call."""
    own = [r for r in receipts if r["call_id"] == call["call_id"]]
    if not own:
        return {"status": "missing", "receipt_id": None, "reasons": ["no_receipt"]}
    if len(own) > 1:
        return {"status": "invalid", "receipt_id": None, "reasons": ["multiple_receipts"]}
    receipt = own[0]
    reasons = []
    if receipt["executor"] not in ACCEPTED_EXECUTORS:
        reasons.append("unrecognised_executor")
    if receipt["tool_id"] != call["tool_id"]:
        reasons.append("tool_mismatch")
    try:
        digest = output_digest(receipt["output"])
    except (RecursionError, TypeError, ValueError):
        reasons.append("output_not_digestable")
    else:
        if receipt["output_sha256"] != digest:
            reasons.append("output_digest_mismatch")
    if receipt["status"] not in ("ok", "error"):
        reasons.append("unknown_status")
    if reasons:
        return {"status": "invalid", "receipt_id": receipt["receipt_id"], "reasons": reasons}
    if receipt["status"] == "error":
        return {"status": "failed", "receipt_id": receipt["receipt_id"], "reasons": ["execution_error"]}
    return {"status": "valid", "receipt_id": receipt["receipt_id"], "reasons": [],
            "tool_id": receipt["tool_id"], "output_sha256": receipt["output_sha256"]}
