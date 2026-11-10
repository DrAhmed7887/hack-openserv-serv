#!/usr/bin/env python3
"""Live SERV Reasoning batches: where does SERV help, and does the guard hold when it over-reaches?

Each batch is 24 synthetic variants of tool spec SRC-SYN-D (tool SYN-CARDIAC-1; obligation OB-4: cardiac size on
chest-xr). The deterministic rule says "uncertain" for every one (the catalog quote does not name chest-xr), so
each goes to SERV. Every variant has a designed answer, written here before its batch was run:
  sufficient (8)    the spec names chest-xr as covered          -> designed "supported"
  insufficient (8)  the spec never settles the study type        -> designed "uncertain"
  excluded (8)      the spec rules chest-xr out                  -> designed "unsupported"
v1 was run first. The quote-relevance rule (a "supported" quote must name the modality) was written after v1.
v2 is held out: new wording, committed before it was run, scored with the rule already in place.

Usage (key read from the macOS Keychain, never written to disk or printed):
    SERV_API_KEY="$(security find-generic-password -s SERV_API_KEY -w)" \\
        python3 scripts/serv_eval.py --batch v2 --model gpt-6-luna
    python3 scripts/serv_eval.py --rebuild     # recompute summaries and eval/SERV_BATCH.md; sends nothing
Writes eval/results/serv_batch_<batch>.json and eval/SERV_BATCH.md. Costs SERV credits (24 requests).
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import hashlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contract_audit import cli  # noqa: E402
from contract_audit.audit import build_audit  # noqa: E402
from contract_audit.serv import attach_advisory  # noqa: E402

PREFIX = "SYNTHETIC SPECIFICATION D (fictional, engineering test only). "
CASE = ROOT / "data" / "cases" / "c04_uncertain_source_insufficient.json"
GROUPS = ("sufficient", "insufficient", "excluded")
DESIGNED = {"sufficient": "supported", "insufficient": "uncertain", "excluded": "unsupported"}

_V1_LEAD = "Tool SYN-CARDIAC-1 is specified to measure cardiac size on radiographs."
_V1_EXTRA = {
    "sufficient": ["Supported study types: chest-xr (PA and AP views).", "It is validated on chest-xr studies.",
                   "Intended study type: chest-xr.", "The supported modality is chest-xr.",
                   "Use it on chest-xr studies; other modalities are out of scope.", "Applies to chest-xr studies.",
                   "Coverage: chest-xr studies, frontal projection.", "The radiographs it reads are chest-xr studies."],
    "insufficient": ["Supported study types are listed in a separate document that is not included here.", "",
                     "Study types will be confirmed in a later release.",
                     "See the vendor portal for supported modalities.",
                     "Validation status for each study type: pending.",
                     "Supported views and modalities are configured by each site.",
                     "It was developed in research settings.", "Modality coverage is documented elsewhere."],
    "excluded": ["It does not support chest-xr studies.",
                 "Supported study types: extremity-xr. chest-xr is not supported.",
                 "Excluded study types: chest-xr.", "Not for use on chest-xr studies.",
                 "chest-xr studies are out of scope.", "Support for chest-xr was withdrawn.",
                 "Only extremity-xr studies are supported.", "chest-xr support was removed in version 2."],
}
BATCHES = {
    "v1": {g: [f"{_V1_LEAD} {x}".strip() for x in xs] for g, xs in _V1_EXTRA.items()},
    # v2: held out. Written and committed before its run; new leads and new wording throughout.
    "v2": {
        "sufficient": [
            "Version 3 of SYN-CARDIAC-1 will measure cardiac size on radiographs. It was cleared for chest-xr use.",
            "SYN-CARDIAC-1 can measure cardiac size on radiographs. Target modality: chest-xr.",
            "This module is built to measure cardiac size on radiographs. Every chest-xr study is in scope.",
            "SYN-CARDIAC-1 was trained to measure cardiac size on radiographs, and its target studies are chest-xr.",
            "Purpose: measure cardiac size on radiographs. Study type covered: chest-xr.",
            "SYN-CARDIAC-1 is designed to measure cardiac size on radiographs. Inputs accepted: chest-xr studies.",
            "The tool's job is to measure cardiac size on radiographs. It is meant for chest-xr.",
            "SYN-CARDIAC-1 aims to measure cardiac size on radiographs; chest-xr is the supported study type.",
        ],
        "insufficient": [
            "SYN-CARDIAC-1 can measure cardiac size on radiographs. Which study types it accepts is not stated here.",
            "Purpose: measure cardiac size on radiographs. The list of study types is pending review.",
            "This module is built to measure cardiac size on radiographs. Study types vary by deployment.",
            "SYN-CARDIAC-1 aims to measure cardiac size on radiographs. Contact the vendor about study types.",
            "The tool's job is to measure cardiac size on radiographs. Its study-type list is in annex B (not provided).",
            "SYN-CARDIAC-1 was trained to measure cardiac size on radiographs from several sites.",
            "SYN-CARDIAC-1 is designed to measure cardiac size on radiographs. Performance data will follow.",
            "Version 3 of SYN-CARDIAC-1 will measure cardiac size on radiographs once configured.",
        ],
        "excluded": [
            "SYN-CARDIAC-1 can measure cardiac size on radiographs. chest-xr is outside its intended use.",
            "Purpose: measure cardiac size on radiographs. Study type covered: extremity-xr only.",
            "This module is built to measure cardiac size on radiographs. Do not run it on chest-xr.",
            "SYN-CARDIAC-1 aims to measure cardiac size on radiographs. chest-xr inputs are rejected.",
            "The tool's job is to measure cardiac size on radiographs. It must not be used for chest-xr studies.",
            "SYN-CARDIAC-1 was trained to measure cardiac size on radiographs, excluding chest-xr.",
            "SYN-CARDIAC-1 is designed to measure cardiac size on radiographs. chest-xr is an unsupported input.",
            "Version 3 of SYN-CARDIAC-1 will measure cardiac size on radiographs. chest-xr support ended with version 2.",
        ],
    },
}


def spec_text(row):
    """The full SRC-SYN-D text a row was run against (v1 rows store only the extra sentence)."""
    if "spec_text" in row:
        return PREFIX + row["spec_text"]
    return PREFIX + f"{_V1_LEAD} {row['spec_extra']}".strip()


def variant_catalog(base, text):
    cat = copy.deepcopy(base)
    src = cat["sources"]["SRC-SYN-D"]
    src["text"] = text
    src["sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return cat


def accepted_now(base, case, row):
    """Acceptance of the recorded verdict and quote under the CURRENT rules. Offline; sends nothing."""
    if not row["answered"]:
        return False
    cat = variant_catalog(base, spec_text(row))
    audit = build_audit(cat, case)
    interp = {"fixture": True, "verdict": row["verdict"], "quote": row["quote"], "reasons": []}
    try:
        return attach_advisory(audit, "OB-4", interp, cat)["serv_advisory"]["OB-4"]["accepted"]
    except ValueError:
        return False


def run_variant(cat, model, tmp):
    cat_path, out_path = Path(tmp) / "catalog.json", Path(tmp) / "audit.json"
    cat_path.write_text(json.dumps(cat), encoding="utf-8")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        code = cli.main(["audit", "--catalog", str(cat_path), "--case", str(CASE),
                         "--serv", "--serv-model", model, "--out", str(out_path)])
    return code, json.loads(out_path.read_text(encoding="utf-8")), err.getvalue().strip()


def summarise(rows, base, case):
    out = {}
    for row in rows:
        row["accepted_now"] = accepted_now(base, case, row)
    for group in GROUPS:
        g = [r for r in rows if r["group"] == group]
        out[group] = {"n": len(g), "designed": DESIGNED[group],
                      "verdicts": {v: sum(r["verdict"] == v for r in g) for v in ("supported", "uncertain", "unsupported")},
                      "matches_designed": sum(r["verdict"] == DESIGNED[group] for r in g),
                      "accepted_at_run": sum(r["accepted"] for r in g),
                      "accepted_now": sum(r["accepted_now"] for r in g),
                      "quote_names_chest_xr": sum(isinstance(r["quote"], str) and "chest-xr" in r["quote"] for r in g)}
    answered = [r for r in rows if r["answered"]]
    out["guard"] = {"answered": len(answered),
                    "disposition_unchanged": sum(r["disposition"] == "uncertain" for r in answered),
                    "full_support_set": sum(r["full_support"] for r in answered),
                    "completeness_full_support": sum(r["completeness"] == "full_support" for r in answered)}
    over = [r for r in rows if r["group"] != "sufficient" and r["verdict"] == "supported"]
    out["over_reach"] = {"n": len(over), "of": sum(r["group"] != "sufficient" for r in rows),
                         "accepted_now": sum(r["accepted_now"] for r in over)}
    acc = [r for r in rows if r["accepted_now"]]
    out["accepted_advice_now"] = {"n": len(acc), "match_designed": sum(r["verdict"] == DESIGNED[r["group"]] for r in acc)}
    return out


def batch_md(name, r):
    s, g, o, a = r["summary"], r["summary"]["guard"], r["summary"]["over_reach"], r["summary"]["accepted_advice_now"]
    note = {"v1": "Run before the quote-relevance rule existed; the rule was written after it, so this batch "
                  "shaped the rule and does not validate it.",
            "v2": "Held out: new wording, committed before the run, scored with the rule already in place."}[name]
    lines = [f"## Batch {name} ({r['run_at']}, `{r['model']}`)", "", note, "",
             "| Group | n | Designed | SERV: supported / uncertain / unsupported | Matches designed | "
             "Accepted at run | Accepted under current rules | Quote names chest-xr |",
             "|---|---|---|---|---|---|---|---|"]
    for group in GROUPS:
        x = s[group]
        v = x["verdicts"]
        lines.append(f"| {group} | {x['n']} | {x['designed']} | {v['supported']} / {v['uncertain']} / "
                     f"{v['unsupported']} | {x['matches_designed']} | {x['accepted_at_run']} | {x['accepted_now']} | "
                     f"{x['quote_names_chest_xr']} |")
    lines += ["",
              f"- **Guard:** the deterministic disposition stayed `uncertain` in {g['disposition_unchanged']}/"
              f"{g['answered']} answered cases; `full_support` was set {g['full_support_set']} times; completeness "
              f"reached `full_support` {g['completeness_full_support']} times.",
              f"- **Over-reach:** SERV said `supported` on {o['n']} of the {o['of']} specs that do not establish "
              f"chest-xr coverage; under the current rules {o['accepted_now']} of those answers are accepted.",
              f"- **Accepted advice under the current rules:** {a['n']} answers, {a['match_designed']} of them match "
              "the designed answer.",
              f"- Tokens: {r['tokens']['prompt']} in, {r['tokens']['completion']} out, {r['requests']} requests.", ""]
    return lines


def markdown(results):
    lines = ["# SERV Reasoning batches (live, synthetic)", "",
             "Generated by `scripts/serv_eval.py`; raw answers in `eval/results/serv_batch_<batch>.json`. "
             "Do not edit by hand. Cost: read it from the SERV console.", "",
             "Every variant is one the deterministic rule can only call `uncertain` (the catalog quote does not name "
             "chest-xr), so each goes to SERV. SERV's answer is advice: it never changes the disposition, "
             "`full_support` or completeness. \"Accepted\" means well-formed, verbatim in the source and, for "
             "`supported`, naming the study modality. It is not the same as correct.", ""]
    for name in sorted(results):
        lines += batch_md(name, results[name])
    lines += ["Limits: synthetic sentences, one tool, one obligation, one model, one run per batch. This measures "
              "this setup, not SERV in general.", ""]
    return "\n".join(lines)


def load_results():
    out = {}
    for name in BATCHES:
        p = ROOT / "eval" / "results" / f"serv_batch_{name}.json"
        if p.exists():
            out[name] = json.loads(p.read_text(encoding="utf-8"))
    return out


def write_all(results, base, case):
    for name, r in results.items():
        r["summary"] = summarise(r["rows"], base, case)
        p = ROOT / "eval" / "results" / f"serv_batch_{name}.json"
        p.write_text(json.dumps(r, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (ROOT / "eval" / "SERV_BATCH.md").write_text(markdown(results), encoding="utf-8")


def live_batch(name, model, base):
    rows, tokens = [], {"prompt": 0, "completion": 0}
    for group in GROUPS:
        for i, text in enumerate(BATCHES[name][group], 1):
            with tempfile.TemporaryDirectory() as tmp:
                code, audit, err = run_variant(variant_catalog(base, PREFIX + text), model, tmp)
            adv = audit.get("serv_advisory", {}).get("OB-4")
            ob = audit["obligations"]["OB-4"]
            usage = (adv or {}).get("usage", {})
            tokens["prompt"] += usage.get("prompt_tokens", 0)
            tokens["completion"] += usage.get("completion_tokens", 0)
            rows.append({"id": f"{group}-{i}", "group": group, "spec_text": text, "exit_code": code,
                         "answered": adv is not None, "verdict": adv["verdict"] if adv else None,
                         "quote": adv["quote"] if adv else None, "accepted": bool(adv and adv["accepted"]),
                         "reasons": adv["reasons"] if adv else [err[:200]],
                         "disposition": ob["disposition"], "full_support": ob["full_support"],
                         "completeness": audit["completeness"], "serv_status": audit["serv"]["status"]})
            print(f"{name} {group}-{i}: {rows[-1]['verdict']} (accepted {rows[-1]['accepted']}) exit {code}")
    return {"schema": "contract-audit-serv-batch/v1", "batch": name, "model": model,
            "run_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "requests": len(rows), "tokens": tokens, "rows": rows}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--batch", choices=sorted(BATCHES), help="run this batch live")
    p.add_argument("--model", help="model id from the SERV catalog (required with --batch)")
    p.add_argument("--rebuild", action="store_true", help="recompute summaries and SERV_BATCH.md; sends nothing")
    args = p.parse_args()
    base = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    case = json.loads(CASE.read_text(encoding="utf-8"))
    results = load_results()
    if args.batch:
        if not args.model:
            p.error("--model is required with --batch")
        if not os.environ.get("SERV_API_KEY", "").strip():
            print("SERV_API_KEY is not set; nothing was sent", file=sys.stderr)
            return 3
        if args.batch in results:
            p.error(f"batch {args.batch} already has recorded results; a re-run would replace them")
        results[args.batch] = live_batch(args.batch, args.model, base)
    elif not args.rebuild:
        p.error("give --batch to run live, or --rebuild")
    write_all(results, base, case)
    for name, r in sorted(results.items()):
        print(name, json.dumps({k: r["summary"][k] for k in ("guard", "over_reach", "accepted_advice_now")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
