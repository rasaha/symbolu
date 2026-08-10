# CORPUS_ACCEPTANCE_REPORT — Verdict

## Pilot acceptance gates
| # | Gate | Result |
|---|---|---|
| 1 | Existing 22 seed cases byte-for-byte unchanged | PASS (verified) |
| 2 | Frozen measurement code unchanged | PASS (verified) |
| 3 | No resolver run | PASS |
| 4 | Every new executable case has a completed adjudication record | PASS |
| 5 | Every accepted case passes leakage checks | PASS (0 findings) |
| 6 | Every accepted graph edge has evidence provenance | PASS (gold sufficiency 0 issues) |
| 7 | No accepted case has unresolved determinate-answer ambiguity | PASS |
| 8 | Duplicate/template checks pass or have documented overrides | PASS (0 hits; 1 documented override pair) |
| 9 | Difficulty calibration complete | PASS (rubric-adjudicated; recal reported) |
| 10 | Corpus statistics regenerated deterministically | PASS |
| 11 | Repeated builds byte-identical | PASS |

## FINAL VERDICT

### Curation pipeline: **CURATION PIPELINE VALIDATED**
Every gate passes; lifecycle, blinding, agreement, duplicate/template, difficulty,
gold-sufficiency, answer-position, and leakage checks are clean and deterministic;
the reject/quarantine gates demonstrably fire on planted defects; the seed remains
immutable. The corpus-EXPANSION PROCESS is reliable and reproducible.

### Is the expanded hidden corpus sufficient to certify BROAD relationship generalization? **No.**
Conservative, evidence-based:
- The combined corpus is **60 cases** (22 + 38). A defensible floor for broad
  certification is ~300–600 cases (~5–10 varied per capability per difficulty
  band); 60 is ~10–20% of that floor.
- Every capability now has ≥3 cases, but **≥3 is enough to detect gross
  memorisation, not to certify generalisation** — several capabilities sit at
  exactly 3, and some edge types (`effective_after` 1, `amends` 2) and Level-5
  depth remain thin.
- Agreement statistics come from a **single annotating process**, not multiple
  independent human annotators, so true inter-annotator reliability is unmeasured.
- Certification is explicitly NOT claimed merely because every capability has
  several cases.

**Two separate conclusions, both evidence-backed:** the curation *process* is
validated; the *corpus* is a prerelease pilot (v0.2) that is not yet sufficient
to certify broad generalisation. No resolver performance is reported.

## Versioning
- Relationship Corpus Curation Specification **v1.0** (the process).
- Hidden Relationship Corpus **Pilot v0.2** (prerelease; 60 cases total).
- Original 22-case seed preserved as an immutable subset.
- NOT labelled RRB v1.0.
