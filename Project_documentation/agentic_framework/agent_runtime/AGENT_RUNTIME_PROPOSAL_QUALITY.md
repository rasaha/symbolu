# Agent Runtime — Proposal Quality (Deliverable 4)

Real-model proposal quality (§6). Labels: `FACT` · `INTERPRETATION`.

## Status: NOT ASSESSABLE — `BLOCKED_NO_REAL_MODEL`
`FACT`. Proposal quality measures a REAL model's output BEFORE governance. No live/local model can run
in this environment (see the probe), so **no real proposals exist to measure**. Issuing
`REAL_MODEL_PROPOSALS_ACCEPTABLE` or `…_UNACCEPTABLE` would be fabrication. The verdict is therefore
**blocked**, not one of the three quality grades.

## Metrics defined + harness ready
`FACT`. `benchmark/real_model_eval.py` computes, per the frozen corpus: valid-plan rate, correct
tool-selection, argument validity, CER-generation rate, malformed-output rate, repair-attempt rate,
hallucinated-tool rate, missing-required-field rate, materially-unsafe-proposal rate,
unnecessary-action rate. With no model it returns `BLOCKED_NO_REAL_MODEL`
(`benchmark/phase3_real_model_results.json`).

## Note
`INTERPRETATION`. The AI Control Plane catching a bad proposal is reported as *containment*, not as
proposal quality — the runner records both separately, so a future real-model run will show proposal
quality AND governance containment independently.
