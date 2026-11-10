"""Live SERV path. Offline: the HTTP function is injected, and the real urllib sender is tested against a
local 127.0.0.1 server. No test reaches the internet."""
import io
import json
import threading
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from contract_audit import cli
from contract_audit.audit import build_audit
from contract_audit.serv import (ENDPOINT, LiveServClient, NotConfigured, ServCallFailed, attach_advisory,
                                 load_config, urllib_post)

KEY = "sk-test-not-a-real-key-0000000000"
MODEL = "gpt-6-luna"
ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "catalog.json"
C04 = ROOT / "data" / "cases" / "c04_uncertain_source_insufficient.json"
SOURCE_D = ("SYNTHETIC SPECIFICATION D (fictional, engineering test only). Tool SYN-CARDIAC-1 is specified to "
            "measure cardiac size on radiographs. Supported study types are listed in a separate document "
            "that is not included here.")


def completion(verdict="uncertain", quote="listed in a separate document that is not included here"):
    return {"id": "chatcmpl-x", "object": "chat.completion", "model": MODEL,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant",
                                     "content": json.dumps({"verdict": verdict, "quote": quote})}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 20, "total_tokens": 140}}


class FakeHttp:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response or completion(), error, []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": headers, "body": body, "timeout": timeout})
        if self.error:
            raise self.error
        return self.response


def client(http):
    return LiveServClient(load_config({"SERV_API_KEY": KEY}), http)


def interpret(c):
    return c.interpret(MODEL, "cardiac_size", "chest-xr", "SRC-SYN-D", SOURCE_D)


# --- client ---

def test_live_client_requires_a_config():
    with pytest.raises(NotConfigured):
        LiveServClient(None, FakeHttp())


def test_live_client_sends_one_post_with_bearer_key_added_at_send_time():
    http = FakeHttp()
    interpret(client(http))
    (call,) = http.calls
    assert call["url"] == ENDPOINT
    assert call["headers"]["Authorization"] == f"Bearer {KEY}"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["body"]["model"] == MODEL and call["body"]["messages"][0]["role"] == "system"
    assert KEY not in json.dumps(call["body"])
    assert 0 < call["timeout"] <= 60


def test_live_result_is_labelled_executed_not_fixture_and_keeps_usage():
    r = interpret(client(FakeHttp()))
    assert r["executed"] is True and r["fixture"] is False
    assert r["model"] == MODEL and r["usage"]["total_tokens"] == 140
    assert r["verdict"] == "uncertain" and r["accepted"] is True


def test_live_response_claiming_to_be_a_fixture_is_refused():
    resp = completion()
    resp["fixture"] = True
    with pytest.raises(ServCallFailed, match="fixture"):
        interpret(client(FakeHttp(resp)))


def test_live_parse_rules_still_apply_quote_must_be_verbatim():
    r = interpret(client(FakeHttp(completion("supported", "measures cardiac size on chest-xr studies"))))
    assert r["accepted"] is False and "quote_not_in_source" in r["reasons"]


def test_http_failure_surfaces_status_without_the_key():
    with pytest.raises(ServCallFailed) as exc:
        interpret(client(FakeHttp(error=ServCallFailed("HTTP 401 from SERV", status=401))))
    assert exc.value.status == 401 and KEY not in str(exc.value)


def test_live_client_repr_hides_the_key():
    c = client(FakeHttp())
    assert KEY not in repr(c) and KEY not in str(c)


# --- attaching a live advisory ---

def test_live_advisory_attaches_without_changing_the_deterministic_result(catalog, case):
    case = case("c04_uncertain_source_insufficient")
    audit = build_audit(catalog, case)
    out = attach_advisory(audit, "OB-4", interpret(client(FakeHttp())))
    assert out["serv"] == {"status": "executed", "executed": True, "fixture": False, "model": MODEL}
    assert out["obligations"] == audit["obligations"] and out["completeness"] == audit["completeness"]
    assert out["serv_advisory"]["OB-4"]["human_confirmation_required"] is True


def test_live_result_that_lost_its_provenance_is_refused(catalog, case):
    audit = build_audit(catalog, case("c04_uncertain_source_insufficient"))
    r = interpret(client(FakeHttp()))
    forged = {k: v for k, v in r.items() if k != "live_token"}
    with pytest.raises(ValueError, match="no live transport"):
        attach_advisory(audit, "OB-4", forged)


