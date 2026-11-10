# For the judges

**OpenServ SERV Hackathon 02, Open Track.** Rules read on the official page, openserv.ai/hackathon-2, on 10 Nov 2026.

## Try it in 30 seconds

- **Replay page, no install, no keys:** https://drahmed7887.github.io/hack-openserv-serv/ (the same file is `mock/index.html`). It shows the validator's real output for one synthetic case and the live SERV answer recorded for it.
- **Reproduce every number** (Python 3.9+, standard library only, no keys, under a minute):

```bash
git clone https://github.com/DrAhmed7887/hack-openserv-serv && cd hack-openserv-serv
PYTHONPATH=src python3 -m contract_audit audit --catalog data/catalog.json --case data/cases/c07_combined.json
python3 scripts/make_eval.py --check      # the seeded adversarial eval, byte for byte
python3 scripts/serv_eval.py --rebuild    # re-scores the recorded SERV answers; sends nothing
```

## Who it is for

An engineer wiring specialist tools into a radiology reporting agent. The agent's draft reads as finished, and the engineer cannot see whether a tool was skipped, whether no tool exists for that study type, or whether a tool's documentation never confirmed it. Releasing that draft means reports that claim assessments no tool performed. The audit answers that question per assessment, before release.

## Criteria, word for word, and the evidence

| Criterion | Evidence | Where |
|---|---|---|
| "SERV Reasoning must be part of your build." | When the deterministic rule can only say `uncertain`, `--serv` sends the tool's source text to SERV Reasoning (OpenServ inference API, chat completions with a strict JSON schema). The answer is attached as advice; a person confirms it. 50 live requests on `gpt-6-luna` on 10 Nov 2026: 2 on the fixtures, 48 in two batches. | `src/contract_audit/serv.py` (`build_request`, `LiveServClient`, `attach_advisory`), `docs/SERV_RUN.md`, `eval/SERV_BATCH.md` |
| "creativity" | It separates four reasons a draft can look complete (`supported_called`, `supported_omitted`, `unsupported`, `uncertain`) and checks each claim against an execution receipt. It also measures the model it relies on: SERV's over-reaching answers were well-formed and verbatim, so "verbatim" was not enough. The rule that followed (a `supported` quote must name the study type) was fixed before a held-out batch, which then confirmed it. | `src/contract_audit/coverage.py`, `reconcile.py`, `eval/SERV_BATCH.md` |
| "user readiness" | One offline command; deterministic, byte-identical output; exit codes made for CI (0 ok, 1 gaps found, 2 bad input, 3 to 5 SERV states, 6 internal error). Over 500 tests on Python 3.9 and 3.12 in CI, plus the seeded eval re-run in CI. The replay page works at phone and laptop width. | `README.md`, `.github/workflows/ci.yml`, `eval/RESULTS.md`, `mock/index.html` |
| "revenue potential" | The check a team would run on every agent release, the way a test suite runs on every merge. The lasting value is the catalog of tool contracts, each tied to the exact words of its source. A possible model is a per-pipeline CI check. Nothing is offered for sale here. | `docs/USER_FLOW.md` |

**Required items:** a public code repository (this one), a demo link (the replay page above), a short write-up (in the submission form: what it does, how it uses SERV Reasoning, the track) and an X post linked in the form.

## Headline numbers

All are synthetic and reproducible. Each one is traced to a file and a command in [CLAIMS.md](CLAIMS.md).
- **Seeded adversarial eval:** 120 broken reports that each look complete, 12 kinds of break × 10. **120/120 flagged for the right reason, 0 passed as complete; 30/30 clean reports passed.** The code from before the 10 Nov fixes let 20/120 through.
- **SERV, held-out live batch v2 (24 specs):** SERV said `supported` on 8 of 16 specs that do not establish chest-xr coverage. The guard accepted **0** of those 8. All 13 answers it accepted matched the designed answer. The deterministic result stayed `uncertain` in 24/24 cases, and `full_support` was never set.

## Open items (dated backlog)

Every review finding not yet fixed, with hours. Fixed findings are in `docs/BLOCKER_REVIEW_2026-11-10.md` and the PR history.

| Added | Item | Hours | Status |
|---|---|---|---|
| 10 Nov | Physician/operator sign-off on the assessment obligations (what a report must address) | 0.2 | open |
| 10 Nov | SERV wrapped 2 of 24 quotes in quotation marks, so 2 correct answers were held back. A narrow normalisation would accept them; it needs a fresh held-out batch | 1 | open |
| 10 Nov | The 3-word quote floor rejected a correct 2-word exclusion quote ("excluding chest-xr") | 0.5 | open (with the row above) |
| 10 Nov | A negation that comes after the quote ("X, but not on portable films") is not caught | 1 | open (`docs/KNOWN_LIMITATIONS.md`) |
| 10 Nov | Real tool documentation instead of the fictional catalog | — | out of scope for the hackathon |
| 10 Nov | A 2-minute demo video (the rules accept a demo link instead) | 1.5 to 2 | open |
