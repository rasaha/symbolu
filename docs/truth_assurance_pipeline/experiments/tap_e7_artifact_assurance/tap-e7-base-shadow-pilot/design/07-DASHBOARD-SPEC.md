# 7. Dashboard Specification

## Audience & intent
One screen for a decision-maker to judge TAP-E7's operational value **and its limits** at a glance,
without over-claiming.

## Required elements
1. **Header:** package commit, config fingerprint, sample size, explicit "read-only / no decisions" banner.
2. **Stat tiles:** Precision; Recall (overall); Recall (BASE-detectable); Indeterminate rate;
   Engine-gap misses. Each tile carries a one-line honest caption.
3. **Outcome distribution** bar chart (ASSURED / NOT_ASSURED / INDETERMINATE) with counts.
4. **Detection-by-issue table:** issue, in-BASE-scope flag, flag rate, typical outcome.
5. **Honesty panel:** strengths, the bounded-recall gap (scope/qualifier), escalation value, verdict.
6. **Footnote:** reviewer-agreement / review-time are human-pilot metrics, N/A in synthetic demo.

## Design rules
- Self-contained (inline CSS/SVG), no external assets; theme-aware (light/dark).
- No metric shown that TAP-E7 cannot support. No RAG-style "score" that implies semantic judgment.
- Color: green ASSURED, red NOT_ASSURED, amber INDETERMINATE — consistent everywhere.
- Numbers link back to `results/metrics.json` (single source of truth; dashboard is generated, not hand-edited).

## Reference implementation
`reports/executive-dashboard.html`, generated from `results/metrics.json` by the pilot harness.
