# Hybrid LLM thesis — Version 1.0 → Version 1.1 changelog

**Version 1.1 · 6 August 2026.** Documentation-only evidence alignment. No experiment, model, dataset, seed,
benchmark, or architecture work. Research status unchanged: *research hypothesis under validation — not a
production-readiness claim.*

**Canonical-source note.** No editable Markdown source for Version 1.0 (4 August 2026) was found in the
repository at revision time. Version 1.1 is therefore established as the canonical editable source
(`HYBRID_LLM_ENTERPRISE_RELATIONAL_REASONING_V1_1.md`), reconstructing the thesis structure and updating all
evidence-dependent claims from **merged** evidence (PRs #1344–#1361). Unrelated sections were not rewritten.

## Changes

- **Architecture dependency change.** The deterministic-retrieval → typed working set → bounded reasoning →
  evidence-grounded answer/action → ActionGate/human-approval path is promoted from "fallback" to the
  **primary operational architecture**. A Version 1.1 architecture note fixes the dependency boundary at
  *deterministic retrieval → bounded reasoning → governed action*; neural memory sits inside "bounded
  reasoning" as optional and under validation, never on the retrieval/authorization path.

- **BindingSlots status change.** BindingSlots removed from the operational critical path and relabelled
  *"Optional research pathway; not required by the operational architecture."* The "BindingSlots is the
  principal unresolved dependency" framing is retired. Recorded current evidence: values storable; read-
  address routing unreliable; A1 and G1 interventions **not selected**; confidence-triggered fallback missed
  confidently-wrong reads; always-verify exact but one table read/query and far slower than table-only;
  `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`. No new BindingSlots optimization sweep as next step.

- **Explicit-key E1 evidence (new section).** Explicit semantic-key matching materially outperformed
  anonymous slots and independently replicated on controlled synthetic tasks (~32 episode-local memories):
  `EXPLICIT_KEY_SEMANTIC_MATCHING_VALIDATED`, `E1_INDEPENDENTLY_CONFIRMED`. Narrowly bounded: does not repair
  anonymous BindingSlots, prove enterprise transfer, replace the database, or unblock KDA.

- **Temporal evidence + track closures.** Supported (controlled synthetic) vs. unresolved capabilities
  separated. Evidence chain recorded: `E1_TEMPORAL_TRANSFER_PARTIAL` → `T4_SHORTFALL_MIXED` →
  `T4_FACTORIAL_NO_INTERVENTION_SELECTED` → `FROZEN_REPRESENTATION_READOUT_SIGNAL_NOT_FOUND`. Bounded closure
  added: tested C1-level and bounded frozen-readout approaches did not recover sufficient latest-state
  capability; no further C1 or frozen-readout intervention authorized — without claiming all temporal neural
  architectures impossible.

- **External-table operational positioning.** External database/table confirmed as the authoritative exact-
  fact path under tested reference conditions; table-only and always-verify both exact; always-verify one
  read/query and far slower; the neural layer must justify itself through reasoning value, not lookup
  reliability. Reference latency not generalized to production; no production-reliability claim.

- **Roadmap changes.** BindingSlots-first R1–R4 roadmap replaced by a status-based roadmap: deterministic
  retrieval (foundation) · explicit-key addressing (controlled-task confirmed) · temporal latest-state
  (partial; C1 & readout tracks closed) · structured relational benchmark (unauthorized) · optional bounded
  reader (unauthorized) · real-model adaptation (unauthorized) · read-only shadow pilot (unauthorized) · KDA
  (blocked). No future item is described as an approved execution phase.

- **Supported-claim changes.** Three explicit categories (supported on controlled synthetic tasks /
  partially supported / not currently supported), with "controlled synthetic task" qualifiers throughout. A
  new limitation states that explicit-key E1 beating anonymous slots does **not** establish typed structured
  input superiority over flattened prose in a real model. A 16-row capability status matrix added.

- **Future research authorization boundary.** A future-research menu (A–J) added, each item marked
  **unauthorized**: "Each item requires its own preregistration and explicit authorization. Inclusion in
  this roadmap does not authorize implementation or execution."

## Invariants (unchanged)
Preserved: `E1_TEMPORAL_TRANSFER_PARTIAL` · `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` ·
`KDA_VALIDATION_BLOCKED`. Not emitted: `E1_TEMPORAL_TRANSFER_VALIDATED` · `E1_STRUCTURAL_TRANSFER_CONFIRMED`
· `E1_FOLLOW_ON_RESEARCH_ELIGIBLE` · `KDA_VALIDATION_ELIGIBLE`. No production-readiness claim.
