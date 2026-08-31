# Policy Workflow Compiler — Contract Audit (for AWC consumption)

**Purpose.** Freeze the *exact* live public contract of the implemented Policy
Workflow Compiler so the Agent Workforce Composer (AWC) consumes canonical types
instead of inventing a second conceptual workflow representation
(`WorkflowGraphSource` in the merged AWC docs). All names below are copied from
source at the merge commit of PR #1303 (`96afb58a…`).

Package: `packages/tooling/policy-workflow-compiler/`
Distribution: `ugence-policy-workflow-compiler` · Namespace: `ugence_policy_workflow_compiler`
Supported import surface: **`ugence_policy_workflow_compiler.api`** (71 frozen public names)
Versions: distribution `0.1.0`, product `0.1.0`, IR `workflow_ir.v1`, schema `policy_pack.v1`, registry `capability_registry.v1`.

## 1. Canonical types AWC must consume

| Concept | Canonical live type | Defined at |
|---|---|---|
| Workflow representation | **`WorkflowIR`** | `compiler/workflow_ir.py:93` |
| Workflow node | **`WorkflowNode`** | `compiler/workflow_ir.py:56` |
| Workflow edge | **`WorkflowEdge`** | `compiler/workflow_ir.py:82` |
| Node categories | **`NodeKind`** (14) | `compiler/workflow_ir.py:27` |
| Edge categories | **`EdgeKind`** (9) | `compiler/workflow_ir.py:44` |
| Capability identity | **`CapabilityId`** (8) | `models/common.py:84` |
| Advisory vs authoritative | **`AuthorityDisposition`** (`ADVISORY`/`AUTHORITATIVE`) | `models/common.py:104` |
| Capability metadata | **`CapabilityDefinition`**, **`CapabilityManifest`**, **`CapabilityRegistry`** | `compiler/capability_registry.py:28,145`; `compiler/release.py:43` |
| Compiled package identity | **`CompiledReleasePackage`**, **`ReleaseManifest`**, `structural_digest` | `compiler/release.py:64,53` |
| Fail-closed default | **`BlockBehavior`** (`WorkflowNode.failure_behavior`) | field on `WorkflowNode` |

> There is **no** `WorkflowGraphSource` type in the compiler. That name exists
> only in the AWC design documents. The canonical upstream representation is
> `WorkflowIR`. This is the central semantic-drift finding.

## 2. `WorkflowIR` (exact fields — `workflow_ir.py:96`)

- `policy_pack_id: str`
- `policy_pack_version: int`
- `ir_version: str = "workflow_ir.v1"`
- `nodes: Tuple[WorkflowNode, ...] = ()`
- `edges: Tuple[WorkflowEdge, ...] = ()`
- `referenced_capabilities: Tuple[str, ...] = ()`
- property `node_kinds`; method `logical_digest()` (digest over nodes+edges only, no timestamps).

## 3. `WorkflowNode` (exact fields — `workflow_ir.py:59`)

| Field | Type | Meaning (AWC relevance) |
|---|---|---|
| `node_id` | `str` | Content-addressed id (see §5). **Stable node-to-role mapping key.** |
| `kind` | `NodeKind` | Node category. Drives classification (see §6). |
| `owning_capability` | `CapabilityId` | The capability that owns this node's authority function. **Capability-ownership propagation.** |
| `authority_type` | `str = ""` | Free-text label (⚠ distinct from the `AuthorityType` enum in `models/common.py:112`). |
| `disposition` | `AuthorityDisposition` | `ADVISORY` or `AUTHORITATIVE`. **Authority-boundary preservation.** |
| `public_contract_target` | `str = ""` | Owning capability's public-contract module (e.g. `ugence_decision_authority.api`). |
| `input_object_ids` | `Tuple[str, ...] = ()` | Policy-object references feeding the node. **Input object references.** |
| `output_contract` | `str = ""` | Declarative output description. |
| `failure_behavior` | `BlockBehavior = BLOCK` | Fail-closed default ("never proceed by default"). |
| `audit_requirements` | `Tuple[str, ...] = ()` | Audit-field names the node must emit. **Provenance/audit propagation.** |
| `label` | `str = ""` | Human label. |

