# Changelog — `ugence-ai-hiring`

All notable changes to the independent AI Hiring distribution. This file tracks
the **distribution** (wheel packaging) version, which is distinct from the
**product** capability-maturity version (`PRODUCT_VERSION`, currently `0.6.0`).

The format follows [Keep a Changelog](https://keepachangelog.com/); the
distribution uses pre-1.0 semantic versioning.

## [Unreleased] — Hiring Decision Authority: decision plane (assessment → gates → eligibility → recommendation)

Implements spec §21 steps 2–4, 6 (models), and 9. Additive only: new
`ugence_ai_hiring.hiring_decision` package (canonical re-export at
`ugence_ai_hiring.hiring.decision`); no existing API changed; no product behavior
changed; `production_certified` remains `False`. Full suite 842 passed / 12
skipped (32 new tests); `python -m ugence_ai_hiring verify` PASS.

### Added
- **`hiring_decision` package** — the governance-first decision layer:
  - `HiringDecisionCase` — aggregate root for one candidate-role lifecycle;
    immutable, append-only history; binds **only** via a `DecisionAuthorityOutcome`
    (HUMAN, binding=True).
  - `DimensionAssessment` — advisory per-dimension `{dimension, outcome, score,
    confidence, evidence_refs, assessment_version, rationale, provenance}`;
    rejects CULTURE_FIT/RESILIENCE; keeps ROLE_SUSTAINABILITY_AND_ADAPTATION
    post-hire unless `pre_hire_justified` with job-relevant evidence.
  - `MandatoryGateEvaluator` — deterministic, **admitted-evidence-only**,
    fail-closed (`PASS`/`FAIL`/`INDETERMINATE`); unadmitted/missing evidence can
    never satisfy a gate.
  - `Eligibility` + `derive_eligibility` — derived from mandatory gates only; no
    score/OFI input.
  - `HiringRecommendation` + `build_recommendation` — advisory
    (`actor_type=AI`, `binding=False`); forces `NOT_ELIGIBLE` on gate failure;
    never reads the Overall Fit Index.
  - `HiringActionRequest` + `to_cer_payload()` — hiring-domain action contract
    translated to the neutral CER / shared-ActionGate payload (carries decision +
    contract provenance).
  - Post-hire `ReviewRecord` / `ReviewObservation` (1/3/6/12-month) and
    `CalibrationProposal` — proposes/versions Decision Contract or role-policy
    changes; **no hidden-weight retraining**.
- **Analytics-only `OverallFitIndex`** (`hiring_decision.analytics`) — weighted
  fit + HIGH/MEDIUM/LOW range; intentionally **not** re-exported from the plane
  and not importable by gate/eligibility/policy code (enforced by tests).
- **Integration ports (interfaces only, no implementations):**
  `EvidenceAdmissionPort` → TAP; `DecisionAuthorityPort`;
  `ActionAuthorizationPort` → ActionGate; `RuntimeAssurancePort` → Runtime
  Assurance / ACP; `ReconciliationPort`. Shared governance capabilities are
  referenced through ports, never copied into this package; the package imports
  and runs standalone with test adapters (no platform required at import).
- 32 tests (`tests/test_hiring_decision.py`, `tests/hiring_decision_fakes.py`).

### Changed (design contracts)
- `docs/schemas/dimension_assessment.schema.json` — aligned to the implemented
  model (`evidence_refs`, `assessment_version`, `rationale`, `provenance`,
  `pre_hire_justified`).
- `docs/schemas/hiring_recommendation.schema.json` — added `binding` (const
  false) and `proposed_action.employment_type`.
- `docs/schemas/hiring_action_request.schema.json` — new contract.
- `docs/HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md` §21.1 — build status.

## [Unreleased] — Hiring Decision Authority: policy plane (PWC → IR → Contract)

Implements spec §21 step 1 of
[`docs/HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md`](docs/HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md).
Additive only: new `ugence_ai_hiring.hiring_policy` package (canonical re-export
at `ugence_ai_hiring.hiring.policy`); no existing API changed; no product
behavior changed; `production_certified` remains `False`.

### Added
- **`hiring_policy` package** — the governance-first authoring surface, mirroring
  the platform Policy Workflow Compiler / WorkflowIR / Decision Contract pattern:
  - `HiringPolicy` — declarative, human-authored policy source (HR declares
    requirements, not weights).
  - `HiringPolicyCompiler` (PWC) — compiles a policy into a signed,
    content-addressed `HiringWorkflowIR` (`hiring_workflow_ir.v1`); derivation is
    deterministic (same policy → same digest).
  - `HiringWorkflowIR` — canonical compiled artifact (dimensions, normalized
    weights summing to 1.0, mandatory gates, per-dimension required evidence,
    confidence thresholds, action constraints, runtime-assurance checks, human
    approval chain), with a SHA-256 content digest over its semantic body and a
    detached signature (offline `DeterministicHMACSigner`).
  - `HiringDecisionContract` + `project_contract()` — a deployable projection of
    one IR digest, carrying `compiled_from` provenance; projection verifies the
    IR digest (and signature when a signer is supplied) and refuses a tampered IR.
- **Compile-time rejections** enforcing the invariants: (a) no Overall Fit Index
  reference and no forbidden legacy dimension (`CULTURE_FIT`→Operating Environment
  Compatibility, `RESILIENCE`→Role Sustainability & Adaptation); (b) mandatory
  requirements are gates, never weighted/compensable dimensions; (c) every
  weighted dimension declares required evidence; (d) human-only approval chain;
  (e) action constraints within some approver's authority; (f) constrained actions
  carry the required runtime-assurance checks. All violations are reported at once.
- 22 tests (`tests/test_hiring_policy_compiler.py`).

### Notes
- The Overall Fit Index is structurally absent from the IR and contract (it is
  analytics-only and never enters policy). This layer authors/compiles/signs/
  projects policy only — it does not evaluate gates, score candidates, gate
  actions, run runtime assurance, write to any HRIS/ATS, or make/authorize a
  decision (later spine stages; spec §21 steps 2–7).

## [0.1.1] — Canonical TAP / ActionGate dependency normalization

A **packaging / dependency-metadata change only.** The AI Hiring **product
version is unchanged (`0.6.x`)**, no public core API was added or removed, no
product behavior changed, and `production_certified` remains `False`.

### Changed
- Optional dependency normalization: the `tap` / `actiongate` extras now resolve
  the **canonical** distributions `ugence-tap-provider>=0.1.0` /
  `ugence-actiongate-provider>=0.1.0` (previously `dgm-tap-provider` /
  `dgm-actiongate-provider`). The user-facing extra names are unchanged. TAP and
  ActionGate remain **optional, dependency-injected** — never core dependencies.
- Distribution version bumped `0.1.0 → 0.1.1` (packaging change only).
- `version_info().optional_integrations` retains its `tap_legacy` /
  `actiongate_legacy` keys for schema stability but now probes the canonical
  namespaces `ugence_tap_provider` / `ugence_actiongate_provider`.

### Added
- Canonical adapter modules `integrations/tap_adapter.py` and
  `integrations/actiongate_adapter.py` targeting the canonical provider namespaces
  (lazy import; logic-free; no adjudication/authorization/execution logic).
- Neutral exception alias `ProviderUnavailable`
  (`LegacyProviderUnavailable is ProviderUnavailable`, behavior unchanged).
- Provider-dependency metadata tests, canonical-adapter + object-identity tests,
  strengthened AST dependency-boundary tests, a behavioral-equivalence capture
  (`scripts/ai_hiring_provider_normalization_capture.py`), a canonical-provider
  clean-install matrix in the distribution verifier, and audit artifacts under
  `docs/audits/ai_hiring_provider_normalization/`.
- Documentation: `docs/PROVIDER_DEPENDENCY_MIGRATION.md`; updated
  `docs/TAP_ACTIONGATE_DEPENDENCY_BOUNDARY.md`.

### Preserved / unchanged
- The old adapter module names (`tap_legacy_adapter`, `actiongate_legacy_adapter`)
  remain as logic-free compatibility import paths that re-export the canonical
  adapter callables (object identity preserved); no second implementation exists.
- `dgm-tap-provider` / `dgm-actiongate-provider` remain usable **provider
  compatibility distributions** for old deployments (they pull in the canonical
  providers) — but are no longer AI Hiring dependencies.
- Behavioral equivalence verified: product semantics are byte-identical before,
  after (canonical adapters), and after (legacy adapter paths); only the
  distribution version, dependency distribution names, and provider import
  namespaces differ.
- TAP semantics, ActionGate semantics, the advisory-AI / human-binding-decision
  boundary, and the authorization-vs-execution boundary are unchanged.

## [0.1.0] — Independent extraction

First independent packaging of the AI Hiring product, extracted from the
monolithic `symbolu` distribution into `packages/products/ai-hiring/` with the
canonical import surface `ugence_ai_hiring`.

### Added
- Independent, pure-Python distribution `ugence-ai-hiring` (canonical import
  `ugence_ai_hiring`), built from `packages/products/ai-hiring/`.
- Distribution/product version split: `__version__` (distribution `0.1.0`) vs
  `PRODUCT_VERSION` (`0.6.0`), surfaced by `version_info()` alongside contract
  versions, dependency versions, release classification, and optional-integration
  availability. `production_certified` is hard-coded `False`.
- Top-level CLI: `python -m ugence_ai_hiring version|verify|demo|report` and the
  `ugence-ai-hiring` console script.
- Logic-free `ai_hiring` compatibility facade (re-exports the canonical objects
  with object identity and deep submodule paths preserved) for clean-environment
  installs.
- Minimal core dependency set: `pydantic>=2`, `ugence-decision-authority`,
  `ugence-governance-provider-framework`, `ugence-governance-contracts`. NumPy
  and all vendor AI SDKs are intentionally **not** dependencies.
- Optional `api` extra (FastAPI adapter); no extra is declared without
  corresponding code.
- Migrated behavioral test suite plus new packaging, dependency-boundary,
  import-isolation, compatibility-facade, governance-invariant, and determinism
  tests.
- Distribution verifier (`scripts/verify_ai_hiring_distribution.py`) and scoped
  CI (`.github/workflows/ai-hiring-package-ci.yml`).
- Provenance artifacts (`artifacts/source_manifest.json`,
  `artifacts/source_hashes.json`, `artifacts/public_api_baseline.json`,
  `artifacts/test_migration_manifest.json`).

### Preserved / unchanged
- Product semantics and governance invariants are unchanged; no new hiring
  algorithm, scoring/ranking/fairness model, or LLM inference was introduced.
- The original monorepo `ai_hiring/` source tree is preserved unchanged (the
  in-repo facade conversion is deferred to a later cleanup PR to keep the
  platform freeze intact).
- No production HRIS/ATS/offer/payroll adapter is included.

### Notes
- The pure-Python wheel is bit-for-bit reproducible with `SOURCE_DATE_EPOCH`
  pinned; the sdist is content-reproducible.
- Not production certified; controlled-pilot maturity only.
