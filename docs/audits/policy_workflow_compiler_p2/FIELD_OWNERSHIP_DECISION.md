# Field-Ownership Decision — P2

Grounded in the binding P3A ownership matrix
(`apps/ugence-governance-studio/docs/COMPILER_VS_OVERLAY_OWNERSHIP.md`). Machine
form: `P3A_FIELD_RESOLUTION.json` (37 fields).

## Outcome summary

| Outcome | Count |
|---|---|
| `COMPILER_EMITTED` | 14 |
| `CORRECTLY_REMAINS_OVERLAY` | 19 |
| `DEFERRED` (compiler slot exists; populated only on source declaration) | 3 |
| `AWC_DERIVED` | 1 |
| `RUNTIME_DERIVED` | 0 |
| `UNRESOLVED` | 0 |

## What P2 moves INTO the compiler (temporary overlay compensation removed)

The P3A ownership doc flagged these as structural semantics the compiler *should*
emit. P2 now emits them, each provenance-backed:

- **`role_name` / `role_description`** → v2 `WorkflowNodeSemantics.semantic_purpose`
  (canonical per node kind) + `semantic_description` (node label, verbatim). The
  overlay no longer needs to patch a stable role name.
- **`required_capabilities` (functional/base)** → v2 `CapabilityRequirement` with
  source `NODE_KIND_MAPPING` (e.g. `evidence_extraction` for an evidence node),
  carrying provenance. This is exactly the base capability the AWC adapter used to
  inject.
- **`input_contract_refs` / `output_contract_refs`** → v2 typed `NodeInputRequirement`
  / `NodeOutputDeclaration` with `DataContractRef` (versioned) plus resolved
  producer/consumer node ids.
- **`human_review_requirement`** → v2 `HumanReviewRequirement` (human_review vs
  human_authority vs none), classified deterministically from node kind/owner/
  disposition.
- **`authority_context`** → v2 `authority_disposition` + `canonical_capability_owner`
  + `governance_boundary_refs`.

## What P2 deliberately keeps OUT of the compiler (remains overlay)

The 19 `CORRECTLY_REMAINS_OVERLAY` fields encode a specific enterprise's posture and
must not enter a portable compiled workflow: provider / residency / deployment
constraints, security classification, permission ceilings / authority ceilings,
cost / latency / quality SLAs, audit-capability requirements, tool allow/deny,
domain scoping, model refs, evidence/policy refs, and state requirements. Baking any
of these into the compiler would make the same workflow un-portable across
enterprises.

## `DEFERRED` — a slot exists, populated only when source policy declares

Three fields have a v2 slot but are populated **only** when the source policy
declares the value (never invented):
- `data_classification` → `WorkflowNodeSemantics.data_classification_refs`
- `required_permissions` (permission *intent*) → `permission_intent_refs`
- `required_tools` → `required_tool_refs`

The demo/reference packs do not source-declare these, so they correctly remain
overlay for now. The **enterprise** classification floor / permission ceiling / tool
denylist always remains overlay regardless.

## `AWC_DERIVED` / `RUNTIME_DERIVED`

- `role_fingerprint` stays `AWC_DERIVED`; the compiler emits its own node/workflow
  fingerprints separately.
- **No `WorkflowRoleRequirement` field is runtime-derived** — the role requirement
  is a planning-time contract. P2 preserves this: nothing runtime enters the IR.
