# TAP-E5 — Failure Analysis

E5 treats assembly mistakes as **information-integrity failures**: a packet that is
incomplete, non-minimal, orphaned, or lossy corrupts everything downstream. The twelve
critical-failure classes are therefore counted independently and gated to zero.

## Critical-failure classes and where they surface (DEV)

| Class | Meaning | Triggered on |
|---|---|---|
| `DUPLICATE_IDENTIFIERS` | the same object id appears twice | A |
| `ORPHAN_EVIDENCE` | evidence present but referenced by no relationship | A, B |
| `LOST_PROVENANCE` | a packet object has no provenance-index entry | A, B, C, D |
| `PACKET_SMALLER_BUT_INCOMPLETE` | a required object was dropped | C |
| `BROKEN_DEPENDENCY` | an edge / reference points at an absent object | C |
| `PACKET_LARGER_WITHOUT_JUSTIFICATION` | unused evidence or downstream-unused raw metadata retained | A, B, C, D, E |
| `ORPHAN_RELATIONSHIP` / `ORPHAN_GOVERNANCE_DECISION` | ungrounded relationship / unsupported decision | guard (0) |
| `LOST_CONFLICT` / `LOST_GAP` | an upstream conflict/gap missing | guard (0) |
| `SCHEMA_CORRUPTION` / `NON_DETERMINISTIC_PACKET` | round-trip / determinism failure | guard (0) |

Severe critical counts on DEV: **A=52, B=36, C=43, D=32, E=16, F=0**.

## Why each baseline is unsafe

- **A (naive union).** Ships everything with duplicate references (duplicate ids), retains
  retrieved-but-unused evidence (orphans), and attaches no provenance index. The
  "grab-everything" anti-pattern: complete but bloated, ambiguous, and untraceable.
- **B (deduplicate).** Fixes duplicate ids and shrinks the packet, but still ships unused
  evidence (orphans) and no provenance. Deduplication is necessary but not sufficient.
- **C (winner-only closure).** The instructive failure: by pruning from the *selected*
  authority only, it drops the **rejected authorities' relationships and minority evidence**
  and leaves conflicts pointing at absent members. The packet is **smaller** (size reduction
  0.50) but **incomplete** (completeness 0.79, reference-integrity 0.81) — a
  `PACKET_SMALLER_BUT_INCOMPLETE`. Smaller is not better if it discards downstream-required
  alternatives.
- **D (full closure).** Complete again, correctly minimal on evidence, but carries **no
  provenance index** — objects are present without traceable source, so downstream cannot
  audit them (`LOST_PROVENANCE`).
- **E (+ provenance).** Complete, provenanced, orphan-free — but not minimized (retains
  downstream-unused raw upstream signals) and never runs the validator or freezes, so it can
  ship a structurally-unchecked, non-minimal packet.
- **F (full).** Deduplicates, closes fully (keeping minority/rejected/conflicts/gaps),
  attaches provenance, minimizes downstream-unused metadata, validates, and freezes — zero
  severe failures on both splits.

## What remains true even at F (limits)

- **Synthetic corpus, authored fixtures.** Zero failures means the assembler is internally
  correct on this corpus against an independently-authored gold — not that real packet
  assembly is solved. Upstream records are authored, not produced by noisy real extraction.
- **Assembly, not judgement.** A complete, minimal packet asserts nothing about whether the
  packaged evidence is *true* or whether a claim is *supported* — that is TAP-E6's job. E5
  guarantees traceability and completeness, not correctness.
- **Conflicts/gaps are carried, not adjudicated.** A `CONFLICTED` governance decision and its
  tied authorities are preserved intact; E5 never breaks the tie or fills the gap.
