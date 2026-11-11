"""Assemble the structured audit document for one case. Pure and deterministic: no clock, no randomness."""
from __future__ import annotations

from collections import Counter

from .catalog import catalog_digest
from .coverage import assess_obligations
from .inputs import validate_case, validate_catalog
from .reconcile import reconcile_report

SCHEMA = "contract-audit/v0"
DISPOSITIONS = ("supported_called", "supported_omitted", "unsupported", "uncertain")
NOTICES = (
    "Synthetic fixture data only. No images, DICOM, patients or real devices.",
    "Catalog is fictional and unsigned. The physician/operator signed the engineering rules on 2026-11-11 (SIGNOFF.md); no clinical threshold is claimed.",
    "Full support means: confirmed catalog entry, valid call and valid mock receipt. It is not a clinical or SERV performance claim.",
)


# The not-run states a caller may report. "executed" and "fixture" are set only by attach_advisory.
SERV_NOT_RUN = ("not_run", "not_configured", "model_not_chosen", "call_failed")


def _serv_block(serv):
    """Validate a caller's SERV status block and return a fresh copy. Live execution cannot be asserted here."""
    if serv is None:
        return {"status": "not_run", "executed": False, "fixture": False}
    if not isinstance(serv, dict) or set(serv) != {"status", "executed", "fixture"} \
            or serv["executed"] is not False or serv["fixture"] is not False or serv["status"] not in SERV_NOT_RUN:
        raise ValueError(f"serv must be exactly {{status, executed: false, fixture: false}} with status one of "
                         f"{list(SERV_NOT_RUN)} (a SERV advisory is attached afterwards with attach_advisory)")
    return {"status": serv["status"], "executed": False, "fixture": False}


def build_audit(catalog, case, serv=None):
    """Build the audit. `serv` is a not-run status block (copied, never aliased); default says it was not run."""
    validate_catalog(catalog)
    validate_case(case)
    serv = _serv_block(serv)
    obligations, call_results = assess_obligations(
        catalog, case["study"], case["proposed_calls"], case["receipts"])
    report = reconcile_report(obligations, case["draft_report"])
    counts = Counter(o["disposition"] for o in obligations.values())
    all_full = bool(obligations) and all(o["full_support"] for o in obligations.values())
    return {
        "schema": SCHEMA,
        "case_id": case["case_id"],
        "catalog_id": catalog["catalog_id"],
        "catalog_sha256": catalog_digest(catalog),
        "synthetic": bool(case.get("synthetic")) and bool(catalog.get("synthetic")),
        "signoff": {"status": "engineering_rules_signed", "date": "2026-11-11", "record": "SIGNOFF.md", "catalog": "fictional, unsigned"},
        "serv": serv,
        "notices": list(NOTICES),
        "study": {"study_id": case["study"]["study_id"], "modality": case["study"]["modality"]},
        "obligations": obligations,
        "calls": {c["call_id"]: {"status": c["status"], "reasons": c["reasons"]} for c in call_results},
        "statements": report["statements"],
        "report_gaps": report["report_gaps"],
        "summary": {
            "obligations": len(obligations),
            "by_disposition": {d: counts.get(d, 0) for d in DISPOSITIONS},
            "fully_supported": sum(1 for o in obligations.values() if o["full_support"]),
            "report_consistent": report["report_consistent"],
        },
        "completeness": "full_support" if all_full and report["report_consistent"] else "gaps_found",
    }
