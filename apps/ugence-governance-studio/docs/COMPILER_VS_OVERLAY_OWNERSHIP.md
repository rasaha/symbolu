# Compiler vs. Overlay Ownership of `WorkflowRoleRequirement`

Every AI-agent role the studio evaluates is a `WorkflowRoleRequirement` produced by
`adapt_compiled_workflow(...)`. Each of its fields is populated from exactly one of
four sources. Getting this ownership right is what keeps the Policy Workflow Compiler
**enterprise-neutral and portable** while letting each enterprise govern the same
compiled workflow differently through the overlay.

This document classifies **every** `WorkflowRoleRequirement` field, grounded in the
real adapter (`ugence_agent_workforce_composer/adapter.py::_build_role`,
`_OVERLAY_FIELDS`, `_KIND_BASE_CAPABILITIES`). It is analysis and **recommendation
only** — P3A modifies neither the compiler nor the AWC contract, and P3B will build
on the current `workflow_ir.v1` unchanged.

## Ownership categories

1. **Compiler-derived** — emitted by the Policy Workflow Compiler into the
   serialized `workflow_ir.v1` document and read straight through by the AWC adapter.
   Structural: a property of the *workflow*, independent of which enterprise runs it.
2. **Enterprise-policy / overlay-derived** — supplied by the enterprise role overlay
   (`adapt_compiled_workflow(role_overlay=...)`). Reflects a specific enterprise's
   risk appetite, vendor list, jurisdiction, clearance model, budget, or SLAs.
3. **AWC-derived** — set/stamped by AWC itself (contract version constants, content
   fingerprints). Not authored by anyone; a function of the other fields.
4. **Runtime-derived** — would be filled at execution time. **No
   `WorkflowRoleRequirement` field is runtime-derived**: the role requirement is a
   pure planning-time contract. Runtime/measured facts live on agents, evidence, and
   (in later phases) the runtime — never on the role. This empty category is itself a
   boundary guarantee.

## Full field classification

Legend — **Src**: C=compiler, O=overlay, A=AWC, R=runtime. **Demo**: does a demo
fixture populate it?

| Field | Src | Demo | Notes |
|---|---|:---:|---|
| `contract_version` | **A** | auto | `CONTRACT_VERSION` (`awc.v1`) stamped by the adapter. |
| `role_id` | **C** | ✓ | `role::<node_id>` — derived from the compiled node id. |
| `workflow_id` | **C** | ✓ | Workflow identity from the IR. |
| `workflow_version` | **C** | ✓ | IR `policy_pack_version`. |
| `source_node_id` | **C** | ✓ | The originating `workflow_ir.v1` node. |
| `source_node_kind` | **C** | ✓ | `EVIDENCE_REQUIREMENT` for every demo role. |
| `role_name` | **C→O** | ✓ (O) | Overlay-preferred, else node `label`, else kind. Demo sets it via overlay. |
| `role_description` | **C→O** | ✗ | Overlay-preferred, else node `output_contract`. Demo leaves it compiler-derived. |
| `required_capabilities` | **C∪O** | ✓ (both) | Base `evidence_extraction` is **compiler-derived** (`_KIND_BASE_CAPABILITIES`); the specialist capability (e.g. `procurement_risk_analysis`) is **overlay-derived**. Unioned. |
| `input_contract_refs` | **C** | ✓ | Node `input_object_ids` (free strings). |
| `output_contract_refs` | **C** | ✓ | Node `output_contract` (free string). |
| `authority_context` | **C** | ✓ | Node `owning_capability` / `disposition` / `authority_type`. |
| `provenance` | **C** | ✓ | Adapter provenance (synthetic in the demo). |
| `source_package_digest` | **C** | ✓ | IR structural digest. |
| `role_fingerprint` | **A** | auto | Content hash stamped by AWC. |
| `optional_capabilities` | O | ✗ | Overlay only; unused by the demo. |
| `required_tools` | O | ✗ | Overlay only; unused. |
| `prohibited_tools` | O | ✗ | Overlay only; unused (enterprise policy also carries `forbidden_tools`). |
| `domain_requirements` | O | ✗ | Overlay only; unused. |
| `data_classification` | **O** | ✓ | Set on the procurement supplier/risk roles (`confidential`). |
| `residency_constraints` | O | ✗ | Overlay only; residency is enforced via enterprise policy in the demo. |
| `provider_constraints` | O | ✗ | Overlay only; provider policy is enterprise-level in the demo. |
| `deployment_constraints` | O | ✗ | Overlay only. |
| `required_permissions` | **O** | ✓ | `read_context` on every demo role. |
| `prohibited_permissions` | O | ✗ | Overlay only; governance-owned perms come from the permission policy. |
| `authority_ceiling` | O | ✗ | Overlay only; authority is bounded by enterprise + permission policy. |
| `required_audit_capabilities` | O | ✗ | Overlay only; `trace` required at enterprise level. |
| `required_security_classification` | **O** | ✓ | Level `4` on every cybersecurity role. |
| `required_evidence_classes` | **O** | ✓ | `MEASURED` on every demo role. |
| `state_requirement` | O | ✗ | Overlay only; unused. |
| `human_review_requirement` | O | ✗ | Overlay only; human steps are handled by node disposition in the demo. |
| `minimum_quality_constraint` | O | ✗ | Overlay only; quality floor enforced via enterprise policy. |
| `maximum_latency_constraint` | O | ✗ | Overlay only; latency ceiling via enterprise + composition policy. |
| `maximum_cost_constraint` | O | ✗ | Overlay only; cost ceiling via enterprise + composition policy. |
| `model_requirement_refs` | O | ✗ | Overlay only; out of P3A scope (no Model Selection). |
| `fallback_policy_ref` | O | ✗ | Overlay only; fallback policy passed separately in the demo. |
| `evidence_refs` | O | ✗ | Overlay only. |
| `policy_refs` | O | ✗ | Overlay only. |

