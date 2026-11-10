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
| `build_fixtures.py` | Writes `catalog.json` and `cases/`. Static data and hashing only. Not seeded because nothing is random. |

## Fields

Catalog tool: `tool_id`, `finding_class`, `modality` (the catalog author's claimed mapping), `required_args`, `source_id`, `quote` (must appear verbatim in the source text), `modality_term` and `finding_term` (must both appear inside `quote`, otherwise the mapping is *not confirmed*).

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
