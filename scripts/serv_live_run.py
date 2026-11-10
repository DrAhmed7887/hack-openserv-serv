"""Run the live SERV advisory on every fixture case that has an uncertain obligation, and record it.

Usage (key read from the macOS Keychain, never written to disk or printed):
    SERV_API_KEY="$(security find-generic-password -s SERV_API_KEY -w)" \
        python3 scripts/serv_live_run.py --model gpt-6-luna

Writes docs/serv_run/<case>.json (the audit with the advisory attached) and docs/SERV_RUN.md.
Each request costs SERV credits; with the fixture set this is one request per uncertain obligation.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contract_audit import cli  # noqa: E402

CASES = ("c04_uncertain_source_insufficient", "c07_combined")


def run_case(name, model):
    out_dir = ROOT / "docs" / "serv_run"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{name}.json"
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        code = cli.main(["audit", "--catalog", str(ROOT / "data" / "catalog.json"),
                         "--case", str(ROOT / "data" / "cases" / f"{name}.json"),
                         "--serv", "--serv-model", model, "--out", str(out)])
    return code, json.loads(out.read_text(encoding="utf-8")), err.getvalue().strip()


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--model", required=True)
    args = p.parse_args()
    if not os.environ.get("SERV_API_KEY", "").strip():
        print("SERV_API_KEY is not set; nothing was sent", file=sys.stderr)
        return 3
    when = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows, worst = [], 0
    for name in CASES:
        code, audit, err = run_case(name, args.model)
        worst = max(worst, code if code != cli.EXIT_GAPS else 0)
        serv = audit["serv"]
        for oid, adv in sorted(audit.get("serv_advisory", {}).items()):
            u = adv.get("usage", {})
            rows.append(f"| {name} | {oid} | {audit['obligations'][oid]['disposition']} | {adv['verdict']} | "
                        f"{'yes' if adv['accepted'] else 'no: ' + ', '.join(adv['reasons'])} | "
                        f"\"{adv['quote']}\" | {u.get('prompt_tokens', '?')} / {u.get('completion_tokens', '?')} |")
        if not audit.get("serv_advisory"):
            rows.append(f"| {name} | - | - | not run ({serv['status']}) | - | {err or '-'} | - |")
    md = [
        "# SERV Reasoning live run",
        "",
        f"Run {when} with model `{args.model}` via `scripts/serv_live_run.py`. "
        "Raw audits with the advisory attached: `docs/serv_run/`.",
        "",
        "SERV's answer is advice for a human: it never changes the disposition, `full_support` or completeness. "
        "A quote is accepted only if it appears verbatim in the tool's source text.",
        "",
        "| Case | Obligation | Deterministic disposition | SERV verdict | Accepted | Quote | Tokens in / out |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "",
        "Cost: read it from the SERV console usage page (prices per model are in the SERV models docs).",
        "",
    ]
    (ROOT / "docs" / "SERV_RUN.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    return worst


if __name__ == "__main__":
    sys.exit(main())
