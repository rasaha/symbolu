# Implementation Decisions — P2.1

## D1 — v1 adapter byte-frozen; v2 is a parallel module
`adapt_compiled_workflow` is untouched. All v2 logic lives in new `adapter_v2.py`
+ `compatibility.py`, so v1 fingerprints are byte-identical by construction.

## D2 — Data-only seam preserved
The v2 adapter consumes the compiler's serialized `workflow_ir.v2` **document**, not
compiler pydantic objects. AWC imports nothing from the compiler package; the
dependency direction stays one-way.

## D3 — Reuse `classify_node` on the embedded base graph
Node disposition in v2 is computed by the SAME `classify_node` applied to `base_ir`,
guaranteeing byte-identical dispositions to v1 and preventing any authority
broadening through overlay.

## D4 — Contracts sourced from base_ir; typed refs surfaced in the envelope
`input_contract_refs` / `output_contract_refs` on the role come from the base_ir node
(identical to v1) so composition interface compatibility is unchanged. The compiler's
richer typed contract refs and the v2 dependency graph are surfaced in the
`AdaptationResultV2` envelope, demonstrating consumption without perturbing the
frozen planning result.

## D5 — Overlay reduction removes only compiler-emitted fields
`reduce_overlay` removes `role_name` / `role_description` / `human_review_requirement`
(the compiler-compensation fields) and retains all enterprise policy. The adapter
additionally stops synthesizing the base `evidence_extraction` capability, taking it
from the compiler instead. Enterprise domain-specialist capabilities are retained, so
`required_capabilities` (and hence eligibility) is unchanged.

## D6 — Monotonic merge with typed conflict diagnostics
Enterprise policy may narrow / strengthen / add review, never broaden authority or
remove a compiler human review / governance boundary. Violations produce typed,
fail-closed `AdapterDiagnostic`s (`OVERLAY_REMOVES_HUMAN_REVIEW`,
`OVERLAY_BROADENS_AUTHORITY`, …).

## D7 — Uniform envelope, frozen inner result
`adapt_workflow` returns a uniform `AdaptationResultV2` envelope for both contracts;
the embedded `adaptation_result` is the ordinary `CompilerAdaptationResult` the
frozen P1/P2 pipeline consumes unchanged. Adapter metadata and the adapter contract
version (`awc.compiler_adapter.v2`) live on the envelope, NOT in any planning
fingerprint.

## D8 — Equivalence is SEMANTICALLY_EQUIVALENT, reported honestly
v2 plans carry richer provenance and a different source contract, so raw fingerprints
differ. The harness compares the planning projection and reports
SEMANTICALLY_EQUIVALENT — it never claims byte identity where only semantic
equivalence holds.

## D9 — Conformance fixtures package-local; P3A untouched
The four P3A scenarios are migrated to committed conformance fixtures under
`packages/capabilities/agent-workforce-composer/conformance/governance_studio_v2/`
by READING the frozen P3A demo_data (never mutating it). No Governance Studio source
is changed; tests run without the compiler or the app present.

## D10 — Version bump 0.2.0 → 0.2.1 (additive minor)
The compiler v2 adapter is a minor feature. The `awc.v1` / `awc.composition.v1`
planning contracts are unchanged; a new `awc.compiler_adapter.v2` metadata version
covers adaptation envelopes only.

## D11 — Branch
`claude/awc-p2-1-compiler-v2-adapter` (env prefix; supersedes suggested
`chatgpt/awc-p2-1-compiler-v2-adapter`).
