# Stale-Assumption Inventory (merged AWC docs vs. live repository)

The merged AWC documents (PR #1305) were written treating the Policy Workflow
Compiler as an unbuilt, spec-only upstream. PR #1303 landed the compiler as an
implemented, independently packaged tooling distribution **before** #1305 merged.
This inventory lists every stale statement, its verified correction, and the
consequence. It is the input to the seven-document correction and to the
`UPSTREAM_CONTRACT_ALIGNMENT_AND_SEMANTIC_DRIFT` risk that replaces the old
"spec-only upstream" risk.

## A. Compiler-is-unbuilt statements (9 occurrences, 3 files)

| # | File | Line | Stale text (quoted) | Correction |
|---|---|---|---|---|
| 1 | DESIGN_SPEC | 201 | "…`POLICY_PACK_GOVERNED_WORKFLOW_COMPILER_SPEC.md` (spec-only)" | Implemented as `ugence-policy-workflow-compiler` (PR #1303). |
| 2 | DESIGN_SPEC | 201 | "**Spec-only today**; AWC must define an adapter against its 15-object policy-pack IR and degrade gracefully when it is absent" | Compiler emits a typed `WorkflowIR` (14 node kinds / 9 edge kinds); AWC consumes it via `CompilerWorkflowAdapter`. "15-object policy-pack IR" is inaccurate (20 object categories → `WorkflowIR`). |
| 3 | DESIGN_SPEC | 249 | "`[EXISTING]` spec-only: …§9 output contract" | Relabel: `[EXISTING]` implemented; cite the live `WorkflowIR` contract. |
| 4 | DESIGN_SPEC | 251 | "Because that compiler is **not yet implemented**, …" | The compiler is implemented; AWC consumes canonical `WorkflowIR` today. |
| 5 | DESIGN_SPEC | 694 | "role extraction from a hand-authored governed-workflow graph (Policy Workflow Compiler is spec-only)" | MVP consumes a real `WorkflowIR` fixture from the compiler; hand-authored graphs are only a supplementary offline fixture. |
| 6 | DESIGN_SPEC | 766 | "the upstream compiler is spec-only; the `WorkflowGraphSource` adapter must be…" | Rename the seam to consume `WorkflowIR`; the risk is contract alignment + semantic drift, not absence. |
| 7 | DESIGN_SPEC | 803 | "dependence on a **spec-only** upstream compiler (IR risk)" | Replace with `UPSTREAM_CONTRACT_ALIGNMENT_AND_SEMANTIC_DRIFT`. |
| 8 | ARCHITECTURE | 32 | "Policy Workflow Compiler … `[EXISTING: spec-only]`" (self-contradictory tag) | `[EXISTING]` (implemented); remove "spec-only". |
| 9a | ROADMAP | 90 | "…integration when it ships…" | Integration is against the shipped `workflow_ir.v1` contract; remove "when it ships". |
| 9b | ROADMAP | 103 | "**Spec-only upstream** — the Policy Workflow Compiler is not implemented; the `WorkflowGraphSource` adapter must…" | Replace risk with `UPSTREAM_CONTRACT_ALIGNMENT_AND_SEMANTIC_DRIFT`; adapter consumes `WorkflowIR`. |

Absent phrasings (confirmed not present): literal `SPEC_ONLY_UPSTREAM`, "spec only"
(space form), "unimplemented", "no typed WorkflowIR", "to be integrated". The old
risk is expressed as the prose "Spec-only upstream" (ROADMAP L103) and "spec-only …
upstream compiler" (DESIGN_SPEC L803).

## B. Semantic-drift statements (a second conceptual workflow representation)

| Item | Stale in docs | Live truth | Consequence |
|---|---|---|---|
| `WorkflowGraphSource` | AWC's invented adapter type, 8 references (DESIGN_SPEC 252/636/766, ARCHITECTURE 35/139, ROADMAP 53/103, ASSURANCE_PLAN 22) | Canonical type is `WorkflowIR`; no `WorkflowGraphSource` exists in the compiler | AWC must consume `WorkflowIR`; `WorkflowGraphSource` is renamed to a thin, versioned adapter (`CompilerWorkflowAdapter`) over `WorkflowIR`, not a rival representation. |
| "15-object policy-pack IR" | DESIGN_SPEC 201 | Compiler models 20 object categories → a `WorkflowIR` of 14 node kinds / 9 edge kinds | Correct the shape claim; cite the real node/edge taxonomy. |
| `WorkflowIR` term | Absent from all 7 docs | Live canonical type | Introduce it as the canonical upstream contract in all relevant docs. |

## C. H16 collision markers deferring to an open decision

| Marker | Location | Correction |
|---|---|---|
| "⚠ name collides with H16 `AgentProfile`; reconcile" | DESIGN_SPEC 219/223; OBJECT_MODEL 69 | Cite the finalized ADR (`AgentProfile` canonicalized into AWC; H16 compat re-export). |
| "⚠ reconcile with H16 `AgentAssignment`" | OBJECT_MODEL 179 | Cite the ADR (distinct namespaces; H16's runtime `AgentAssignment` retained). |
| ADAPT/canonicalize disposition not restated | SELECTION_POLICY, ASSURANCE_PLAN | Add a cross-reference to the ADR so all seven docs agree. |

## D. Correction-note requirement (recorded per the phase brief)

Each corrected doc gains a dated **Implementation-Status Correction** note stating:
Original assumption · Current verified state · Architectural consequence · Documents
changed. The former upstream risk (**"spec-only upstream" / `SPEC_ONLY_UPSTREAM`**)
is replaced by **`UPSTREAM_CONTRACT_ALIGNMENT_AND_SEMANTIC_DRIFT`**: AWC Phase 1
consumes the canonical compiler contract rather than inventing a second conceptual
workflow representation, and must actively detect contract/semantic drift.
