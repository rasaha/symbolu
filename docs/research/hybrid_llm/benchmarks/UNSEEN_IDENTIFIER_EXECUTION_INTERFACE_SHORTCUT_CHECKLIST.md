# Unseen-identifier execution-interface & shortcut completion — authorization checklist

Documentation-only. Maximum state:
`EXECUTION_INTERFACE_SHORTCUT_COMPLETION_AUTHORIZATION_DRAFT_READY`.

| # | Item | Status |
|---|---|---|
| 1 | PR #1373 remains unmerged (verified open/draft, head `3ddb8fe9`) | ✅ pass |
| 2 | Command-contract blocker reproduced (no CLI/train/eval/replay/manifest interface) | ✅ pass |
| 3 | Shortcut implementation gap reproduced (8 of 12 baselines) | ✅ pass |
| 4 | Exact planned files frozen (Decision 1) | ✅ pass |
| 5 | CLI subcommands frozen (Decision 2) | ✅ pass |
| 6 | Single-explicit-seed contract frozen (no wildcard/range/list/all-dev) | ✅ pass |
| 7 | Authorization-record schema frozen (Decision 3) | ✅ pass |
| 8 | Primitive guard threading frozen | ✅ pass |
| 9 | Training orchestration frozen (Decision 4; no training in impl/tests) | ✅ pass |
| 10 | Evaluation path frozen (Decision 5; greedy; no constrained/candidate-index) | ✅ pass |
| 11 | Replay definition frozen (Decision 6; retrain+re-eval, digest compare) | ✅ pass |
| 12 | Manifest and trace schemas frozen (Decision 7; actual digests; atomic) | ✅ pass |
| 13 | Four missing shortcuts frozen (source-target co-occurrence, seen-ID freq, output-template, task-label) | ✅ pass |
| 14 | All twelve shortcut definitions frozen | ✅ pass |
| 15 | Aggregation hierarchy frozen (Decision 9; example-count-weighted; per-split frequency isolation) | ✅ pass |
| 16 | Competence-floor comparison frozen (per split) | ✅ pass |
| 17 | Failure modes frozen (Decision 11) | ✅ pass |
| 18 | Fixture-only tests frozen (Decision 12; seeds 993000–993004) | ✅ pass |
| 19 | CI restrictions frozen (fixture-only; no train/cohort/reserved-seed/verdict) | ✅ pass |
| 20 | **No code implemented** | ✅ enforced |
| 21 | **No scientific authorization record created** | ✅ enforced |
| 22 | **No seed consumed** (9070 / 9071–9073 / 90760–90764 untouched) | ✅ enforced |
| 23 | **No execution authorized** | ✅ enforced |
| 24 | Standing invariants preserved | ✅ pass |

**Result:** the corrective execution-interface + shortcut-completion scope, contracts, tests, CI, and
lifecycle are fully specified for independent review. Status:
**`EXECUTION_INTERFACE_SHORTCUT_COMPLETION_AUTHORIZATION_DRAFT_READY`** — no implementation or
execution authorized; PR #1373 unchanged; reserved final seeds remain prohibited.
