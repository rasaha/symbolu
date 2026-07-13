# ANNOTATION_GUIDE

Two-pass annotation of source spans to ActionGate envelope fields and assurance
requirements.

## What is annotated

For every context, a structured oracle mapping links each source span to its
contribution to the canonical envelope and to assurance requirements: operation,
target, arguments, scope, current state, expected effects, reversibility,
rollback, evidence, simulation, approval, attestation, policy version, freshness,
and sequence/correlation context. This mapping is the unit `contrib` (consumed by
the `STRUCTURED_ORACLE_EXTRACTOR`).

## Span criticality labels (pass 1 — declared)

Each unit carries an authored `expected` label:

| label | meaning |
|---|---|
| `envelope_critical` | changes a non-assurance envelope field (e.g. an amount) |
| `decision_critical` | flips the six-outcome ActionGate disposition |
| `assurance_critical` | changes a requirement/constraint/scope/freshness at equal outcome |
| `structure_critical` | a reference/binding another span depends on |
| `redundant_decision_relevant` | decision-relevant but duplicated elsewhere |
| `non_critical` | filler (justification, history, logs, stale notes) |
| `uncertain` | annotator is unsure (excluded from agreement denominator) |

## Two-pass protocol

1. **Pass 1 (declared):** the authored `expected` label above.
2. **Pass 2 (independent, deterministic):** the frozen gate + ablation engine
   derive each span's *actual* primary criticality (`annotation.derive_primary`),
   using single- and redundancy-set ablation outcomes. This is a genuinely
   independent reviewer — it never reads the declared label.

The two are compared per span. **Disagreements are recorded, not silently
resolved** (`annotation.review` → `Disagreement` list). The agreement rate is a
proxy for annotation quality and is reported with results. Disagreements are
expected and informative — e.g. a span declared `assurance_critical` that the gate
shows is also outcome-decisive is recorded as (`assurance_critical` →
`decision_critical`), surfacing an under-call rather than hiding it.

## Priority when a span carries several derived effects

`decision > envelope > assurance > structure > redundant > non_critical`. The
derived *primary* label uses this order; the full multi-label set is retained by
the ablation engine for the metrics (which count the critical union once).

## What annotation does NOT do

It does not decide the verdict, and it does not "fix" the gate. The gate is ground
truth for envelope/decision/assurance effects; annotation measures how well the
authored expectations match that ground truth, and flags where they don't.
