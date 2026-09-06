# Maturity

Maturity is reported programmatically by `version_info()` as a set of explicit
booleans. This document states what each gate means, what is claimed, and — just
as importantly — what is not.

## Phase 1 maturity gates

| Gate | Value | Meaning |
| --- | --- | --- |
| `structured_policy_pack_implemented` | `true` | The structured policy-pack object model exists and is usable. |
| `deterministic_compilation_verified` | `true` | Deterministic compilation is verified: identical approved input + compiler version yields an identical logical digest. |
| `procurement_reference_equivalence_verified` | `true` | The compiler's Procurement interpretation is verified `EQUIVALENT` to the live product across the modeled dimensions. |
| `document_extraction_implemented` | `false` | No document ingestion / extraction. |
| `runtime_deployment_implemented` | `false` | No runtime execution or deployment. |
| `pilot_validated` | `false` | Not validated in a pilot. |
| `production_certified` | `false` | Not certified for production. |

## Phase 2 maturity gates (contract `workflow_ir.v2`)

| Gate | Value | Meaning |
| --- | --- | --- |
| `workflow_ir_v1_supported` | `true` | The frozen v1 contract is still emitted and validated. |
| `workflow_ir_v2_supported` | `true` | The additive v2 semantic-enrichment contract is emitted and validated. |
| `semantic_node_enrichment_implemented` | `true` | Per-node semantic purpose, description and role relevance are derived deterministically. |
| `capability_requirement_extraction_implemented` | `true` | Functional capability requirements are extracted from node kind, with provenance. |
| `typed_contract_references_implemented` | `true` | Typed input/output data-contract references with resolved producers/consumers. |
| `dependency_semantics_implemented` | `true` | Typed edges are classified into dependency semantics. |
| `authority_semantics_implemented` | `true` | Authority disposition, canonical owner and governance boundary refs are classified. |
| `human_review_semantics_implemented` | `true` | Human review vs human authority vs none is classified deterministically. |
| `policy_provenance_implemented` | `true` | Every emitted semantic value carries a provenance ref and derivation class. |
| `release_validation_implemented` | `true` | `CompiledReleaseValidator` with hard authority and digest integrity floors. |
| `deterministic_replay_verified` | `true` | Enrichment replays identically across processes and input orderings. |

## Explicit non-goals

These booleans are hard-coded `false`. They are not roadmap placeholders that a
build might silently flip — this package makes no such claim at any version, and
each belongs to a different component.

| Gate | Value | Meaning |
| --- | --- | --- |
| `awc_adapter_updated` | `false` | The compiler does not update or own the Agent Workforce Composer adapter. That adapter is AWC-owned; see "Where AWC v2 consumption lives" below. |
| `agent_eligibility_implemented` | `false` | Eligibility is an AWC concern, not a compiler concern. |
| `agent_ranking_implemented` | `false` | Ranking is an AWC concern. |
| `team_composition_implemented` | `false` | Team composition is an AWC concern. |
| `runtime_execution_implemented` | `false` | The compiler never executes a workflow. |
| `action_authorization_implemented` | `false` | Authorization is held by canonical capabilities, never the compiler. |
| `enterprise_policy_evaluation_implemented` | `false` | Enterprise deployment-policy overlay evaluation stays outside the portable compiled workflow. |

### Where AWC v2 consumption lives

`awc_adapter_updated=false` is a statement about *this package's* responsibility,
not about the platform. The Agent Workforce Composer does consume
`workflow_ir.v2` — its own `compiler_v2_adapter_implemented` gate reports that.
The two gates are consistent: the consumer owns the adapter, the compiler owns
the contract.

## Version and contract identity

`version_info()` also reports the distribution/product version, the supported
workflow-IR contracts, and the frozen per-contract digest semantic identities
(`workflow_ir.v1` -> `0.1.0`, `workflow_ir.v2` -> `0.2.0`). Those identities are
pinned constants, decoupled from the package version, so a version bump can never
perturb an existing logical digest.

## What is claimed

- The structured policy pack, the object model, and the compiler pipeline are
  implemented.
- Compilation is deterministic and this is **verified**, not merely asserted.
- The Procurement reference equivalence gate is **achieved and verified**.

These three `true` gates are the substance of the Phase 1 product: a working,
deterministic, reference-validated compiler. The Phase 2 gates add a deterministic,
provenance-backed semantic description of that same compiled workflow — and nothing
else: enrichment describes, it does not bind, decide, authorize or execute.

## What is NOT claimed

- **No document extraction.** The compiler does not read source documents into a
  pack; a structured pack is a precondition.
- **No runtime.** The compiler does not execute workflows or deploy anything.
- **Not pilot-validated.** No claim of validation in a real pilot.
- **Not production-certified.** No claim of production readiness.

Honesty about maturity is itself a product feature: the false gates are surfaced
by `version_info()` so downstream consumers can gate their own usage. See
`KNOWN_LIMITATIONS.md` for the scope boundaries these gates reflect and
`NEXT_PHASES.md` for what later phases would address.
