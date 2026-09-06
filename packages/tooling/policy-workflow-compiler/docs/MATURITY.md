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

## Phase 3A maturity gate (governed diff-driven review)

| Gate | Value | Meaning |
| --- | --- | --- |
| `diff_driven_review_implemented` | `true` | Review requirements are derived deterministically from a structural diff and the pack's own declared approval path, and a fail-closed review gate verifies a ledger against one. Routing and recording only — the compiler never performs, grants or waives an approval. See `DIFF_DRIVEN_REVIEW.md`. |
| `policy_pack_v2_supported` | `true` | The additive `policy_pack.v2` schema is accepted: source-declared data classification, permission intent, required tools and typed contract versions are carried in a sidecar collection, together with the authoritative-source coordinate. `policy_pack.v1` packs and digests are byte-identical under it. See `POLICY_PACK_SCHEMA.md`. |
| `source_declared_semantics_implemented` | `false` | Declared values are carried, digest-bound and validated, but `workflow_ir.v2` enrichment does not yet read them into node semantics. |

## Explicit non-goals

These booleans are hard-coded `false`. They are not roadmap placeholders that a
build might silently flip — this package makes no such claim at any version, and
each belongs to a different component.

| Gate | Value | Meaning |
| --- | --- | --- |
| `awc_adapter_updated` | `false` | The compiler does not update or own the Agent Workforce Composer adapter. **Deprecated by ratification** — held `false` for compatibility, removed at the next compatibility-controlled version. See "`awc_adapter_updated` is deprecated" below. |
| `agent_eligibility_implemented` | `false` | Eligibility is an AWC concern, not a compiler concern. |
| `agent_ranking_implemented` | `false` | Ranking is an AWC concern. |
| `team_composition_implemented` | `false` | Team composition is an AWC concern. |
| `runtime_execution_implemented` | `false` | The compiler never executes a workflow. |
| `action_authorization_implemented` | `false` | Authorization is held by canonical capabilities, never the compiler. |
| `enterprise_policy_evaluation_implemented` | `false` | Enterprise deployment-policy overlay evaluation stays outside the portable compiled workflow. |

### `awc_adapter_updated` is deprecated

This gate was introduced when the AWC adapter had not been updated, and at that
time it read the same way under either interpretation. That is no longer true.
AWC P2.1 is delivered: the Agent Workforce Composer does consume `workflow_ir.v2`,
and its own `compiler_v2_adapter_implemented` gate reports so. This package's gate
still reports `false`.

The owner has ruled (decision D5): the gate is **deprecated as a cross-package
maturity flag and must not be used to represent platform state**. It remains
`false` through the current 0.2.x line for compatibility, and is removed only at
the next compatibility-controlled version — removing a key from
`version_info().to_dict()` is a contract change, and spending a version bump to
delete one field is not warranted while this deprecation carries the same
information.

Until then: read the gate as scoped to this package's own responsibility, which
remains true and permanent — the adapter is AWC-owned and this package will never
update it. For AWC's actual state, read the AWC gates.

## Earning the pilot and production gates

`pilot_validated` and `production_certified` are `false` and are earned by recorded
evidence, never flipped administratively. The owner-ratified evidence list (decision
D4) is in
`Project_documentation/repository/docs/audits/policy_workflow_compiler_ratification/RATIFICATION.md`.
Summarized, with what this build already satisfies:

| Pilot evidence | Status |
| --- | --- |
| Procurement reference equivalence | satisfied — `EQUIVALENT`, 5 dimensions, 28 checks |
| AI Hiring reference equivalence | not built |
| One named real pilot policy corpus | not done |
| Source policy passed legitimate human approval | mechanism exists; not demonstrated on a pilot corpus |
| Exact source artifact and digest retained | requires the PA/PWC-X1 source-linkage coordinate |
| Deterministic compilation | satisfied — verified, with pinned v1 and v2 digests |
| Diff-driven re-review demonstrated | signal exists; the governed workflow is PWC-P3A |
| Approval bound to the exact changed pack | implemented; demonstration outstanding |
| No critical unresolved semantics in the corpus | assessable only against a real corpus |
| Assurance package generated | satisfied — fail-closed coverage invariant |
| Replay evidence retained | satisfied — `deterministic_replay_verified` |

`production_certified` additionally requires distribution integrity, upgrade
compatibility, a security review, an authority-boundary review, demonstrated
fail-closed behavior, release provenance, operational recovery and replay, supported
contract migration, and a formal certification record. Each still needs its own
acceptance threshold defined; the ratification names the set, not the thresholds.

The package remains tooling throughout. It does not need to become a runtime package
to earn either gate.

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
`KNOWN_LIMITATIONS.md` for the scope boundaries these gates reflect,
`NEXT_PHASES.md` for the owner-ratified phases that would address them, and
`Project_documentation/repository/docs/audits/policy_workflow_compiler_ratification/RATIFICATION.md`
for the binding decision record behind both.
