import hashlib
import json

import pytest

from contract_audit.audit import build_audit
from contract_audit.serv import (LiveTransportNotImplemented, ServClient, attach_advisory,
                                 load_config, parse_interpretation)

QUOTE = "measure cardiac size on radiographs"


def completion(content, finish="stop", fixture=True):
    r = {"id": "chatcmpl-FIXTURE", "object": "chat.completion", "model": "MODEL-PLACEHOLDER",
         "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                      "finish_reason": finish}],
         "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
    if fixture:
        r["fixture"] = True
    return r


def source(catalog):
    return catalog["sources"]["SRC-SYN-D"]["text"]


def good(catalog, verdict="supported", quote=QUOTE):
    return parse_interpretation(completion(json.dumps({"verdict": verdict, "quote": quote})), source(catalog))


def test_parse_accepts_schema_valid_answer_with_verbatim_quote(catalog):
    r = good(catalog)
    assert r["accepted"] is True and r["verdict"] == "supported" and r["fixture"] is True
    assert r["quote_in_source"] is True


def test_parse_rejects_quote_not_in_source(catalog):
    r = good(catalog, quote="measure cardiac size on chest-xr studies")
    assert r["accepted"] is False and "quote_not_in_source" in r["reasons"]


def test_parse_rejects_non_json_content(catalog):
    r = parse_interpretation(completion("Sure! It is supported."), source(catalog))
    assert r["accepted"] is False and "content_not_json" in r["reasons"]


def test_parse_rejects_verdict_outside_enum(catalog):
    r = good(catalog, verdict="definitely")
    assert r["accepted"] is False and "verdict_not_allowed" in r["reasons"]


def test_parse_rejects_truncated_or_filtered_completion(catalog):
    body = json.dumps({"verdict": "supported", "quote": QUOTE})
    for finish in ("length", "content_filter", "tool_calls"):
        r = parse_interpretation(completion(body, finish=finish), source(catalog))
        assert r["accepted"] is False and "finish_reason_not_stop" in r["reasons"]


def test_parse_rejects_malformed_response_shape(catalog):
    r = parse_interpretation({"error": {"type": "invalid_request_error", "message": "x"}}, source(catalog))
    assert r["accepted"] is False and "malformed_response" in r["reasons"]


def test_client_without_a_transport_refuses_to_call_out(catalog):
    client = ServClient(load_config({"SERV_API_KEY": "test-not-a-real-key-123"}))
    with pytest.raises(LiveTransportNotImplemented):
        client.interpret("MODEL-PLACEHOLDER", {"obligation_id": "OB-4"}, "chest-xr", "SRC-SYN-D", source(catalog))


def test_fixture_transport_result_is_labelled_fixture_and_not_executed(catalog):
    seen = {}

    def transport(request, config):
        seen["request"] = request
        return completion(json.dumps({"verdict": "uncertain", "quote": ""}))

    client = ServClient(load_config({"SERV_API_KEY": "test-not-a-real-key-123"}), transport)
    r = client.interpret("MODEL-PLACEHOLDER", {"obligation_id": "OB-4"}, "chest-xr", "SRC-SYN-D", source(catalog))
    assert r["fixture"] is True and r["executed"] is False
    assert seen["request"]["url"].startswith("https://inference-api.openserv.ai/")


def test_unlabelled_response_from_a_non_live_transport_is_refused(catalog):
    client = ServClient(load_config({"SERV_API_KEY": "test-not-a-real-key-123"}),
                        lambda req, cfg: completion(json.dumps({"verdict": "uncertain", "quote": ""}), fixture=False))
    with pytest.raises(ValueError, match="fixture"):
        client.interpret("MODEL-PLACEHOLDER", {"obligation_id": "OB-4"}, "chest-xr", "SRC-SYN-D", source(catalog))


def audit(catalog, case):
    return build_audit(catalog, case("c04_uncertain_source_insufficient"))


def test_advisory_cannot_change_disposition_support_or_completeness(catalog, case, clone):
    # even an ACCEPTED 'supported' advisory (its quote names chest-xr) leaves the deterministic result alone
    cat = clone(catalog)
    src = cat["sources"]["SRC-SYN-D"]
    src["text"] += " Intended study type: chest-xr."
    src["sha256"] = hashlib.sha256(src["text"].encode("utf-8")).hexdigest()
    before = audit(cat, case)
    after = attach_advisory(before, "OB-4", good(cat, verdict="supported", quote="Intended study type: chest-xr."), cat)
    assert after["obligations"] == before["obligations"]
    assert after["completeness"] == before["completeness"] == "gaps_found"
    assert after["statements"] == before["statements"]
    assert after["obligations"]["OB-4"]["full_support"] is False
    assert after["serv_advisory"]["OB-4"]["accepted"] is True
    assert after["serv_advisory"]["OB-4"]["human_confirmation_required"] is True


def test_advisory_marks_serv_block_as_fixture_not_executed(catalog, case):
    after = attach_advisory(audit(catalog, case), "OB-4", good(catalog), catalog)
    assert after["serv"] == {"status": "fixture", "executed": False, "fixture": True}


def test_advisory_is_attached_without_mutating_the_input_audit(catalog, case):
    before = audit(catalog, case)
    snapshot = json.dumps(before, sort_keys=True)
    attach_advisory(before, "OB-4", good(catalog), catalog)
    assert json.dumps(before, sort_keys=True) == snapshot


def test_advisory_only_for_uncertain_obligations(catalog, case):
    a = build_audit(catalog, case("c01_supported_called"))
    with pytest.raises(ValueError, match="uncertain"):
        attach_advisory(a, "OB-1", good(catalog), catalog)


def test_rejected_interpretation_is_recorded_as_rejected(catalog, case):
    after = attach_advisory(audit(catalog, case), "OB-4", good(catalog, quote="invented words"), catalog)
    assert after["serv_advisory"]["OB-4"]["accepted"] is False
