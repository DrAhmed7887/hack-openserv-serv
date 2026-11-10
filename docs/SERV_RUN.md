# SERV Reasoning live run

Run 2026-11-10 10:47 UTC with model `gpt-6-luna` via `scripts/serv_live_run.py`. Raw audits with the advisory attached: `docs/serv_run/`.

SERV's answer is advice for a human: it never changes the disposition, `full_support` or completeness. A quote is accepted only if it appears verbatim in the tool's source text.

| Case | Obligation | Deterministic disposition | SERV verdict | Accepted | Quote | Tokens in / out |
|---|---|---|---|---|---|---|
| c04_uncertain_source_insufficient | OB-4 | uncertain | supported | yes | "Tool SYN-CARDIAC-1 is specified to measure cardiac size on radiographs." | 503 / 78 |
| c07_combined | OB-4 | uncertain | supported | yes | "measure cardiac size on radiographs" | 503 / 90 |

Cost: read it from the SERV console usage page (prices per model are in the SERV models docs).
## What this run shows (read by the builder, 10 Nov 2026)

- **SERV ran and returned schema-valid answers** both times: verdict `supported`, with a quote that is verbatim in source SRC-SYN-D, so the parser accepted the format (`accepted: yes` means "well-formed and verbatim", not "correct").
- **The verdict over-reaches.** The same source goes on: "Supported study types are listed in a separate document that is not included here." It never names chest-xr. The deterministic rule therefore keeps OB-4 `uncertain`, and that is the right call on this text.
- **The guard held.** In both audits OB-4 stays `uncertain`, `full_support` stays false and completeness stays `gaps_found`. The advisory is attached with `human_confirmation_required: true`. This is the case the advisory-only design exists for: a plausible, well-quoted model answer that a human must check before anyone edits the catalog.
- **Cost:** 1,006 input + 168 output tokens in total. At the SERV models page price for `gpt-6-luna` ($0.13 / $0.65 per million) that is about $0.0002; the console balance is the real figure.
- Two cases, one obligation, one model: this says nothing about SERV's accuracy in general.

- **Under the rules since 10 Nov (PR #4)** this answer is **not accepted**: a `supported` quote must name the study type, and "measure cardiac size on radiographs" does not name chest-xr. The rule came from the larger live batches in `eval/SERV_BATCH.md`, where it was checked on held-out wording.

(This section is written by hand; `scripts/serv_live_run.py` regenerates the table above it.)
