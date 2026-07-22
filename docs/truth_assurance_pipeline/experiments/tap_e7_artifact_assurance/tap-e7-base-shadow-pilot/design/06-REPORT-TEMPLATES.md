# 6. Report Templates

## 6.1 Per-artifact report
```
case_id, domain, package_commit, config_fingerprint
validation_record (summary), candidate_artifact (hash + excerpt)
expected_relationship | human_assessment (reviewer1, reviewer2, category, confidence, time)
tap_outcome | tap_findings[] | projection_pi_sha256
comparison: {agreement: human_vs_tap, taxonomy_class, adjudication, disposition}
```

## 6.2 Daily summary
- cases run today, per-domain counts, outcome distribution
- running precision/recall/indeterminate, new tracked issues, fingerprint/immutability check result

## 6.3 Domain summary (see reports/domain-summary.md)
Per domain: N, outcome distribution, issue count, flagged count, issue-recall; note that BASE is
domain-agnostic (recall uniform across domains in the demo).

## 6.4 Overall pilot report (see reports/overall-pilot-report.md)
Setup + read-only attestation; outcome distribution; confusion + precision/recall/indeterminate;
per-issue detection table; honest interpretation (strengths, bounded recall, escalation value).

## 6.5 Executive dashboard (see reports/executive-dashboard.html)
Stat tiles (precision, recall, indeterminate, engine-gap misses); outcome bar chart; per-issue
detection table; plain-language "read this honestly" section. Self-contained HTML, theme-aware.
