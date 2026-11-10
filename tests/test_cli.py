import json
import os
import socket
import subprocess
import sys

import pytest

from contract_audit.cli import main
from conftest import DATA

CATALOG = str(DATA / "catalog.json")


def case_path(case_id):
    return str(DATA / "cases" / f"{case_id}.json")


def run(argv, capsys, environ=None):
    code = main(argv, environ={} if environ is None else environ)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_cli_emits_audit_json_and_exits_zero(capsys):
    code, out, _ = run(["audit", "--catalog", CATALOG, "--case", case_path("c07_combined")], capsys)
    audit = json.loads(out)
    assert code == 0
    assert audit["case_id"] == "c07_combined" and audit["completeness"] == "gaps_found"
    assert audit["serv"] == {"status": "not_run", "executed": False, "fixture": False}


def test_cli_makes_no_network_connection(capsys, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    code, out, _ = run(["audit", "--catalog", CATALOG, "--case", case_path("c01_supported_called")], capsys)
    assert code == 0 and json.loads(out)["completeness"] == "full_support"


def test_fail_on_gaps_exits_one_but_still_prints_the_audit(capsys):
    code, out, _ = run(["audit", "--catalog", CATALOG, "--case", case_path("c02_supported_omitted"),
                        "--fail-on-gaps"], capsys)
    assert code == 1 and json.loads(out)["completeness"] == "gaps_found"


def test_fail_on_gaps_exits_zero_when_fully_supported(capsys):
    code, _, _ = run(["audit", "--catalog", CATALOG, "--case", case_path("c01_supported_called"),
                      "--fail-on-gaps"], capsys)
    assert code == 0


def test_out_option_writes_the_same_json(capsys, tmp_path):
    target = tmp_path / "audit.json"
    code, out, _ = run(["audit", "--catalog", CATALOG, "--case", case_path("c05_missing_receipt"),
                        "--out", str(target)], capsys)
    assert code == 0 and out == ""
    assert json.loads(target.read_text(encoding="utf-8"))["case_id"] == "c05_missing_receipt"


def test_bad_input_exits_two_with_message_and_no_traceback(capsys, tmp_path):
    code, out, err = run(["audit", "--catalog", CATALOG, "--case", str(tmp_path / "missing.json")], capsys)
    assert code == 2 and out == "" and "cannot read" in err and "Traceback" not in err


def test_non_synthetic_input_exits_two(capsys, tmp_path, case, clone):
    c = clone(case("c01_supported_called"))
    c["synthetic"] = False
    p = tmp_path / "real.json"
    p.write_text(json.dumps(c), encoding="utf-8")
    code, _, err = run(["audit", "--catalog", CATALOG, "--case", str(p)], capsys)
    assert code == 2 and "synthetic" in err


def test_serv_flag_without_key_fails_closed(capsys):
    code, out, err = run(["audit", "--catalog", CATALOG, "--case", case_path("c04_uncertain_source_insufficient"),
                          "--serv"], capsys, environ={})
    audit = json.loads(out)
    assert code == 3
    assert audit["serv"] == {"status": "not_configured", "executed": False, "fixture": False}
    assert "SERV was not run" in err
    assert "SERV result" not in out + err and "serv_advisory" not in audit


def test_serv_flag_with_key_still_makes_no_call_in_this_spike(capsys):
    code, out, err = run(["audit", "--catalog", CATALOG, "--case", case_path("c04_uncertain_source_insufficient"),
                          "--serv"], capsys, environ={"SERV_API_KEY": "test-not-a-real-key-123"})
    audit = json.loads(out)
    assert code == 4
    assert audit["serv"] == {"status": "live_transport_not_implemented", "executed": False, "fixture": False}
    assert "test-not-a-real-key-123" not in out + err


def test_module_entry_point_is_reproducible_offline():
    env = {k: v for k, v in os.environ.items() if k != "SERV_API_KEY"}
    env["PYTHONPATH"] = str(DATA.parent / "src")
    cmd = [sys.executable, "-m", "contract_audit", "audit", "--catalog", CATALOG, "--case", case_path("c07_combined")]
    one = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(DATA.parent))
    two = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(DATA.parent))
    assert one.returncode == 0 and one.stdout == two.stdout
    assert json.loads(one.stdout)["summary"]["fully_supported"] == 1
