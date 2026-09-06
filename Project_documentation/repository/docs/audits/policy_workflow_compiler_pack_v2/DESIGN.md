# `policy_pack.v2` — Source-Declarable Semantics: Design

**Status:** design. **V2-A is ruled and delivered** (the shared canonical-view
extraction); **V2-B remains open**. No further source change is authorized by this
document.
**Scope:** `packages/tooling/policy-workflow-compiler`. Ratified as decision **D2**
(`../policy_workflow_compiler_ratification/RATIFICATION.md`) and required by the X1
carriage design (`../policy_workflow_compiler_x1/DESIGN.md`), which cannot bind an
authoritative source without it.

Findings carry `[V]` verified against the repository, `[I]` inferred, `[R]` requires
ratification, `[G]` gap.

## The constraint, measured four ways

Against the procurement reference, baseline `sha256:fb9fd4b9…`:

| Approach | v1 release digest |
| --- | --- |
| (a) Additive optional field on each object model (`DecisionRule.data_classification_refs`) | `[V]` **moves** |
| (b) One top-level sidecar key, unconditionally serialized, even when empty | `[V]` **moves** |
| (c) That key **pruned** from the logical view when `schema_version == policy_pack.v1` | `[V]` **byte-identical** |
| (d) Pruned in `_pack_logical` but not in `compute_pack_digest` | `[V]` **approval digests break** |

(a) rules out the natural design: `_pack_logical` serializes `pack.model_dump()`, so
a defaulted field on any object model is a new canonical key on every pack that
holds one.

(c) is viable, and it is not a novel trick. `[V]` Both `_pack_logical` and
`compute_pack_digest` already prune `status` (`data.pop("status", None)`) so a pack
keeps one digest across the `APPROVED -> COMPILED` transition. Schema-gated pruning
is the same mechanism, gated on `schema_version` rather than applied unconditionally.

## Prerequisite — one canonical view, not two `[G]`

Measurement (d) is the trap. The "logical view of a pack" is implemented **twice**:
`compiler/release.py::_pack_logical` and `approval/records.py::compute_pack_digest`,
each independently popping `status`. If only one learns the v2 pruning rule, every
approval bound to every v1 pack silently stops matching — a failure that presents as
"approval digest does not match the pack" long after the change that caused it.

**v2 therefore lands in two steps:**

1. Extract a single shared canonical-view function that both callers use. Pure
   refactor, digests pinned, no behavior change.
2. Add the schema gate to that one function.

Two implementations of one rule is the dual-source-of-truth pattern this
architecture rejects everywhere else; the digest is the last place to tolerate it.

## Carriage — a sidecar collection, not per-object fields

Add **one** top-level collection, `semantic_declarations`, alongside the single
`authoritative_source` slot X1 requires. Each declaration names its subject rather
than living on it:

```text
SemanticDeclaration
  subject_object_id          the object this declares about
  data_classification_refs   "this workflow may access customer PII"
  permission_intent_refs     "this node requires write permission"
  required_tool_refs         "this action requires Salesforce"
  input_contract_refs   }    typed {contract_id, contract_data_version}
  output_contract_refs  }
```

Why a sidecar rather than fields spread across the twenty object models:

- **One pruned key, one gate.** The pruning rule stays a single reviewable line
  rather than a per-model concern.
- **The v1 object models stay literally untouched**, so nothing a v1 reader parses
  changes shape.
- **It mirrors the ratified P2 precedent** — `workflow_ir.v2` embeds the v1 graph
  beside the enrichment rather than mutating it.

The honest cost is **indirection**: a declaration references its subject by id, so
validation must resolve every subject and reject duplicates. That is the trade for
keeping twenty models and every existing digest untouched.

## Schema-version handling

`[V]` `SUPPORTED_SCHEMA_VERSIONS` is a one-element tuple and
`validation/provenance.py::check_schema_version` already fails closed at `FATAL` on
anything else, so widening it to both versions is an explicit, reviewable act.

The gate must cut **both** ways. A v1 pack that declares v2 content is **refused**
(`V2_FIELD_IN_V1_PACK`), never quietly pruned. A field that is present, reviewed,
approved, and then silently excluded from the digest is worse than either accepting
it or rejecting it: it is signed-but-ignored governance content.