## 4. `NodeKind` (14) and `EdgeKind` (9) — verbatim

**`NodeKind`** (`workflow_ir.py:27`): `EVIDENCE_REQUIREMENT`, `EVIDENCE_ADMISSIBILITY`,
`DECISION_RULE`, `AUTHORITY_CHECK`, `APPROVAL_GATE`, `SEGREGATION_OF_DUTIES_GATE`,
`PROHIBITED_CONDITION`, `EXCEPTION_BRANCH`, `OVERRIDE_GATE`, `ACTION_CONSTRAINT`,
`SEQUENCE_RISK_CHECK`, `ACTION_CLEARANCE_REQUIREMENT`, `AUDIT_EMISSION`, `TERMINAL_OUTCOME`.

**`EdgeKind`** (`workflow_ir.py:44`): `NEXT`, `ON_PASS`, `ON_FAIL`, `ON_MISSING`,
`ON_EXCEPTION`, `ON_OVERRIDE`, `ON_ESCALATE`, `ON_DENY`, `ON_INDETERMINATE`.

## 5. Node identity (content-addressing) — `make_node_id()` `workflow_ir.py:119`

`node_id = "node_{kind.lower()}_{sha256(...)[:12]}"` where the digest covers
`{kind, owning_capability, sorted(input_object_ids)}`. **Identity is a pure
function of (kind, owning capability, input object ids).** This is the stable key
AWC must use to map a node → a `WorkflowRoleRequirement`, and to detect
semantic drift when the upstream contract changes.

## 6. Capability registry & governance ownership — `capability_registry.py`

`CapabilityId` (8): `TAP`, `DECISION_AUTHORITY`, `ACTION_GATE`, `ACTION_CLEARANCE`,
`STORYGRAPH`, `MODEL_SELECTION`, `OPTIONAL_ORCHESTRATOR`, `COMPILER`.

Each has a frozen `CapabilityDefinition` (`capability_registry.py:49`) with
`disposition`:

| CapabilityId | disposition | mandatory? | authority owned (verbatim) |
|---|---|---|---|
| `TAP` | ADVISORY | optional | assertion-support evaluation (evidence admissibility) |
| `DECISION_AUTHORITY` | **AUTHORITATIVE** | **required** | governs when a recommendation may become a binding decision |
| `ACTION_GATE` | **AUTHORITATIVE** | optional | exact-action authorization (range/digest/once-only) |
| `ACTION_CLEARANCE` | **AUTHORITATIVE** | optional | commit-time operational clearance of an already-authorized action |
| `STORYGRAPH` | ADVISORY | optional | sequence-risk analysis (advisory) |
| `MODEL_SELECTION` | ADVISORY | optional | policy-bounded model eligibility (mandatory) + selection (advisory) |
| `OPTIONAL_ORCHESTRATOR` | ADVISORY | optional | optional workflow composition (bypassable) |
| `COMPILER` | ADVISORY | required | structural nodes (evidence collection, audit emission, terminal outcomes) |

**There is no single boolean "is-governance" field.** Governance ownership is the
combination of `owning_capability` (an authoritative capability) + `disposition ==
AUTHORITATIVE` + governance `NodeKind`. The AWC adapter must never reclassify an
`AUTHORITATIVE` node owned by Decision Authority / ActionGate / Action Clearance
as agent work.

## 7. Compiled package identity & digest — `release.py`, `serialization/`

- `CompiledReleasePackage` bundles `manifest`, `policy_pack`, `workflow_ir`,
  `capability_manifest`, `assurance_manifest`, `coverage_matrix`, `audit_schema`,
  `approval_record?`, `validation_report`, `structural_digest`, `release_metadata`.
- Logical (content-addressed) digest = `sha256:` over
  `{policy_pack (status-stripped), workflow_ir, capability_manifest,
  assurance_manifest, coverage_matrix, audit_schema, compiler_distribution_version}`
  (timestamps & release_metadata excluded). Identical approved input + compiler
  version → identical logical digest. **AWC must pin and echo this digest + the
  compiler distribution version in every plan for replay.**

