# Known limitations and evidence caveats

Status: synthetic G1/G2 precursor. Blocked for live SERV compliance. SERV has not been run: no account, no key, no call.

## What the validator does not do

- **Fixtures are not evidence about real tools.** The catalog is fictional, its sources are invented, and nothing was checked against a public source. Physician/operator sign-off is **pending**.
- **Argument bounds are engineering limits, not clinical ones.** `args_schema` bounds (`min`, `max`, `max_total`, ...) are values a catalog author picks for a synthetic mock tool. Passing them says the call is well-formed, not that the value is right for any patient or device. The shipped catalog models only `study_id`; numeric and list arguments are exercised by test-only tools.
- **Receipts detect edits, not forgery.** The digest is not a signature. Receipt output content is not interpreted, and a receipt whose `call_id` matches no valid call is ignored (not reported).
- **Capability matching is a strict string rule** and report text is not inspected.
- **Conflicting outputs are detected only by digest.** Two valid receipts from the same tool for one obligation with different digests block full support (`conflicting_outputs`); receipts from different tools are not compared.
- **The SERV quote floor is a minimum, not a semantic check.** A 3-word, 12-character verbatim stretch of the source is accepted as a quote; a human still confirms every advisory. There is no live transport and none was added.
- **Exit codes.** `2` covers unreadable or malformed input files, a malformed catalog, and an unwritable `--out`. An unexpected internal error is still an uncaught Python exception (exit 1 with a traceback). That is not expected from any input tested here, but it is not guarded by a catch-all, on purpose: a catch-all would hide bugs.

## Evidence caveats for review round 2 (cycles `13a` to `13n`, `docs/red/`)

- RED logs are real runs saved before the change. Where a first run was not a clean demonstration, the file is kept and named for what it is: `13f_...GREEN-attempt1.FAILED.log`, `13m_...GREEN-attempt1.FAILED.log`, `13n_...RED-attempt0.IMPORT-ERROR.log`. Nothing failing was overwritten with a passing log, except that re-recorded RED runs replaced earlier RED runs of the same test file after the test itself was corrected (13a: scan scope; 13b: one test now fails for its own reason instead of a fixture KeyError).
- `13a`: `scripts/scrub_paths.py` and the `tdd_step.sh` hook were written before the RED run (tooling, not production behaviour), so its unit test passed on first run; the hygiene scan was the RED test. The scrub of `12_review_findings.RED.log` is redaction only (10 temp-path lines).
- `13d`: the invalid-value cases already passed before the change because unknown spec types fail closed; the in-bounds cases were the RED.
- `13e`: the sum-overflow guard in `number_list` was written after seeing `math.fsum` raise `OverflowError` in a scratch run, and its test `test_sum_that_overflows_is_invalid_even_with_huge_bounds` was added afterwards, not RED-first. It was checked by mutation: with the guard neutralised the test fails. No log was saved for that check.
- `13m`: the saved RED log is from the first version of the test file; the sample quotes were then corrected (some were not substrings of the source) and GREEN recorded on the corrected file. The corrected file was not re-run against the pre-change code.
- `13n`: the routing and label behaviour is checked by running the mock's real script in node against a stub DOM (`tests/mock_harness.js`); those tests skip if node is absent. A stub DOM is not a browser, so real-browser back/forward behaviour was not checked. Two declaration constants (`OUTCOMES`, `ACTIONS`) were added to `reconcile.py` before the RED run so the failure shows the behaviour rather than an ImportError.
- **Hand-synthesised parts.** The mock's HTML and JavaScript are written by hand; only the embedded data block is generated (`scripts/build_mock.py`). The brief mentions "one handheld synthesis after industrialising a virtual engine"; I could not map that phrase to a specific item in this repo, so no caveat is attributed to it here.
- Review round 2 also found that the previous multi-call behaviour was **fail-open**, not only a misreport: a second valid call with no receipt still gave `full_support: true` because only the first valid call was checked.
