"""Capability resolution against a source-linked catalog."""
from __future__ import annotations

import hashlib


def _words(label):
    """'nodule-like' and 'nodule_like' compare equal; spacing and case are ignored."""
    return label.lower().replace("-", " ").replace("_", " ").split()


def entry_reasons(catalog, entry):
    """Reasons a catalog entry's mapping is NOT confirmed. Empty list means confirmed."""
    reasons = []
    source = catalog["sources"].get(entry["source_id"])
    if source is None:
        reasons.append("source_missing")
    else:
        if hashlib.sha256(source["text"].encode("utf-8")).hexdigest() != source["sha256"]:
            reasons.append("source_hash_mismatch")
        if entry["quote"] not in source["text"]:
            reasons.append("quote_not_in_source")
    if not entry["quote"] or not entry["modality_term"] or not entry["finding_term"]:
        reasons.append("empty_quote_or_term")
    if entry["modality_term"] != entry["modality"]:
        reasons.append("modality_term_mismatch")
    if _words(entry["finding_term"]) != _words(entry["finding_class"]):
        reasons.append("finding_term_mismatch")
    if entry["modality_term"] not in entry["quote"]:
        reasons.append("modality_term_not_in_quote")
    if entry["finding_term"] not in entry["quote"]:
        reasons.append("finding_term_not_in_quote")
    return reasons


def resolve_capability(catalog, modality, finding_class):
    """Return {"capability": supported|unsupported|uncertain, "tool_id", "reasons"}.

    unsupported: no entry claims this finding class for this modality (never substituted).
    uncertain:   an entry claims it, but the source link does not confirm the mapping.
    supported:   an entry claims it and the source link confirms it.
    """
    claims = [t for t in catalog["tools"]
              if t["finding_class"] == finding_class and t["modality"] == modality]
    if not claims:
        return {"capability": "unsupported", "tool_id": None, "reasons": ["no_catalog_entry"]}
    unconfirmed = []
    for entry in claims:
        reasons = entry_reasons(catalog, entry)
        if not reasons:
            return {"capability": "supported", "tool_id": entry["tool_id"], "reasons": []}
        unconfirmed.append((entry, reasons))
    entry, reasons = unconfirmed[0]
    return {"capability": "uncertain", "tool_id": entry["tool_id"], "reasons": reasons}
