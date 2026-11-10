# Current OpenServ blockers — 2026-11-10

> **Status (10 Nov 2026, later): B1–B5 are fixed** on branch `fix/review-b1-b6`, test-first: `tests/test_review_round2.py` (46 tests), RED and GREEN logs in `docs/red/15_review_round2.*`. Each was first reproduced on `main` at `b2de604`. Two optional findings are fixed too: the "report that says nothing" (B6: an obligation the report never mentions is now a gap) and the negation part of the catalog-quote finding (B7: `tests/test_negation.py`, logs `docs/red/16_negation.*`). The other optional items are recorded in `docs/KNOWN_LIMITATIONS.md`.

Exact reviewed implementation commit: `dc11c60a6472a95da0275a438652229956b4890a`.

Conductor execution at this head: **378 passing tests**, with the missing-credential SERV path exiting 3 and making no request. Those green tests do not cover every newly identified boundary. A separate bounded independent source review returned **REQUEST_CHANGES** and reproduced the defects below from current code. Publication and submission remain blocked; no real SERV call occurred.

Defects to carry into the next authorized repair session:
1. A 5000-digit integer can raise plain ValueError in JSON loading, leading to a traceback/exit 1 rather than the intended input exit 2.
2. Integers in the 309–4300 digit range can raise OverflowError during finite-number/spec checking, again bypassing the intended input handling.
3. A lone-surrogate JSON escape in catalog source text can raise UnicodeEncodeError during source hashing; classify/reject it before that boundary rather than crash.
4. The SERV status block permits arbitrary status/extra keys and aliases the caller's mutable dict. Permit only known not-run/not-configured/unimplemented status states, rebuild a fresh dict and never label execution that was not actual transport.
5. `attach_advisory` still trusts caller-provided accepted/verdict fields without revalidating the quote against the obligation's own source. Require known verdict, own-source quote, computed acceptance and safe malformed-input errors.

The actual review below includes further optional test/UI/provenance caveats; they are not all production bugs. Do not upgrade this to a real tool or a valid sponsored entry from the static DESIGN MOCK. Actual account/key authorization, real signed-off tool specifications, live SERV behavior and privacy/public release remain unverified. The G2 mock's current routing was checked through a stub DOM, not a full browser replay.

## Raw independent source review

**Review of dc11c60: REQUEST_CHANGES.** I did not run anything. The source you supplied has no line numbers, so locations are given as file and function. The repair closes the earlier cases (deep nesting, bad UTF-8, `--out` failures). Three crash paths remain that still end in a traceback and exit 1, the same code as "gaps found". The SERV status and advisory labels are also still forgeable.

## Blocking

**B1. Large integer literal crashes the loader (exit 1, traceback).**
- Where: `inputs.py::_read` catches only `json.JSONDecodeError` and `RecursionError`.
- Repro: a case or catalog file `{"synthetic": true, "x": <5000 digits>}`. `json.loads` raises a plain `ValueError` ("Exceeds the limit (4300 digits)"), not a `JSONDecodeError`. It propagates out of `cli.main`.
- This is the same class of defect the repair targeted, and the tests don't cover it.
- Fix: after the `JSONDecodeError` handler, add `except ValueError as exc: raise InputError(...)`.

**B2. Integer of 309–4300 digits raises `OverflowError` (exit 1).**
- Where: `inputs.py::is_finite_number` calls `math.isfinite(int)`, which raises `OverflowError` for ints above about 1.8e308.
- `calls.py::_arg_reasons` only catches `(KeyError, TypeError)`. `_number_list_ok` evaluates `is_finite_number` before its own `try`, so its `OverflowError` guard around `fsum` never covers the int case.
- Repro 1 (case): a call arg for a `number` or `number_list` spec set to `10**400` written as digits.
- Repro 2 (catalog): `"min": <310-digit int>` in any spec. `inputs.py::_validate_spec` crashes at load instead of raising `InputError`.
- Fix: make `is_finite_number` return `True` for non-bool ints without `isfinite` (comparisons are exact), or catch `OverflowError` and return `False`.

**B3. Lone-surrogate escape in a source text crashes `entry_reasons` (exit 1).**
- Where: `catalog.py::entry_reasons` runs `source["text"].encode("utf-8")`.
- Repro: catalog `sources.SRC-SYN-A.text` = `"x\ud800"`. The file is valid UTF-8, but the JSON escape yields a lone surrogate, and `UnicodeEncodeError` escapes from `resolve_capability` or `validate_calls` through `build_audit`.
- `output_digest` is safe because `json.dumps` uses `ensure_ascii`.
- Fix: reject unencodable strings in `validate_catalog`, or encode with `"surrogatepass"` and let the hash mismatch fail closed.
- Hardening for B1–B3: add a final guard in `cli.main` so any unexpected exception from `build_audit` returns a code other than 1. Add real-process tests for all three inputs.

