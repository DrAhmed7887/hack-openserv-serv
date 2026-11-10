# User flow: Radiology tool-capability contract audit

**Replay of real output.** The clickable page is `mock/index.html` (open it in a browser; no server, no network). It shows the offline validator's real output for synthetic case `c07_combined`, and the live SERV Reasoning answer recorded for it on 10 Nov 2026, scored under the current rules. It does not call SERV, and it does not simulate a SERV answer or a repaired report.

## Who this is for

An engineer integrating specialist tools into a reporting agent. Their question is not "is the report good?" but **"is this report complete because every needed tool ran, or only because nobody noticed what was missing?"** A finished-looking report can hide two different gaps: a tool that does not exist for the study's modality, and a tool that exists but was never called.

All data is synthetic and the catalog is fictional. Physician/operator sign-off on obligations and mappings is pending.

## The flow, one screen at a time

| # | Screen | What the user sees | What they do next | Why it helps |
|---|---|---|---|---|
| 1 | **Capability catalog** | Each tool with the exact words of its source and a badge: *confirmed* or *not confirmed* (with the reason, such as "modality not named in the quote"). | Read which mappings can be trusted. Press Next. | Capability claims are only as good as their source link. An unconfirmed mapping is shown as unconfirmed, not quietly accepted. |
| 2 | **Synthetic study** | The study (modality) and the list of assessment obligations the report must address. | Check that these are the obligations they care about. Press Next. | Everything downstream is judged against this list. It is also where the pending physician/operator sign-off applies. |
| 3 | **Coverage matrix** | One row per obligation: *supported, called* / *supported, omitted* / *unsupported* / *uncertain*, plus receipt status (valid, missing, failed, n/a) and a yes/no for full support, with the reason. Under the table, the SERV Reasoning advice recorded for the uncertain row and whether the current rules accept it. | Find the rows that are not full support. Press Next. | Separates "no tool exists" (fix the catalog or disclose the limit) from "a tool exists but was not called" (fix the plan) and from "we cannot tell" (get a better source). |
| 4 | **Calls and report** | Each proposed call with its check result (valid, invalid, unconfirmed and why), then each draft-report statement against the receipts, with a proposed action label such as "run the tool, or remove the claim". Obligations with no statement are listed as gaps. | Decide what to change in the plan or the report. The page applies nothing. | A claim without a valid receipt is surfaced before it ships. The tool proposes an action; it does not rewrite the report. |
| 5 | **Auditable export** | The command that reproduces the audit offline and the structured JSON, with its notices: synthetic, sign-off pending, and the SERV status of this offline run. | Save the JSON, re-run the command, compare. | Anyone can reproduce the result byte for byte, and the limits travel with the file. |

## Rules the flow keeps

- No score without its reason on the same screen.
- Full support is never shown without a confirmed mapping, a valid call and a valid receipt. A receipt alone cannot upgrade an unsupported or uncertain row.
- Every screen has one obvious next step. Nothing is applied for the user: the page proposes, a person decides.
- SERV appears only as recorded advice next to the uncertain row it was asked about, with its date and model. It never changes a row.

## SERV Reasoning in the flow (built, run live)

Where the validator can only say *uncertain*, `--serv` asks SERV Reasoning to read the tool's source text and answer `supported`, `unsupported` or `uncertain` with a verbatim quote. The answer is attached as **advice** behind the boundary in `docs/SERV_INTEGRATION.md`: the quote must be verbatim in the source, a `supported` quote must name the study type, a person confirms, and the deterministic result never changes. Measured on live batches in `eval/SERV_BATCH.md`. Not built: drafting report wording for the proposed actions.

## Review checklist

1. Open `mock/index.html` at laptop and phone width (screenshots: `docs/g2/`).
2. Walk screens 1 to 5 and say in one line what each tells the engineer.
3. Confirm the banner and the SERV note make it clear that nothing on the page is live and that SERV is advice.
