import json

import pytest

from contract_audit.serv import ENDPOINT, NotConfigured, build_request, load_config

KEY = "test-not-a-real-key-123"


@pytest.mark.parametrize("environ", [{}, {"SERV_API_KEY": ""}, {"SERV_API_KEY": "   "}])
def test_missing_or_blank_key_fails_closed(environ):
    with pytest.raises(NotConfigured, match="SERV was not run"):
        load_config(environ)


def test_config_never_exposes_the_key_in_repr_or_str():
    cfg = load_config({"SERV_API_KEY": KEY})
    assert KEY not in repr(cfg) and KEY not in str(cfg)
    assert cfg.api_key == KEY


def source_text(catalog):
    return catalog["sources"]["SRC-SYN-D"]["text"]


def make(catalog, **kw):
    args = dict(model="MODEL-PLACEHOLDER", obligation={"obligation_id": "OB-4", "finding_class": "cardiac_size"},
                modality="chest-xr", source_id="SRC-SYN-D", source_text=source_text(catalog))
    args.update(kw)
    return build_request(**args)


def test_request_targets_documented_chat_completions_endpoint(catalog):
    req = make(catalog)
    assert ENDPOINT == "https://inference-api.openserv.ai/v1/chat/completions"
    assert req["method"] == "POST" and req["url"] == ENDPOINT


def test_request_has_system_message_first_as_the_docs_require(catalog):
    msgs = make(catalog)["body"]["messages"]
    assert msgs[0]["role"] == "system" and msgs[0]["content"]
    assert msgs[1]["role"] == "user"


def test_request_asks_for_strict_json_schema_with_closed_verdict_enum(catalog):
    rf = make(catalog)["body"]["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    schema = rf["json_schema"]["schema"]
    assert schema["properties"]["verdict"]["enum"] == ["supported", "unsupported", "uncertain"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"verdict", "quote"}


def test_request_embeds_the_source_text_and_obligation(catalog):
    user = json.loads(make(catalog)["body"]["messages"][1]["content"])
    assert user["source_text"] == source_text(catalog)
    assert user["obligation"]["finding_class"] == "cardiac_size"
    assert user["study_modality"] == "chest-xr"


def test_request_contains_no_credential_and_model_is_caller_supplied(catalog):
    req = make(catalog)
    assert "Authorization" not in json.dumps(req) and "Bearer" not in json.dumps(req)
    assert req["body"]["model"] == "MODEL-PLACEHOLDER"


def test_model_is_required_not_guessed(catalog):
    with pytest.raises(ValueError, match="model"):
        make(catalog, model="")
