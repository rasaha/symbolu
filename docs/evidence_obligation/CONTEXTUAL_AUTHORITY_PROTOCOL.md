# Contextual Authority & Implementation Evidence (Phases 11–12)

*`evidence_obligation/contextual_authority.py` + `implementation_evidence.py`. Can an artifact serve as
evidence for its own claims, and what can implementation evidence actually prove?*

## Contextual authority validation (Phase 11)

16 canonical cases run through the frozen-in-this-track `authority.py`. Results: **accuracy 1.0, false
authority 0, unsafe self-support 0, circular self-verification detected 4, stale/historical detected 1.**

| Case | Verdict |
|---|---|
| implementation code × current behavior | AUTHORITATIVE |
| comment / README contradicting code | NOT_AUTHORITATIVE |
| approved policy | AUTHORITATIVE |
| draft / expired policy | NOT_AUTHORITATIVE |
| test result × behavior | AUTHORITATIVE |
| benchmark claim without raw results | SELF_REFERENTIAL |
| telemetry summary / raw telemetry × performance/status | AUTHORITATIVE |
| generated report × current fact | SELF_REFERENTIAL |
| user preference | AUTHORITATIVE |
| model self-description | SELF_REFERENTIAL |
| vendor marketing copy | SELF_REFERENTIAL |
| signed approval record × permission | AUTHORITATIVE |
| audit log × what occurred | HISTORICAL_ONLY |

**Metrics:** true authority recognition, false authority (0), circular self-verification (detected on
benchmark-without-data, generated-report, model-self-description, vendor-marketing), stale authority
(audit log → historical only), unsafe self-support (0). The circular-self-verification guard is the
safety centerpiece: a source can never be evidence for its own factual claim.

## Implementation evidence (Phase 12)

14-case matrix through `implementation_evidence.assess`. Results: **accuracy 1.0.**

| Evidence | Claim | Verdict |
|---|---|---|
| source_code / unit_test | code_behavior | SUPPORTS |
| integration_test | api_behavior | SUPPORTS |
| configuration | internal_policy | SUPPORTS |
| function_signature | api_behavior | SUPPORTS |
| comment_only / dead_code / stale_documentation / mocked_behavior / version_mismatch | code_behavior | INSUFFICIENT |
| feature_flag_disabled | product_capability | INSUFFICIENT |
| source_code | measured_performance | **NON_PRODUCTION** |
| unit_test | current_fact | **NON_PRODUCTION** |
| generated_fixture | measured_performance | NON_PRODUCTION |

**The load-bearing rule:** implementation evidence may support a *behavior/capability* claim but never
automatically proves **production reliability, operational performance, customer availability, security
certification, or real-world effectiveness** — those return `NON_PRODUCTION` and require
telemetry/external authority. This is what stops "the code does X" from becoming "X is reliable in
production."

## Falsification links

- **H0-6** (implementation evidence creates unsafe self-verification): the circular guard yields 0
  unsafe self-support and 0 false authority; weak/stale/mocked evidence is INSUFFICIENT — H0-6 rejected.
- **H0-5** (authority cannot be classified reliably): authority-case accuracy 1.0 on the canonical set —
  evidence against H0-5 (measured again on the natural set in the final evaluation).
