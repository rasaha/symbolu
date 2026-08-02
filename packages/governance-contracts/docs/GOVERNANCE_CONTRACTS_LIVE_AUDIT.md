# Governance Contracts — Live Audit

**Phase:** live audit, boundary verification, compatibility & package hardening
(not a redesign). **Verdict:** `PACKAGE_HARDENING_REQUIRED` (narrow, bounded).
**Maturity:** `IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED`.

This document records the starting live state and the evidence-based findings for
the `ugence-governance-contracts` package. It was written from the live repository
at the commit below; every status/name/claim in the task prompt was treated as
unverified until confirmed here.

---

## 1. Verified starting state (live)

| Fact | Value (verified from the live repo) |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` (GitHub HEAD-branch) |
| Default-branch HEAD | `a34f43992c1feec5b9158e95b7d2e942aba72925` |
| Audit branch | `claude/governance-contracts-audit-2p8mvl` (started at the default-branch HEAD; identical commit) |
| PR #1289 | **MERGED** — `fix: harden Agent Runtime exact-action proposal contract`; merged 2026-08-02T17:20:49Z by `rasaha`; head `12d2c73a`, base `5cee363c`; merge commit **`a34f4399`** (== current default HEAD) |
| Agent Runtime version | `ugence_agent_runtime` **0.1.2** (`packages/runtime/agent-runtime/src/ugence_agent_runtime/version.py`) |
| Exact-action hardening present | **Yes** — deeply-immutable proposal identity, mandatory correlation binding folded into the fingerprint, inclusive expiry, exact-action re-fingerprint (per PR #1289; confirmed in-tree) |

The current default HEAD **is** the PR #1289 merge commit, so this phase begins
from the merged Agent Runtime contract-hardening work as required.

---

## 2. Canonical package location & identity

| Attribute | Value |
|---|---|
| Package path | `packages/governance-contracts` |
| Source layout | `src/ugence_governance_contracts/` |
| Distribution | `ugence-governance-contracts` |
| Namespace | `ugence_governance_contracts` |
| Package version | **0.1.0** (`__version__`, dynamic in `pyproject.toml`) |
| Contract version | **1.0.0** (`CONTRACT_VERSION`) |
| Runtime dependencies | **none** — Python standard library only (declared `dependencies = []`) |
| Curated public API | `ugence_governance_contracts.api` (33 symbols) |
| Full namespace `__all__` | 35 symbols (adds `is_legal_transition`, `assert_transition`, `api`) |

There is exactly **one** canonical source tree for these contracts. The expected
distribution name in the prompt (`ugence-governance-contracts`) is confirmed
correct (the prompt's "ugence-governance-contracts" typo notwithstanding).

### What the package actually is

A **provider-neutral contract layer for governance _providers_** — request/result
envelopes, provider protocols, provider metadata/descriptors, a lifecycle state
machine, and an error taxonomy for the three governance provider families
(assertion / action / external-execution). It is a **leaf**: stdlib-only, no
third-party and no other Ugence package.

> **Scope correction (evidence-based).** The task prompt hypothesizes a much
> broader "universal disposition vocabulary" (governance dispositions, decision
> outcomes, clearance outcomes, `CLEAR/HOLD/BLOCK/ESCALATE`, evidence references,
> tenant/subject binding, validity/expiry, fingerprints, etc.). **The live package
> is deliberately narrower than that.** Those disposition/decision/clearance
> vocabularies exist and are **component-owned** by the capability packages
> (Decision Authority, Action Clearance, Agent Runtime), not by this contract
> layer. This is the correct architecture (§4) and is **not** a defect — see §5,
> §6, §7. Per the prompt, universal abstractions are not invented where multiple
> live consumers do not demonstrably need them; the documented evolution plan
> (§9 below) owns any future additions.

---

## 3. Architectural role & authority boundary (verified)

Governance Contracts is a **neutral contract layer, not an executing governance
service**. Verified against the source:

- No evidence evaluation, policy authoring, decision minting, authorization,
  clearance, provider dispatch, retries, orchestration, ledger, or execution
  logic lives in the package. It is dataclasses, enums, `Protocol`s, a pure
  lifecycle transition table, and exception classes.
- No product import, no Agent Runtime import, no concrete governance-provider
  import (AST-scanned by `tests/packaging/test_leaf_dependency.py`).
- Authority note is explicit in `__init__.py`/README: these are neutral
  *contracts*, not authority; the meaning of each result (advisory vs binding) is
  owned by the capability that produces it. A DTO named `ActionGovernanceOutcome`
  does not itself authorize; a `Provider` protocol does not execute.

Dependency direction (acyclic, correct):

```
consumers
  -> governance_providers.*            (logic-free legacy shim, aliases GPF submodules)
  -> ugence_governance_provider_framework.{errors,lifecycle,metadata,contracts.*}
                                       (re-export modules -> SAME objects)
  -> ugence_governance_contracts       (leaf: stdlib only)
