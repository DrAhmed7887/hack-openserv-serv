"""Command line: `python3 -m contract_audit audit --catalog C --case X`. Offline and deterministic."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .audit import build_audit
from .inputs import InputError, load_case, load_catalog
from .serv import LiveServClient, NotConfigured, ServCallFailed, attach_advisory, load_config, urllib_post

# EXIT_BAD_INPUT covers unreadable or malformed input files and an unwritable --out path: never a crash.
EXIT_OK, EXIT_GAPS, EXIT_BAD_INPUT, EXIT_SERV_NOT_CONFIGURED, EXIT_SERV_NO_MODEL, EXIT_SERV_CALL_FAILED = \
    0, 1, 2, 3, 4, 5


def _parser():
    p = argparse.ArgumentParser(prog="contract_audit", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("audit", help="audit one synthetic case against the catalog")
    a.add_argument("--catalog", required=True, type=Path)
    a.add_argument("--case", required=True, type=Path)
    a.add_argument("--out", type=Path, help="write the audit JSON here instead of stdout")
    a.add_argument("--fail-on-gaps", action="store_true", help="exit 1 unless completeness is full_support")
    a.add_argument("--serv", action="store_true",
                   help="ask SERV Reasoning for advice on uncertain obligations (needs SERV_API_KEY and "
                        "--serv-model; fails closed otherwise). Advice never changes the audit result.")
    a.add_argument("--serv-model", help="model id from the SERV catalog, e.g. gpt-6-luna (not guessed)")
    return p


def _serv_block(status):
    return {"status": status, "executed": False, "fixture": False}


def _serv_gate(environ, model):
    """Return (config or None, serv status block, exit code, stderr message). Never makes a call."""
    try:
        config = load_config(environ)
    except NotConfigured as exc:
        return None, _serv_block("not_configured"), EXIT_SERV_NOT_CONFIGURED, str(exc)
    if not (model or "").strip():
        return (None, _serv_block("model_not_chosen"), EXIT_SERV_NO_MODEL,
                "no --serv-model given; no request was sent")
    return config, None, EXIT_OK, ""


def _with_live_advice(audit, catalog, case, config, model, http):
    """One SERV request per uncertain obligation; each answer is attached as advice only."""
    client = LiveServClient(config, http)
    tools = {t["tool_id"]: t for t in catalog["tools"]}
    classes = {o["obligation_id"]: o["finding_class"] for o in case["study"]["obligations"]}
    for oid, ob in sorted(audit["obligations"].items()):
        if ob["disposition"] != "uncertain" or ob["tool_id"] not in tools:
            continue
        source_id = tools[ob["tool_id"]]["source_id"]
        result = client.interpret(model, classes[oid], case["study"]["modality"], source_id,
                                  catalog["sources"][source_id]["text"])
        audit = attach_advisory(audit, oid, result)
    return audit


def main(argv=None, environ=None, http=urllib_post):
    args = _parser().parse_args(argv)
    environ = os.environ if environ is None else environ
    try:
        catalog, case = load_catalog(args.catalog), load_case(args.case)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    serv, code, message, config = None, EXIT_OK, "", None
    if args.serv:
        config, serv, code, message = _serv_gate(environ, args.serv_model)
    audit = build_audit(catalog, case, serv=serv)
    if config is not None:
        try:
            audit = _with_live_advice(audit, catalog, case, config, args.serv_model.strip(), http)
        except ServCallFailed as exc:
            audit = build_audit(catalog, case, serv=_serv_block("call_failed"))
            code, message = EXIT_SERV_CALL_FAILED, str(exc)
    text = json.dumps(audit, indent=2, sort_keys=True) + "\n"
    if args.out:
        try:
            args.out.write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write {args.out}: {exc.strerror or exc}", file=sys.stderr)
            return EXIT_BAD_INPUT
    else:
        sys.stdout.write(text)
    if message:
        print(f"error: {message}", file=sys.stderr)
    if code == EXIT_OK and args.fail_on_gaps and audit["completeness"] != "full_support":
        return EXIT_GAPS
    return code
