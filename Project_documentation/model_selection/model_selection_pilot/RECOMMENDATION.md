# Final Recommendation — Provisional, Gated on the Pending Real Run

## The honest constraint

The primary research question — *can the policy predict the best eligible **real**
model before execution?* — **could not be answered in this environment.** No real model
was executable (no LLM API keys; AWS and Google credentials invalid; no local-model
tooling — see `PILOT_STATUS.md`). The workstream's own instruction is explicit for this
case: build the ready-to-run harness, state the block, and **do not fabricate real-model
results.** That is what was done. The self-test (stub) numbers validate the harness only
and are excluded from the falsification test by construction (`SELF_TEST_REPORT.md`).

Therefore no *new* empirical evidence upgrades or downgrades the prior conclusions.

## Primary recommendation (one, as required)

> **Category 3 — build as a bounded, governed Hybrid LLM model-selection capability —
> but PROVISIONALLY, explicitly gated on running this now-ready pilot against real
> models and clearing the pre-registered criteria.**

Rationale, kept strictly to what is actually established:

- **Carried forward (established in phase 1, synthetic):** a constraint-first, explainable
  policy reduced selection regret versus every simpler baseline and held hard-constraint
  violations at zero with 100% explanation completeness — but its differentiated, durable
  value is **compliance + auditable explanation + cold-start robustness**, not raw
  optimization, and its margin over good static rules is modest and workload-dependent.
- **Added this phase (design, not evidence):** the mandated **F1→F2 correction** is
  implemented and unit-tested — minimum quality is now a hard eligibility gate (lenient
  under thin evidence to avoid over-abstention). This directly addresses phase 1's
  soft-quality weakness. Its *value* on real tasks is untested.
- **Not established:** that any of this survives contact with real models. The circularity
  in the self-test (telemetry derived from the same stub that produces outcomes) means the
  stub cannot stand in for the real question.

Category 3 is provisional because the evidence needed to make it firm — a real
shadow run clearing `FALSIFICATION_PREREGISTRATION.md` — does not yet exist.

## Fallbacks, pre-committed

- If the real run shows F2's optimization margin over static rules is small or
  class-narrow, drop to **Category 2 (internal deterministic rules)** for optimization,
  keeping only the governance/explanation spine.
- If F2 ≈ cheapest-eligible or shows no cost-per-success win, **Category 1 (stop)** for
  the optimization claim; the governance value alone does not need this machinery.
- **Categories 4 and 5 (standalone product / broad orchestrator) are NOT recommended** —
  consistent with the workstream's explicit bar (real-model results must *clearly* justify
  a standalone boundary) and with every prior phase.

## The single next action

Supply provider credentials and a spend cap, run `harness.py` in `REAL` mode over the
shadow set (worst-case ~$1.36 at current corpus size), and grade against the
pre-registered thresholds. Until then, the recommendation stands at **provisional
Category 3**, and the empirical question is honestly **open**.