```

The architectural path the contracts support (runtime proposes → TAP evaluates →
Decision Authority mints → ActionGate authorizes → Action Clearance validates →
runtime/provider executes) is served on the **provider-integration side**: the
`tap_provider` / `actiongate_provider` adapters and the provider framework speak
these neutral contracts. The capability packages that own each stage's authority
keep their own vocabularies (§5).

---

## 4. Canonical contract inventory & classification

All symbols are `PUBLIC_STABLE` and live only in this package. Machine-readable
snapshot: `packages/governance-contracts/public_api.json` (asserted equal to the
actual package by `tests/packaging/test_public_api.py`).

| Contract | Kind | Values / notable fields | Classification |
|---|---|---|---|
| `ProviderKind` | enum | ASSERTION_GOVERNANCE, ACTION_GOVERNANCE, EXTERNAL_EXECUTION | CANONICAL_NEUTRAL |
| `ProviderLifecycleState` | enum | REGISTERED…STOPPED (7) | CANONICAL_NEUTRAL |
| `FailureClass` | enum | RETRYABLE, TERMINAL, INDETERMINATE, CONFIGURATION, COMPATIBILITY | CANONICAL_NEUTRAL |
| `ActionGovernanceOutcome` | enum | AUTHORIZED, AUTHORIZED_WITH_CONSTRAINTS, DENIED, INDETERMINATE, EXPIRED | CANONICAL_NEUTRAL |
| `AssertionCoverage` | enum | SUPPORTED, UNSUPPORTED, INDETERMINATE, CONSTRAINED | CANONICAL_NEUTRAL |
| `ExecutionBusinessOutcome` | enum | SUCCEEDED, FAILED, REJECTED, PENDING, DUPLICATE, UNKNOWN | CANONICAL_NEUTRAL |
| `ActionGovernanceRequest/Result` | dataclass (frozen) | incl. `evidence_refs`, `decision_refs`, `idempotency_key`, `correlation_id`, `constraints`, `obligations`, `expiry`, `reason_codes`, `fingerprint` | CANONICAL_NEUTRAL |
| `AssertionGovernanceRequest/Result` | dataclass (frozen) | incl. `evidence_refs`, `evidence_coverage`, `constraints`, `obligations`, `fingerprint` | CANONICAL_NEUTRAL |
| `ExecutionDispatchRequest/Result`, `ExecutionObservation` | dataclass (frozen) | transport vs business-outcome split; `idempotency_key`, `correlation_id`, `fingerprint` | CANONICAL_NEUTRAL |
| `Provider`, `ActionGovernanceProvider`, `AssertionGovernanceProvider`, `ExternalExecutionProvider` | `Protocol` (runtime_checkable) | — | CANONICAL_NEUTRAL |
| `BaseProvider` | class | deterministic lifecycle bookkeeping | CANONICAL_NEUTRAL |
| `ProviderCapabilities/Compatibility/Descriptor/Health` | dataclass (frozen) | provider metadata | CANONICAL_NEUTRAL |
| `ProviderError` (+8 subclasses) | exception | each carries a `failure_class` | CANONICAL_NEUTRAL |
| `CONTRACT_VERSION` | constant | "1.0.0" | CANONICAL_NEUTRAL |
| `is_legal_transition`, `assert_transition` | function | on full namespace, **not** curated `api` | COMPONENT_OWNED (framework-internal mechanic) |
| `governance_providers.*`, GPF `errors/lifecycle/metadata/contracts.*` | modules | identity re-exports | LEGACY_COMPATIBILITY |
| tenant/environment id, authority-type field, error envelope | — | documented gaps G1–G3+ | FUTURE_NOT_IMPLEMENTED |

**No `DUPLICATED_EQUIVALENT` / `DUPLICATED_DIVERGENT` / `DEPRECATED` contract was
found** among the package's own vocabulary.

---

## 5. Outcome-vocabulary audit (§7)

The package uses **component-appropriate, non-conflated** outcome enums:
`ActionGovernanceOutcome` (authorization family), `AssertionCoverage` (evidence
family), `ExecutionBusinessOutcome` (execution family). These are peers and are
never string-converted into one another.

The other governance vocabularies the prompt lists live where they belong and are
**intentionally separate** (duplicate-contract policy **Outcome B — intentional
component ownership**):

| Vocabulary | Owner (live path) | Semantics | Interchangeable with a contract-layer enum? |
|---|---|---|---|
| `ClearanceStatus` = CLEAR/HOLD/BLOCK/ESCALATE (least-permissive-wins; no DENY) | `packages/capabilities/action-clearance` | operational clearance | **No** |
| `DecisionOutcome` = ADVANCE/HOLD/REJECT/DEFER; `ProposedOutcome`; `AuthorizationOutcome` | `packages/capabilities/decision-authority` | human-binding decision/authorization | **No** |
| Agent Runtime governance interfaces (`CLEAR/HOLD/BLOCK/ESCALATE` at the hook boundary) | `packages/runtime/agent-runtime` | runtime governance hook | **No** — Agent Runtime does not import this package |

There is **no loose string conversion** in the package that could broaden an
outcome, and no shared enum that forces materially-different semantics together.
Enforcement/mapping between these vocabularies is owned by the consuming
components, which fail closed on unknown values (verified in action-clearance:
`UNKNOWN` on a required signal → HOLD; `combine_statuses` empty → CLEAR).

---

## 6. Authority-boundary findings (§6)

For every exported contract the ten authority questions were checked. Highlights:

- **Descriptive/advisory vs binding:** every symbol here is descriptive DTO/enum
  or a structural `Protocol`; **none binds**. Binding is minted by Decision
  Authority, which does not use these types.
- **Can it broaden authority?** No. Outcomes are closed enums; there is no
  coercion path from a permissive value to a more-permissive one inside the
  package.
- **Reconstructable from values / stable across boundaries?** Yes — frozen
  dataclasses of scalars/tuples/mappings; identity is preserved across the legacy
  boundary (see §8).
- **Credentials/secrets?** None. Fields are ids, refs, and free-form string maps;
  no secret material is defined or persisted.
- **Exact-action identity:** the request contracts already carry `idempotency_key`,
  `correlation_id`, `evidence_refs`, `decision_refs`, `policy_refs`, and a
  `fingerprint` slot on results — enough to *reference* exact-action identity
  **without importing Agent Runtime models** (§8 below).
- **Validity/version semantics:** `ActionGovernanceResult.expiry`,
  `authorization_expired`, `EXPIRED` outcome, and `CONTRACT_VERSION` exist;
  finer-grained validity/authority-type fields are documented gaps (§9).

No accidental authority leakage was found. A runtime-visible `AUTHORIZED` value
does not imply this package authorized anything — the producing capability owns
that meaning, and this is stated in the package docstring/README.

---

## 7. Exact-action identity & Agent Runtime compatibility (§8, §9)

- The package **does not import Agent Runtime** and Agent Runtime **does not import
  the contracts** (verified: agent-runtime `tests/test_import_boundaries.py` lists
  `governance_providers` as a *forbidden* import). The two are independent, as
  required.
- Neutral exact-action **reference** carriage is available today via
  `idempotency_key` + `correlation_id` + `fingerprint` (a generic string slot) +
  `evidence_refs`/`decision_refs`. A dedicated neutral exact-action fingerprint
  reference / contract-version reference / validity-horizon is a documented,
  additive future field (§9), not a present defect.
- **Argument-value serialization caveat (Agent Runtime pre-v1):** tuple/list may
  canonicalize to the same JSON array; set/frozenset may materialize as lists;
  Python type identity is not necessarily preserved across canonical JSON. **This
  package does not define canonical action payloads or a fingerprint
  *serialization* function** — its `fingerprint` fields are opaque
  producer-supplied strings, and `dataclasses.asdict` + `json.dumps(sort_keys=…)`
  is used only in tests for equivalence pinning. Therefore this is recorded as an
  **external pre-v1 compatibility consideration** and **no runtime change is made**
  here. Should this package ever define canonical payload serialization, the
  documented preferred policy is to restrict values to JSON-compatible types
  (str/finite-number/bool/null/str-keyed mapping/ordered list) and reject
  tuple/set/frozenset/bytes/datetime/arbitrary objects unless a versioned contract
  encodes them.

---

## 8. Serialization, determinism & compatibility (§10, §16)

- Determinism guard: `tests/serialization/test_serialization_equivalence.py` pins
  `asdict`, canonical `json.dumps(sort_keys=True)`, a sha256 fingerprint, `repr`,
  constructor signatures, enum value maps, and error `failure_class` to a frozen
  baseline (`frozen_contract_fixtures.json`). Equivalent inputs → equivalent
  outputs; a field/enum drift fails loudly.
- No unstable `repr()` is used for identity; no cryptographic claims beyond a
  sha256 over sorted JSON in the *test* fixtures.
- **Compatibility is genuinely tested, not asserted.**
  `tests/compatibility/test_legacy_compat.py` imports the *actual* legacy paths
  (`governance_providers.errors`, `…lifecycle`, `…metadata`, `…contracts.base/…`,
  `…api`) and asserts **object identity** with the canonical symbols, plus a
  cross-boundary `isinstance`. This avoids the earlier "aliases called legacy
  compatibility without testing real imports" mistake. GPF's
  `tests/compatibility` + `tests/boundaries` (44 tests) further verify the
  re-export identity and dependency boundaries.
- **Compatibility path is two hops** (`governance_providers` → GPF → contracts),
  because the `governance_providers` namespace now aliases the Governance Provider
  Framework, which re-exports these contracts. Identity is preserved end to end
  (proven by the tests). This is more indirection than the README/MIGRATION prose
  implies ("logic-free re-export shims that import from this package"); the prose
  is accurate about the *result* (same objects) but understates the *mechanism*.
  Recorded as a documentation-accuracy note; no code change required.

---

## 9. Versioning & documented gaps (§11)

- Distinct axes exist: package version `0.1.0` (SemVer of the wheel) vs contract
  version `CONTRACT_VERSION = "1.0.0"` (the contract schema). They are **not**
  equated — correct.
- Additive optional fields → MINOR; enum expansion / field removal / semantic
  change → breaking → version transition. The frozen baseline + freeze verifier
  enforce "no silent reinterpretation."
- Deferred contract-evolution work is documented (not implemented) in
  `docs/migrations/governance_contracts/CONTRACT_GAPS_AND_EVOLUTION_PLAN.md`:
  G1 tenant identity, G2 environment identity, G3 authority-type/advisory-binding
  classification, standard error envelope, idempotency/expiry *contract*,
  CER/audit unification. All are `FUTURE_NOT_IMPLEMENTED`, most additive/MINOR.

---

## 10. Consumer matrix (summary; machine-readable in `governance_contracts_consumer_matrix.json`)

**Direct canonical consumer:** the Governance Provider Framework (declares
`ugence-governance-contracts>=0.1.0`, re-exports the whole surface).

**Provider-integration consumers (via the `governance_providers.*` shim):**
`tap_provider` (TAP assertion adapter), `actiongate_provider` (ActionGate action
adapter), `baseline_assertion_provider`, `baseline_action_provider`, `ai_hiring`,
`products/code-governance` (TAP/ActionGate adapters), `ugence_console_api`,
`enterprise_validation_pilot`, `comparative_governance_benchmark`,
`provider_heterogeneity_validation`, and `scripts/gpf_equivalence_capture.py`.
Every production consumer imports via the legacy shim; none imports the canonical
path directly (intentional — avoids cascading frozen-tree re-baselines).

**Named in the prompt but NOT consumers** (component-owned; boundary-forbidden):
Decision Authority, Action Clearance, StoryGraph, **Agent Runtime**, Model
Selection. Each owns its own vocabulary; migrating them into this package would be
**wrong** (Outcome B).

No consumer duplicates a canonical contract. `products/code-governance` actively
guards against it (tests assert `class ProviderKind` is absent from its source).

---

## 11. Duplicate-contract findings (§13)

- **Canonical symbols:** zero duplicates. `ProviderKind`, `ProviderLifecycleState`,
  `ActionGovernanceOutcome`, `AssertionCoverage`, `ExecutionBusinessOutcome`, the
  request/result dataclasses, the provider protocols, and the error taxonomy are
  each defined in exactly one place.
- **Unrelated name collisions (not duplicates):** `FailureClass` also appears in
  `agentic/enterprise_ontology/failure_classes.py` and
  `cloud_controller/**/observability/edge_cases.py` — different domains, no import
  relationship. Classification: **not** a duplicate; no action.
- **Component-owned lookalikes (Outcome B):** `ClearanceStatus`, `DecisionOutcome`,
  `AuthorizationOutcome` — intentionally separate; unsafe conversion prohibited.

No consolidation is warranted → this is **not** `CONTRACT_CONSOLIDATION_REQUIRED`.

---

## 12. Package independence (§14) — verified

`verify_governance_contracts_distribution.py` builds the wheel, asserts it bundles
**no foreign top-level package** and **ships `py.typed`**, installs it into a fresh
`--no-index` venv (no monorepo path), and proves inside that env: import from
site-packages; curated API resolves; contracts construct/serialize/round-trip;
enum & failure-class integrity; and **no unrelated Ugence package is importable**.
Imports are side-effect-free (no threads/network/db/scheduler; no credential
reads). Result: **PASS** (see §15).

---

## 13. Public API (§15) — verified & tightened

The curated `ugence_governance_contracts.api` exposes only stable contract objects
(33 symbols). It correctly **excludes** framework mechanics (`is_legal_transition`,
`assert_transition` stay on the full namespace for the framework only), test
utilities, internal serializers, product models, and mutable global registries. A
machine-readable `public_api.json` is now committed and asserted equal to the
actual package surface by `tests/packaging/test_public_api.py`.

---

## 14. CI (§17) — the material gap, now addressed

**Finding:** at audit start there was **no scoped CI workflow** for Governance
Contracts (only `agent-runtime-ci.yml` and `terminology-ci.yml` were recently
added; neither exercises this package). This is the one substantive gap.

**Correction:** added `.github/workflows/governance-contracts-ci.yml` (mirrors the
established agent-runtime pattern), path-filtered to the package + its
compatibility surfaces (`packages/governance-provider-framework/**`,
`governance_providers/**`) + the workflow file, on PRs and on default-branch
pushes. Jobs: (1) package suite + GPF compatibility/boundary tests; (2) wheel/sdist
build + isolated clean-venv install proof; (3) platform-freeze verification.

> CI status is reported honestly: the workflow **file exists and is locally
> reproduced**, but the GitHub Actions run has not yet been observed. Maturity
> stays `IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED` until a green run is seen.

---

## 15. Local verification evidence (offline)

| Check | Command | Result |
|---|---|---|
| Package suite | `pytest packages/governance-contracts/tests -q` | **48 passed** (45 pre-existing + 3 new public-API/py.typed) |
| GPF compatibility + boundaries | `pytest packages/governance-provider-framework/tests/{compatibility,boundaries} -q` | **44 passed** |
| Isolated single-wheel distribution | `python packages/governance-contracts/verify_governance_contracts_distribution.py` | **VERIFIED** — wheel `0.1.0`, only `ugence_governance_contracts/` (+ `py.typed`) + dist-info, no foreign packages, clean `--no-index` install, no unrelated Ugence package importable |
| Platform-freeze | `python -m platform_freeze.verify --manifest platform/PLATFORM_FREEZE_V1.json` | **PASS** (digest `d4ad77e1…` unchanged; freeze does not track this leaf) |

---

## 16. Corrections made (bounded to Governance Contracts + its scoped CI)

1. `.github/workflows/governance-contracts-ci.yml` — **new** scoped CI (§17 gap).
2. `src/ugence_governance_contracts/py.typed` + `pyproject.toml` package-data —
   ship the PEP 561 marker (the package is fully typed; §14).
3. `public_api.json` + `tests/packaging/test_public_api.py` — machine-readable
   public-API snapshot and an agreement test (§15).
4. `verify_governance_contracts_distribution.py` — assert `py.typed` ships in the
   wheel and is installed.
5. Audit artifacts — this document + `governance_contracts_consumer_matrix.json`.

No contract field, enum value, default, serialization, or authority meaning was
changed. No consumer was migrated. No legacy path was deleted.

## 17. Explicitly deferred / out of scope

Contract-evolution fields (tenant/environment id, authority-type, error envelope,
idempotency/expiry contract, CER/audit unification) — documented, not implemented.
Consumer migration off the `governance_providers` shim; removal of the legacy shim
(target `governance_providers` 0.2.0); any Agent Runtime change; H22; product
packaging. Tightening the README/MIGRATION prose about the two-hop compat
mechanism is a documentation nicety, not a functional change.

## 18. Decision

**`PACKAGE_HARDENING_REQUIRED`** — the package's contracts, boundaries, public
API, isolation, and existing tests were already correct; the corrections are
narrow packaging/CI/typing/documentation additions. Not
`CONTRACT_CONSOLIDATION_REQUIRED` (no real duplicates) and not
`ARCHITECTURAL_CONFLICT_FOUND` (authority semantics are consistent and
component-owned). H22 was **not** implemented.
