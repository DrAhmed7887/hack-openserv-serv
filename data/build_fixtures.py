#!/usr/bin/env python3
"""Writes the fixed synthetic fixtures under data/. No randomness, no network.

Run: python3 data/build_fixtures.py
Only hashing and static data live here. The audit logic does not.
Expected outcomes (data/expected/) are hand-written and are NOT produced here.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STUDY_ID = "SYN-STUDY-001"
MODALITY = "chest-xr"

SOURCES = {
    "SRC-SYN-A": ("Synthetic specification A",
        "SYNTHETIC SPECIFICATION A (fictional, engineering test only). "
        "Tool SYN-NODULE-1 is specified to flag nodule-like findings on chest-xr studies."),
    "SRC-SYN-B": ("Synthetic specification B",
        "SYNTHETIC SPECIFICATION B (fictional, engineering test only). "
        "Tool SYN-EFFUSION-1 is specified to flag effusion-like findings on chest-xr studies."),
    "SRC-SYN-C": ("Synthetic specification C",
        "SYNTHETIC SPECIFICATION C (fictional, engineering test only). "
        "Tool SYN-FRACTURE-1 is specified to flag fracture-like findings on extremity-xr studies only."),
    "SRC-SYN-D": ("Synthetic specification D",
        "SYNTHETIC SPECIFICATION D (fictional, engineering test only). "
        "Tool SYN-CARDIAC-1 is specified to measure cardiac size on radiographs. "
        "Supported study types are listed in a separate document that is not included here."),
    "SRC-SYN-E": ("Synthetic specification E",
        "SYNTHETIC SPECIFICATION E (fictional, engineering test only). "
        "Tool SYN-LINE-1 is specified to flag tube-position-like findings on chest-xr studies."),
    "SRC-SYN-F": ("Synthetic specification F",
        "SYNTHETIC SPECIFICATION F (fictional, engineering test only). "
        "Tool SYN-VOLUME-1 is specified to flag lung-volume-like findings on chest-xr studies."),
}

# tool_id, finding_class, modality (catalog author's claimed mapping), source, quote, modality_term, finding_term
TOOLS = [
    ("SYN-NODULE-1", "nodule_like", "chest-xr", "SRC-SYN-A",
     "flag nodule-like findings on chest-xr studies", "chest-xr", "nodule-like"),
    ("SYN-EFFUSION-1", "effusion_like", "chest-xr", "SRC-SYN-B",
     "flag effusion-like findings on chest-xr studies", "chest-xr", "effusion-like"),
    ("SYN-FRACTURE-1", "fracture_like", "extremity-xr", "SRC-SYN-C",
     "flag fracture-like findings on extremity-xr studies only", "extremity-xr", "fracture-like"),
    ("SYN-CARDIAC-1", "cardiac_size", "chest-xr", "SRC-SYN-D",
     "measure cardiac size on radiographs", "chest-xr", "cardiac size"),
    ("SYN-LINE-1", "tube_position_like", "chest-xr", "SRC-SYN-E",
     "flag tube-position-like findings on chest-xr studies", "chest-xr", "tube-position-like"),
    ("SYN-VOLUME-1", "lung_volume_like", "chest-xr", "SRC-SYN-F",
     "flag lung-volume-like findings on chest-xr studies", "chest-xr", "lung-volume-like"),
]

OBLIGATIONS = {  # id -> finding class (engineering placeholders, not clinical requirements)
    "OB-1": "nodule_like", "OB-2": "effusion_like", "OB-3": "fracture_like",
    "OB-4": "cardiac_size", "OB-5": "tube_position_like", "OB-6": "lung_volume_like",
}
TOOL_FOR = {t[1]: t[0] for t in TOOLS}
LABEL = {"nodule_like": "Nodule-like", "effusion_like": "Effusion-like", "fracture_like": "Fracture-like",
         "cardiac_size": "Cardiac-size", "tube_position_like": "Tube-position-like", "lung_volume_like": "Lung-volume-like"}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest(output):
    return sha(json.dumps(output, sort_keys=True, separators=(",", ":")))


def call(n, ob):
    return {"call_id": f"CALL-{n}", "tool_id": TOOL_FOR[OBLIGATIONS[ob]], "obligation_id": ob,
            "args": {"study_id": STUDY_ID}}


def receipt(n, ob, status):
    output = {"result_code": "MOCK-OK" if status == "ok" else "MOCK-ERROR", "region_id": f"R-{n:03d}"}
    return {"receipt_id": f"RCPT-{n}", "call_id": f"CALL-{n}", "tool_id": TOOL_FOR[OBLIGATIONS[ob]],
            "executor": "mock-tool", "fixture": True, "status": status, "output": output,
            "output_sha256": digest(output)}


def claim(n, ob, cites):
    return {"statement_id": f"ST-{n}", "obligation_id": ob, "kind": "claims_assessed", "cites_receipt": cites,
            "text": f"{LABEL[OBLIGATIONS[ob]]} assessment completed (synthetic placeholder text)."}


def disclose(n, ob):
    return {"statement_id": f"ST-{n}", "obligation_id": ob, "kind": "discloses_not_assessed",
            "cites_receipt": None,
            "text": f"{LABEL[OBLIGATIONS[ob]]} assessment not performed (synthetic placeholder text)."}


def case(case_id, obs, calls, receipts, statements):
    return {"case_id": case_id, "synthetic": True,
            "study": {"study_id": STUDY_ID, "modality": MODALITY,
                      "obligations": [{"obligation_id": o, "finding_class": OBLIGATIONS[o]} for o in obs]},
            "proposed_calls": calls, "receipts": receipts,
            "draft_report": {"statements": statements}}


CASES = [
    case("c01_supported_called", ["OB-1"], [call(1, "OB-1")], [receipt(1, "OB-1", "ok")],
         [claim(1, "OB-1", "RCPT-1")]),
    case("c02_supported_omitted", ["OB-2"], [], [], [claim(1, "OB-2", None)]),
    # a call to an extremity-only tool is proposed for a chest-xr obligation: the call must be rejected
    case("c03_unsupported", ["OB-3"],
         [{"call_id": "CALL-1", "tool_id": "SYN-FRACTURE-1", "obligation_id": "OB-3",
           "args": {"study_id": STUDY_ID}}], [], [disclose(1, "OB-3")]),
    # source is insufficient AND a mock receipt exists: the receipt must not upgrade the result
    case("c04_uncertain_source_insufficient", ["OB-4"], [call(1, "OB-4")],
         [receipt(1, "OB-4", "ok")], [claim(1, "OB-4", "RCPT-1")]),
    case("c05_missing_receipt", ["OB-5"], [call(1, "OB-5")], [], [claim(1, "OB-5", None)]),
    case("c06_execution_failure", ["OB-6"], [call(1, "OB-6")], [receipt(1, "OB-6", "error")],
         [claim(1, "OB-6", "RCPT-1")]),
    case("c07_combined", ["OB-1", "OB-2", "OB-3", "OB-4", "OB-5", "OB-6"],
         [call(1, "OB-1"), call(4, "OB-4"), call(5, "OB-5"), call(6, "OB-6"),
          {"call_id": "CALL-3", "tool_id": "SYN-FRACTURE-1", "obligation_id": "OB-3",
           "args": {"study_id": STUDY_ID}}],
         [receipt(1, "OB-1", "ok"), receipt(4, "OB-4", "ok"), receipt(6, "OB-6", "error")],
         [claim(1, "OB-1", "RCPT-1"), claim(2, "OB-2", None), disclose(3, "OB-3"),
          claim(4, "OB-4", "RCPT-4"), claim(5, "OB-5", None)]),  # no statement for OB-6
]


def catalog():
    return {
        "catalog_id": "SYN-CATALOG-001", "synthetic": True,
        "notice": "FICTIONAL engineering catalog for a mechanism spike. Not a real device list. "
                  "Does not describe any real product's intended use.",
        "signoff": {"status": "pending", "by": None},
        "sources": {k: {"title": v[0], "text": v[1], "sha256": sha(v[1])} for k, v in SOURCES.items()},
        "tools": [{"tool_id": t[0], "finding_class": t[1], "modality": t[2], "required_args": ["study_id"],
                   "source_id": t[3], "quote": t[4], "modality_term": t[5], "finding_term": t[6]}
                  for t in TOOLS],
    }


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    dump(ROOT / "catalog.json", catalog())
    for c in CASES:
        dump(ROOT / "cases" / f"{c['case_id']}.json", c)
    print(f"wrote catalog + {len(CASES)} cases")
