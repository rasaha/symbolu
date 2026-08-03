# Architecture

The Agent Workforce Composer (AWC) is a **pure, offline, deterministic** planning
capability. It is a leaf: it depends only on the Python standard library and
`pydantic`. It has no runtime, no side effects, no network, no clock reads
(logical time is always injected), and no agent execution.

## Layering

```
serialized WorkflowIR (workflow_ir.v1)         <-- upstream, data-only seam
        │
   adapter.py            CompilerWorkflowAdapter / adapt_compiled_workflow
        │  produces
   workflow.py           WorkflowRoleRequirement[], NonAgentDisposition[],
        │                WorkflowNodeDisposition[] (total node accounting)
        │
   agents.py             AgentProfile, AgentCapability*, AgentRegistrySnapshot
   policy.py             EnterpriseAgentPolicy, EligibilityPolicy
        │
   eligibility.py        evaluate_agent_eligibility / evaluate_registry_for_role /
        │                evaluate_workflow_eligibility (hard gate, fail-closed)
        │  produces
   AgentEligibilityResult (role × agent), RoleEligibilityReport,
   EligibilityExplanation, EligibilityReplayRecord
```

Support modules: `contracts.py` (neutral enum mirrors of the compiler vocabulary),
`reasons.py` (elimination taxonomy), `canonical.py` (frozen base model + canonical
JSON + digests), `fingerprint.py` (content-addressing), `fixtures.py` (synthetic
demos), `cli.py` (offline CLI), `version.py` (versions + honest maturity).

## Why the compiler seam is data-only

To remain a leaf importable outside the monorepo, AWC never imports
`ugence_policy_workflow_compiler`. The adapter consumes a **serialized**
`workflow_ir.v1` document (a dict / JSON). `contracts.py` mirrors the compiler's
`NodeKind` / `EdgeKind` / `AuthorityDisposition` / `CapabilityId` **by value**, so
a real compiled package's serialized IR parses losslessly. The optional
`compiler-reference` extra proves this against the live compiler in CI.

## Determinism

Every object is frozen and content-addressed. All digests are `sha256:<hex>` over
canonical JSON (sorted keys, enums-by-value, tuples/sets normalized). Registry
snapshots are stored in canonical (id-sorted) order, so digests are independent of
input container ordering. Identical logical inputs yield byte-identical results
across runs and processes.
