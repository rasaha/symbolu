# Implementation Decisions — P2

## D1 — Additive `workflow_ir.v2` as a new `semantics/` subpackage
P2 lives in a new `semantics/` subpackage plus one new `validation/` module. The v1
emission path (`compiler/`, `models/`, `serialization/`) is **untouched**, so v1
digests are byte-stable by construction, not by careful editing.

## D2 — v2 embeds the v1 graph rather than replacing it
`WorkflowIRv2.base_ir` holds the exact v1 `WorkflowIR`; `base_ir_digest` pins it.
Enrichment is a strict superset beside the v1 graph. This makes v2 self-contained,
keeps the v1 fingerprint recoverable, and lets the validator re-verify base
integrity.

## D3 — Hold `DISTRIBUTION_VERSION` at 0.1.0; bump `PRODUCT_VERSION` to 0.2.0
`DISTRIBUTION_VERSION` feeds the v1 release digest, so bumping it would break v1
fingerprints. The P2 marker is carried by `PRODUCT_VERSION` (not in any digest) and
the `workflow_ir.v2` contract. See `WORKFLOW_IR_VERSION_DECISION.md`.

## D4 — v2 fingerprint == v2 logical digest
The stored `workflow_fingerprint` equals `WorkflowIRv2.logical_digest()` (over the
base digest + all enriched fields, excluding the slot). This makes it recomputable;
the validator flags any mismatch as `INTEGRITY_FAILURE`.

## D5 — Deterministic extraction only; no NL/keyword/LLM inference
Every emitted value derives from a documented rule: node-kind mapping, capability-
owner mapping, typed contract string, or graph edge. `semantic_purpose` comes from a
fixed per-kind table, not the free-text label (the label is preserved verbatim as
`semantic_description`). No substring/keyword heuristics, no model calls.

## D6 — Provenance on every value; unresolved is never fabricated
Every semantic value carries a `PolicyProvenanceRef` with a `derivation_class`
(`EXPLICIT` / `DETERMINISTIC_MAPPING` / `DERIVED_FROM_CONTRACT` / `DERIVED_FROM_EDGE`
/ `DEFAULTED_SAFE` / `UNRESOLVED`) and the named compiler rule. Structural nodes with
no functional capability emit an empty (not fabricated) capability set.

## D7 — Canonical, order-free enrichment output
`node_semantics` is emitted sorted by `node_id`; `dependency_semantics` sorted by
`(source, target, edge)`. Reordering the input nodes leaves the enriched semantic
content invariant. The v2 fingerprint still tracks the v1 canonical node order via
`base_ir_digest` (that order is itself deterministic compiler output).

## D8 — Release validation states with hard integrity floors
`ReleaseValidationState`: `VALID`, `VALID_WITH_WARNINGS`, `INVALID`,
`UNSUPPORTED_VERSION`, `INTEGRITY_FAILURE`. A digest mismatch → `INTEGRITY_FAILURE`;
any authority/structural/semantic/contract/dependency/provenance blocking failure →
`INVALID`. Authority and digest failures can never be reduced to warnings.

## D9 — Reuse existing primitives; no parallel objects
v2 models subclass the existing `CompilerModel`; digests use the existing
`serialization.hashing`/`canonical_json`; severities reuse the P1 vocabulary; the
authority classification aligns with the existing `_NODE_AUTHORITY_TABLE`. No
redundant parallel object model was created.

## D10 — Branch name
Development on the environment-assigned `claude/policy-workflow-compiler-p2`
(supersedes the suggested `chatgpt/policy-workflow-compiler-p2`).

## D11 — P3A fixtures reconstructed in the compiler's own test area
The four P3A scenario shapes are rebuilt as v1 `WorkflowIR` graphs in
`tests/_v2_helpers.py` (compiler-owned test fixtures), so P2 conformance is tested
without importing AWC or the Studio app, and without modifying any P3A artifact.
