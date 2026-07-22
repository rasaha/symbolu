# TAP-E3 — Failure Analysis

Severe critical failures by baseline (locked eval, reported independently of aggregates):

| failure | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| DIRECTION_REVERSED | 1 | 1 | 0 | 0 | 0 | 0 |
| AUTHORIZATION_INVERTED | 2 | 0 | 0 | 0 | 0 | 0 |
| PROHIBITION_DROPPED | 2 | 0 | 0 | 0 | 0 | 0 |
| CONFLICT_HIDDEN | 1 | 1 | 1 | 1 | 1 | 0 |
| UNSUPPORTED_RELATIONSHIP_EMITTED | 1 | 0 | 0 | 0 | 0 | 0 |
| UPSTREAM_GAP_IGNORED | 1 | 1 | 1 | 1 | 0 | 0 |
| **total** | **8** | **3** | **2** | **2** | **1** | **0** |

## Where each baseline fails

- **A (co-occurrence)** — the unsafe baseline, exactly as intended. It emits a generic
  relationship whenever two entities co-occur (`cooccurrence_false_positive_rate` 1.0,
  `unsupported_relationship_rate` 1.0), inverts authorization (permit vs prohibit lost),
  reverses direction, and drops prohibitions. This is *why* co-occurrence must not be
  treated as a relationship.
- **B (predicate keyword)** — recovers predicates (f1 0.95) but, without normalization,
  **reverses passive direction** ("System B is operated by Acme" → wrong subject), and,
  without polarity/modality, drops negation and collapses `must`/`may` (polarity and
  modality accuracy 0).
- **C (+normalization)** — fixes direction (1.0) but still has no polarity/modality.
- **D (+polarity/modality)** — fixes those (1.0/1.0) but still no temporality, and still
  no conflict detection or upstream-gap preservation.
- **E (+temporality/scope/conditions)** — full per-assertion structure (1.0), preserves
  upstream gaps, detects co-occurrence gaps — but **cannot detect cross-evidence
  conflicts** (`CONFLICT_HIDDEN` persists), so it fails the conflict and severe gates.
- **F (full)** — cross-evidence consolidation + conflict detection eliminate the last
  `CONFLICT_HIDDEN`; zero severe failures.

## Why F is selected (honest necessity, not "complex wins")

The preregistered gates include `conflict_detection_f1 ≥ 0.75` and
`severe_critical_failure_count == 0`. Cross-evidence conflict detection is a distinct
capability that only the consolidation stage (F) provides; without it the value/ontology
conflict cases produce `CONFLICT_HIDDEN`. Every simpler baseline fails at least one gate
on dev, so **F is the simplest baseline that satisfies all gates** — the selection rule,
applied literally, yields F.

## Residual (non-severe)

`relationship_f1` caps at 0.95: "Engineers should review the design document" uses a verb
("review") outside the bounded lexicon, so no assertion is produced (a visible recall
miss, above the 0.80 gate). This is the intended behavior of a deterministic, bounded
extractor — it declines rather than guesses.
