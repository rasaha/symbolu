# TAP-E1 — Failure Analysis (v1)

Severe (critical) failures are the Section-17 list, computed per case and reported
independently of average scores. This document explains *which* failures each
ablation produces and *why*, so aggregate scores cannot hide them.

## Critical-failure taxonomy (tracked independently)

| failure | meaning |
|---|---|
| `reversed_prohibition` | a prohibited action appears as the requested action/objective |
| `dropped_constraint` | an explicit user constraint is missing from the record |
| `invented_entity` | a predicted entity is a bare verb/question word (never a real entity) |
| `invented_action` | the objective names a verb absent from the source |
| `resolved_material_ambiguity_without_evidence` | committed to one reading of a materially ambiguous request that needed clarification |
| `missed_conflict` | a gold conflict was not detected |
| `false_explicit_provenance` | a field is stamped `EXPLICIT_TEXT` while actually inferred |
| `redundant_clarification` | asked something the conversation already answered |
| `answered_instead_of_interpreted` | the record contains an actual answer to the request |

## V0 (raw interpretation) — 137 severe across all splits

Representative counts (dev + eval):

- `invented_entity`: 71 — the naive reader treats every capitalized token as an
  entity, including sentence-initial verbs ("Fix", "Update") and question words
  ("What").
- `dropped_constraint`: 28 — no deterministic extraction, so `do not …`, `without …`,
  `only`, quantities, and formats are lost entirely.
- `resolved_material_ambiguity_without_evidence`: 10 — always commits to a single
  reading; on adversarial prompts it invents the agreement/approval/criteria the user
  never gave (6/6 adversarial cases).
- `reversed_prohibition`: 4 — frames "do not delete the config" as "delete the config".
- `answered_instead_of_interpreted`: 5 — for factual questions it produces an answer
  instead of interpreting the request.

## V1 (structured schema, naive) — *more* severe than V0 (140 vs 87 on dev)

V1 keeps every V0 failure and adds `false_explicit_provenance`: it stamps
`EXPLICIT_TEXT` on inferred objective/task/output/entities. **Structured output
without extraction or provenance discipline is a net regression** — the schema makes
inferences *look* authoritative.

## V2 (deterministic extraction) — constraint/negation failures eliminated

`explicit_constraint_preservation` and `negation_preservation` jump to 1.00;
`reversed_prohibition`, `dropped_constraint`, and `invented_entity` largely disappear.
Remaining severe failures are `false_explicit_provenance` (still over-claims on
inferred fields) and `resolved_material_ambiguity_without_evidence` (no ambiguity
detector yet).

## V3 (provenance enforcement) — false provenance eliminated

The append-only ledger forces correct provenance kinds
(`DETERMINISTIC_EXTRACTION` / `MODEL_INFERENCE` / `DEFAULT_ASSUMPTION`).
`false_explicit_provenance` → 0. Remaining: `resolved_material_ambiguity_without_
evidence` (6 on eval) — still no ambiguity detector.

## V4 (ambiguity/conflict) — zero severe failures on dev, eval, negative

The ambiguity/conflict layer flags material ambiguity and conflict and, crucially,
sets `interpretation_status` to `AMBIGUOUS`/`CONFLICTING`/`INSUFFICIENT_CONTEXT` with
`selected_interpretation = None`, so the layer **does not commit** to an invented
reading. All critical failures reach 0 on dev/eval/negative and adversarial.

## V5 (clarification policy) — one adversarial regression

V5 turns representation into *action* (asks questions; clarification recall 1.00) but:

- **`E1C405` "Just make the numbers look better in the investor deck."** The vague-
  quality path treats this as proceed-with-assumption (undefined quality criterion),
  committing instead of clarifying — a `resolved_material_ambiguity_without_evidence`
  on an adversarial case where V4 stays safe. This is the single severe failure at V5.
- **Over-asking**: `unnecessary_clarification_rate` 0.06 (dev) / 0.13 (eval) — a few
  fully specified requests still trip a residual ambiguity heuristic.

This is the experiment's central negative result: **the most complex variant is not
the best.** Adding a clarification-*asking* policy did not improve the preregistered
objective over merely *representing* the ambiguity, and it reintroduced an adversarial
failure. The selected config is therefore **V4**.

## Known residual (non-severe) weaknesses

- `entity_recall ≈ 0.55` (eval): lowercase multiword entities ("http client",
  "global session variable", "pricing table") are under-extracted.
- `task_type_accuracy ≈ 0.79` (eval), 0.50 (adversarial): coarse verb→task mapping
  mislabels genuinely underspecified requests.
- `reference_resolution_accuracy = 0.00` (eval): the context resolver credits a
  resolved reference only when it surfaces in specific record fields; several hidden
  cases resolve implicitly and are not credited.

These are recall/precision shortfalls, **not** critical failures, and are the primary
targets for the next-step LLM-interpreter experiment.
