# Changelog — ugence-agent-runtime

All notable changes to the independent Agent Runtime distribution are recorded here.
This project follows semantic versioning for the distribution.

## 0.1.1 — post-merge governance-safety & fidelity correction

Corrects issues found after 0.1.0 merged (PR #1287). This is a bounded correction
phase, **not** H22.

### Changed (governance safety)
- **Fail closed by default.** The default governance hook is now
  `UnconfiguredGovernanceHook`, which BLOCKs every consequential transition with reason
  `GOVERNANCE_NOT_CONFIGURED`. The previous default (`NoopGovernanceHook`, always CLEAR)
  was fail-open and is removed as a default.
- **Exact-action binding.** The runtime now constructs an immutable `TransitionProposal`
  with a deterministic fingerprint before evaluation, and the governance hook evaluates
  that proposal. A CLEAR result is honored **only** when it is bound to the exact
  proposal fingerprint, carries a non-empty binding reference, and is not expired; the
  provider invocation is re-fingerprinted immediately before the call. Any missing,
  mismatched, unreferenced, expired, or drifted binding fails closed.
- `GovernanceHook.evaluate(proposal, evaluation_time)` replaces the prior
  `evaluate(context, proposed_transition, evaluation_time)` signature.
- `GovernanceEvaluation` gains `proposal_fingerprint`, `authorization_reference`,
  `clearance_reference`; `valid_until` is now validated.

### Changed (honesty)
- **Compatibility reframed** as honest coexistence (Outcome B). The legacy runtime and
  the kernel are different implementations; the invented identity-preserving aliases and
  the "no duplicate implementation" claim are removed. `ugence_agent_runtime.compat` now
  offers a migration map + classification, not aliases.
- Documentation corrected: the package is described as a coordination kernel, not a
  behavior-preserving relocation; maturity is `IMPLEMENTED_AND_OFFLINE_VERIFIED`.

### Added
- `TransitionProposal` (+ `compute_fingerprint`), `UnconfiguredGovernanceHook`,
  `AllowAllGovernanceHook` (explicit, opt-in, unsafe), `validate_clearance`.
- Post-merge fidelity audit + fidelity matrix; governance-binding test suite; a scoped
  `agent-runtime-ci` GitHub workflow.

### Renamed / deprecated
- `NoopGovernanceHook` → `AllowAllGovernanceHook` (the old name remains as a deprecated
  alias that emits `DeprecationWarning`); never a default.

## 0.1.0 — first independent distribution

The Agent Runtime becomes an independently buildable and installable, domain-neutral
capability. This is a packaging and boundary-hardening release; no multi-workflow
orchestration (H22) is added.

> **Correction (see 0.1.1):** 0.1.0 described this as behavior-preserving with "no
> duplicate implementation." That was inaccurate — the package is a *new coordination
> kernel* that coexists with the legacy proposer. The 0.1.1 entry above supersedes those
> claims.

### Added
- Independent Python distribution `ugence-agent-runtime` (namespace
  `ugence_agent_runtime`), stdlib-only, `py.typed`.
- Curated public API (`ugence_agent_runtime.api`): `AgentRuntime`, `AgentRuntimeConfig`,
  workflow/task models, provider interfaces + registry, persistence interfaces +
  in-memory reference, neutral governance boundary, recovery, error taxonomy, and
  convenience functions.
- Neutral governance-integration boundary (`GovernanceHook`) with the established
  `CLEAR / HOLD / BLOCK / ESCALATE` vocabulary and a fixed, non-broadening mapping to
  runtime coordination behavior.
- Neutral provider/tool execution boundary (no vendor coupling).
- Deterministic workflow/task state machine with an auditable transition table.
- Checkpoints with content-digest integrity, and durable recovery that performs no
  external provider or governance call.
- Observability: deterministic, replayable event stream and neutral event types.
- Compatibility aliases (`ugence_agent_runtime.compat`) — *reframed in 0.1.1 as honest
  migration guidance, not identity-preserving aliases.*
- Package-local test suite, isolated-install verification, and a standalone demo.

### Boundary decisions
- The core imports **no** concrete governance (TAP, Decision Authority, ActionGate,
  Action Clearance, Code Governance, StoryGraph), **no** robotics, **no** product
  package, and **no** LLM/agent framework.
- Concrete governance and provider adapters remain outside this package (application
  layer or optional integration packages).

### Not included (by design)
- H22 multi-workflow orchestration, distributed scheduling, agent planning/memory,
  LLM routing, new provider kinds, enforcement, external database, GitHub execution.
