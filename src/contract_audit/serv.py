"""Explicit SERV Reasoning boundary.

Interface facts come from the public docs read on 2026-11-10 (see docs/SERV_INTEGRATION.md).
Missing credentials fail closed: no SERV output is ever produced without a configured key.
Only LiveServClient sends a request; ServClient stays fixture-only. A SERV answer is advice:
it never changes a disposition or full_support.
"""
from __future__ import annotations

import copy
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from .catalog import catalog_digest

ENDPOINT = "https://inference-api.openserv.ai/v1/chat/completions"
TIMEOUT_SECONDS = 30
MAX_RESPONSE_BYTES = 1_000_000

# Module-private provenance marker. Only LiveServClient sets it, and it does not survive a copy through
# JSON, so a caller cannot attest live execution by writing "executed": true into a dict.
_LIVE_TOKEN = object()

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
    """ServClient ships no live HTTP transport (use LiveServClient). No call was made."""


class ServCallFailed(RuntimeError):
    """A live SERV request failed. Carries the HTTP status when there is one; never the key."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def _allowed_url(url):
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in ("127.0.0.1", "::1"))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect: urllib would resend the Authorization header to the new host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
MAX_ERROR_CHARS = 200


def _clean(text, headers):
    """Redact the bearer key, strip control characters and cap length: upstream text is untrusted."""
    text = str(text)
    auth = headers.get("Authorization", "")
    key = auth[7:] if auth.startswith("Bearer ") else ""
    if key:
        text = text.replace(key, "<redacted>")
    text = _CONTROL.sub("", text)
    return text if len(text) <= MAX_ERROR_CHARS else text[:MAX_ERROR_CHARS] + "..."


def urllib_post(url, headers, body, timeout):
    """POST JSON with the standard library and return the parsed JSON object.

    https only (plain http is allowed for loopback, which the tests use). Errors carry the status and the
    upstream error type, never the request headers.
    """
    if not _allowed_url(url):
        raise ServCallFailed("refusing to send: SERV requests must use https")
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with _OPENER.open(req, timeout=timeout) as resp:  # scheme checked above; redirects refused
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            err = json.loads(exc.read(10_000) or b"{}").get("error", {})
            detail = ": " + _clean(f"{err.get('type', '')} {err.get('message', '')}".strip(), headers)
        except (ValueError, AttributeError, RecursionError, OSError, http.client.HTTPException):
            pass  # the status alone is reported when the error body is unreadable (e.g. connection reset)
        raise ServCallFailed(f"HTTP {exc.code} from SERV{detail}", status=exc.code) from None
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as exc:
        raise ServCallFailed("SERV request did not complete: "
                             + _clean(getattr(exc, "reason", exc), headers)) from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ServCallFailed("SERV response larger than the 1 MB limit")
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError):
        raise ServCallFailed("SERV response is not JSON") from None
    if not isinstance(data, dict):
        raise ServCallFailed("SERV response is not a JSON object")
    return data


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


class LiveServClient:
    """Sends one chat-completions request per interpretation. The HTTP function is injected for tests.

    The key is added to the Authorization header at send time and never stored in the request body or
    the result. A response labelled "fixture" is refused: a live call must come back as a live answer.
    """

    def __init__(self, config, http=urllib_post, timeout=TIMEOUT_SECONDS):
        if not isinstance(config, ServConfig):
            raise NotConfigured("a ServConfig from load_config() is required; SERV was not run")
        self._config, self._http, self._timeout = config, http, timeout

    def __repr__(self):
        return "LiveServClient(config=<hidden>)"

    __str__ = __repr__

    def interpret(self, model, obligation, modality, source_id, source_text):
        request = build_request(model, obligation, modality, source_id, source_text)
        headers = {"Authorization": f"Bearer {self._config.api_key}", "Content-Type": "application/json"}
        response = self._http(request["url"], headers, request["body"], self._timeout)
        if not isinstance(response, dict) or "fixture" in response:
            raise ServCallFailed("live SERV response carried a fixture label or was not an object; refused")
        result = parse_interpretation(response, source_text)
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        result.update(executed=True, fixture=False, live_token=_LIVE_TOKEN,
                      model=str(response.get("model") or model),
                      usage={k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                             if isinstance(usage.get(k), int)})
        return result


def _own_source_text(audit, obligation_id, catalog):
    """The obligation and the catalog source text of its own tool. Raises ValueError, never KeyError."""
    obligations = audit.get("obligations") if isinstance(audit, dict) else None
    if not isinstance(obligations, dict) or obligation_id not in obligations:
        raise ValueError(f"unknown obligation {obligation_id!r} in this audit")
    if not isinstance(catalog, dict) or catalog.get("catalog_id") != audit.get("catalog_id"):
        raise ValueError("the catalog must be the one this audit was built from (catalog_id differs)")
    try:
        same = catalog_digest(catalog) == audit.get("catalog_sha256")
    except (TypeError, ValueError, RecursionError):
        same = False
    if not same:
        raise ValueError("the catalog must be the one this audit was built from (catalog_sha256 differs)")
    ob = obligations[obligation_id]
    try:
        tool = next(t for t in catalog["tools"] if t["tool_id"] == ob["tool_id"])
        return ob, catalog["sources"][tool["source_id"]]["text"]
    except (KeyError, TypeError, StopIteration):
        raise ValueError(f"no catalog source text for the tool of {obligation_id!r}") from None


def _recheck(interpretation, source_text, modality):
    """Re-derive acceptance from verdict and quote against the obligation's own source.

    A caller can only make acceptance stricter (its reasons are kept), never looser. A 'supported' quote must
    also name the study's modality: the general capability sentence is verbatim in a spec that never settles
    the study type, so quoting it proves nothing (live batch v1, eval/SERV_BATCH.md).
    """
    try:
        verdict, quote, reasons = interpretation["verdict"], interpretation["quote"], interpretation["reasons"]
    except (KeyError, TypeError):
        raise ValueError("an interpretation must carry verdict, quote and reasons") from None
    if verdict is not None and verdict not in VERDICTS:
        raise ValueError(f"verdict not allowed: expected one of {VERDICTS} or none")
    if quote is not None and not isinstance(quote, str):
        raise ValueError("quote must be a string or none")
    if not isinstance(reasons, list) or not all(isinstance(r, str) for r in reasons):
        raise ValueError("reasons must be a list of strings")
    own = []
    if verdict is None:
        own.append("no_verdict")
    elif verdict in ("supported", "unsupported"):
        if not isinstance(quote, str) or not _meaningful_quote(quote):
            own.append("quote_too_short")
        elif quote not in source_text:
            own.append("quote_not_in_source")
        elif verdict == "supported" and modality not in quote:
            own.append("quote_does_not_name_modality")
    return verdict, quote, list(dict.fromkeys([*reasons, *own]))


def attach_advisory(audit, obligation_id, interpretation, catalog):
    """Return a copy of the audit with SERV's interpretation attached as advice only.

    Disposition, full_support, statements and completeness are copied unchanged: SERV cannot
    override a deterministic result, and a confirmed capability still needs a human edit to the catalog.
    Executed results are accepted only straight from LiveServClient (module-private provenance marker).
    Acceptance is recomputed here against the obligation's own catalog source, never taken from the caller.
    """
    ob, source_text = _own_source_text(audit, obligation_id, catalog)
    if ob["disposition"] != "uncertain":
        raise ValueError("SERV advisory is only attached to uncertain obligations")
    if not isinstance(interpretation, dict):
        raise ValueError("interpretation must be a dict from parse_interpretation or LiveServClient")
    fixture, executed = interpretation.get("fixture"), interpretation.get("executed", False)
    if fixture is True and executed is True:
        raise ValueError("fixture and executed are mutually exclusive; refusing to label it")
    live = executed is True and fixture is False and interpretation.get("live_token") is _LIVE_TOKEN
    if executed is not False and not live:
        raise ValueError("executed results are accepted only from LiveServClient: no live transport token, "
                         "and a caller cannot attest live execution")
    if not live and fixture is not True:
        raise ValueError("interpretation is neither fixture nor executed; refusing to label it")
    modality = (audit.get("study") or {}).get("modality")
    if not isinstance(modality, str) or not modality:
        raise ValueError("the audit has no study modality to check the quote against")
    verdict, quote, reasons = _recheck(interpretation, source_text, modality)
    out = copy.deepcopy(audit)
    advisory = {
        "verdict": verdict, "quote": quote, "accepted": not reasons, "reasons": reasons,
        "human_confirmation_required": True,
    }
    if live:
        advisory["usage"] = dict(interpretation.get("usage", {}))
        out["serv"] = {"status": "executed", "executed": True, "fixture": False,
                       "model": interpretation["model"]}
    else:
        out["serv"] = {"status": "fixture", "executed": False, "fixture": True}
    out.setdefault("serv_advisory", {})[obligation_id] = advisory
    return out