## 8. Versioned AWC upstream adapter contract — `CompilerWorkflowAdapter` [PROPOSED, not implemented in Phase 0]

The AWC upstream seam is a **pure, data-only adapter** — proposed name
**`CompilerWorkflowAdapter`** — that consumes a compiler `WorkflowIR` (never
importing runtime providers) and produces AWC planning inputs:

```
ugence_policy_workflow_compiler.WorkflowIR
        │  (data only, no provider imports)
        ▼
CompilerWorkflowAdapter.classify(node) → NodeDisposition
        ▼
WorkflowRoleRequirement[]     (nodes eligible for / requiring an AI agent role)
NonAgentDisposition[]         (nodes that are governance-owned, human, or deterministic)
```

### 8.1 Node classification (the seven outcomes)

| Outcome | Trigger (from `WorkflowNode`) |
|---|---|
| `EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP` | `owning_capability ∈ {DECISION_AUTHORITY, ACTION_GATE, ACTION_CLEARANCE}` **and** `disposition == AUTHORITATIVE` |
| `HUMAN_AUTHORITY_REQUIRED` | `kind ∈ {APPROVAL_GATE, OVERRIDE_GATE}` or `authority_type` names a human authority (`HUMAN_APPROVER`/`HUMAN_REVIEWER`/`COMMITTEE`/`EXTERNAL_AUTHORITY`) |
| `HUMAN_REVIEW_REQUIRED` | `kind == SEGREGATION_OF_DUTIES_GATE`, or an advisory node the policy marks review-required |
| `DETERMINISTIC_SERVICE_PREFERRED` | `kind ∈ {EVIDENCE_ADMISSIBILITY, PROHIBITED_CONDITION, ACTION_CONSTRAINT, AUDIT_EMISSION}` (deterministic, no judgment) |
| `NO_AI_AGENT_REQUIRED` | `kind ∈ {TERMINAL_OUTCOME}` and structural COMPILER-owned nodes with no cognitive work |
| `AI_AGENT_ELIGIBLE` | advisory, non-governance cognitive work (e.g. evidence summarization/analysis under `EVIDENCE_REQUIREMENT` / `SEQUENCE_RISK_CHECK` advisory framing) |
| `UNSUPPORTED_NODE` | unknown `NodeKind`, unknown `CapabilityId`, or unsupported `ir_version` |

Worked mappings (from the task, validated against the registry dispositions):

- Decision Authority node → `HUMAN_AUTHORITY_REQUIRED` **or** `EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP`
- ActionGate node → `EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP`
- Action Clearance node → `EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP`
- Evidence summarization/analysis node → potentially `AI_AGENT_ELIGIBLE`
- Deterministic validation node → `DETERMINISTIC_SERVICE_PREFERRED`

### 8.2 Adapter guarantees (specified now; implemented in P1)

- **Supported contract version:** `ir_version == "workflow_ir.v1"`; registry `capability_registry.v1`.
- **Unknown-version behavior:** fail closed → all nodes `UNSUPPORTED_NODE`; no plan emitted.
- **Unsupported-node behavior:** classify `UNSUPPORTED_NODE`; the workflow is not staffable until resolved (never silently dropped).
- **Provenance propagation:** carry `input_object_ids`, `audit_requirements`, `owning_capability`, `disposition`, and the node `node_id` onto the derived requirement.
- **Capability-ownership propagation:** `owning_capability` is preserved unchanged; the adapter never re-owns a node.
- **Authority-boundary preservation:** `AUTHORITATIVE` never becomes agent work.
- **Stable node-to-role mapping:** keyed by `WorkflowNode.node_id` (content-addressed).
- **Fail-closed behavior:** default `failure_behavior = BLOCK` is honored; ambiguity → escalation, never proceed.
- **Semantic-drift detection:** the adapter pins the compiler distribution version and the set of `(NodeKind, EdgeKind, CapabilityId)` values it was written against; any new/removed enum member trips a drift alarm rather than a silent misclassification.

> The adapter is **specified only** in Phase 0. Implementation is P1 work
> (see the ADR exit gates and the revised roadmap).
