"""Malformed files and catalogs are input errors: InputError at the boundary, exit 2 and no traceback in the CLI.
Exit 1 means 'gaps found' and must never be produced by a crash."""
import json
import os
import subprocess
import sys

import pytest

from contract_audit.audit import build_audit
from contract_audit.cli import EXIT_BAD_INPUT, EXIT_GAPS, main
from contract_audit.inputs import InputError, load_case, load_catalog
from contract_audit.receipts import check_receipt
from conftest import DATA

CATALOG = DATA / "catalog.json"
CASE = DATA / "cases" / "c01_supported_called.json"


def write_bytes(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def deep(n):
    return b'{"synthetic": true, "x": ' + b"[" * n + b"]" * n + b"}"


BAD_FILES = {
    "invalid utf-8": (b'{"synthetic": true, "a": "\xff\xfe"}', "UTF-8"),
    "deeply nested json": (deep(100_000), "nested"),
    "empty file": (b"", "not valid JSON"),
    "utf-8 bom": (b'\xef\xbb\xbf{"synthetic": true}', "not valid JSON"),
}


@pytest.mark.parametrize("name", sorted(BAD_FILES))
@pytest.mark.parametrize("loader", [load_case, load_catalog])
def test_unreadable_or_pathological_file_is_an_input_error(tmp_path, loader, name):
    data, needle = BAD_FILES[name]
    with pytest.raises(InputError, match=needle):
        loader(write_bytes(tmp_path, "f.json", data))


def run_cli(capsys, catalog, case, *extra):
    code = main(["audit", "--catalog", str(catalog), "--case", str(case), *extra], environ={})
    out = capsys.readouterr()
    return code, out.out, out.err


@pytest.mark.parametrize("name", sorted(BAD_FILES))
def test_cli_exits_two_without_traceback_on_a_bad_case_file(capsys, tmp_path, name):
    code, out, err = run_cli(capsys, CATALOG, write_bytes(tmp_path, "f.json", BAD_FILES[name][0]))
    assert code == EXIT_BAD_INPUT == 2 and out == "" and err.startswith("error:") and "Traceback" not in err


@pytest.mark.parametrize("name", sorted(BAD_FILES))
def test_cli_exits_two_without_traceback_on_a_bad_catalog_file(capsys, tmp_path, name):
    code, out, err = run_cli(capsys, write_bytes(tmp_path, "f.json", BAD_FILES[name][0]), CASE)
    assert code == 2 and out == "" and "Traceback" not in err


def test_cli_exits_two_when_a_catalog_tool_has_no_required_args(capsys, tmp_path, catalog, clone):
    cat = clone(catalog)
    del cat["tools"][0]["required_args"]
    code, out, err = run_cli(capsys, write_bytes(tmp_path, "c.json", json.dumps(cat).encode()), CASE)
    assert code == 2 and out == "" and "required_args" in err and "Traceback" not in err


def test_cli_exits_two_when_a_catalog_tool_has_no_args_schema(capsys, tmp_path, catalog, clone):
    cat = clone(catalog)
    del cat["tools"][0]["args_schema"]
    code, out, err = run_cli(capsys, write_bytes(tmp_path, "c.json", json.dumps(cat).encode()), CASE)
    assert code == 2 and "args_schema" in err and "Traceback" not in err


def test_real_process_exit_code_is_two_not_one_for_a_crash_prone_file(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "SERV_API_KEY"}
    env["PYTHONPATH"] = str(DATA.parent / "src")
    cmd = [sys.executable, "-m", "contract_audit", "audit", "--catalog", str(CATALOG), "--case"]
    for name in ("invalid utf-8", "deeply nested json"):
        r = subprocess.run(cmd + [str(write_bytes(tmp_path, "f.json", BAD_FILES[name][0]))],
                           capture_output=True, text=True, env=env, cwd=str(DATA.parent))
        assert r.returncode == 2 and "Traceback" not in r.stderr, name
    gaps = subprocess.run(cmd + [str(DATA / "cases" / "c02_supported_omitted.json"), "--fail-on-gaps"],
                          capture_output=True, text=True, env=env, cwd=str(DATA.parent))
    assert gaps.returncode == EXIT_GAPS == 1


def test_receipt_output_too_deep_to_digest_is_an_invalid_receipt_not_a_crash(catalog, case, clone):
    c = clone(case("c01_supported_called"))
    node = out = {}
    for _ in range(50_000):
        node["a"] = {}
        node = node["a"]
    c["receipts"][0]["output"] = out
    r = check_receipt(c["proposed_calls"][0], c["receipts"])
    assert r["status"] == "invalid" and "output_not_digestable" in r["reasons"]
    assert build_audit(catalog, c)["obligations"]["OB-1"]["full_support"] is False


# ---- output-write failures are an IO error (exit 2, named on stderr), never a traceback or exit 1 ----
def unwritable_dir(tmp_path):
    d = tmp_path / "ro"
    d.mkdir()
    d.chmod(0o500)
    return d


def bad_out_paths(tmp_path):
    d = unwritable_dir(tmp_path)
    return {"missing parent dir": tmp_path / "no" / "such" / "audit.json",
            "path is a directory": tmp_path,
            "unwritable dir": d / "audit.json",
            "parent is a file": CASE / "audit.json"}


@pytest.mark.parametrize("name", ["missing parent dir", "path is a directory", "unwritable dir", "parent is a file"])
def test_unwritable_out_path_exits_two_with_a_clear_message(capsys, tmp_path, name):
    if name == "unwritable dir" and os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    code, out, err = run_cli(capsys, CATALOG, CASE, "--out", str(bad_out_paths(tmp_path)[name]))
    assert code == 2 and out == ""
    assert err.startswith("error: cannot write") and "Traceback" not in err


def test_write_failure_beats_the_gaps_exit_code(capsys, tmp_path):
    code, _, err = run_cli(capsys, CATALOG, DATA / "cases" / "c02_supported_omitted.json",
                           "--fail-on-gaps", "--out", str(tmp_path / "no" / "audit.json"))
    assert code == 2 and "cannot write" in err


def test_write_failure_beats_the_serv_exit_codes(capsys, tmp_path):
    code, _, err = run_cli(capsys, CATALOG, CASE, "--serv", "--out", str(tmp_path / "no" / "audit.json"))
    assert code == 2 and "cannot write" in err


def test_real_process_out_failure_exit_code_is_two(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "SERV_API_KEY"}
    env["PYTHONPATH"] = str(DATA.parent / "src")
    r = subprocess.run([sys.executable, "-m", "contract_audit", "audit", "--catalog", str(CATALOG), "--case",
                        str(CASE), "--out", str(tmp_path / "no" / "audit.json")],
                       capture_output=True, text=True, env=env, cwd=str(DATA.parent))
    assert r.returncode == 2 and "Traceback" not in r.stderr
