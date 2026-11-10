"""Assemble the structured audit document for one case. Pure and deterministic: no clock, no randomness."""
from __future__ import annotations

from collections import Counter

from .coverage import assess_obligations
from .inputs import validate_case, validate_catalog
from .reconcile import reconcile_report

SCHEMA = "contract-audit/v0"
DISPOSITIONS = ("supported_called", "supported_omitted", "unsupported", "uncertain")
NOTICES = (
    "Synthetic fixture data only. No images, DICOM, patients or real devices.",
    "Catalog is fictional. Physician/operator sign-off is pending.",
    "Full support means: confirmed catalog entry, valid call and valid mock receipt. It is not a clinical or SERV performance claim.",
)


def build_audit(catalog, case, serv=None):
    """Build the audit. `serv` is a status block from the SERV boundary; default says it was not run."""
    validate_catalog(catalog)
    validate_case(case)
    obligations, call_results = assess_obligations(
        catalog, case["study"], case["proposed_calls"], case["receipts"])
    report = reconcile_report(obligations, case["draft_report"])
    counts = Counter(o["disposition"] for o in obligations.values())
    all_full = bool(obligations) and all(o["full_support"] for o in obligations.values())
    return {
        "schema": SCHEMA,
        "case_id": case["case_id"],
        "catalog_id": catalog["catalog_id"],
        "synthetic": bool(case.get("synthetic")) and bool(catalog.get("synthetic")),
        "signoff": {"status": "pending"},
        "serv": serv or {"status": "not_run", "executed": False, "fixture": False},
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
