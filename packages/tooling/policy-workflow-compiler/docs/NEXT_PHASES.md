# Next Phases

This document **describes** — it does not implement — work that would follow the
current Phase 1 tooling product. Nothing here is present in version 0.1.0; the
current maturity gates (see `MATURITY.md`) remain the authoritative statement of
what exists today.

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
