# Radiology tool-capability contract audit

> **Status: G1 mechanism spike plus a G2 design mock. Not a clinical product.** Synthetic data only. SERV Reasoning has **not been run**: no account, no key, no call. Product name not yet chosen (neutral descriptor used).

An engineer wires specialist tools into a reporting agent and gets a report that looks complete. This audit asks why it looks complete. It separates four situations per required assessment:

| Disposition | Meaning |
|---|---|
| `supported_called` | A confirmed catalog entry exists and a valid call was proposed |
| `supported_omitted` | A confirmed entry exists, but no valid call covers it |
| `unsupported` | No catalog entry covers this modality and finding class (never substituted) |
| `uncertain` | An entry exists but its source link does not confirm the mapping |

It then validates the proposed calls, checks each execution receipt, and reconciles the draft report against those receipts. **Full support requires a confirmed mapping, a valid call and a valid receipt.** Nothing else can set it.

Why this shape: the motivating arXiv paper ([2611.09836](https://arxiv.org/abs/2611.09836v1), submitted 6 Nov 2026) separates tools that do not exist from tools that existed and were not called. The paper does not validate this repo's catalog, and no figure from it is used here. See `docs/EVIDENCE_SUMMARY.md`.

## Run it (offline, Python 3.9+, no dependencies)

```bash
# one case, structured audit JSON on stdout (deterministic, byte-identical across runs)
PYTHONPATH=src python3 -m contract_audit audit \
  --catalog data/catalog.json --case data/cases/c07_combined.json

# exit 1 unless completeness is full_support
PYTHONPATH=src python3 -m contract_audit audit \
  --catalog data/catalog.json --case data/cases/c01_supported_called.json --fail-on-gaps
```

Exit codes: `0` audit produced, `1` gaps found (only with `--fail-on-gaps`), `2` bad or non-synthetic input, `3` `--serv` without credentials, `4` `--serv` with credentials but no live transport. Inputs not marked `"synthetic": true` are refused.

## Test it

```bash
python3 -m pip install -r requirements-dev.txt   # pytest only
python3 -m pytest -q                              # 148 tests, offline
python3 scripts/make_g1_results.py                # re-runs everything, rewrites docs/G1_RESULTS.md
python3 scripts/build_mock.py                     # re-embeds fixture output in mock/index.html
```

Measured results and the RED-before-GREEN logs: `docs/G1_RESULTS.md`, `docs/red/`.

## What is here

| Path | What |
|---|---|
| `src/contract_audit/` | Validator: catalog, calls, receipts, coverage, report reconciliation, audit, CLI, SERV boundary |
| `data/` | Fictional catalog, 7 fixed synthetic cases, hand-written expected outcomes, `DATA_CARD.md` |
| `docs/USER_FLOW.md`, `mock/index.html` | G2 flow and a static **DESIGN MOCK — NOT CONNECTED** (open the file in a browser) |
| `docs/SERV_INTEGRATION.md` | Documented SERV interface, the boundary, what is unverified |
| `docs/G1_RESULTS.md` | Actual test log and case table |

## Known boundaries (read these)

- **SERV is unverified and unrun.** The request builder follows the public docs read on 2026-11-10. There is no live transport. Credentials absent: fail closed. Credentials present: still no call. The audit never prints a "SERV result" or a SERV step trace, because none was produced.
- **Fixtures are not evidence about real tools.** The catalog is fictional (`SYN-*`), its source texts are invented, and no public source validates the mapping. Passing fixture tests prove the mechanism, not clinical accuracy and not SERV performance.
- **Physician/operator sign-off is pending** for what counts as an assessment obligation and for any capability interpretation. No clinical rule here is signed.
- **Receipts are mock-tool receipts**: a digest check detects edited output, not a forged receipt.
- **Capability matching is a deliberate strict string rule** (non-empty quote verbatim in an unchanged source, naming the entry's own modality and finding class). It will say `uncertain` for wording a human would accept. That is the safe direction; interpreting such cases is the job reserved for an authenticated SERV step, advisory only.
- No images, DICOM, diagnosis or real patient data anywhere.
- Report repair is a proposed action label per statement. No report text is generated.

## Licence

MIT, see `LICENSE`. Repository is private until the owner decides otherwise.