def test_live_advisory_cannot_set_full_support(catalog, case):
    audit = build_audit(catalog, case("c04_uncertain_source_insufficient"))
    r = interpret(client(FakeHttp(completion("supported", "measure cardiac size on radiographs"))))
    out = attach_advisory(audit, "OB-4", r)
    assert out["obligations"]["OB-4"]["full_support"] is False
    assert out["obligations"]["OB-4"]["disposition"] == "uncertain"


# --- CLI ---

def run_cli(argv, environ, http=None):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv, environ=environ, http=http)
    return code, out.getvalue(), err.getvalue()


def test_cli_live_run_attaches_advisory_for_each_uncertain_obligation():
    http = FakeHttp()
    code, out, err = run_cli(["audit", "--catalog", str(CATALOG), "--case", str(C04), "--serv",
                              "--serv-model", MODEL], {"SERV_API_KEY": KEY}, http)
    audit = json.loads(out)
    assert code == 0, err
    assert audit["serv"]["executed"] is True and audit["serv"]["model"] == MODEL
    assert set(audit["serv_advisory"]) == {"OB-4"} and len(http.calls) == 1
    assert KEY not in out and KEY not in err


def test_cli_live_run_without_a_key_makes_no_call():
    http = FakeHttp()
    code, out, _ = run_cli(["audit", "--catalog", str(CATALOG), "--case", str(C04), "--serv",
                            "--serv-model", MODEL], {}, http)
    assert code == cli.EXIT_SERV_NOT_CONFIGURED and http.calls == []
    assert json.loads(out)["serv"]["status"] == "not_configured"


def test_cli_with_key_but_no_model_makes_no_call():
    http = FakeHttp()
    code, out, _ = run_cli(["audit", "--catalog", str(CATALOG), "--case", str(C04), "--serv"],
                           {"SERV_API_KEY": KEY}, http)
    assert code == cli.EXIT_SERV_NO_MODEL and http.calls == []
    assert json.loads(out)["serv"] == {"status": "model_not_chosen", "executed": False, "fixture": False}


def test_cli_live_http_failure_exits_with_serv_error_and_keeps_the_audit():
    http = FakeHttp(error=ServCallFailed("HTTP 401 from SERV", status=401))
    code, out, err = run_cli(["audit", "--catalog", str(CATALOG), "--case", str(C04), "--serv",
                              "--serv-model", MODEL], {"SERV_API_KEY": KEY}, http)
    audit = json.loads(out)
    assert code == cli.EXIT_SERV_CALL_FAILED
    assert audit["serv"] == {"status": "call_failed", "executed": False, "fixture": False}
    assert "401" in err and KEY not in err and "Traceback" not in err


# --- the real urllib sender, against a local server only ---

class _Handler(BaseHTTPRequestHandler):
    status, payload, seen = 200, b"{}", {}

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        _Handler.seen = {"auth": self.headers.get("Authorization"), "body": json.loads(self.rfile.read(n))}
        self.send_response(_Handler.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(_Handler.payload)

    def log_message(self, *a):
        pass


@pytest.fixture
def local_server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}/v1/chat/completions"
    srv.shutdown()


def test_urllib_post_returns_parsed_json(local_server):
    _Handler.status, _Handler.payload = 200, json.dumps(completion()).encode()
    r = urllib_post(local_server, {"Authorization": "Bearer x", "Content-Type": "application/json"},
                    {"model": MODEL}, 5)
    assert r["model"] == MODEL and _Handler.seen["auth"] == "Bearer x"
    assert _Handler.seen["body"] == {"model": MODEL}


def test_urllib_post_raises_with_status_on_http_error(local_server):
    _Handler.status, _Handler.payload = 401, b'{"error":{"type":"auth","message":"bad key"}}'
    with pytest.raises(ServCallFailed) as exc:
        urllib_post(local_server, {"Content-Type": "application/json"}, {}, 5)
    assert exc.value.status == 401 and "auth" in str(exc.value)


def test_urllib_post_refuses_non_json(local_server):
    _Handler.status, _Handler.payload = 200, b"<html>not json</html>"
    with pytest.raises(ServCallFailed, match="not JSON"):
        urllib_post(local_server, {}, {}, 5)


def test_urllib_post_only_allows_https_or_loopback():
    with pytest.raises(ServCallFailed, match="https"):
        urllib_post("http://example.com/v1/chat/completions", {}, {}, 5)
