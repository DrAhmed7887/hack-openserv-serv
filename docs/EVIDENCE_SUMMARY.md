# Evidence summary (public facts only)

The full evidence pack, with quotes, check dates and status per row, is kept outside this repository in the owner's private research folder (`research/G1_EVIDENCE.md` under the hackathon folder). It is not linked here on purpose: this repo is meant to become public later and the pack is private.

Row ids below match the pack. Public documentation was read on **2026-11-10** without signing in. Quotes are short strings returned from the pages; anything else is a paraphrase and should be re-read before reuse.

| Id | Fact | Public source |
|---|---|---|
| E2 | "Every track needs to use SERV Reasoning." | https://www.openserv.ai/hackathon-2 |
| E6 | "Yes. You'll need an OpenServ account and API key to build with SERV Reasoning." | same |
| S1, S2 | Base URL `https://inference-api.openserv.ai`; bearer-token auth | https://docs.openserv.ai/serv-reasoning/api/index.md |
| S5, S6 | Chat-completions request fields; response is plain OpenAI shape, no documented trace field | https://docs.openserv.ai/serv-reasoning/api/chat-completions.md |
| S7 | Structured JSON output via `response_format` (tutorial) | https://docs.openserv.ai/serv-reasoning/tutorials/structured-outputs.md |
| S8 | "When the model calls an application tool, your server executes it and sends the result in a follow-up request." | https://docs.openserv.ai/serv-reasoning/tutorials/tools.md |
| S11 | Credits pay for API requests; no free allowance stated on that page | https://docs.openserv.ai/serv-reasoning/tutorials/credits-and-api-keys.md |
| P1 to P3 | Motivating paper: separates tools no cleared device offers from tools offered and not called, in a simulated setting | https://arxiv.org/abs/2611.09836v1 |

## What the paper is and is not used for

It motivates separating "no tool exists" from "a tool existed and was not called". It does **not** validate this repo's catalog or mapping rules, and no figure from it is used as a target or result here. The exact share of "offered and not called" misses was not re-verified (row P4: unverified).

## Not used

No real device intended-use text, no FDA listing content, no clinical claim, no pricing or revenue figure. The catalog in `data/` is fictional. Physician/operator sign-off: **pending**.
