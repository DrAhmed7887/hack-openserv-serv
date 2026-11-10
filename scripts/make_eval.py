#!/usr/bin/env python3
"""Seeded adversarial evaluation: does a report that LOOKS complete ever pass when it is not?

Builds clean synthetic cases (each obligation covered by a confirmed tool, a valid call, a valid receipt and a
statement that cites it), then breaks each one in exactly one way. What every break must produce is written
here, from the break itself, before the validator runs:
  - completeness must be "gaps_found" (never "full_support"), and
  - the named signal must appear (the right reason, not just any failure).
Clean cases must come out "full_support": a validator that flags everything would fail the controls.

Run:  python3 scripts/make_eval.py           writes eval/results/adversarial_v1.json and eval/RESULTS.md
      python3 scripts/make_eval.py --check   exit 1 if the committed results are stale (CI)
      python3 scripts/make_eval.py --src <checkout>/src --out <file>   score another version of the code
Deterministic: fixed seed, no clock, no network. Synthetic data only; no clinical claim.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261110
N_CLEAN = 30
N_PER_BREAK = 10
RESULTS = ROOT / "eval" / "results" / "adversarial_v1.json"
REPORT = ROOT / "eval" / "RESULTS.md"

# Confirmed catalog tools by modality (data/catalog.json). SYN-CARDIAC-1 is unconfirmed, so clean cases skip it.
CONFIRMED = {
    "chest-xr": {"nodule_like": "SYN-NODULE-1", "effusion_like": "SYN-EFFUSION-1",
                 "tube_position_like": "SYN-LINE-1", "lung_volume_like": "SYN-VOLUME-1"},
    "extremity-xr": {"fracture_like": "SYN-FRACTURE-1"},
}
OTHER_MODALITY = {"chest-xr": "extremity-xr", "extremity-xr": "chest-xr"}


def digest(output):
    """Receipt digest: sha256 of canonical JSON (data/DATA_CARD.md). Written here, not imported."""
    return hashlib.sha256(json.dumps(output, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def clean_case(rng, n):
    modality = "extremity-xr" if n % 5 == 4 else "chest-xr"
    classes = sorted(CONFIRMED[modality])
    chosen = sorted(rng.sample(classes, rng.randint(1, len(classes))))
    study_id = f"SYN-EVAL-{n:04d}"
    obligations, calls, receipts, statements = [], [], [], []
    for i, finding in enumerate(chosen, 1):
        tool = CONFIRMED[modality][finding]
        output = {"result_code": "MOCK-OK", "region_id": f"R-{rng.randint(1, 999):03d}"}
        obligations.append({"obligation_id": f"OB-{i}", "finding_class": finding})
        calls.append({"call_id": f"CALL-{i}", "tool_id": tool, "obligation_id": f"OB-{i}",
                      "args": {"study_id": study_id}})
        receipts.append({"receipt_id": f"RCPT-{i}", "call_id": f"CALL-{i}", "tool_id": tool, "executor": "mock-tool",
                         "fixture": True, "status": "ok", "output": output, "output_sha256": digest(output)})
        statements.append({"statement_id": f"ST-{i}", "obligation_id": f"OB-{i}", "kind": "claims_assessed",
                           "cites_receipt": f"RCPT-{i}", "text": "Assessment completed (synthetic placeholder)."})
    return {"case_id": f"eval-{n:04d}", "synthetic": True,
            "study": {"study_id": study_id, "modality": modality, "obligations": obligations},
            "proposed_calls": calls, "receipts": receipts, "draft_report": {"statements": statements}}


def _drop(rows, key, value):
    return [r for r in rows if r[key] != value]


def _row(rows, key, value):
    return next(r for r in rows if r[key] == value)


def _source_of(catalog, case, j):
    tool_id = _row(case["proposed_calls"], "obligation_id", f"OB-{j}")["tool_id"]
    tool = _row(catalog["tools"], "tool_id", tool_id)
    return tool, catalog["sources"][tool["source_id"]]


# Each break: (mutate(case, catalog, j) -> None, expected signal(audit, j) -> bool, what the signal is)
def b_call_omitted(case, cat, j):
    case["proposed_calls"] = _drop(case["proposed_calls"], "call_id", f"CALL-{j}")
    case["receipts"] = _drop(case["receipts"], "call_id", f"CALL-{j}")


def b_receipt_missing(case, cat, j):
    case["receipts"] = _drop(case["receipts"], "call_id", f"CALL-{j}")


def b_output_edited(case, cat, j):
    _row(case["receipts"], "call_id", f"CALL-{j}")["output"]["region_id"] = "R-EDITED"


def b_execution_failed(case, cat, j):
    r = _row(case["receipts"], "call_id", f"CALL-{j}")
    r["status"], r["output"] = "error", {"result_code": "MOCK-ERROR"}
    r["output_sha256"] = digest(r["output"])


def b_wrong_study(case, cat, j):
    _row(case["proposed_calls"], "call_id", f"CALL-{j}")["args"]["study_id"] = "SYN-EVAL-OTHER"


def b_receipt_other_tool(case, cat, j):
    r = _row(case["receipts"], "call_id", f"CALL-{j}")
    r["tool_id"] = "SYN-FRACTURE-1" if r["tool_id"] != "SYN-FRACTURE-1" else "SYN-NODULE-1"


def b_modality_swapped(case, cat, j):
    case["study"]["modality"] = OTHER_MODALITY[case["study"]["modality"]]


def b_source_negated(case, cat, j):
    tool, src = _source_of(cat, case, j)
    src["text"] = f"Tool {tool['tool_id']} is not validated to {tool['quote']}."
    src["sha256"] = hashlib.sha256(src["text"].encode("utf-8")).hexdigest()


def b_source_tampered(case, cat, j):
    _source_of(cat, case, j)[1]["text"] += " Revised after publication."


def b_statement_dropped(case, cat, j):
    case["draft_report"]["statements"] = _drop(case["draft_report"]["statements"], "obligation_id", f"OB-{j}")


def b_citation_wrong(case, cat, j):
    _row(case["draft_report"]["statements"], "obligation_id", f"OB-{j}")["cites_receipt"] = "RCPT-999"


def b_disclosure_contradicts(case, cat, j):
    _row(case["draft_report"]["statements"], "obligation_id", f"OB-{j}")["kind"] = "discloses_not_assessed"


def _ob(a, j):
    return a["obligations"][f"OB-{j}"]


def _st(a, j):
    return a["statements"].get(f"ST-{j}", {})


BREAKS = {
    "call_omitted": (b_call_omitted, lambda a, j: _ob(a, j)["disposition"] == "supported_omitted"
                     and _st(a, j).get("outcome") == "unsupported_claim", "supported_omitted + unsupported_claim"),
    "receipt_missing": (b_receipt_missing, lambda a, j: _ob(a, j)["receipt_status"] == "missing", "receipt missing"),
    "output_edited": (b_output_edited, lambda a, j: "output_digest_mismatch" in _ob(a, j)["reasons"],
                      "output_digest_mismatch"),
    "execution_failed": (b_execution_failed, lambda a, j: _ob(a, j)["receipt_status"] == "failed", "receipt failed"),
    "wrong_study": (b_wrong_study, lambda a, j: a["calls"][f"CALL-{j}"]["status"] == "invalid"
                    and "arg_invalid:study_id" in a["calls"][f"CALL-{j}"]["reasons"], "arg_invalid:study_id"),
    "receipt_other_tool": (b_receipt_other_tool, lambda a, j: "tool_mismatch" in _ob(a, j)["reasons"], "tool_mismatch"),
    "modality_swapped": (b_modality_swapped, lambda a, j: _ob(a, j)["disposition"] == "unsupported", "unsupported"),
    "source_negated": (b_source_negated, lambda a, j: _ob(a, j)["disposition"] == "uncertain"
                       and "negation_near_quote" in _ob(a, j)["reasons"], "uncertain: negation_near_quote"),
    "source_tampered": (b_source_tampered, lambda a, j: _ob(a, j)["disposition"] == "uncertain"
                        and "source_hash_mismatch" in _ob(a, j)["reasons"], "uncertain: source_hash_mismatch"),
    "statement_dropped": (b_statement_dropped, lambda a, j: a["report_gaps"].get(f"OB-{j}") == "add_cited_claim",
                          "report gap: add_cited_claim"),
    "citation_wrong": (b_citation_wrong, lambda a, j: _st(a, j).get("outcome") == "receipt_mismatch",
                       "receipt_mismatch"),
    "disclosure_contradicts": (b_disclosure_contradicts,
                               lambda a, j: _st(a, j).get("outcome") == "disclosure_contradicts_support",
                               "disclosure_contradicts_support"),
}


def evaluate(build_audit, catalog):
    rng = random.Random(SEED)
    clean = {"n": 0, "full_support": 0, "false_alarms": []}
    by_type = {name: {"n": 0, "flagged": 0, "right_reason": 0, "false_full_support": 0, "expected": sig}
               for name, (_, _, sig) in BREAKS.items()}
    failures, n = [], 0
    for _ in range(N_CLEAN):
        case = clean_case(rng, n)
        n += 1
        clean["n"] += 1
        if build_audit(catalog, case)["completeness"] == "full_support":
            clean["full_support"] += 1
        else:
            clean["false_alarms"].append(case["case_id"])
    for name, (mutate, signal, _) in BREAKS.items():
        for _ in range(N_PER_BREAK):
            case, cat = clean_case(rng, n), copy.deepcopy(catalog)
            n += 1
            j = rng.randint(1, len(case["study"]["obligations"]))
            mutate(case, cat, j)
            a = build_audit(cat, case)
            row = by_type[name]
            row["n"] += 1
            flagged, right = a["completeness"] == "gaps_found", signal(a, j)
            row["flagged"] += flagged
            row["right_reason"] += bool(flagged and right)
            row["false_full_support"] += a["completeness"] == "full_support"
            if not (flagged and right):
                failures.append({"case_id": case["case_id"], "break": name, "obligation": f"OB-{j}",
                                 "completeness": a["completeness"]})
    total = {k: sum(r[k] for r in by_type.values()) for k in ("n", "flagged", "right_reason", "false_full_support")}
    return {"clean": clean, "broken": dict(total, by_type=by_type), "failures": failures}


def code_digest(src):
    h = hashlib.sha256()
    for p in sorted((src / "contract_audit").glob("*.py")):
        h.update(p.name.encode() + b"\0" + p.read_bytes())
    h.update((ROOT / "data" / "catalog.json").read_bytes())
    return h.hexdigest()[:16]


def run(src):
    sys.path.insert(0, str(src))
    from contract_audit.audit import build_audit  # noqa: E402
    catalog = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    result = evaluate(build_audit, catalog)
    return {"schema": "contract-audit-eval/v1", "seed": SEED, "code_digest": code_digest(src),
            "n_clean": N_CLEAN, "n_per_break": N_PER_BREAK, **result}


def markdown(r):
    b, c = r["broken"], r["clean"]
    lines = [
        "# Adversarial evaluation (seeded, synthetic)",
        "",
        "Generated by `scripts/make_eval.py` (seed {seed}, code digest `{d}`); raw numbers in "
        "`eval/results/adversarial_v1.json`. Do not edit by hand.".format(seed=r["seed"], d=r["code_digest"]),
        "",
        f"**{b['flagged']}/{b['n']} broken reports flagged, {b['right_reason']}/{b['n']} for the right reason, "
        f"{b['false_full_support']} passed as complete. {c['full_support']}/{c['n']} clean reports passed "
        f"({len(c['false_alarms'])} false alarms).**",
        "",
        "Every broken case looks complete: each obligation has a claim in the report. One thing is wrong in each.",
        "",
        "| Break (one per case) | n | Flagged | Right reason | Passed as complete | Expected signal |",
        "|---|---|---|---|---|---|",
    ]
    for name, row in b["by_type"].items():
        lines.append(f"| `{name}` | {row['n']} | {row['flagged']} | {row['right_reason']} | "
                     f"{row['false_full_support']} | {row['expected']} |")
    before = ROOT / "eval" / "results" / "adversarial_v1_at_b2de604.json"
    if before.exists():
        o = json.loads(before.read_text(encoding="utf-8"))["broken"]
        missed = ", ".join(f"`{k}` {v['false_full_support']}/{v['n']}" for k, v in o["by_type"].items()
                           if v["false_full_support"])
        lines += ["", f"**The same set on the code before the 10 Nov fixes** (commit `b2de604`, "
                  "`eval/results/adversarial_v1_at_b2de604.json`): "
                  f"{o['false_full_support']}/{o['n']} broken reports passed as complete ({missed}). "
                  "Those two holes were found by review and closed in PR #3; this set confirms both."]
    lines += ["", "Limits: the cases are generated from a fictional six-tool catalog, and each break is one the "
              "validator was designed to catch. This shows the checks hold on cases nobody hand-picked, and that "
              "clean reports are not over-flagged. It is not evidence about real tools, real reports or SERV.", ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true", help="exit 1 if eval/ is stale")
    p.add_argument("--src", type=Path, default=ROOT / "src", help="score the contract_audit package under this src")
    p.add_argument("--out", type=Path, help="write the JSON here instead of eval/results/ (no RESULTS.md)")
    args = p.parse_args()
    r = run(args.src.resolve())
    text = json.dumps(r, indent=2, sort_keys=True) + "\n"
    if args.check:
        stale = not RESULTS.exists() or RESULTS.read_text(encoding="utf-8") != text \
            or not REPORT.exists() or REPORT.read_text(encoding="utf-8") != markdown(r)
        print("eval results are stale: run python3 scripts/make_eval.py" if stale else "eval results are current")
        return 1 if stale else 0
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        RESULTS.parent.mkdir(parents=True, exist_ok=True)
        RESULTS.write_text(text, encoding="utf-8")
        REPORT.write_text(markdown(r), encoding="utf-8")
    b = r["broken"]
    print(f"clean {r['clean']['full_support']}/{r['clean']['n']} | broken flagged {b['flagged']}/{b['n']}, "
          f"right reason {b['right_reason']}, passed as complete {b['false_full_support']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
