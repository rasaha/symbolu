# P3A Requirements Trace — P2

Every P2 compiler addition traces to a P3A ownership-matrix requirement, a real P3A
scenario need, or an explicit architecture decision. No field was added merely
because it might be useful later. Machine forms: `P3A_REQUIREMENTS_TRACE.json` and
`P3A_FIELD_RESOLUTION.json`.

| P2 addition | Traces to | P2 artifact |
|---|---|---|
| Node semantic purpose + description | P3A: `role_name`/`role_description` should be compiler-emitted | `WorkflowNodeSemantics.semantic_purpose` / `.semantic_description` |
| Functional capability requirement | P3A: base `required_capabilities` (`evidence_extraction`) should be compiler-emitted, not overlay-patched | `CapabilityRequirement` (`NODE_KIND_MAPPING`, provenance) |
| Typed input/output contract refs | P3A limitation: contracts are opaque strings | `DataContractRef` / `NodeInputRequirement` / `NodeOutputDeclaration` |
| Dependency semantics | P3A: downstream must not reconstruct dependencies from display order | `WorkflowDependencySemantics` (7 typed kinds) |
| Authority + human-review semantics | P3A: `authority_context` / `human_review_requirement` are compiler-owned | `role_relevance` + `HumanReviewRequirement` + `authority_disposition` |
| Policy provenance | P3A: `provenance` is compiler-owned | `PolicyProvenanceRef` (6 derivation classes) |
| Release validation | Compiler owns release structural/semantic/authority/digest integrity | `CompiledReleaseValidator` + `ReleaseValidationState` |

## Scenario coverage (compiler-owned semantics)

Each merged P3A scenario shape is reconstructed as a v1 `WorkflowIR`
(`tests/_v2_helpers.py`) and enriched + validated (`tests/test_v2_p3a_conformance.py`):

| Scenario | Agent-eligible nodes | Result |
|---|---|---|
| Procurement | 3 (evidence/risk/recommendation) + human approval + governance action | enriches, `VALID`; correct role-relevance split |
| Customer Support | 3 (triage/retrieval/drafting) + human review + approval | enriches, `VALID` |
| Cybersecurity — feasible | 4 (evidence/threat/correlation/recommendation) + governance/human | enriches, `VALID` |
| Cybersecurity — no feasible team | 2 (threat/correlation) | enriches, `VALID` |

The "no feasible team" outcome is an **AWC planning** result, not a compiler
concern: the compiler enriches the graph identically and the release is `VALID`. The
compiler describes the job; the workforce planner decides feasibility.

## Discipline confirmed

- Every P3A **compiler-owned** field now has a compiler P2 source (14 fields).
- Every **enterprise-owned** field remains outside compiler output (19 fields).
- Every **AWC-derived** field remains absent from the compiler (1 field).
- Every **runtime-derived** classification remains empty (0 role fields).
