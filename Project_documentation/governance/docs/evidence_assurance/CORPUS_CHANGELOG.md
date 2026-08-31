# ea_corpus Changelog

The EvidenceAssurance corpus is generated deterministically in `evidence_assurance/dataset.py`
(`all_cases()`). It is **not** one of the four frozen prior-track artifacts guarded by
`verify_prior_artifacts.py` (those are the AGE and AssertionGate datasets/results). The corpus is
frozen for final evaluation only at Phase 21 (M13); corrections before that point are expected and
recorded here rather than hidden.

## ea_corpus_v1_1 — high-risk-gate correction (found during Phase 12 baselines)

**What was wrong.** Two conditions in `dataset.py` gated on high risk by writing
`c["risk_class"] in HIGH_RISK`. But `risk_class` holds a **severity** label (`low` / `medium` /
`high` / `critical`) while `HIGH_RISK` is a set of **domain names** (`medical`, `legal`,
`financial`, `cybersecurity`, `jurisdiction_sensitive`, `high_risk_reco`). The two vocabularies never
intersect, so both conditions were **always false**:

1. `_hard_precedence()` — the rule "non-authoritative source in a high-risk decision →
   `AUTHORITY_MISMATCH`" never fired. The `indep_lowauth` template (labeled *"AUTHORITY_MISMATCH
   (high-risk)"* in the source) produced **zero** `AUTHORITY_MISMATCH` gold cases; those cases were
   mislabeled `VERIFIED`.
2. `_delivery()` — the escalation "high-risk raises soft withholds (`INSUFFICIENT` / `DEPENDENT` /
   `STALE`) to `ESCALATE`" never fired, so high-risk soft-withhold cases were delivered as `QUALIFY` /
   `INDETERMINATE` instead of `ESCALATE`.

**How it surfaced.** The Phase-12 baselines revealed a degenerate result: composites requiring
authority blocked **100%** of gold-supported cases, because the observed authority vocabulary
(`reputable` / `low`) never matched the strings the predicate compared against — and, digging in, the
gold itself contained no `AUTHORITY_MISMATCH` at all despite the taxonomy and template comments
requiring it. That inconsistency was traced to the severity-vs-domain comparison above.

**Fix.** Both conditions now test `risk_class in ("high", "critical")`. Because `risk_class` is
assigned `high`/`critical` exactly when the domain is in `HIGH_RISK` (see `_mk`), this is equivalent
to the intended domain check while using the field actually available to `_hard_precedence()` /
`_delivery()`.

**Effect on gold (v1 → v1_1).**

| Gold state | v1 | v1_1 |
|---|---:|---:|
| VERIFIED | 104 | 80 |
| AUTHORITY_MISMATCH | 0 | 24 |
| VERIFIED_WITH_LIMITATIONS | 52 | 52 |
| STALE / CONFLICTED / MISALIGNED / REJECT | 104 each | 104 each |
| DEPENDENT | 52 | 52 |

- 24 high/critical-risk, low-authority cases moved `VERIFIED` → `AUTHORITY_MISMATCH`.
- Partition counts unchanged (312 / 156 / 104 / 52).
- `MISALIGNED` gold count unchanged (104) — the alignment module still flags 104/104.
- Annotator disagreement unchanged at 8.33% (the fix is in shared hard precedence, not the soft tail).
- Some high/critical-risk `INSUFFICIENT` / `DEPENDENT` / `STALE` cases now carry `gold_delivery =
  ESCALATE` rather than `QUALIFY` / `INDETERMINATE`.

**Why fix rather than freeze-around.** The corpus had not yet been frozen for evaluation (that is
Phase 21). Keeping a gold-labeling bug that makes an entire disposition (`AUTHORITY_MISMATCH`)
unreachable would silently weaken the evaluation. Per the study's standing rule, the inconsistency is
flagged and corrected in the open, not resolved by inventing a label. The version string is bumped so
no measurement is silently reinterpreted under the same name.
