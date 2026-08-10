# Contract Ownership Matrix — Governance Provider Framework

Audit-only. **No contract is moved or modified in this phase.** Ownership is
assigned by *semantic* criteria (capability-neutral, authority-neutral, stable
across implementations, genuinely shared at a lower layer) — not by "many
packages import it."

## Ownership key
- **GC** = Governance Contracts (`ugence_governance_contracts`) — pure neutral leaf
- **GPF** = Governance Provider Framework (`governance_providers`) — framework mechanism
- **TAP / ActionGate / DA / ACP / StoryGraph** = a bounded capability
- **PROV** = a concrete provider package
- **KERNEL** = `decision_governance.api` (kernel ports/contracts)

## 1. Public models/enums currently reachable through `governance_providers.api`

| Symbol | Correct semantic owner | Current physical home | Aligned? | Rationale |
|---|---|---|---|---|
| `ProviderKind` | **GC** | `ugence_governance_contracts.metadata` (shim in GPF) | ✅ | capability-neutral provider taxonomy |
| `ProviderDescriptor` | **GC** | GC (shim) | ✅ | neutral registration descriptor |
| `ProviderCapabilities` | **GC** | GC (shim) | ✅ | neutral capability declaration |
| `ProviderCompatibility` | **GC** | GC (shim) | ✅ | neutral version-compat declaration |
| `ProviderHealth` | **GC** | GC (shim) | ✅ | neutral health snapshot |
| `ProviderLifecycleState` + transitions | **GC** | `ugence_governance_contracts.lifecycle` (shim) | ✅ | neutral lifecycle state machine |
| `Provider`, `BaseProvider` | **GC** | `ugence_governance_contracts.contracts.base` (shim) | ✅ | neutral provider protocol/base |
| `AssertionGovernance{Request,Result,Provider}`, `AssertionCoverage` | **GC** | GC (shim) | ✅ | neutral assertion-family envelope (kind-level, not TAP-specific) |
| `ActionGovernance{Request,Result,Provider,Outcome}` | **GC** | GC (shim) | ✅ | neutral action-family envelope (kind-level, not ActionGate-specific) |
| `Execution{DispatchRequest,DispatchResult,Observation,BusinessOutcome}`, `ExternalExecutionProvider` | **GC** | GC (shim) | ✅ | neutral execution-family envelope |
| Error taxonomy (`ProviderError` … `FailureClass`) | **GC** | `ugence_governance_contracts.errors` (shim) | ✅ | neutral provider error taxonomy |
| `CONTRACT_VERSION`, `__version__`, `is_contract_compatible`, `is_kernel_compatible`, `TARGET_KERNEL_MAJOR` | **GPF** | `governance_providers.version` | ✅ | framework's own version/compat mechanism |
| `ProviderRegistry` | **GPF** | `governance_providers.registry` | ✅ | framework registration/discovery mechanism |
| `resolve`, `ResolutionRequest`, `ResolutionRecord`, `SelectionRule` | **GPF** | `governance_providers.resolution` | ✅ | framework deterministic-selection mechanism |
| `ProvidersConfiguration`, `ProviderEntry` | **GPF** | `governance_providers.configuration` | ✅ | framework declarative-config mechanism |
| `ProviderInvocationRecord`, `ProviderInvocationLog`, `record_invocation` | **GPF** | `governance_providers.observability` | ✅ | framework observability mechanism |
| `ActionGovernanceControlPlaneAdapter` | **GPF** (kernel-bound port) | `governance_providers.adapters` | ✅ (see note) | framework↔KERNEL adapter; correctly a framework port, not a capability |
| `ExternalExecutionAdapter` | **GPF** (kernel-bound port) | `governance_providers.adapters` | ✅ | framework↔KERNEL adapter |
| `AssertionAssessmentIntegration`, `AssertionAssessment`, `AssertionLinkedRecordAdapter` | **GPF** (kernel-bound port) | `governance_providers.adapters` | ✅ | framework↔KERNEL assessment integration |

**Result:** every public contract is already in its correct semantic layer. The
neutral contracts sit in **GC**; the framework mechanism (registry, resolution,
config, observability, versioning) and the kernel-bound adapters sit in **GPF**.
There is **no** neutral contract still trapped inside the framework, and **no**
framework mechanism misfiled into Governance Contracts.

## 2. Adapter/port note (the one nuance)

The three `adapters/*` classes are framework **ports** that depend on
`decision_governance.api`. They are correctly framework-owned (not
capability-owned), because they translate *any* provider of a kind onto a kernel
port without knowing the concrete vendor. Their kernel dependency is the
designed framework↔kernel seam, not a contract-ownership error. If a future phase
splits the framework into `sdk` (pure) + `runtime`/`adapters` (kernel-bound)
distributions, these three modules are the natural `runtime` boundary — but they
do **not** belong in Governance Contracts (GC must stay a pure leaf importing
nothing but stdlib).

## 3. Capability-owned contracts (correctly outside the framework)

| Model family | Owner | Home | Note |
|---|---|---|---|
| `Tap*` (Outcome, EvidenceClass, EvidenceItem, Constraint, Obligation, EvaluationRequest/Result, Rule, Engine) | **TAP** | `tap_provider/core` | vendor vocabulary; correctly private to the provider |
| `ActionGate*` (Outcome, Constraint, Obligation, Request, Decision, Engine, ConstrainedRule) | **ActionGate** | `actiongate_provider/core.py` | vendor vocabulary; correctly private |
| Kernel ports/contracts (`ActionControlPlanePort`, `ExternalExecutionPort`, `LinkedRecordPort`, `LinkedRecordSnapshot`, `ActionAuthorizationResponse`, …) | **KERNEL** | `decision_governance.api` | correctly kernel-owned; framework adapters consume them |

## 4. Contract *gaps* documented for future versioned work (do NOT act now)

These are candidates a later, contract-versioned phase may consider. They are
**recorded only** — this audit does not modify Governance Contracts.

1. **Provider observability record.** TAP and ActionGate each ship their own
   invocation record/log (supersets of GPF's `ProviderInvocationRecord`). If the
   *neutral* subset (provider_id, kind, operation, completed, outcome, trace_id,
   error/failure class) is genuinely shared and stable, a neutral
   `ProviderInvocationRecord` base could live in **GC** with capability
   extensions layered on. Not proven shared-and-stable enough to move now.
2. **Conformance report envelope.** `CheckResult` and the conformance-report
   shape are re-implemented in GPF, TAP, and ActionGate. A neutral
   conformance-report base is a plausible GC (or GPF-public) contract, but it is
   test-harness scaffolding, not a runtime contract — low priority.
3. **`CONTRACT_VERSION` provenance.** It is published by GPF (`version.py`) but is
   fundamentally a property of the *contracts* in GC. A future phase could let GC
   own the canonical `CONTRACT_VERSION` and have GPF re-export it, tightening the
   "contracts are the versioned artifact" story.

None of these blocks the framework's canonical-package migration; all are
additive, MINOR-or-lower, and independent of a physical move.

## 5. Ownership verdict

- Governance Contracts already owns the full neutral contract closure (31 public
  symbols per the contracts migration report). **Aligned.**
- The framework owns only *mechanism* + *kernel adapters*. **Aligned.**
- No contract needs to move *out of* the framework for the migration — that carve
  was completed by the Governance Contracts migration. The framework is
  contract-clean and can migrate as a coherent unit.
