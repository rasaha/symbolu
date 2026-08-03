# AI Hiring — Release-Claim Audit

Machine-readable: [`ai_hiring_release_claim_audit.json`](ai_hiring_release_claim_audit.json).
Each historical maturity claim was classified against the live repository.

| Claim | Status | Evidence |
|---|---|---|
| `PACKAGE_READY_FOR_CONTROLLED_PILOT` | **LIVE_VERIFIED** | Product `STABILITY='pre-1.0 / controlled-pilot'`; retained for the independent package only after its own build + clean-install gates passed. |
| 778 AI Hiring tests passed | **LIVE_VERIFIED** | Reran `python -m pytest ai_hiring/tests` → 778 collected, 778 passed. |
| 917 integrated tests passed | **DOCUMENTED_NOT_RERUN** | Full monorepo integrated suite not rerun in this scoped phase; reported as historical. This phase’s scoped totals: **773** package tests + **778** monorepo `ai_hiring` tests. |
| bit-for-bit reproducible wheel | **LIVE_VERIFIED** | Independent wheel built twice with `SOURCE_DATE_EPOCH` pinned → identical `sha256 887e11bf…a38c1f50`. |
| clean-environment install verified | **LIVE_VERIFIED** | Fresh-venv wheel / sdist / editable installs; import + CLI + full test suite run from outside the repo. |
| no vendor AI SDK dependency | **LIVE_VERIFIED** | AST scan: 0 imports of openai/anthropic/mistralai/torch/transformers; core deps are pydantic + 2 Ugence packages. |
| no production certification | **LIVE_VERIFIED** | `version_info().production_certified == False` (hard-coded); asserted by CLI `verify` and tests. |
| human-only binding employment decisions | **LIVE_VERIFIED** | `Decision` validator pins `actor_type=HUMAN`; `decision_boundary.assert_*` enforced; covered by migrated + new governance tests. |
| AI recommendations are advisory only | **LIVE_VERIFIED** | `Recommendation` pins `actor_type=AI`; advisory workflow; covered by migrated tests. |

**Discipline applied:** the historical "917 integrated" count is labelled
historical rather than carried forward as if rerun. The "778" count was rerun and
confirmed. Reproducibility and clean-install claims were re-established against
the *independent* wheel (the historical claims referred to the monorepo wheel).
