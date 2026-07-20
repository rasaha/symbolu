# Truth Assurance Pipeline (TAP) — Architecture v0.1

**Phase:** architecture definition only. **No production code. No modification of any
existing experiment, benchmark, governance/packet/retrieval/parser, or evaluation
infrastructure.** No historical result is reinterpreted or changed.

> ## Scientific boundary (binding — restated in `12_RESEARCH_BOUNDARIES.md`)
> This document proposes an **architectural framework**. It makes **no empirical
> performance claims**, does not establish production readiness, does not claim
> hallucination elimination, and does not supersede any previous experiment.

---

## 1. Purpose

TAP is a modular research framework with a single top-level responsibility:

> **Every externally verifiable assertion must pass through progressively stronger
> truth-validation layers before reaching the user.**

It unifies — *without merging* — four distinct scientific problems:

| Problem | Question it answers | Owned by |
|---|---|---|
| **relationship truth** | is a proposed relationship supported by evidence? | Layer 1 |
| **governance truth** | which supported relationships actually govern (applicability)? | Layer 2 |
| **claim truth** | is each factual claim from the evidence packet supported? | Layer 4 |
| **response truth** | is the complete answer faithful to the validated claims? | Layer 5 |

These are treated as **different problems with different corpora, metrics, and
failure modes**. The architecture forbids conflating them.

## 2. The pipeline

```
User Request
   ↓
Intent Understanding      (scoping; not a truth layer)
   ↓
Trusted Retrieval         (candidate evidence; not a truth layer)
   ↓
Layer 1  Relationship Truth Layer   — are proposed relationships supported?
   ↓
Layer 2  Governance Truth Layer     — which supported relationships govern?
   ↓
Layer 3  Evidence Packet            — minimum complete evidence (no NL generation)
   ↓
Layer 4  Claim Truth Layer          — is each claim from the packet supported?
   ↓
Layer 5  Response Truth Layer       — is the whole answer faithful?
   ↓
Safety / Policy Layer               — final admissibility (not a truth layer)
   ↓
Final Response
```

Every layer exposes a **typed interface** (`03_INTERFACE_SPECIFICATIONS.md`),
appends to a shared **provenance object** (`04_PROVENANCE_MODEL.md`), emits
**multidimensional confidence** (`05_CONFIDENCE_MODEL.md`), and has its own
**abstention** (`09_ABSTENTION_MODEL.md`), **repair** (`08_REPAIR_MODEL.md`), and
**evaluation** (`10_EVALUATION_FRAMEWORK.md`) definitions.

## 3. Design invariants

1. **Single responsibility.** Each layer owns exactly one responsibility; the
   layer-vs-responsibility matrix (`02_LAYER_SPECIFICATIONS.md` §Ownership) has no
   shared cells.
2. **Independently testable.** Each layer has its own inputs, ground truth, metrics,
   and required corpora.
3. **Independently replaceable.** A layer may be swapped without touching another,
   because layers communicate only through the typed interfaces.
4. **No responsibility leakage.** Layer 1 never makes governance decisions; Layer 2
   never invents relationships; Layer 3 never generates natural language; judges
   never replace deterministic evidence.
5. **Provenance is append-only.** No layer overwrites upstream provenance.
6. **Falsifiable.** Every layer defines its own failure attribution so a negative
   result localizes to one layer.

## 4. Honest build status (what exists vs what is proposed)

This is critical to the framework's integrity. In this repository, **only one layer
has a self-contained prototype**, and it is on **synthetic** data:

| Layer / stage | Status in this repo |
|---|---|
| Intent Understanding | **proposed only** |
| Trusted Retrieval | **proposed only** |
| Layer 1 Relationship Truth | **proposed only** (no code) |
| Layer 2 Governance Truth | **proposed only** (no code) |
| Layer 3 Evidence Packet | **proposed only** (no code) |
| Layer 4 Claim Truth | **synthetic prototype exists** → `relationship_claim_validation/` (v0.1), deterministic judges, self-authored synthetic corpus; construction-validated only. See its `docs/relationship_claim_validation/FINAL_VERDICT.md`. |
| Layer 5 Response Truth | **proposed only** (no code) |
| Safety / Policy | **proposed only** here (a separate ActionGate/enforcement line exists elsewhere in the monorepo and is out of TAP scope) |

The resolver series, hidden corpus, and frozen proposal/governance/packet pipeline
referenced by prior briefs **do not exist in this repository**. TAP is therefore a
**forward-looking scaffold**, not a description of a running system. The roadmap
(`11_FUTURE_EXPERIMENT_ROADMAP.md`) lists what would have to be built and measured.

## 5. Deliverable index

| # | Deliverable | File |
|---|---|---|
| 1 | Truth Assurance Architecture | `01_TRUTH_ASSURANCE_ARCHITECTURE.md` (this file) |
| 2 | Layer Specifications | `02_LAYER_SPECIFICATIONS.md` |
| 3 | Interface Specifications | `03_INTERFACE_SPECIFICATIONS.md` |
| 4 | Provenance Model | `04_PROVENANCE_MODEL.md` |
| 5 | Confidence Model | `05_CONFIDENCE_MODEL.md` |
| 6 | Judge Model | `06_JUDGE_MODEL.md` |
| 7 | Deterministic Validation Model | `07_DETERMINISTIC_VALIDATION_MODEL.md` |
| 8 | Repair Model | `08_REPAIR_MODEL.md` |
| 9 | Abstention Model | `09_ABSTENTION_MODEL.md` |
| 10 | Evaluation Framework | `10_EVALUATION_FRAMEWORK.md` |
| 11 | Future Experiment Roadmap | `11_FUTURE_EXPERIMENT_ROADMAP.md` |
| 12 | Research Boundaries | `12_RESEARCH_BOUNDARIES.md` |

## 6. Success criteria (for the architecture, not for any system)

The architecture is successful iff: every responsibility belongs to exactly one
layer; every layer is independently replaceable; every layer is independently
evaluable; every layer exposes explicit provenance; future experiments fit the
framework naturally; and the whole remains modular and scientifically falsifiable.
Whether any *implementation* of it works is an empirical question the roadmap
defines and this document does not answer.
