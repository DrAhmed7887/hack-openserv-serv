# Sign-off record

**Signed by the physician/operator (Dr Ahmed Zayed), 11 Nov 2026.** These are engineering rules with a clinical flavour. None of them is a clinical threshold, and none is a claim about any real device.

1. The six assessment classes (nodule-like, effusion-like, fracture-like, cardiac size, tube position, lung volume) are **engineering placeholders** on a synthetic chest X-ray study. They make no clinical claim and are published as placeholders.
2. **A report must address every required assessment.** An assessment it never mentions is a gap, even when the tool evidence is complete.
3. **An honest "not assessed" disclosure is acceptable** for an assessment without full support (`limitation_disclosed` counts as consistent).
4. **A negated source never confirms a tool.** "does not / is not validated to / unable to…" before the quote means not confirmed.
5. **SERV is advice only.** A "supported" answer counts only if its quote is verbatim and names the study type; a person confirms it, and it never changes the result.

**Not signed:** the fictional catalog (`data/catalog.json`, `SYN-*` tools and invented source texts). It describes no real product, so there is nothing real to sign; it keeps `"signoff": {"status": "pending"}`.

The recorded live SERV runs in `docs/serv_run/` were produced on 10 Nov, before this sign-off, and are kept unchanged as records.
