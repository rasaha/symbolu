# Eligibility Matrix Design

- **Rows** = agents; **columns** = the union of API-provided condition names for
  the selected role (`features/eligibility/matrix.ts`). One role is evaluated at a
  time via a role selector.
- **Cells** derive purely from API condition results: a condition is `pass`,
  `fail`, `unknown`, or `na` — never recomputed from registry/policy fields in the
  browser. `passed_conditions` are names; `failed`/`unknown` are ConditionResult
  objects normalized by `conditionName`.
- **Row summary**: canonical identity, provider, overall state pill (glyph + text),
  passed/failed/unknown counts, and an Explain action.
- **Filtering**: state, provider, residency, evidence class, elimination reason,
  agent status. **Sorting**: identity, state, provider, failed-count,
  unknown-count — all stable and deterministic. A visible note states display
  order is not a selection decision; no score, rank, recommendation or preferred
  agent is shown.
- **Explanation drawer**: an accessible dialog (focus trap + restoration) fed by
  `POST /explanations/eligibility`, showing passed/failed/unknown conditions,
  deterministically-labeled reason codes, evidence/policy refs and fingerprints.
