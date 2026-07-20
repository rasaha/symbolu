# PILOT_EXPANSION_REPORT — Hidden Relationship Corpus Pilot v0.2

## Counts
- Candidates authored: **43**
- **ACCEPTED: 38** · REJECTED: 4 · QUARANTINED: 1
- Combined hidden corpus: **22 seed + 38 pilot = 60** (seed immutable).

## Accepted by capability / difficulty / relationship type / negative control
See UPDATED_CAPABILITY_COVERAGE.md. Every capability ≥3 total; L5 = 5; every
negative-control category ≥3 total.

## Agreement (author intended vs blind annotator)
Edge presence P/R/F1 = 0.984; exact-match 0.977. Governing exact-match 0.953.
Abstention exact-match 0.953, Cohen's κ 0.884. (Single-annotator caveat applies.)

## Similarity / duplicate findings
Accepted quarantine hits after documented overrides: **0**. Planted near-duplicate
detected and quarantined. One contrastive pair retained via documented override.

## Answer-position correlations
No excessive (>0.8) correlations. Highest is `longest_doc_governs` 0.70 (below
threshold, flagged for monitoring). Tables/appendices do not systematically lose;
abstention spread across L2–L4.

## Difficulty recalibration (reported, not applied)
Rubric differs from seed hand-labels in 16/22 cases and from author-proposed pilot
difficulty in 27/38 — authors do not set final difficulty; the rubric does.

## Target vs achieved (quality over count)
| Sub-target | Required | Achieved |
|---|---|---|
| ≥3 total for every single-example seed capability | 8 caps | **met** (3–6 each) |
| Additional Level-5 cases | 5 | **met** (5 adjudicated L5) |
| ≥3 per negative-control category | 5 categories | **met** |
| sentence-structure variation | present | **met** |
| clause-numbering variation | present | **met** |
| harmful and benign cycles | both | **met** (`cr_harmful`, `cr_benign`) |
| ~40–60 accepted | 40–60 | **38 — slightly under** (documented shortfall; quality prioritised) |

**Shortfall:** accepted count is 38, just below the 40–60 band. Every itemised
sub-target was met; the aggregate was capped by quality (candidates that failed a
gate were rejected/quarantined rather than accepted). Expansion toward the band is
straightforward future work.
