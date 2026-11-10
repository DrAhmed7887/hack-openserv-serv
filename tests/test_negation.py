"""A source that negates a capability never confirms it (review round 2, optional finding; fixed as B7).

A quote can be verbatim in the source while the sentence around it says the opposite. The source
"Tool SYN-NODULE-1 does not flag nodule-like findings on chest-xr studies." contains the quote
"flag nodule-like findings on chest-xr studies". The safe answer is "uncertain", never "supported".
The negation list is an engineering rule of this validator, not a clinical one.
"""
import hashlib

import pytest

from contract_audit.audit import build_audit
from contract_audit.catalog import entry_reasons, resolve_capability

QUOTE = "flag nodule-like findings on chest-xr studies"


def with_source(catalog, clone, text, quote=QUOTE):
    cat = clone(catalog)
    tool = next(t for t in cat["tools"] if t["tool_id"] == "SYN-NODULE-1")
    tool["quote"] = quote
    src = cat["sources"][tool["source_id"]]
    src["text"] = text
    src["sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return cat, tool


@pytest.mark.parametrize("text", [
    "Tool SYN-NODULE-1 does not flag nodule-like findings on chest-xr studies.",
    "Tool SYN-NODULE-1 is not validated to flag nodule-like findings on chest-xr studies.",
    "This tool cannot flag nodule-like findings on chest-xr studies.",
    "It will never flag nodule-like findings on chest-xr studies.",
    "SYN-NODULE-1 doesn’t flag nodule-like findings on chest-xr studies.",  # curly apostrophe
    "Not in scope: flag nodule-like findings on chest-xr studies.",
])
def test_negation_just_before_the_quote_is_not_confirmed(catalog, clone, text):
    cat, tool = with_source(catalog, clone, text)
    assert "negation_near_quote" in entry_reasons(cat, tool)
    assert resolve_capability(cat, "chest-xr", "nodule_like")["capability"] == "uncertain"


@pytest.mark.parametrize("quote", [
    "does not flag nodule-like findings on chest-xr studies",
    "flag nodule-like findings on chest-xr studies except portable films",
    "never flag nodule-like findings on chest-xr studies",
])
def test_negation_inside_the_quote_is_not_confirmed(catalog, clone, quote):
    cat, tool = with_source(catalog, clone, f"Tool SYN-NODULE-1: it will {quote}.", quote=quote)
    assert "negation_near_quote" in entry_reasons(cat, tool)


@pytest.mark.parametrize("text", [
    "Tool SYN-NODULE-1 is specified to flag nodule-like findings on chest-xr studies.",
    "Tool SYN-NODULE-1 is specified to flag nodule-like findings on chest-xr studies. It is not a diagnosis.",
    "It is not a diagnostic device. Tool SYN-NODULE-1 is specified to flag nodule-like findings on chest-xr studies.",
])
def test_an_affirmative_sentence_still_confirms_whatever_other_sentences_say(catalog, clone, text):
    cat, tool = with_source(catalog, clone, text)
    assert entry_reasons(cat, tool) == []


def test_a_negated_capability_never_reaches_full_support(catalog, case, clone):
    cat, _ = with_source(catalog, clone, "Tool SYN-NODULE-1 does not flag nodule-like findings on chest-xr studies.")
    a = build_audit(cat, case("c01_supported_called"))
    assert a["obligations"]["OB-1"]["disposition"] == "uncertain"
    assert a["obligations"]["OB-1"]["full_support"] is False and a["completeness"] == "gaps_found"