Demo overlay keys actually used (all four scenarios): `role_name`,
`required_capabilities`, `required_evidence_classes`, `required_permissions`,
`required_security_classification`, `data_classification`.

## Fields that correctly belong in the enterprise overlay

These encode a **specific enterprise's** governance posture and must stay per-enterprise
so one compiled workflow can be governed differently by different customers:

- `residency_constraints`, `provider_constraints`, `deployment_constraints` —
  jurisdiction and vendor posture.
- `required_security_classification`, `required_audit_capabilities` — control/clearance
  posture.
- `required_permissions`, `prohibited_permissions`, `authority_ceiling` — least-privilege
  posture.
- `minimum_quality_constraint`, `maximum_latency_constraint`, `maximum_cost_constraint` —
  SLA / budget appetite.
- `human_review_requirement`, `prohibited_tools`, `required_tools`,
  `model_requirement_refs`, `evidence_refs`, `policy_refs`, `state_requirement`,
  `optional_capabilities` — enterprise/registry references and preferences.

The demo exercises the meaningful subset (`required_security_classification`,
`required_permissions`, `data_classification`) and leaves the rest available.

## Overlay-supplied today, but should eventually be compiler-emitted

These are **structural properties of the workflow step** that the demo is forced to
inject via the overlay only because `workflow_ir.v1` has no field for them. They
conflate "what does this step inherently need" (compiler) with "what does this
enterprise require" (overlay):

1. **`required_capabilities` (specialist part).** The compiler that authored a
   "supplier-risk analysis" node already knows the step needs a risk-analysis
   capability; today only the base `evidence_extraction` is compiler-derived and the
   specialist capability is overlay-patched. The functional capability of a step is
   structural and should be compiler-emitted, with the overlay free to *add* optional
   capabilities.
2. **`role_name` / `role_description`.** Currently fall back to the node `label`
   (presentation text). A stable, non-presentation role identity belongs in the IR.
3. **`data_classification`.** The compiler frequently knows the sensitivity of the
   object a node consumes/produces (e.g. a node handling `supplier_evidence` of
   `confidential` class). A structural sensitivity floor should be compiler-emitted;
   the overlay may tighten it.
4. **A minimum evidence-class floor.** A node that makes a binding-risk determination
   is structurally evidence-bearing; today `required_evidence_classes` is entirely
   overlay. The compiler should emit a floor (e.g. "≥ MEASURED"); the overlay may
   raise it.

## Fields that must remain outside the compiler

The compiler must produce a **portable, enterprise-neutral** workflow. Anything
reflecting a particular enterprise's vendors, jurisdiction, budget, clearance model,
or least-privilege stance must **never** be baked into the compiled IR:

- `provider_constraints`, `residency_constraints`, `deployment_constraints`
- `required_security_classification`, `required_audit_capabilities`
- `required_permissions`, `prohibited_permissions`, `authority_ceiling`
- `minimum_quality_constraint`, `maximum_latency_constraint`, `maximum_cost_constraint`
- `model_requirement_refs`, `evidence_refs`, `policy_refs`, `state_requirement`

Baking any of these into the compiler would make the same workflow un-portable across
enterprises and would smuggle vendor/jurisdiction/budget decisions into a governance
artifact that is supposed to be neutral.

## `workflow_ir.v1` limitations exposed by the realistic fixtures

1. **No first-class functional capability on a node.** Nodes carry a free-text
   `label` and an `output_contract`, but no field naming the cognitive capability the
   step requires — so the demo must inject the specialist capability via the overlay.
2. **Contracts are opaque strings.** `input_object_ids` and `output_contract` are free
   strings; interface compatibility in composition relies on exact string matching,
   with no typed contract identity or version. A compiler cannot guarantee that an
   upstream output and a downstream input remain compatible across versions.
3. **No stable role identity/name/description.** Role naming leans on the presentation
   `label`.
4. **No structural evidence-class floor or data-classification per node**, even where
   the compiler plausibly knows them.
5. **Authority metadata is adequate.** `owning_capability` / `disposition` /
   `authority_type` are compiler-emitted and consumed cleanly (they drive the
   disposition of every non-agent node in the fixtures). This part of the contract
   needs no change.

## Recommended compiler-contract additions before P3B

Additive and backward-compatible (proposed as `workflow_ir.v1.1` / `workflow_ir.v2`;
**not** implemented in P3A/P3B). Per node, add **optional** fields:

- `required_capabilities: [str]` — functional capability(ies) the step needs
  (structural), distinct from the enterprise overlay's additions.
- `role_name: str`, `role_description: str` — stable, non-presentation role identity.
- `data_classification: str` — sensitivity of the node's primary object (a floor the
  overlay may tighten).
- `minimum_evidence_class: str` — structural evidence floor (the overlay may raise it).
- **Typed contract references** — replace free-string `output_contract` /
  `input_object_ids` with `{contract_id, contract_version}` so interface compatibility
  in composition is version-aware.

Explicitly **kept out** of the compiler contract (remain overlay-only): provider /
residency / deployment constraints, security classification, permissions / authority
ceilings, cost / latency / quality SLAs, audit-capability requirements, model refs,
and `human_review_requirement`.

### Impact on P3B

None required. P3B builds the deterministic demo API on the **current, unchanged**
`workflow_ir.v1` and the current AWC public API. This document exists so the
compiler-contract evolution is planned deliberately — driven by realistic fixtures —
rather than discovered late. Until a `required_capabilities`/typed-contract emission
lands in the compiler, the studio's overlay legitimately carries the structural gap,
and the ownership table above is the authority on which field comes from where.
