# Next Phases

This document **describes** — it does not implement — work that would follow the
current tooling product. Nothing described here as future work is present in the
shipped build; the maturity gates reported by `version_info()` (see `MATURITY.md`)
remain the authoritative statement of what exists today. Where a section records
work as delivered, it says so explicitly and names the evidence.

## Phase 2 (proposed): Canonical Runtime Binding and Human Review Interface

**Canonical Runtime Binding and Human Review Interface:** bind compiled IR nodes
to optional canonical capability adapters, add governed review/diff approval
workflows, and execute only in deterministic offline simulation before any
enterprise shadow deployment.

Unpacking the three strands of that description:

### 1. Bind compiled IR nodes to optional canonical capability adapters

Today the compiler references capabilities by metadata only and never imports a
provider (see `CAPABILITY_REGISTRY.md`). Phase 2 would introduce **optional**
adapters that bind an IR node's `owning_capability` to a concrete canonical
capability implementation. Binding would remain optional and would preserve the
existing authority-boundary guarantees (see `AUTHORITY_BOUNDARIES.md`): an
adapter could not let an advisory capability decide, nor let a decision maker
perform action authorization.

### 2. Governed review / diff approval workflows

The structural diff already reports change types and an impact summary, including
`approval_re_review_required` (see `STRUCTURAL_DIFF.md`). Phase 2 would build
**governed review workflows** around that signal: a human review and approval
flow driven by the diff, so that a structurally meaningful change routes to a
reviewer and re-binds approval to the new structural digest (see
`HUMAN_APPROVAL.md`). The no-self-approval and digest-binding rules would carry
forward unchanged.

### 3. Execute only in deterministic offline simulation

Runtime deployment is explicitly not implemented today
(`runtime_deployment_implemented=false`). Phase 2 would allow execution **only in
deterministic, offline simulation** first — exercising the compiled IR and its
assurance specifications in a reproducible sandbox — **before any enterprise
shadow deployment**. Simulation would inherit the package's offline-determinism
and fail-closed posture (see `DETERMINISM.md` and `SECURITY_AND_FAILURE_MODEL.md`).

## What Phase 2 does not change

Even as described, Phase 2 preserves the product boundary (see
`PRODUCT_BOUNDARY.md`): the tooling still compiles and simulates; humans and
canonical capabilities still hold decision, approval, authorization, and
execution authority. Any move toward enterprise deployment would follow the
maturity gates — pilot validation and production certification — that remain
`false` today.

## Status update — Phase 2 semantic enrichment is now implemented

The `workflow_ir.v2` semantic-enrichment contract described as future work is
**implemented** in product 0.2.0 (see `WORKFLOW_IR_V2.md` and the P2 maturity flags
in `version_info()`). It enriches the workflow description only; it does not bind a
runtime or execute anything.

### AWC P2.1 — delivered (in the AWC package)

**AWC P2.1 — Policy Workflow Compiler v2 Compatibility Adapter, Overlay Reduction and
P1/P2 Fingerprint-Preserving Migration** was the named next phase for the v2 contract:
update the Agent Workforce Composer to consume enriched `workflow_ir.v2`, reduce only
the temporary overlay fields the compiler now emits (`role_name`, `role_description`,
`human_review_requirement`, the functional base capability, typed contracts), and
preserve every enterprise-policy overlay that remains correctly external.

That work is **delivered**, and it landed where it belongs — in the AWC package, not
here. Its evidence is AWC-side: `ugence_agent_workforce_composer.adapter_v2`, the
`COMPILER_V2_ADAPTER.md` contract document, the scoped
`agent-workforce-composer-p2-1-ci.yml` workflow, and the AWC maturity gates
`compiler_v2_adapter_implemented`, `overlay_reduction_implemented` and
`v1_v2_equivalence_harness_implemented`.

This package emitted no new contract for it and changed no digest. Its own
`awc_adapter_updated` gate stays `false` by design: the compiler does not own that
adapter (see `MATURITY.md`, "Where AWC v2 consumption lives").

### The next compiler phase is not yet ratified

With AWC P2.1 delivered, there is no owner-ratified next phase for **this** package.
The three Phase 2 strands described above — canonical capability-adapter binding,
governed diff-driven review workflows, and deterministic offline simulation — remain
descriptions, not commitments; none is scheduled, and `version_info()` reports none
of them as implemented. The scope of the next phase, whether the three `DEFERRED` v2
fields become source-declarable, whether reference equivalence must extend beyond
Procurement, and what evidence would flip `pilot_validated` and
`production_certified`, are all open owner decisions. Until they are ratified, this
document describes options rather than a plan.
