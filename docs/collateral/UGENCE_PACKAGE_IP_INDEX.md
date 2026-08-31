# Ugence — Package IP Index

Every independently packaged module under `packages/`, one or two lines each.
Companion to [`UGENCE_PLATFORM_ONE_PAGER.md`](UGENCE_PLATFORM_ONE_PAGER.md).
Descriptions are taken from each package's own README; they describe what is
**built and packaged**, not what is externally deployed. The platform is
pre-revenue and pre-external-deployment.

## Governance kernel — the authority layer

| Module | What it is |
| --- | --- |
| `ugence-risk-authority` | Turns an approved governance decision into cryptographically bound, scoped, time-bound, revocable runtime authority — and enforces it at the exact point of action. The sole machine-execution authority artifact. |
| `ugence-decision-authority` | Domain-neutral governance kernel deciding when an AI recommendation may become a binding business decision: decision cases, authorization, execution, reconciliation. |
| `ugence-policy-authority` | The one platform-wide policy authority: issues, signs, registers, resolves, verifies and revokes policy versions for any registered policy family. |
| `ugence-governance-contracts` | Canonical neutral contract layer every capability depends on, so capabilities never depend on each other. Leaf package, no authority of its own. |
| `ugence-governance-provider-framework` | Registration, resolution, invocation, observation and conformance testing of governance providers. Owns no governance authority. |
| `ugence-trusted-evidence-authority` | Trusted-evidence contracts plus the verification authority: trust anchors, key trust and revocation, signing, independent verification. |
| `ugence-benchmark-registry` | Frozen benchmark identity and lifecycle contracts — the shared, platform-wide benchmark definition layer. |
| `ugence-benchmark-registry-authority` | Registry and exact-resolution contracts above the frozen identity layer. Resolves; computes nothing. |
| `ugence-uvi-policy-contracts` | Immutable contract shapes for Ugence Value Intelligence governed-assessment context and policy artifacts. Schema layer only. |

## Governance providers — pluggable evaluators

| Module | What it is |
| --- | --- |
| `ugence-actiongate-provider` | **ActionGate** — action-governance provider: given a proposed action and its authority, policy, risk, evidence and decision context, returns authorized / authorized-with-constraints / denied / indeterminate. |
| `ugence-tap-provider` | **TAP** — assertion-governance provider: given a material assertion and evidence references, returns supported / unsupported / constrained / indeterminate, component by component. |

## Control-plane capabilities

| Module | What it is |
| --- | --- |
| `ugence-context-minimization` | Deterministic, extractive, fail-closed context reduction that preserves a caller-defined equivalence condition. Never generative; fails closed when equivalence cannot be established. |
| `ugence-action-clearance` | Decides whether an already-authorized exact action remains operationally CLEAR immediately before execution. May narrow, hold, escalate or block — never broaden. |
| `ugence-model-selection` | **Model Authority** — determines which model, if any, is *permitted* to execute the current request under policy and runtime constraints. |
| `ugence-llm-steering-controller` | Deterministic, provider-neutral, advisory-only LLM routing: candidate discovery, fail-closed hard constraints applied before scoring, then ranking. |
| `ugence-storygraph` | Advisory sequence-risk analyzer: detects when individually-acceptable actions assemble a prohibited capability, and emits evidence for a downstream authority to escalate. |
| `ugence-agent-workforce-composer` | Deterministic offline planning: which workflow nodes may be performed by AI agents, what capabilities those roles require, which registered agents are eligible under frozen hard constraints. |
| `ugence-agent-value-readiness` | Experimental, advisory readiness-determination evaluator with a fail-closed trust boundary. Not a deployment authority. |
| `ugence-governed-value` | Experimental post-deployment value-calculation kernel over caller-reported, unverified inputs. Cannot claim a figure is observed, attributed or verified. |
| `ugence-policy-workflow-compiler` | Compiles a reviewed governance policy pack into a deterministic governed-workflow artifact plus an assurance package: workflow IR, assurance manifest, test scenarios, audit schema, structural diffs, content-addressed package. |

## Execution runtime

| Module | What it is |
| --- | --- |
| `ugence-agent-runtime` | Domain-neutral execution-coordination kernel for agent and workflow execution. Deliberately excludes agent planning, reasoning and memory. |

## Cloud scaling — advisory through controlled execution

| Module | What it is |
| --- | --- |
| `ugence-cloud-scaling-controller` | Deterministic, provider-neutral, advisory-only adaptive scaling controller producing explainable recommendations from normalized observations. |
| `ugence-cloud-scaling-operations` | The controlled-execution layer: in LIVE mode, with credentials and explicit external authorization, it can patch Kubernetes deployment scale and trigger ArgoCD syncs. |
| `ugence-cloud-scaling-risk-integration` | Phase 4C — one-way, non-executing adapter projecting a capacity recommendation into the neutral Risk Authority subject-risk contract; stops at a non-executable risk decision. |
| `ugence-cloud-scaling-producer-attestation` | Phase 5B-0A — establishes *who produced* a recommendation. A verified attestation grants nothing. |
| `ugence-cloud-scaling-policy-authenticity` | Phase 5B-0B — establishes that one exact policy version was authentically issued and valid at an injected instant. A verified proof grants nothing. |
| `ugence-cloud-scaling-authorization-contracts` | Phase 5A — turns a reconciled projection, risk binding, attestation evidence and policy binding into an explicitly non-authoritative capacity-authorization *candidate*. |

## Risk Authority runtime integrations (RA-4.5 → RA-8)

| Module | What it is |
| --- | --- |
| `ugence-risk-authority-runtime` | RA-4.5 — fail-closed composition of the machine-authority owner with Decision Authority and ActionGate into a single execution-eligibility decision. |
| `ugence-risk-authority-evidence-runtime` | RA-5 — trusted evidence admission and control assurance, closing the gap where a caller could self-assert a control status. |
| `ugence-risk-authority-status-runtime` | RA-6 — post-issuance authority lifecycle: revocation and epoch propagation around the single signed authorization envelope. |
| `ugence-risk-authority-runtime-assurance` | RA-7 — observes runtime trajectories through the neutral event seam and emits authority-reassessment signals on material deviation. Observes; does not own consequences. |
| `ugence-risk-authority-execution-assurance` | RA-8 — post-execution reconciliation: did the actual effect match what was authorized, and should the discrepancy reassess future machine authority? |
| `ugence-context-minimization-token-accounting-runtime` | CM-TA1 — narrow one-way integration wiring Context Minimization token accounting to Agent Runtime provider-attempt telemetry and budgets. |

## Governance verticals

| Module | What it is |
| --- | --- |
| `ugence-ai-hiring` | AI-assisted hiring **governance** product: audited workflow state machine, deterministic evidence normalization, decision cases, and the AI/human separation enforced in types, services, persistence and API permissions. |
| `ugence-procurement` | Governed purchase approvals and authorized supplier actions on the Decision Authority kernel, with the same separation enforced in code rather than documentation. |

---

**The pattern across all of it:** each module owns exactly one decision, states
plainly what it does *not* grant, and hands off across a typed boundary. That is
what makes the loop — propose → govern → run → respond → learn — auditable
end-to-end.
