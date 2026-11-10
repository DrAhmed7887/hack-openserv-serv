"""A 'supported' SERV advisory must quote words that name the study's modality (10 Nov 2026).

Live batch v1 (eval/SERV_BATCH.md, 24 requests): each of SERV's 8 correct 'supported' answers quoted the sentence
naming chest-xr; none of its 7 wrong 'supported' answers (specs that never settle the study type) did. They quoted
the general capability sentence, which is verbatim in every spec and so proves nothing about the study type.
Engineering rule of this validator, not a clinical one. It was written after batch v1, so batch v1 does not
validate it; the held-out batch v2 (new wording, run after this rule was fixed) is the check.
"""
import hashlib

import pytest

from contract_audit.audit import build_audit
from contract_audit.serv import _names_modality, attach_advisory

GENERIC = "Tool SYN-CARDIAC-1 is specified to measure cardiac size on radiographs."
NAMES_CHEST = "Intended study type: chest-xr."


def catalog_with(catalog, clone, extra):
    """SRC-SYN-D rewritten as the general capability sentence plus one extra sentence (hash recomputed)."""
    cat = clone(catalog)
    src = cat["sources"]["SRC-SYN-D"]
    src["text"] = f"SYNTHETIC SPECIFICATION D (fictional, engineering test only). {GENERIC} {extra}"
    src["sha256"] = hashlib.sha256(src["text"].encode("utf-8")).hexdigest()
    return cat


def advise(cat, case, verdict, quote, reasons=()):
    audit = build_audit(cat, case("c04_uncertain_source_insufficient"))
    assert audit["obligations"]["OB-4"]["disposition"] == "uncertain"
    interp = {"fixture": True, "verdict": verdict, "quote": quote, "reasons": list(reasons)}
    return attach_advisory(audit, "OB-4", interp, cat)["serv_advisory"]["OB-4"]


@pytest.mark.parametrize("quote", [GENERIC, "measure cardiac size on radiographs"])
def test_supported_quote_that_does_not_name_the_modality_is_not_accepted(catalog, case, clone, quote):
    adv = advise(catalog_with(catalog, clone, NAMES_CHEST), case, "supported", quote)
    assert adv["accepted"] is False and adv["reasons"] == ["quote_does_not_name_modality"]


@pytest.mark.parametrize("quote", [NAMES_CHEST, GENERIC + " " + NAMES_CHEST])
def test_supported_quote_that_names_the_modality_is_accepted(catalog, case, clone, quote):
    adv = advise(catalog_with(catalog, clone, NAMES_CHEST), case, "supported", quote)
    assert adv["accepted"] is True and adv["reasons"] == []


@pytest.mark.parametrize("quote", ["Only extremity-xr studies are supported.", "Excluded study types: chest-xr."])
def test_unsupported_quote_need_not_name_the_studys_modality(catalog, case, clone, quote):
    adv = advise(catalog_with(catalog, clone, quote), case, "unsupported", quote)
    assert adv["accepted"] is True


def test_the_rule_never_changes_the_deterministic_result(catalog, case, clone):
    cat = catalog_with(catalog, clone, NAMES_CHEST)
    before = build_audit(cat, case("c04_uncertain_source_insufficient"))
    after = attach_advisory(before, "OB-4", {"fixture": True, "verdict": "supported", "quote": NAMES_CHEST,
                                            "reasons": []}, cat)
    assert after["obligations"] == before["obligations"] and after["completeness"] == before["completeness"]


@pytest.mark.parametrize("quote,modality,expected", [
    ("Intended study type: chest-xr.", "chest-xr", True),
    ("Applies to Chest-XR studies", "chest-xr", True),          # case does not matter
    ("chest-xr", "chest-xr", True),
    ("nonchest-xr studies", "chest-xr", False),                 # not a whole word
    ("chest-xray studies", "chest-xr", False),
    ("Use it on CT studies.", "ct", True),
    ("the subject and its effect", "ct", False),                # 'ct' inside other words
])
def test_the_modality_must_appear_as_a_whole_word(quote, modality, expected):
    assert _names_modality(quote, modality) is expected