**B4. The SERV status block is forgeable and aliased.**
- Where: `audit.py::_check_serv_block` and `build_audit`.
- The block is checked only for `executed is False`, `fixture is False` and `status` being a string. Any status text and any extra keys pass.
- Repro: `build_audit(cat, case, serv={"status": "serv_confirmed", "executed": False, "fixture": False, "verdict": "supported"})` embeds all of it verbatim in `audit["serv"]`.
- The dict is also embedded by reference, not copied. A caller can set `blk["executed"] = True` after validation and the audit then claims execution.
- Fix: whitelist `status` to `{not_run, not_configured, live_transport_not_implemented}`, build a fresh three-key dict, and drop everything else.

**B5. `attach_advisory` has no provenance or content check.**
- Where: `serv.py::attach_advisory`.
- Repro: `attach_advisory(a, "OB-4", {"fixture": True, "executed": False, "verdict": "CONFIRMED", "quote": "x", "accepted": True, "reasons": []})` succeeds. The hand-built dict is attached with `accepted: True` and an arbitrary verdict and quote.
- It also never checks that the interpretation came from the obligation's own source. A result parsed against a different source can be attached to any uncertain obligation.
- A missing `verdict`, `quote` or `reasons` key, or an unknown `obligation_id`, raises `KeyError` instead of `ValueError`.
- Fix: whitelist the verdict against `VERDICTS`. Re-run the quote check against the obligation's catalog source text, taken from the catalog or passed in. Recompute `accepted` there instead of trusting the caller's value. Raise `ValueError` for missing keys.

## Optional (non-blocking)

- **Advisory quote relevance.** `parse_interpretation` accepts `supported` with the quote "engineering test only", and a test asserts this. The quote only needs to be 3+ words and 12+ characters. It need not mention the obligation's finding class or modality, so `accepted: True` overstates it. Require both terms in the quote for `supported` and `unsupported`.
- **Catalog quote floor.** `entry_reasons` doesn't apply `_meaningful_quote`. A catalog quote of just `"x y"` (modality plus finding term) can confirm. There is also no negation or exclusion check, for example "does NOT flag nodule-like findings on chest-xr".
- **Docstring overclaims.** `coverage.assess_obligations` says "no call or receipt is dropped". In fact:
  - Receipts for invalid or unconfirmed calls, such as RCPT-4 in the mock, and orphan receipts appear nowhere in the audit.
  - `audit["calls"]` is keyed by `call_id`, so duplicate call ids collapse to one entry. The per-obligation lists keep both.
- **Conflict detection.** `_conflicting_tools` compares valid receipts per `tool_id` only. Calls to the same tool with different args and legitimately different outputs are flagged as a conflict. This is fail-closed, but it can false-positive. Different confirmed tools on the same obligation are never compared.
- **`reconcile` trusts `kind`.** The statement `kind` label is accepted without reading the text. A statement labelled `discloses_not_assessed` whose text claims an assessment passes. This is inherent to the design, and the docs should say so.
- **Report that says nothing.** An empty `statements` list with every obligation fully supported yields `completeness: full_support`.

## Mock JS and HTML

The hash routing is correct:
- Clicks set `location.hash`, so `hashchange` runs `route()` once.
- Back and forward fire `hashchange`, including back to the no-hash entry, which shows the catalog.
- The ids are prefixed `step-`, so there is no native fragment jump.
- Unknown hashes fall back to the catalog.
- The `OUTCOME`, `ACTION`, `RECEIPT` and `LABEL` maps cover everything `reconcile.py` and `coverage.py` emit.

The mock text does not imply live SERV. The banner reads "DESIGN MOCK — NOT CONNECTED". The SERV button is disabled and labelled "not connected". The note says "No SERV response is shown or simulated". The full-support cell reads "yes (fixture)", and the export row shows `not_run`.

Minor, optional:
- The click handler leaves focus on a hidden element after navigating, so keyboard users lose their place.
- `scrollTo(0,0)` also runs on back/forward.
- Clicking the current step's nav tab with no hash pushes a redundant history entry.
- The tables are empty without JS, so the `<noscript>` rule only unhides empty sections.
- `data.receipts` is embedded but never rendered, and the per-call receipt relations (`obligations[*].calls`) are not shown, so the multi-call repair isn't visible in the mock.
- A test that the embedded audit matches the CLI output for `c07_combined` would back the "compare byte for byte" claim.

VERDICT: REQUEST_CHANGES