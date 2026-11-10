"""Capability resolution against a source-linked catalog."""
from __future__ import annotations

import hashlib
import json
import re

# Words that turn a capability statement into its opposite. One inside the quote, or among the few words just
# before it in the same sentence of the source, means the mapping is not confirmed: the safe answer is
# "uncertain". An engineering rule of this validator, not a clinical one.
NEGATIONS = frozenset({"not", "no", "never", "cannot", "without", "except", "excluding", "exclude", "excludes",
                       "excluded", "nor", "neither", "unable", "fails", "lacks", "lack", "unsupported"})
NEGATION_WINDOW = 6  # words before the quote, within its sentence


def _negation_words(tokens):
    """Listed negations, plus every contracted one ("doesn't", "wasn't", "hasn't", ...)."""
    return [t for t in tokens if t in NEGATIONS or t.endswith("n't")]


def catalog_digest(catalog):
    """sha256 of the catalog's canonical JSON. The audit records it, so advice can be tied to that exact catalog."""
    canonical = json.dumps(catalog, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _tokens(text):
    return re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower().replace("\u2019", "'"))


def _negated(quote, text):
    """True if the quote, or the words just before any occurrence of it in its sentence, negate it."""
    if _negation_words(_tokens(quote)):
        return True
    start = text.find(quote) if quote else -1
    while start != -1:
        sentence = re.split(r"[.;!?](?:\s|$)", text[:start])[-1]
        if _negation_words(_tokens(sentence)[-NEGATION_WINDOW:]):
            return True
        start = text.find(quote, start + 1)
    return False


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
        elif _negated(entry["quote"], source["text"]):
            reasons.append("negation_near_quote")
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
