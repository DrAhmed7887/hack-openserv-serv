"""Boundary loading and validation of catalog and case files. Fails fast, names the problem."""
from __future__ import annotations

import json


class InputError(ValueError):
    """The input file is unreadable, malformed, or not marked synthetic."""


_CATALOG_KEYS = ("catalog_id", "sources", "tools")
_CASE_KEYS = ("case_id", "study", "proposed_calls", "receipts", "draft_report")


def _read(path):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise InputError(f"{path}: top level must be a JSON object")
    return data


def _require(obj, keys, where):
    for key in keys:
        if key not in obj:
            raise InputError(f"{where}: missing required key '{key}'")


def _require_synthetic(data, path):
    if data.get("synthetic") is not True:
        raise InputError(f"{path}: refused, input is not marked \"synthetic\": true "
                         "(this tool accepts synthetic fixtures only)")


def _object(value, where):
    if not isinstance(value, dict):
        raise InputError(f"{where}: must be a JSON object")
    return value


def _items(value, where):
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise InputError(f"{where}: must be a list of JSON objects")
    return value


def _strings(obj, keys, where, allow_none=()):
    _require(obj, keys, where)
    for key in keys:
        value = obj[key]
        if value is None and key in allow_none:
            continue
        if not isinstance(value, str) or (not value and key not in allow_none and key.endswith("_id")):
            raise InputError(f"{where}: '{key}' must be a non-empty string")


def _unique(rows, key, where):
    seen = set()
    for row in rows:
        if row[key] in seen:
            raise InputError(f"{where}: duplicate {key} '{row[key]}'")
        seen.add(row[key])


def validate_catalog(data):
    """Structural checks only (types, required keys, unique ids). Raises InputError."""
    _require(data, _CATALOG_KEYS, "catalog")
    sources = _object(data["sources"], "catalog sources")
    for sid, src in sources.items():
        _strings(_object(src, f"catalog sources[{sid}]"), ("text", "sha256"), f"catalog sources[{sid}]")
    tools = _items(data["tools"], "catalog tools")
    for i, tool in enumerate(tools):
        where = f"catalog tools[{i}]"
        _strings(tool, ("tool_id", "finding_class", "modality", "source_id", "quote",
                        "modality_term", "finding_term"), where)
        if not isinstance(tool["required_args"], list) or not all(isinstance(a, str) for a in tool["required_args"]):
            raise InputError(f"{where}: 'required_args' must be a list of strings")
    _unique(tools, "tool_id", "catalog tools")


def validate_case(data):
    """Structural checks only (types, required keys, unique ids). Raises InputError."""
    _require(data, _CASE_KEYS, "case")
    study = _object(data["study"], "case study")
    _strings(study, ("study_id", "modality"), "case study")
    obligations = _items(study.get("obligations"), "case study obligations")
    for i, ob in enumerate(obligations):
        _strings(ob, ("obligation_id", "finding_class"), f"case obligations[{i}]")
    _unique(obligations, "obligation_id", "case obligations")
    calls = _items(data["proposed_calls"], "case proposed_calls")
    for i, call in enumerate(calls):
        _strings(call, ("call_id", "tool_id", "obligation_id"), f"case proposed_calls[{i}]")
        if not isinstance(call.get("args"), dict):
            raise InputError(f"case proposed_calls[{i}]: 'args' must be a JSON object")
    receipts = _items(data["receipts"], "case receipts")
    for i, r in enumerate(receipts):
        _strings(r, ("receipt_id", "call_id", "tool_id", "executor", "status", "output_sha256"),
                 f"case receipts[{i}]")
        if not isinstance(r.get("output"), dict):
            raise InputError(f"case receipts[{i}]: 'output' must be a JSON object")
    _unique(receipts, "receipt_id", "case receipts")
    report = _object(data["draft_report"], "case draft_report")
    statements = _items(report.get("statements"), "case draft_report statements")
    for i, st in enumerate(statements):
        _strings(st, ("statement_id", "obligation_id", "kind", "cites_receipt"),
                 f"case statements[{i}]", allow_none=("cites_receipt",))
    _unique(statements, "statement_id", "case statements")


def load_catalog(path):
    data = _read(path)
    _require_synthetic(data, path)
    validate_catalog(data)
    return data


def load_case(path):
    data = _read(path)
    _require_synthetic(data, path)
    validate_case(data)
    return data
