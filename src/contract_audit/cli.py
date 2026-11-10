"""Command line: `python3 -m contract_audit audit --catalog C --case X`. Offline and deterministic."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .audit import build_audit
from .inputs import InputError, load_case, load_catalog
from .serv import NotConfigured, load_config

# EXIT_BAD_INPUT covers unreadable or malformed input files and an unwritable --out path: never a crash.
EXIT_OK, EXIT_GAPS, EXIT_BAD_INPUT, EXIT_SERV_NOT_CONFIGURED, EXIT_SERV_NO_TRANSPORT = 0, 1, 2, 3, 4


def _parser():
    p = argparse.ArgumentParser(prog="contract_audit", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("audit", help="audit one synthetic case against the catalog")
    a.add_argument("--catalog", required=True, type=Path)
    a.add_argument("--case", required=True, type=Path)
    a.add_argument("--out", type=Path, help="write the audit JSON here instead of stdout")
    a.add_argument("--fail-on-gaps", action="store_true", help="exit 1 unless completeness is full_support")
    a.add_argument("--serv", action="store_true",
                   help="request the SERV advisory step (fails closed: no credentials or no transport, no call)")
    return p


def _serv_block(status):
    return {"status": status, "executed": False, "fixture": False}


def _serv_gate(environ):
    """Return (serv status block, exit code, stderr message). Never makes a call.

    With a key configured there is still nothing to call: this spike ships no live transport.
    """
    try:
        load_config(environ)
    except NotConfigured as exc:
        return _serv_block("not_configured"), EXIT_SERV_NOT_CONFIGURED, str(exc)
    return (_serv_block("live_transport_not_implemented"), EXIT_SERV_NO_TRANSPORT,
            "credentials are present but this spike has no live transport; no request was sent")


def main(argv=None, environ=None):
    args = _parser().parse_args(argv)
    environ = os.environ if environ is None else environ
    try:
        catalog, case = load_catalog(args.catalog), load_case(args.case)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    serv, code, message = None, EXIT_OK, ""
    if args.serv:
        serv, code, message = _serv_gate(environ)
    audit = build_audit(catalog, case, serv=serv)
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
