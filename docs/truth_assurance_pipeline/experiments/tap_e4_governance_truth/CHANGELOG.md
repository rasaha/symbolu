# TAP-E4 — Changelog

## v4.1 (Governance Resolution — interface-boundary completion; additive, no re-run)

**Additive interface-boundary work only. No frozen algorithm, schema, corpus, metric, gate,
or result was changed; every `frozen_components_hash` and stored artifact is byte-identical
and no experiment was rerun.**

- **Canonical import package** `truth_assurance_pipeline/tap_e4_governance_resolution/` — a
  thin re-export/alias layer (no engine copy) over the historical
  `tap_e4_governance_truth` package. Canonical-name aliases are `is`-identical objects, not
  new types: `GovernanceResolver = GovernanceTruthLayer`, `GovernanceSituation = Situation`,
  `GovernanceDecision = GoverningDecision`. No `resolve_governance` function was invented
  (none exists); resolution is `GovernanceResolver(config(name)).resolve(...)`.
- **Historical package retained** unchanged for reproducibility (directory name, experiment
  IDs, stored manifests, `frozen_components_hash`), with a documentation note that the
  canonical engineering name is Governance Resolution. Its non-hashed `__init__.py` was
  extended additively to expose the full public surface; no runtime deprecation warning.
- **Documented the `GovernanceSituation` contract**: ownership (E1 owns intent; the
  caller/runtime owns operational metadata; E4 only normalizes explicit inputs and never
  discovers/retrieves/invents facts), the actual implemented fields (`jurisdiction`,
  `user_role`, `environment`, `date_year`, `contract`, `product`, `business_unit`), and the
  upstream-record and ActionGate boundaries.
- **Honest provenance disclosure**: field-level situation provenance is **not implemented**;
  provenance preservation applies to upstream evidence and governance decisions only. Future
  `SituationFact` model documented as a version-gated schema extension.
- **Evaluation Input Realism**: disclosed that synthetic situation facts are hand-authored,
  pre-normalized, and construction-coupled to the gold winner; situation extraction is not
  evaluated.
- **Missing/contradictory situation facts**: documented current behavior (missing → reduced
  confidence, never invented; contradictions not representable and must be detected before
  construction) and recorded the permissive-resolution + no-per-missing-field-gap behavior
  as a limitation deferred to a future version-incremented engine revision (the fix would
  touch frozen `scope.py`/`applicability.py`).
- **Tests**: added `tap_e4_governance_resolution/tests/test_canonical_import.py` (10 tests)
  verifying both import paths, re-export identity, cross-path byte-identical resolution, and
  a regression pinning current missing-fact behavior. Full suite **134 passing**.

## v4 (Governance Resolution — initial research & falsification phase)

**Added** a self-contained TAP-E4 track under
`truth_assurance_pipeline/tap_e4_governance_truth/`. It imports TAP-E1 (`IntentRecord`),
TAP-E2 (`RetrievalRecord`, evidence-unit structures), and TAP-E3 (`RelationshipRecord`,
`RelationshipAssertion`) through their **frozen public interfaces** and modifies none of
them.

- `authority.py` — frozen 9-tier authority hierarchy, ranks, immutable/non-selectable sets,
  and `tier_from_evidence` (the only interpreter of upstream authority metadata).
- `schema.py` — versioned `GovernanceRecord` / `GoverningDecision` / `GovernanceConflict` /
  `GovernanceGap` / `GovernanceConfidence` with every dimension separated.
- `jurisdiction.py`, `scope.py`, `temporal.py`, `exceptions.py` — deterministic dimension
  resolvers.
- `precedence.py` — documented precedence key + selection + top-key tie detection.
- `conflict_resolution.py` — surfaces unresolved ties (never a silent winner).
- `confidence.py` — 8-axis governance confidence, band floored by the minimum component.
- `applicability.py` — the resolution engine, `Situation`/`Candidate`, A–F baselines, and
  the 13-stage append-only trace.
- `validator.py` — input coherence checks (never repairs upstream records).
- `metrics.py` — per-dimension metrics + 10 independent critical-failure classes.
- `harness.py` — E1→E2→E3→E4 driver, dev-only selection, 14 preregistered gates, verdict,
  `frozen_components_hash`.
- `loader.py` — gold-free public loader.
- `corpus/` — NEW independent corpus (30 cases / 15 families / 26 units; eval locked).
- `experiments/` — `run_experiment.py`, `preregistration.json`, `results_v4.json`,
  `experiment_lock.json`.
- `tests/test_tap_e4.py` — 28 behavioral tests.

**Result:** selected baseline **F** (the simplest satisfying all preregistered gates — the
conflict/gap/severe gates require it); all fourteen gates pass on the locked eval; verdict
**`PASS_WITH_LIMITED_CLAIM`**.

**Findings:** first-match (A) is unsafe (selects expired/superseded/draft/out-of-jurisdiction,
lets a policy override a law); highest-authority (B) ignores applicability; jurisdiction+
scope (C) is time-blind (selects expired/superseded/future/old-version); +temporal+version
(D) flattens exceptions and ignores customer/emergency override; +precedence (E) resolves
overrides but silently picks winners on genuine ties and drops conflict/gap reporting; only
the full pipeline (F) surfaces conflicts, preserves upstream gaps, and reaches zero severe
governance failures.

**Supported claim (narrow):** a deterministic, provenance-preserving architecture for
resolving *which documented authority governs a situation* — authority precedence,
jurisdiction, scope, temporal/version, supersession, exception, customer/emergency override,
immutable-tier protection, conflict surfacing, gap preservation, and per-authority
provenance — on this study's synthetic corpus. It does **not** establish production legal/
regulatory reasoning, correctness of any obligation, real-world authority hierarchies, or
external generalization, and does **not** decide claim truth, answer the user, or authorize
enforcement.

**Honesty:** synthetic corpus; deterministic documented-rule resolution over already-perfect
relationship inputs; the authority hierarchy/precedence rules are a frozen model, not law;
locked **development** evaluation inspected during iteration (see LEAKAGE_AUDIT). Mechanism/
construction validation only. TAP-E1/E1.1/E2/E3 are unchanged (byte-identical; 124 tests
pass). Next layer: **TAP-E5 — Evidence Assembly.**
