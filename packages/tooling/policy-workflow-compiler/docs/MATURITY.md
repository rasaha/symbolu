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
| `ai_hiring_reference_equivalence_verified` | `true` | The compiler's AI Hiring interpretation is verified `EQUIVALENT` to the live product across five dimensions chosen for its advisory-versus-binding shape (decision D3's second domain). See `AI_HIRING_REFERENCE_VALIDATION.md`. |
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
| `source_declared_semantics_implemented` | `true` | `workflow_ir.v2` enrichment reads declared data classification, permission intent, required tools and contract versions into node semantics, each with `EXPLICIT` per-value provenance. An undeclared value stays unresolved and is never defaulted. |
| `authoritative_source_carriage_implemented` | `true` | A `policy_pack.v2` pack may carry the exact Policy Authority issuance it was compiled from; the reference is digest-bound, structurally validated and denormalized into the release manifest. See `AUTHORITATIVE_SOURCE.md`. |
| `binding_conformance_validation_implemented` | `true` | Every capability binding `workflow_ir.v2` emits is validated against the capability registry — unknown capabilities, advisory-on-authoritative misuse, optionality conflicts, contract-target disagreement and unresolved required bindings all refuse. Validation only: no provider is imported and nothing is emitted. See `BINDING_CONFORMANCE.md`. |
| `offline_simulation_implemented` | `true` | A compiled release can be exercised under a scenario's facts in a reproducible offline traversal that observes requirements and never resolves them. Evidence, not a gate — no compiler entry point consumes a run. See `OFFLINE_SIMULATION.md`. |
| `deterministic_replay_of_simulation_verified` | `true` | A run's digest is a pure function of the release, the scenario and the trace, so replay is digest equality. |

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
| `authoritative_source_verification_implemented` | `false` | The compiler attests carriage, not authenticity: it never verifies a Policy Authority signature, establishes key trust, or consults revocation state. |
| `simulation_grants_authorization` | `false` | A simulation observes that a requirement exists; it never grants, approves or clears one. Permanent. |

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

| Pilot evidence | Status | Settled by |
| --- | --- | --- |
| Procurement reference equivalence | **satisfied** | `EQUIVALENT`, 5 dimensions, 28 checks; `procurement_reference_equivalence_verified` |
| AI Hiring reference equivalence | **satisfied** | `EQUIVALENT`, 5 dimensions, 22 checks; `ai_hiring_reference_equivalence_verified` (decision D3's second domain) |
| One named real pilot policy corpus | outstanding | Only two policy-pack builders exist, both references. The Procurement builder in `packages/integration/procurement-policy-compilation` makes a real corpus compilable without new code. |
| Source policy passed legitimate human approval | mechanism complete; demonstration outstanding | `approval/service.py` — digest-bound, no compiler self-approval |
| Exact source artifact and digest retained | **mechanism complete** | PA/PWC-X1 carriage: `authoritative_source` is digest-bound on a `policy_pack.v2` pack and denormalized into the release manifest; `authoritative_source_carriage_implemented` |
| Deterministic compilation | **satisfied** | `deterministic_compilation_verified`, with pinned v1 and v2 digests |
| Diff-driven re-review demonstrated | **mechanism complete**; corpus demonstration outstanding | PWC-P3A: requirements derived from the diff and the pack's declared `ApprovalPath`, blocking gate, `diff_driven_review_implemented` |
| Approval bound to the exact changed pack | **demonstrated in test**; corpus demonstration outstanding | P3A dispositions bind `new_pack_digest`; `DISPOSITION_DIGEST_MISMATCH` refuses a stale one |
| No critical unresolved semantics | **mechanically assessable** (ruling D4-A) | `validate_compiled_release` returns `VALID` with `binding_ok`, and no node semantics carry `DerivationClass.UNRESOLVED` |
| Assurance package generated | **satisfied** | Fail-closed coverage invariant |
| Replay evidence retained | **satisfied** | `deterministic_replay_verified`, and `deterministic_replay_of_simulation_verified` for PWC-P3C runs |

### Two terms the D4 list left open, now ruled

**D4-A — what "critical" means.** Row 9 is satisfied when
`validate_compiled_release` returns `VALID` — not `VALID_WITH_WARNINGS` — with
`binding_ok` true, and no node semantics carry `DerivationClass.UNRESOLVED`.
Counting every warning would make the row unearnable on a real corpus; counting only
fatal errors would let an authority-boundary failure through. The validator's
blocking set is already the line the compiler refuses to cross.

**D4-B — a pilot must hand-author fact-complete scenarios.** Generated scenarios
satisfy the coverage invariant but carry few or no facts, so simulating them blocks
at the first evidence node — real behaviour for those inputs, and no evidence about
the corpus. Simulation is the only D4 evidence that exercises a corpus's *behaviour*
rather than its structure, so a pilot includes hand-authored fact-complete scenarios
beside the generated ones. Making generated scenarios fact-complete would move every
release digest and is **not** ratified.

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
