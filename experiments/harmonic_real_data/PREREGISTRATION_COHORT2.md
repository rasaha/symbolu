# Cohort 2 — strict replication preregistration

**Question:** does the Cohort 1 H-GATE result (harmonic summary tokens beat
statistical summaries, persistence, and daily seasonal-naive on real demand)
replicate on a second, disjoint 200-function cohort?

**Status:** preregistered before any Cohort 2 implementation or selection run;
frozen at the commit introducing this file. Owner-ratified as a strict
replication.

**Everything is inherited unchanged from `PREREGISTRATION.md` (frozen at
0ffc22f9):** eligibility rule, 8/2/4-day split, arms, seeds {0,1,2}, token
definitions, harmonic periods (no tuning), retrieval budget (no redesign),
training budget and optimizer, metric and subject-level aggregation
definitions, variance floor, spike definition, gates V/H/S with identical
thresholds, development envelope, and the one-shot held-out rule. The only
new element is the cohort:

- **Cohort 2 selection (train days d01–d08 only, frozen before any dev or
  held-out use):** apply the identical eligibility rule; exclude the 200
  Cohort 1 functions (`frozen_functions.json`); stratify the remaining
  eligible functions into quintiles by total train invocations; take the 40
  with lexicographically smallest HashFunction per quintile → 200 functions,
  committed as `frozen_functions_cohort2.json` before use.

**Discipline:** no harmonic-period tuning, no retrieval redesign, no
inspection of held-out outcomes before the Cohort 2 freeze commit; harness
plumbing may be parameterized to run a second cohort, with zero changes to
frozen definitions. Held-out (d11–d14) is evaluated exactly once for
Cohort 2.

**Reporting (frozen order):** Cohort 2 gate results are reported separately
first; only then may Cohort 1 + Cohort 2 be aggregated (pooled per-function
win fractions and medians over the 400-function union, labeled as
aggregation). Replication reads on the H-GATE: replicated iff Cohort 2's
H-GATE passes in full; any partial outcome is reported comparison-by-
comparison without softening.

**Non-claims:** dataset stays outside Git; no Phase, semantic-understanding,
production-readiness, or cross-dataset claims; intraday+daily structure only;
verdicts capped at PROVISIONALLY SUPPORTED.
