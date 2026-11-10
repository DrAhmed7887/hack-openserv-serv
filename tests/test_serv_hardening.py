"""SERV boundary hardening. Nothing here makes a network call; this spike ships no live transport, so no
caller can truthfully attest live execution and none is accepted."""
import json

import pytest

from contract_audit.audit import build_audit
from contract_audit.serv import (LiveTransportNotImplemented, NotConfigured, ServClient, attach_advisory,
                                 build_request, load_config, parse_interpretation)

KEY = "test-not-a-real-key-123"
QUOTE = "measure cardiac size on radiographs"


def completion(content, fixture=True):
    r = {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
    if fixture:
        r["fixture"] = True
    return r


def interp(catalog, **over):
    src = catalog["sources"]["SRC-SYN-D"]["text"]
    r = parse_interpretation(completion(json.dumps({"verdict": "supported", "quote": QUOTE})), src)
    r.update(over)
    return r


def audit4(catalog, case):
    return build_audit(catalog, case("c04_uncertain_source_insufficient"))


# model name
@pytest.mark.parametrize("model", ["", "   ", "\t\n", None, 5, ["m"], {"m": 1}, b"m"])
def test_model_must_be_a_nonblank_string(catalog, model):
    with pytest.raises(ValueError, match="model"):
        build_request(model, {"obligation_id": "OB-4"}, "chest-xr", "SRC-SYN-D", "text")


def test_a_real_looking_model_name_is_still_accepted_and_passed_through(catalog):
    assert build_request("MODEL-PLACEHOLDER", {}, "chest-xr", "S", "t")["body"]["model"] == "MODEL-PLACEHOLDER"


# live execution cannot be asserted by the caller
@pytest.mark.parametrize("transport", [None, lambda r, c: completion("{}")])
def test_client_refuses_live_mode_even_with_credentials_and_a_transport(transport):
    with pytest.raises(LiveTransportNotImplemented):
        ServClient(load_config({"SERV_API_KEY": KEY}), transport, live=True)


def test_credentials_are_still_checked_before_live_mode(catalog):
    with pytest.raises(NotConfigured):
        ServClient(None, transport=lambda r, c: {}, live=True)


def test_interpret_never_reports_executed(catalog):
    client = ServClient(load_config({"SERV_API_KEY": KEY}),
                        lambda r, c: completion(json.dumps({"verdict": "uncertain", "quote": ""})))
    r = client.interpret("MODEL-PLACEHOLDER", {"obligation_id": "OB-4"}, "chest-xr", "SRC-SYN-D", "t")
    assert r["fixture"] is True and r["executed"] is False


@pytest.mark.parametrize("over,needle", [
    ({"fixture": True, "executed": True}, "mutually exclusive"),
    ({"fixture": False, "executed": True}, "no live transport"),
    ({"fixture": True, "executed": "yes"}, "executed"),
    ({"fixture": True, "executed": 1}, "executed"),
    ({"fixture": False, "executed": False}, "neither fixture nor executed"),
    ({"fixture": "true", "executed": False}, "neither fixture nor executed"),
    ({"fixture": 1}, "neither fixture nor executed"),
])
def test_attach_advisory_refuses_forged_or_ambiguous_labels(catalog, case, over, needle):
    with pytest.raises(ValueError, match=needle):
        attach_advisory(audit4(catalog, case), "OB-4", interp(catalog, **over))


def test_attach_advisory_without_an_executed_key_is_a_fixture(catalog, case):
    i = interp(catalog)
    i.pop("executed", None)
    out = attach_advisory(audit4(catalog, case), "OB-4", i)
    assert out["serv"] == {"status": "fixture", "executed": False, "fixture": True}


def test_attach_advisory_with_a_missing_fixture_key_is_refused_not_a_crash(catalog, case):
    i = interp(catalog)
    del i["fixture"]
    with pytest.raises(ValueError, match="neither fixture nor executed"):
        attach_advisory(audit4(catalog, case), "OB-4", i)


# a forged serv block cannot reach the audit through build_audit either
@pytest.mark.parametrize("serv", [
    {"status": "executed", "executed": True, "fixture": False},
    {"status": "fixture", "executed": True, "fixture": True},
    {"status": "x", "executed": "no", "fixture": False},
    {"status": "x"}, {}, "executed", ["a"], 5,
])
def test_build_audit_refuses_a_serv_block_that_claims_execution_or_is_malformed(catalog, case, serv):
    with pytest.raises(ValueError, match="serv"):
        build_audit(catalog, case("c01_supported_called"), serv=serv)


@pytest.mark.parametrize("serv", [None, {"status": "not_configured", "executed": False, "fixture": False},
                                  {"status": "live_transport_not_implemented", "executed": False, "fixture": False}])
def test_build_audit_accepts_the_not_run_blocks_the_cli_produces(catalog, case, serv):
    a = build_audit(catalog, case("c01_supported_called"), serv=serv)
    assert a["serv"]["executed"] is False and a["serv"]["fixture"] is False


# ---- the quote must be a meaningful stretch of the source, not any substring ----
SRC = "SYNTHETIC SPECIFICATION D (fictional, engineering test only). Tool SYN-CARDIAC-1 is specified to " \
      "measure cardiac size on radiographs."


def parsed(verdict, quote):
    return parse_interpretation(completion(json.dumps({"verdict": verdict, "quote": quote})), SRC)


@pytest.mark.parametrize("quote", ["a", "o", " ", "size", "SYN-CARDIAC-1", "on radiographs", "to measure", "is specified"])
@pytest.mark.parametrize("verdict", ["supported", "unsupported"])
def test_a_short_substring_is_not_a_verbatim_quote(verdict, quote):
    assert quote in SRC  # every one of these IS a substring: that is the defect being closed
    r = parsed(verdict, quote)
    assert r["accepted"] is False and r["quote_in_source"] is False and "quote_too_short" in r["reasons"]


@pytest.mark.parametrize("quote", [QUOTE, "specified to measure cardiac size", "engineering test only"])
def test_a_meaningful_verbatim_quote_is_still_accepted(quote):
    r = parsed("supported", quote)
    assert r["accepted"] is True and r["quote_in_source"] is True and r["reasons"] == []


def test_a_long_quote_that_is_not_in_the_source_keeps_its_old_reason():
    r = parsed("supported", "measure cardiac size on chest-xr studies")
    assert r["accepted"] is False and r["reasons"] == ["quote_not_in_source"]


def test_uncertain_with_no_quote_is_still_accepted():
    r = parsed("uncertain", "")
    assert r["accepted"] is True and r["reasons"] == []
