# TAP-E4 — Governance Resolution

> **Historical package path retained for experiment reproducibility. The canonical
> engineering name is Governance Resolution.** New downstream code should import through
> the canonical package
> [`truth_assurance_pipeline.tap_e4_governance_resolution`](../tap_e4_governance_resolution/README.md);
> this `tap_e4_governance_truth` path continues to work unchanged and is retained for frozen
> experiments, stored manifests, backward compatibility, and reproducibility (its directory
> name, experiment IDs, and `frozen_components_hash` embed the original name). This is a
> path/name note only — no runtime deprecation warning is emitted, per repository policy.

The fourth TAP research layer. Given an `IntentRecord` (TAP-E1), a `RetrievalRecord`
(TAP-E2), and a `RelationshipRecord` (TAP-E3) — all consumed through their **frozen public
interfaces** — plus an explicit governance `Situation`, it resolves **which documented
authority governs** that situation: the controlling rule / policy / regulation / contract /
version, with jurisdiction, scope, temporal/version, supersession, exception, precedence,
conflict, gap, and per-authority provenance.

> **"Truth" here is narrow:** a deterministic, provenance-preserving determination of
> *which documented authority controls this situation, and why* — **not** whether that
> authority's obligation is factually correct, whether a final claim is justified (Claim
> Truth), whether an action should be executed (enforcement), or a user answer. TAP-E4 may
> conclude "the customer contract governs notification timing here"; it must not decide
> that 24 hours is the *right* number, retrieve new documents, invent relationships, or
> repair upstream gaps.

## Honesty (read first)

- New, independently authored synthetic corpus; no upstream gold is reused as governance
  gold.
- **Deterministic, documented-rule resolution** over already-perfect synthetic relationship
  inputs (upstream confidence 1.0). This phase evaluates the **governance layer**, not
  upstream extraction, and not real legal/regulatory reasoning.
- The authority hierarchy and precedence rules are a **documented, frozen model** — not
  law. "Law > regulation > corporate policy …" is this study's ordering, versioned and
  hashed.
- The eval split is content-hash locked and preregistered, but was inspected during
  iterative engineering — a **locked development evaluation, not an untouched / blind
  holdout**.
- Mechanism/construction validation only — no claim of production governance or external
  generalization.

## Layout

```
tap_e4_governance_truth/
├── authority.py       # frozen tier hierarchy + tier_from_evidence (upstream → tier)
├── schema.py          # GovernanceRecord / GoverningDecision / Conflict / Gap / Confidence
├── jurisdiction.py scope.py temporal.py exceptions.py   # dimension resolvers
├── precedence.py      # documented precedence key + selection + tie detection
├── conflict_resolution.py   # surfaces unresolved ties (never silent)
├── confidence.py      # multidimensional governance confidence (floored by min component)
├── applicability.py   # resolution engine + A–F baselines + 13-stage trace
├── validator.py       # input validation (E1/E2/E3 coherence; never repairs)
├── metrics.py         # per-dimension metrics + independent critical failures
├── harness.py         # E1→E2→E3→E4 driver, dev-only selection, gates, verdict
├── loader.py          # gold-free public loader
├── corpus/            # 30 cases / 15 families (eval locked)
├── experiments/       # runner, preregistration, locks, results
└── tests/
```

## Run

```bash
python -m truth_assurance_pipeline.tap_e4_governance_truth.experiments.run_experiment
python -m pytest truth_assurance_pipeline/tap_e4_governance_truth/tests/ -q
```

## Result

Selected baseline **F** (the simplest satisfying all preregistered gates — the conflict/
gap/severe gates require it). All fourteen gates pass on the locked eval split; verdict
**`PASS_WITH_LIMITED_CLAIM`**.

The `GovernanceRecord` schema is the provisional frozen downstream interface; the **next
layer is TAP-E5 — Evidence Assembly**. See
[`EXPERIMENT_REPORT.md`](../../docs/truth_assurance_pipeline/experiments/tap_e4_governance_truth/EXPERIMENT_REPORT.md).
