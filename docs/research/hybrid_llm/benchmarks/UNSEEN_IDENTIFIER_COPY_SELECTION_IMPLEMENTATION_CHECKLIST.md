# Unseen-identifier copy/selection — implementation-authorization checklist

Documentation-only. Pass/fail record for the implementation-authorization draft. Maximum state:
`IMPLEMENTATION_AUTHORIZATION_DRAFT`.

| # | Item | Status |
|---|---|---|
| 1 | PR #1369 (protocol lock) independently audited and **merged first** (merge `ec9145f2`) | ✅ pass |
| 2 | Protocol source identified (merged `single_hop_typed_vs_prose` + locked protocol docs) | ✅ pass |
| 3 | Exact implementation paths frozen (Decision 2 file table) | ✅ pass |
| 4 | Exact reusable model/trainer identified (imported, not copied) | ✅ pass |
| 5 | No architecture change (sibling package; frozen recipe by import; no new abstraction) | ✅ pass |
| 6 | Identifier-generator contract frozen (Decision 3; disjoint pools, fail-closed) | ✅ pass |
| 7 | C1–C8 generator contract frozen (Decision 4; no constant-gold in primary; no final-pool gen) | ✅ pass |
| 8 | Serializer frozen (Decision 5; byte-identical; no candidate-index) | ✅ pass |
| 9 | Parser categories frozen (Decision 5; 7 categories; no silent repair) | ✅ pass |
| 10 | Metrics frozen (Decision 7) | ✅ pass |
| 11 | Verdict precedence frozen (Decision 7 → protocol-lock Decision 8 total order) | ✅ pass |
| 12 | Shortcut code plan frozen (Decision 8; hard pre-reserved precheck; blocking artifact) | ✅ pass |
| 13 | Fingerprint plan frozen (Decision 9; actual digest values; per-example traces) | ✅ pass |
| 14 | Test matrix frozen (Decision 10) | ✅ pass |
| 15 | CI plan frozen (Decision 11; `unseen-identifier-integrity`; no train/cohort/reserved-seed) | ✅ pass |
| 16 | Fixture-only seed namespace frozen (`993000–993004`; verified unused) | ✅ pass |
| 17 | Reserved-seed guards frozen (fail-closed on 9070 / 9071–9073 / 90760–90764) | ✅ pass |
| 18 | **No implementation performed** (documentation-only) | ✅ enforced |
| 19 | **No execution authorized** (no cohort, no training, no seed consumed) | ✅ enforced |
| 20 | Standing invariants preserved | ✅ pass |

**Result:** implementation scope, tests, CI, fingerprints, and lifecycle fully specified for
independent review. Status:
**`UNSEEN_IDENTIFIER_COPY_SELECTION_IMPLEMENTATION_AUTHORIZATION_DRAFT_READY`** — no implementation
or execution authorized.
