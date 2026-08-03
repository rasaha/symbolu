# Product Boundary

This document states, precisely, what `ugence-policy-workflow-compiler` is and
what it is not. The boundary is a first-class design constraint, not a
disclaimer.

## What it is

A **deterministic tooling product**. It compiles a reviewed, structured
governance policy pack into:

- a governed-workflow intermediate representation (IR), and
- an assurance package (deterministic test specifications plus a coverage
  matrix).

Given identical approved input and an identical compiler version, it produces an
identical logical result.

## What it is not

It is **not a governance authority**. Concretely, the compiler:

- makes **no binding decision**,
- **approves nothing**,
- **authorizes nothing**, and
- **executes nothing**.

It transforms an already-reviewed, already-approved policy pack into
structure. All authority remains with the humans and with the downstream
capabilities the IR references.

## Things it must not do

The following are explicit non-goals and are actively prevented by the design:

- **Decide.** It does not evaluate live cases or reach dispositions. Predicates
  are declarative facts, never executable Python.
- **Authorize actions.** It emits authority-check and clearance-requirement
  *nodes*; it never performs exact-action authorization itself.
- **Approve its own output.** A compiler process principal
  (`COMPILER_PRINCIPAL`) is rejected as an approver.
- **Fabricate provenance.** An object lacking provenance is `PROPOSED_ONLY` and
  `REVIEW_REQUIRED`; it is excluded from synthesis until a reviewer approves the
  gap.
- **Reach out.** No network calls, no credentials, no runtime deployment. The
  optional installation probe never imports a provider.
- **Reinterpret semantics.** The structural diff is exact and object-level; it
  performs no natural-language semantic comparison.
- **Modify referenced products.** The Procurement equivalence harness compares
  against live `ugence-procurement` but never modifies it.

## Role diagram

```
                +--------------------------+
  reviewed  ->  |  Policy Workflow         |  -> workflow IR + assurance package
  policy pack   |  Compiler (TOOLING)      |     (structure only; no decisions)
                +--------------------------+
                     |            |
   binds to human    |            |  references (metadata only)
   APPROVAL record   v            v
             +-------------+   +--------------------------------+
             |  Human      |   |  Downstream capabilities        |
             |  reviewer   |   |  (Decision Authority, Action    |
             |  (authority)|   |   Gate, TAP, ... own the acts)  |
             +-------------+   +--------------------------------+
```

The compiler sits between reviewed policy and governed structure. Decisions,
approvals, authorizations, and execution all live outside the box.
