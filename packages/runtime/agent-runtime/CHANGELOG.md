# Changelog — ugence-agent-runtime

All notable changes to the independent Agent Runtime distribution are recorded here.
This project follows semantic versioning for the distribution.

## 0.1.0 — first independent distribution

The Agent Runtime becomes an independently buildable and installable, domain-neutral
capability. This is a packaging, boundary-hardening, and dependency-cleanup release;
runtime behavior is preserved and no multi-workflow orchestration (H22) is added.

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
- Compatibility aliases (`ugence_agent_runtime.compat`) that re-export canonical
  symbols (identity-preserving; no duplicate implementation) with deprecation warnings.
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