## How `workflow_ir.v2` enrichment consumes declarations

`[V]` The linkage already exists. `semantics/extraction.py::extract_node_semantics`
maps a node to its source policy objects through `node.input_object_ids` — it
already emits them as `source_policy_refs`. Enrichment looks up the declarations for
those ids and fills the slots that are hard-coded empty today:
`data_classification_refs`, `permission_intent_refs`, `required_tool_refs`, and
`DataContractRef.contract_data_version`.

Provenance distinguishes the two origins exactly:

| Origin | `DerivationClass` | `ResolutionStatus` |
| --- | --- | --- |
| Declared by the source policy | `EXPLICIT` | `EXPLICITLY_DECLARED` |
| Derived from node kind (today's behavior) | `DETERMINISTIC_MAPPING` | `DETERMINISTICALLY_INFERRED` |
| Not declared | `UNRESOLVED` | `UNKNOWN` |

An absent declaration stays empty and `UNRESOLVED` — never `DEFAULTED_SAFE`. A
governance claim must not be defaulted into existence; that rule is unchanged from
P2 and is what makes the enriched values worth trusting.

**Digest consequence.** A v1-sourced graph enriches identically, so the v2
fingerprint `sha256:2e031c78…` holds. A v2 pack carrying declarations produces a
different v2 fingerprint — that is new content, not a moved fingerprint, and no
prior v2 artifacts exist to disturb.

## Fail-closed codes

| Code | Raised when |
| --- | --- |
| `UNSUPPORTED_SCHEMA_VERSION` (exists) | The pack declares a schema this build cannot compile |
| `V2_FIELD_IN_V1_PACK` | A `policy_pack.v1` pack carries v2 declarations |
| `DANGLING_DECLARATION_SUBJECT` | `subject_object_id` resolves to no object in the pack |
| `DUPLICATE_DECLARATION_SUBJECT` | Two declarations claim one subject — which governs is not a question the compiler may answer |
| `MALFORMED_CONTRACT_VERSION_REF` | A typed contract reference is missing its id or version |

Plus the authoritative-source codes specified in the X1 design.

## What v2 does not admit

Only what a **source policy** can declare. The nineteen `CORRECTLY_REMAINS_OVERLAY`
fields stay overlay: provider, residency and deployment constraints, security
classification *floors*, permission and authority *ceilings*, cost/latency/quality
SLAs, tool allow/deny lists, model refs.

The line holds on portability. "This node handles PII" is policy semantics and
travels with the workflow. "This enterprise forbids PII outside eu-west" is
enterprise posture; baking it into a compiled workflow would make the same workflow
un-portable across enterprises.

## Digest impact

| Output | Effect |
| --- | --- |
| `policy_pack.v1` pack digest | unchanged — key pruned under the schema gate |
| `workflow_ir.v1` release digest | unchanged — `sha256:fb9fd4b9…` |
| `workflow_ir.v1` IR digest | unchanged — `sha256:169ad24c…` |
| `workflow_ir.v2` fingerprint, v1-sourced | unchanged — `sha256:2e031c78…` |
| Existing approvals | unchanged — the canonical view is identical for v1 packs |
| `policy_pack.v2` artifacts | new by construction; none exist yet |

## Open rulings — required before implementation `[R]`

**V2-A — sequencing of the canonical-view extraction. RULED: its own prior
commit — and delivered.** `models/pack_view.py::canonical_pack_view` is now the one
definition of a pack's logical content; `compiler/release.py::_pack_logical` and
`approval/records.py::compute_pack_digest` both delegate to it, and a test asserts
that no other module reconstructs the view. No schema gate is present yet: the
refactor moved no digest, so it is reviewable in isolation from the schema change
that follows. Step two adds the `schema_version` gate to that single function.

**V2-B — is `SemanticDeclaration` approval-sensitive?** Whether it becomes a
`PolicyObject` with a new `ObjectType.SEMANTIC_DECLARATION` and joins
`APPROVAL_SENSITIVE_OBJECT_TYPES`. Recommendation: **yes**. As a `PolicyObject` it
gains provenance refs, appears in `all_objects()`, and becomes diffable; as an
approval-sensitive type, changing a data classification routes to P3A review, which
is the correct handling for "this now touches PII". The change costs nothing for v1
packs, which contain no such objects.
