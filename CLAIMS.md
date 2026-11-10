# Claims and where each one comes from

Every number or feature word used in the README, the replay page, the submission write-up and the post, with the file that holds it and the command that re-creates it. If a claim is not in this table, it should not be made.

| Claim | Used in | Source file | Re-create it |
|---|---|---|---|
| 120/120 broken reports flagged for the right reason, 0 passed as complete, 30/30 clean passed | README, replay page, JUDGES, write-up | `eval/results/adversarial_v1.json` | `python3 scripts/make_eval.py --check` (also run in CI) |
| 12 kinds of break × 10 cases, seed 20261110 | README, JUDGES, `eval/RESULTS.md` | `scripts/make_eval.py` (`BREAKS`, `SEED`) | read the script |
| The code before the 10 Nov fixes (`b2de604`) let 20/120 through: `source_negated` 10/10, `statement_dropped` 10/10 | JUDGES, `eval/RESULTS.md` | `eval/results/adversarial_v1_at_b2de604.json` | `git worktree add ../old b2de604 && python3 scripts/make_eval.py --src ../old/src --out /tmp/old.json` |
| Held-out SERV batch v2: `supported` on 8 of 16 non-covering specs; guard accepted 0 of them; 13/13 accepted answers matched; 24/24 stayed `uncertain`; `full_support` never set | README, replay page, JUDGES, write-up | `eval/results/serv_batch_v2.json` | `python3 scripts/serv_eval.py --rebuild` (re-scores the saved answers; sends nothing) |
| Batch v2 was committed before it was run | JUDGES, `eval/SERV_BATCH.md` | git: `e3db82d` adds the v2 wording and `4a16418` adds the results; `scripts/serv_eval.py` is identical in both. Outside witness: GitHub's activity log shows the branch created at `e3db82d` at 11:42:48 UTC. The batch results were written at 11:43 UTC (`run_at`, minute precision, set after the last request). The SERV console usage log holds the per-request times | `git diff e3db82d 4a16418 -- scripts/serv_eval.py` (empty); `gh api repos/DrAhmed7887/hack-openserv-serv/activity` |
| Batch v1: over-reach 7 of 16; each correct `supported` quote named chest-xr, none of the 7 over-reaching ones did | JUDGES, `eval/SERV_BATCH.md`, PR #4 | `eval/results/serv_batch_v1.json` | `python3 scripts/serv_eval.py --rebuild` |
| 50 live SERV requests on `gpt-6-luna`, 10 Nov 2026 (2 + 24 + 24) | JUDGES | `docs/serv_run/*.json`, `eval/results/serv_batch_v*.json` (`requests`, `run_at`) | live re-runs cost SERV credits: `scripts/serv_live_run.py`, `scripts/serv_eval.py --batch` |
| Case c07: 1 of 6 required assessments fully supported; the report claims 4 and discloses 1 limit | replay page, workflow diagram | the audit of `data/cases/c07_combined.json` | the run command in the README |
| Recorded SERV answer for c07 is not accepted under the current rules (`quote_does_not_name_modality`) | replay page, `docs/SERV_RUN.md` | `scripts/build_mock.py` (`recorded_serv`) | `python3 scripts/build_mock.py` (CI checks the page is in sync) |
| Deterministic, byte-identical output | README, JUDGES | `tests/test_audit.py::test_audit_is_byte_identical_across_runs` | `python3 -m pytest -q` |
| Exit codes 0, 1, 2, 3, 4, 5, 6 and what each means | README, JUDGES | `src/contract_audit/cli.py` | `tests/test_cli.py`, `tests/test_review_round2.py`, CI step "exit codes are distinct" |
| Over 500 tests, Python 3.9 and 3.12 | README (exact count), JUDGES | `.github/workflows/ci.yml` | `python3 -m pytest -q`; `docs/G1_RESULTS.md` records the last full run |
| "SERV's answer is advice; it never changes the result" | everywhere | `src/contract_audit/serv.py` (`attach_advisory` copies dispositions unchanged) | `tests/test_serv_advisory.py`, `tests/test_serv_quote_relevance.py::test_the_rule_never_changes_the_deterministic_result`, and the `guard` rows of the batch JSONs |
| No images, no DICOM, no patients; fictional catalog | everywhere | `data/DATA_CARD.md`; inputs not marked synthetic are refused (`src/contract_audit/inputs.py`) | `tests/test_audit_synthetic_gate.py` |
| All 50 live SERV answers were finished and schema-valid | `docs/SERV_INTEGRATION.md` | `docs/serv_run/*.json`, `eval/results/serv_batch_v*.json` (no `malformed_response`, `content_not_json`, `verdict_not_allowed` or `finish_reason_not_stop`) | read the JSON |
| Token counts per batch | `eval/SERV_BATCH.md` | `tokens` in `eval/results/serv_batch_v*.json`, summed from the `usage` that SERV returned | `python3 scripts/serv_eval.py --rebuild` |
| "About $0.0002" for the first run, and the per-million prices | `docs/SERV_RUN.md` | An estimate: tokens × the price on the SERV models page. The console usage page is the authority | — |
| Backlog hours | JUDGES | Estimates by the builder, not measurements | — |
| arXiv 2611.09836, submitted 6 Nov 2026; motivation only | README, `docs/EVIDENCE_SUMMARY.md` | the arXiv abstract page (row P1 to P3 there) | open the link |
| Replay page works at phone and laptop width | JUDGES | `docs/g2/*.png`, rendered at 390×844 and 1280×900 with Playwright; no horizontal scroll and no console error on 10 Nov | open the page at 390 px |
| Reproducing every number takes under a minute | JUDGES | Measured on 10 Nov: a fresh `git clone` plus the three commands in JUDGES took 2 s, and `--rebuild` changed 0 files | the commands in JUDGES |

Not claimed anywhere: clinical accuracy, performance on real tools or real reports, SERV accuracy in general, any time or money saved.
