# Changelog — ugence-actiongate-provider

All notable changes to the canonical ActionGate distribution are documented here.

## 0.2.0 — deterministic policy semantics (change class **MAJOR**)

Change class **MAJOR** per `platform/PLATFORM_FREEZE_V1.json` `compatibility_rules`
(*"authority/lifecycle/dependency-direction/fail-safe changes"*). Note that the
platform's own API-diff classifier reports this as `MINOR`/`ADDITIVE`: it compares
API *shape*, and every shape change here is an addition. The MAJOR classification
comes from the semantic change, which no shape diff can see.

Version: `0.1.0` -> `0.2.0`, implementation and distribution together, with the
legacy `dgm-actiongate-provider` shell bumped in lockstep. The minor position is
the breaking position on a pre-1.0 line, and `production_certified` is still
`False`, so `1.0.0` would claim more than this package supports. Because the
classifier cannot see the semantic change, this version string is the only
machine-readable signal a consumer gets that it happened — see
`docs/VERSIONING.md` for the full consumer table. Two `>=0.1.0` floors
(`packages/products/ai-hiring`, `packages/integration/risk-authority-runtime`)
resolve to `0.2.0` with no edit: a floor signals nothing and blocks nothing.

Known regression, not fixed in this release: 84 tests across
`enterprise_validation_pilot`, `comparative_governance_benchmark` and
`provider_heterogeneity_validation` fail once `authorization_expired` is
honoured. Those harnesses build CERs on a frozen scenario clock and construct the
control-plane adapter with its default wall clock, so every scenario CER reads as
months expired. The mismatch predates this change and was inert only because the
engine dropped the field. See the audit record's "Regression found while settling
these items".

### Fixed (fail-safe)

- **`authorization_expired` is no longer discarded.** It was the one neutral request
  field `map_request` dropped, while the control-plane adapter computed it and the
  framework's reference provider honoured it — so ActionGate authorized actions
  riding an expired CER. It is now mapped, and an expired authorization short-circuits
  to `EXPIRED` before any policy is consulted, carrying no authority basis and no
  constraints.
- **Governance dimensions are no longer inert.** The engine branched solely on
  `action_type`; `principal`, `authority`, `resource`, `parameters`, `risk_context`,
  `evidence_refs` and `decision_refs` were mapped and never read. Evaluation now
  routes through `ugence_actiongate_provider.vnext`, which reads all of them.
- **Trace ids distinguish requests that differ.** `_trace` covered `action_type`,
  `parameters` and `tenant` only — and `tenant` is always empty — so requests
  differing in actor, authority, risk and expiry shared a trace id.
- **The inclusive expiry boundary is applied.** `now >= expires_at` is expired. The
  control-plane adapter previously used `expires_at < now`, disagreeing by one
  instant with Action Clearance.

### Added

- `ActionGateOutcome.EXPIRED` and `ActionGateRequest.authorization_expired`.
- `ugence_actiongate_provider.vnext`: closed reason-code catalogue with a declared
  tier per code, a non-compensatory severity lattice reduced from the ActionGate
  reference evaluator, an immutable dimension-policy model, and a pure evaluator.
- `ActionGateEngine(policy=...)` and `ActionGateEngine.governed_dimensions`.
- `.api` exports: `ActionGatePolicy`, `ParameterBound`, `ActionGateReasonCode`,
  `ActionGateTier`, `TIER_TO_NATIVE`, `is_expired`.

### Changed (breaking)

- **Reason codes are UPPER_SNAKE from a closed catalogue.** `policy_allow`,
  `policy_denied`, `policy_unknown`, `policy_allow_with_constraints` become
  `POLICY_ALLOW`, `POLICY_DENIED`, `POLICY_UNKNOWN`, `POLICY_ALLOW_WITH_CONSTRAINTS`.
  A consumer string-matching the old lowercase values must be updated.
- **Mapping version `actiongate-map-1` → `actiongate-map-2`.**
- **Engine policy version `policy-1` → `policy-2`.**
- A default-constructed `ActionGateEngine` governs no dimensions. Dimension rules
  must be supplied via `policy=`; the `denied`/`unknown`/`constrained` shorthand
  still works and is folded into the policy.

### Re-baselined

- `.api` snapshot `9eeb66e3…` → `5334cca1…` (workflow base and
  `public_api_manifests`).
- `conformance_hashes` `07e08bd4…` → `ff605bf9…`.
- `core_tree_hashes["actiongate_provider"]` `9cbeb833…` → `a0010fcf…`.
- Behavioural equivalence: a new `actiongate_equivalence_after_semantics.json`
  baseline (`e1ff5d2a…`) is the comparison target.
  `actiongate_equivalence_before.json` (`d805e6cf…`) is **kept** as the
  pre-migration record and CI asserts it still differs.

### Not changed

- Implementation and distribution versions remain `0.1.0` — an owner decision,
  deliberately not taken here.

## [0.1.0] — canonical package migration

First independent distribution of the ActionGate action-governance provider.

### Migration (no behavior change)

- Established the single canonical source tree
  `packages/providers/actiongate/src/ugence_actiongate_provider` (history-preserving
  relocation from the monorepo `actiongate_provider/` tree; internal framework
  imports rewritten from `governance_providers.api` to
  `ugence_governance_provider_framework.api`).
- New distribution **`ugence-actiongate-provider`** (import namespace
  `ugence_actiongate_provider`). Provider **implementation version stays `0.1.0`** —
  only the package location changed. Initial **distribution version `0.1.0`**.
- Legacy `actiongate_provider` namespace converted to a logic-free compatibility
  facade (object identity preserved). Legacy `dgm-actiongate-provider` converted to a
  compatibility distribution depending on
  `ugence-actiongate-provider[decision-authority]`.
- Dropped the unused `decision-governance` core dependency (ActionGate does not
  import the kernel directly); the kernel remains reachable via the optional
  `decision-authority` extra through the framework adapter.
- Added `version_info()`, a `python -m ugence_actiongate_provider` CLI
  (`version`/`verify`/`demo`) and the `ugence-actiongate-provider` console script.

### Equivalence (proven)

- Public `.api` surface **byte-identical** (26 exports); the only additive change is
  the top-level `version_info` helper (MINOR-compatible overall; frozen `.api`
  snapshot unchanged).
- Behavioral capture **identical** before == canonical == legacy.
- Platform-freeze API snapshot unchanged; only structural tree/conformance hashes
  updated for the relocation.

### Boundary (unchanged)

- **Authorization only.** No dispatch/execute/observe/reconcile surface. No TAP
  dependency. Fail-closed: unknown outcomes and infrastructure failure →
  INDETERMINATE, and DENIED/INDETERMINATE never dispatch.

Not production certified.
