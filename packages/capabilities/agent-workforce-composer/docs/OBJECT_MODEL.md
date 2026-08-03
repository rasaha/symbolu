# Object Model

Every object is a frozen, `extra='forbid'` pydantic model, content-addressed with a
`sha256:<hex>` fingerprint over its canonical JSON. Contract version `awc.v1`.

## Workflow-derived
- **`WorkflowRoleRequirement`** — an AI-agent-eligible role. See COMPILER_ADAPTER.md
  for field provenance. Carries `role_fingerprint`.
- **`NonAgentDisposition`** — a node not assigned to an agent: `disposition`
  (any `NodeDisposition` except `AI_AGENT_ELIGIBLE`), `reason_codes`,
  `canonical_owner`, `authority_context`, `human_review_required`, `provenance`,
  `source_package_digest`, `fingerprint`.
- **`WorkflowNodeDisposition`** — the one-per-node accounting record.
- **`CompilerAdaptationResult`** — `node_dispositions`, `role_requirements`,
  `non_agent_dispositions`, `diagnostics`, `adaptation_fingerprint`, plus the
  `accounting_holds()` invariant.

## Agent-derived
- **`AgentCapability`** — a claimed capability (`declared`). Claims are audited,
  never trusted as measured evidence.
- **`AgentCapabilityEvidence`** — one immutable evidence item: `evidence_class`
  (DECLARED / MEASURED / OBSERVED), `measured_at`, `valid_until`, benchmark/dataset
  refs, `provenance`, `evidence_fingerprint`. `is_expired(now)`.
- **`CapabilityEvidenceSet`** — resolution helpers; `best_class(...)` returns the
  highest-precedence non-expired class.
- **`AgentProfile`** — identity + capability claims + measured/observed evidence
  pointers + runtime requirements. Distinguishes declared claims from measured
  evidence. Carries `profile_fingerprint`.
- **`AgentRegistrySnapshot`** — a frozen planning input. Integrity enforced at
  construction (no duplicate identity, no duplicate evidence id, all evidence
  resolves). `logical_digest()` is order-independent; build via
  `build_registry_snapshot(...)`.

## Policy
- **`EnterpriseAgentPolicy`** — hard constraints only (providers, residency,
  deployment, security floor, approved/forbidden versions, tools, permission scope,
  authority ceiling, required evidence classes, hard cost/latency/quality limits,
  audit requirements, `fail_closed_on_unknown`). No preference weights.
- **`EligibilityPolicy`** — the interpreter's knobs: `evaluation_order`,
  `evidence_precedence`, unknown/expired handling, `require_measured_or_observed_for_hard`,
  `short_circuit`.

## Result
- **`ConditionResult`** — one condition's `verdict` (PASS/FAIL/UNKNOWN), `reason`,
  `criticality`.
- **`AgentEligibilityResult`** — `state` (ELIGIBLE/INELIGIBLE/INDETERMINATE/
  INVALID_INPUT), `passed_conditions`, `failed_conditions`, `unknown_conditions`,
  `elimination_reasons`, the pinned digests, and `result_fingerprint`.
  **No score/rank/winner field exists.**
- **`RoleEligibilityReport`** — every agent's result for a role; `eligible_agent_ids`,
  `eliminated_agent_ids`, `indeterminate_agent_ids`, `outcome`
  (`HAS_ELIGIBLE_AGENT` | `NO_ELIGIBLE_AGENT`).
- **`EligibilityExplanation`**, **`EligibilityReplayRecord`**,
  **`WorkflowEligibilityResult`**.
