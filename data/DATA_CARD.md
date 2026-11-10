# Data card: synthetic fixtures

**Everything here is synthetic and fictional. No real patients, images, DICOM, devices or products.**
The catalog is an engineering stand-in for the mechanism spike. It does not describe any real device's intended use, and no public source validates it.

**Sign-off status: PENDING.** Physician/operator sign-off is pending for (a) what counts as an assessment obligation and (b) how a capability description maps to a finding class. Nothing in `data/` is presented as signed.

## Files

| File | What it is |
|---|---|
| `catalog.json` | Fictional catalog: 6 invented tools (`SYN-*`), each tied to an invented specification text in `sources` with a SHA-256 of that text. |
| `cases/c01..c07*.json` | One study with obligations, proposed calls, mock-tool receipts and a draft report each. |
| `expected/c01..c07*.json` | Expected audit outcomes, **hand-written before any validator code existed** (see git history: the data commit precedes the first `src/` commit). |
| `build_fixtures.py` | (Class `volume_like` was renamed `lung_volume_like` after review cycle 12 so its term matches; expected outcomes did not change.) Writes `catalog.json` and `cases/`. Static data and hashing only. Not seeded because nothing is random. |

## Fields

Catalog tool: `tool_id`, `finding_class`, `modality` (the catalog author's claimed mapping), `required_args`, `args_schema`, `source_id`, `quote` (must appear verbatim in the source text), `modality_term` and `finding_term`. A mapping is *confirmed* only if the quote is non-empty and verbatim in an unchanged source, both terms appear inside the quote, `modality_term` equals the entry's `modality`, and `finding_term` equals the entry's `finding_class` ignoring case, hyphens and underscores. Anything else is *not confirmed*, so the obligation is `uncertain`.

Argument schema (`args_schema`, required for every tool; `required_args` must all appear in it): a map from argument name to a spec. A call is `valid` only if every required argument is present, every supplied argument is in the schema (anything else is `unknown_arg:<name>`), and every value satisfies its spec (otherwise `arg_invalid:<name>`). Spec types:

| `type` | Required keys | A value is valid when |
|---|---|---|
| `study_id` | none | it is a non-empty string exactly equal to the case's `study.study_id` |
| `number` | `min`, `max` | it is a finite int or float (no `bool`, `NaN`, `Infinity`, string) with `min <= value <= max` |
| `number_list` | `max_items`, `item_min`, `item_max`, `max_total` | it is a non-empty list of at most `max_items` finite numbers, each within `[item_min, item_max]`, whose sum is finite and at most `max_total` |

Every shipped tool takes only `study_id`. The `number` and `number_list` types exist so numeric and list inputs cannot be modelled without bounds; they are exercised by test-only catalog tools in `tests/test_call_args.py`. Their bounds are **engineering limits chosen by the catalog author for a synthetic mock tool. They are not clinical thresholds and do not measure anything real.** A catalog whose spec is unbounded, non-finite, inverted or of an unknown type is refused at load.

Case: `study.modality`; `study.obligations[]` (`obligation_id`, `finding_class`: a placeholder label, not a clinical requirement); `proposed_calls[]` (`call_id`, `tool_id`, `obligation_id`, `args`); `receipts[]` (`receipt_id`, `call_id`, `tool_id`, `executor` = `mock-tool`, `fixture: true`, `status` ok|error, `output`, `output_sha256`); `draft_report.statements[]` (`kind` = `claims_assessed` | `discloses_not_assessed`, `cites_receipt`).

Digests: source `sha256` = SHA-256 of the UTF-8 text. Receipt `output_sha256` = SHA-256 of `json.dumps(output, sort_keys=True, separators=(",", ":"))`.

## Cases (each is chosen to force one outcome)

| Case | Forces | Expected disposition | Full support? |
|---|---|---|---|
| c01 | tool confirmed for this modality, called, valid receipt | supported_called | yes (fixture only) |
| c02 | tool confirmed, never called | supported_omitted | no |
| c03 | only tool is for another modality; a call to it is proposed | unsupported | no |
| c04 | source text omits the modality, so the mapping is not confirmed; a mock receipt exists | uncertain | no |
| c05 | called, no receipt | supported_called, receipt missing | no |
| c06 | called, mock execution returned an error | supported_called, receipt failed | no |
| c07 | all six obligations in one study | mixed | no |

## Determinism and limits

- Fixed files, no random generation, no per-visitor variation. Re-running gives byte-identical output.
- "Fully supported" here means only: a confirmed catalog entry, a valid call and a valid mock receipt. It says nothing about clinical accuracy, real tools or SERV.
- The draft-report texts are placeholders, not clinical wording.

## Licence

Fixtures are original text written for this repo (MIT, see `LICENSE`). Nothing was copied from FDA, vendor or paper text.
