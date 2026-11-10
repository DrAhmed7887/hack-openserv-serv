"""Explicit SERV Reasoning boundary. Nothing in this module makes a network call.

Interface facts come from the public docs read on 2026-11-10 (see docs/SERV_INTEGRATION.md).
Missing credentials fail closed: no SERV output is ever produced without a configured key.
"""
from __future__ import annotations

import copy
import json

ENDPOINT = "https://inference-api.openserv.ai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You compare a tool-capability description against a study obligation. "
    "Answer only from the supplied source_text. Return verdict 'supported' only if the source_text "
    "states the tool covers the obligation's finding class on the study modality, 'unsupported' only "
    "if it states it does not, otherwise 'uncertain'. Quote the exact supporting words from source_text."
)

VERDICTS = ["supported", "unsupported", "uncertain"]

# Floor for what counts as a quote: an engineering minimum so "a" or "the" cannot pass as verbatim support.
# It is not a semantic check; a human still confirms any advisory.
MIN_QUOTE_WORDS = 3
MIN_QUOTE_CHARS = 12


def _meaningful_quote(quote):
    return len(quote.split()) >= MIN_QUOTE_WORDS and len(quote.strip()) >= MIN_QUOTE_CHARS


class NotConfigured(RuntimeError):
    """No SERV credentials: SERV was not run."""


class ServConfig:
    def __init__(self, api_key):
        self.api_key = api_key

    def __repr__(self):
        return "ServConfig(api_key=<hidden>)"

    __str__ = __repr__


def load_config(environ):
    key = (environ.get("SERV_API_KEY") or "").strip()
    if not key:
        raise NotConfigured("SERV_API_KEY is not set; SERV was not run")
    return ServConfig(key)


def build_request(model, obligation, modality, source_id, source_text):
    """Build (never send) a chat-completions request. The key is added at send time, not here."""
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model is required: a non-blank name from the SERV model catalog; it is not guessed here")
    user = {"obligation": obligation, "study_modality": modality,
            "source_id": source_id, "source_text": source_text}
    schema = {
        "type": "object",
        "properties": {"verdict": {"type": "string", "enum": list(VERDICTS)},
                       "quote": {"type": "string"}},
        "required": ["verdict", "quote"],
        "additionalProperties": False,
    }
    return {
        "method": "POST",
        "url": ENDPOINT,
        "body": {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": json.dumps(user, sort_keys=True)}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "capability_interpretation", "strict": True,
                                                "schema": schema}},
        },
    }


class LiveTransportNotImplemented(RuntimeError):
    """This spike deliberately ships no live HTTP transport. No call was made."""


def parse_interpretation(response, source_text):
    """Validate a chat-completions response. Output is advisory data, never a decision."""
    result = {"verdict": None, "quote": None, "quote_in_source": False, "accepted": False,
              "reasons": [], "fixture": bool(isinstance(response, dict) and response.get("fixture") is True)}
    try:
        choice = response["choices"][0]
        content, finish = choice["message"]["content"], choice["finish_reason"]
    except (KeyError, IndexError, TypeError):
        result["reasons"].append("malformed_response")
        return result
    if finish != "stop":
        result["reasons"].append("finish_reason_not_stop")
    try:
        payload = json.loads(content)
        verdict, quote = payload["verdict"], payload["quote"]
    except (TypeError, ValueError, KeyError):
        result["reasons"].append("content_not_json")
        return result
    result["verdict"], result["quote"] = verdict, quote
    if verdict not in VERDICTS:
        result["reasons"].append("verdict_not_allowed")
    if not isinstance(quote, str):
        result["reasons"].append("quote_not_string")
        return result
    result["quote_in_source"] = _meaningful_quote(quote) and quote in source_text
    if verdict in ("supported", "unsupported") and not result["quote_in_source"]:
        result["reasons"].append("quote_not_in_source" if _meaningful_quote(quote) else "quote_too_short")
    result["accepted"] = not result["reasons"]
    return result


class ServClient:
    """Builds the request and validates the response. The transport is injected.

    There is no default transport: with transport=None every call raises LiveTransportNotImplemented.
    Any transport may only return responses labelled "fixture": true, and results are never "executed":
    this spike ships no live transport, so a caller cannot switch live mode on (live=True is refused).
    """

    def __init__(self, config, transport=None, live=False):
        if not isinstance(config, ServConfig):
            raise NotConfigured("a ServConfig from load_config() is required; SERV was not run")
        if live:
            raise LiveTransportNotImplemented("live mode cannot be enabled: this spike ships no live transport")
        self._config, self._transport = config, transport

    def interpret(self, model, obligation, modality, source_id, source_text):
        request = build_request(model, obligation, modality, source_id, source_text)
        if self._transport is None:
            raise LiveTransportNotImplemented("no live transport in this spike; no request was sent")
        response = self._transport(request, self._config)
        if not (isinstance(response, dict) and response.get("fixture") is True):
            raise ValueError("transport returned a response not labelled fixture: true")
        result = parse_interpretation(response, source_text)
        result["executed"] = False
        return result


def attach_advisory(audit, obligation_id, interpretation):
    """Return a copy of the audit with SERV's interpretation attached as advice only.

    Disposition, full_support, statements and completeness are copied unchanged: SERV cannot
    override a deterministic result, and a confirmed capability still needs a human edit to the catalog.
    """
    if audit["obligations"][obligation_id]["disposition"] != "uncertain":
        raise ValueError("SERV advisory is only attached to uncertain obligations")
    fixture, executed = interpretation.get("fixture"), interpretation.get("executed", False)
    if fixture is True and executed is True:
        raise ValueError("fixture and executed are mutually exclusive; refusing to label it")
    if executed is not False:
        raise ValueError("executed results are not accepted: this spike has no live transport "
                         "and a caller cannot attest live execution")
    if fixture is not True:
        raise ValueError("interpretation is neither fixture nor executed; refusing to label it")
    out = copy.deepcopy(audit)
    out.setdefault("serv_advisory", {})[obligation_id] = {
        "verdict": interpretation["verdict"], "quote": interpretation["quote"],
        "accepted": interpretation["accepted"], "reasons": list(interpretation["reasons"]),
        "human_confirmation_required": True,
    }
    out["serv"] = {"status": "fixture", "executed": False, "fixture": True}
    return out
