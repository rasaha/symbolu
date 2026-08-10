# TAP — Abstention Model v0.1

Abstention is defined **separately for every layer**. These are **independent
concepts** — one layer abstaining does not imply another does. Architecture-only.

> Boundary: `12_RESEARCH_BOUNDARIES.md`.

---

## 1. Principle

Abstention is a first-class, provenance-recorded outcome, not a failure. Each layer
decides abstention on the dimension it owns (`05_…`); abstentions do not average or
cascade automatically — each is a typed, independent decision.

## 2. Per-layer abstention

| Layer | Abstains when | Meaning |
|---|---|---|
| **Layer 1 relationship** | evidence insufficient to accept or reject a relationship | "cannot decide this relationship" |
| **Layer 2 governance** | a genuine unresolved conflict / undetermined operative source | "cannot decide who governs" |
| **Layer 3 packet** | a complete minimal packet cannot be assembled | "insufficient evidence to reason over" |
| **Layer 4 claim** | claim evidence is missing/incomplete (`INSUFFICIENT_EVIDENCE`/`UNKNOWN`) | "cannot verify this claim" |
| **Layer 5 response** | the answer cannot be made faithful | "decline / hedge the answer" |

## 3. Independence

- A Layer-1 abstention on one relationship does **not** force Layer-2 abstention; the
  governing set may still be determinable from the remaining validated relationships.
- A single Layer-4 claim abstention does **not** force response abstention; Layer 5
  may drop/qualify that claim and still answer faithfully.
- Response abstention is the only one visible to the user; the others shape the packet
  and the claim set upstream.

## 4. Abstain vs the six claim statuses (Layer 4)

At Layer 4, abstention is expressed through the status vocabulary:
`INSUFFICIENT_EVIDENCE` (missing evidence → abstain) and `UNKNOWN` (irreducible
conflict → manual review). These are distinct from `CONTRADICTED`/`UNSUPPORTED`
(remove) — abstention says *"unknown truth value"*, removal says *"known to be
unsupported."*

## 5. False abstention as a measured harm

Over-abstention is a real cost and is measured per layer (`10_…`). The evaluation must
include **negative controls** where evidence *is* sufficient, so that a layer which
abstains too readily is detected — abstention is not a free way to raise precision.

## 6. Reference instantiation

The synthetic Layer-4 prototype implements claim abstention
(`INSUFFICIENT_EVIDENCE`, `UNKNOWN`) and its measured run shows abstention firing only
where designed (0 false removals on that synthetic corpus). Abstention for Layers
1/2/3/5 is defined here but not implemented in this repository.
