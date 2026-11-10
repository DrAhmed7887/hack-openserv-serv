# SERV integration boundary

**Status: live transport built, tested offline (injected HTTP plus a loopback server), and run against SERV on 10 Nov 2026** (`gpt-6-luna`, the two fixture cases with an uncertain obligation). What came back, and why the deterministic result stood: `docs/SERV_RUN.md`. Evidence rows are in the private research pack; public-doc facts are summarised in `docs/EVIDENCE_SUMMARY.md`.

## Interface, as documented publicly (read 2026-11-10, no sign-in)

| Item | Documented fact | Source page |
|---|---|---|
| Endpoint used here | `POST https://inference-api.openserv.ai/v1/chat/completions` (OpenAI chat-completions format) | docs.openserv.ai/serv-reasoning/api/chat-completions.md |
| Auth | `Authorization: Bearer $SERV_API_KEY` | docs.openserv.ai/serv-reasoning/api/index.md |
| Required in the body | `model`, and `messages` that include a system or developer message (a missing system prompt returns 400) | same |
| Structured output | `response_format` with `type: "json_schema"`, shown in a tutorial; the API reference does not list it | docs.openserv.ai/serv-reasoning/tutorials/structured-outputs.md |
| Tools | Application tools are executed by the client, not by SERV | docs.openserv.ai/serv-reasoning/tutorials/tools.md |
| Response | Plain OpenAI shape (`choices[].message.content`, `finish_reason`, `usage`). **No SERV step-trace field is documented.** | chat-completions.md |
| Cost | Calls consume credits; the key page mentions no free allowance | docs.openserv.ai/serv-reasoning/tutorials/credits-and-api-keys.md |

Consequences: the audit's own step record is produced by this repo's code and labelled so; the repo never prints a SERV step trace; the model id is a caller argument because none is chosen here.

## What the code does (`src/contract_audit/serv.py`)

| Piece | Behaviour | Tested in |
|---|---|---|
| `load_config(environ)` | No `SERV_API_KEY`, or a blank one: raises `NotConfigured` ("SERV was not run"). The key is never shown by `repr` or `str`. | `tests/test_serv_boundary.py` |
| `build_request(...)` | Builds, never sends, a chat-completions body: system message first, strict JSON schema with a closed verdict enum (`supported`, `unsupported`, `uncertain`), the source text embedded. No credential inside. A blank, whitespace-only or non-string `model` is an error. | `tests/test_serv_boundary.py`, `tests/test_serv_hardening.py` |
| `parse_interpretation(...)` | Accepts only: `finish_reason == "stop"`, valid JSON, verdict in the enum, and for `supported`/`unsupported` a quote that appears verbatim in the source text **and** meets a minimal floor (at least 3 words and 12 characters, so `"a"` or `"the"` cannot pass; reason `quote_too_short`). The floor is an engineering minimum, not a semantic check. Anything else is `accepted: false` with reasons. | `tests/test_serv_advisory.py`, `tests/test_serv_hardening.py` |
| `ServClient` | Has **no default transport**. Without one it raises `LiveTransportNotImplemented`. `live=True` is refused (after the credential check): a caller cannot switch live mode on. Any transport may only return responses labelled `"fixture": true`, and `interpret` always reports `executed: false`. | `tests/test_serv_advisory.py`, `tests/test_serv_hardening.py` |
| `attach_advisory(audit, obligation_id, interpretation, catalog)` | Returns a copy of the audit with the interpretation attached as advice. Acceptance is recomputed here against the obligation's own catalog source, never taken from the caller: the verdict must be one of the schema's three (or none), a `supported`/`unsupported` quote must be meaningful and verbatim in that source, and the caller's reasons can only make it stricter. The catalog must be the one the audit was built from; an unknown obligation or a missing key is a `ValueError`. Disposition, `full_support`, statements and completeness are unchanged, and `human_confirmation_required` is true. Only valid for `uncertain` obligations. Labels are mutually exclusive and caller-forged live execution is refused: `fixture` must be exactly `true` and `executed` exactly `false` (or absent); `{fixture: true, executed: true}`, `executed: true`, neither label, or non-boolean labels raise `ValueError`. The audit block always reads `fixture`. | same |
| `build_audit(..., serv=...)` | Accepts only a not-run status block (`executed` false, `fixture` false). A block claiming execution, or a malformed one, raises `ValueError`. | `tests/test_serv_hardening.py` |

## CLI behaviour with `--serv`

| Situation | Result |
|---|---|
| No key | Exit 3. Audit JSON still printed with `serv.status = "not_configured"`, `executed = false`. Stderr: "SERV was not run". |
| Key present, no `--serv-model` | Exit 4, `serv.status = "model_not_chosen"`, `executed = false`. Nothing is sent; the model is never guessed. |
| Key and `--serv-model` | One HTTPS request per **uncertain** obligation via `LiveServClient`. Each answer is attached as `serv_advisory` (human confirmation required); `serv = {status: executed, executed: true, fixture: false, model}`. Disposition, `full_support` and completeness are unchanged. Exit code as without `--serv` (0, or 1 with `--fail-on-gaps`). |
| Request fails (HTTP error, timeout, non-JSON, response labelled fixture) | Exit 5, `serv.status = "call_failed"`, the plain audit is still printed, stderr carries the HTTP status and upstream error type. The key is never printed. |
| Neither | Default `serv.status = "not_run"`. |

The words "SERV result" and any step trace never appear in output.

## Live transport (`LiveServClient`, `urllib_post`)

- Standard library only (`urllib`), 30 s timeout, 1 MB response cap, https only (plain http only for 127.0.0.1 in tests).
- The key is added to the `Authorization` header at send time; it is not in the request body, the result, `repr` or any error message.
- A live response carrying a `fixture` label is refused.
- The same `parse_interpretation` rules apply: strict verdict enum, quote verbatim in the source and above the length floor.
- Usage tokens from the response are kept in the advisory; cost is read from the SERV console.
- Run it on the fixture set: `SERV_API_KEY="$(security find-generic-password -s SERV_API_KEY -w)" python3 scripts/serv_live_run.py --model gpt-6-luna`.

## Fixture responses

Tests build chat-completion-shaped dicts with `"fixture": true` and `finish_reason: "stop"`. The resulting audit block reads `serv: {status: "fixture", executed: false, fixture: true}`. A passing fixture test shows the parser and the guard work. It says nothing about what SERV returns.

## Invariants (each has a test)

1. No SERV output can set or raise `full_support`.
2. A SERV quote that is not verbatim in the source is rejected.
3. Missing credentials fail closed with a non-zero exit and an explicit "not run" status.
4. `ServClient` (fixtures) cannot return an unlabelled response. Only `LiveServClient` can produce an executed result, marked with a module-private provenance object that does not survive copying, so no caller can label a result as live-executed by writing `executed: true`.
5. A quote that is a trivial substring of the source is not accepted as verbatim support.

## Not done, and who unblocks it

| Item | Needs |
|---|---|
| Real request/response check, including whether the model honours `response_format` | OpenServ account and API key (Ahmed) |
| Whether authenticated calls are free to a participant | Ahmed reading the console balance; the docs show no free allowance |
| A live HTTP transport | Written only after the two items above, with its own tests; explicit go from Ahmed |
| SERV-drafted report repair text | Same, plus physician/operator sign-off on wording rules |
| Whether `serv_shadow_agent` could validate a drafted report | Not testable offline: its pass/revise outcome is shown in a console report, not in the response, so it could not be audit evidence anyway |
