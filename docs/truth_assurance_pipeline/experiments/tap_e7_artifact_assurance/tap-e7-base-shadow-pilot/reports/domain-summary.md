# Shadow Pilot — Domain Summary

162 synthetic artifacts, 9 domains × 9 issue types × 2. TAP-E7 (Impl B, read-only) vs author-known ground truth.

| Domain | N | ASSURED | NOT_ASSURED | INDETERMINATE | issues | flagged | issue-recall |
|---|---|---|---|---|---|---|---|
| agent_summary | 18 | 6 | 8 | 4 | 16 | 12 | 0.75 |
| audit | 18 | 6 | 8 | 4 | 16 | 12 | 0.75 |
| compliance | 18 | 6 | 8 | 4 | 16 | 12 | 0.75 |
| financial | 18 | 6 | 8 | 4 | 16 | 12 | 0.75 |
| governance | 18 | 6 | 8 | 4 | 16 | 12 | 0.75 |
| healthcare | 18 | 6 | 8 | 4 | 16 | 12 | 0.75 |
| insurance | 18 | 6 | 8 | 4 | 16 | 12 | 0.75 |
| legal | 18 | 6 | 8 | 4 | 16 | 12 | 0.75 |
| policy | 18 | 6 | 8 | 4 | 16 | 12 | 0.75 |

Recall is uniform across domains because TAP-E7-BASE is domain-agnostic: it operates on the ValidationRecord↔CandidateArtifact correspondence, not domain content.
