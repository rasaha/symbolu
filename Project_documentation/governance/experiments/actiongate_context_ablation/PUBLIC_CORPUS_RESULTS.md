# PUBLIC_CORPUS_RESULTS — Naturalistic ActionGate Span-Ablation

> **This study uses public (repository-derived) and authored naturalistic data, NOT confidential customer operational data.** It cannot and does not emit REAL_CUSTOMER_VALIDATED.

- ActionGate reference: `0.1.0-ref`  | manifest: `sha256:d0cde387dc40a6b8…`
- Corpus: **77** contexts (42 public / 35 authored), **11** domains, **16** action types, **347** units, **4818** tokens.

## PUBLIC_NATURALISTIC_CORPUS

**Verdict: `EXTRACTOR_NOT_RELIABLE`**  (scientific=False — naturalistic, not customer data)

- [PUBLIC_NATURALISTIC_CORPUS] naturalistic (NOT customer data; cannot emit REAL_CUSTOMER_VALIDATED). extractor instability 0.14 > 0.1

| metric | value | 95% CI |
|---|---|---|
| critical-union fraction | 30.4% | [28.1%, 32.9%] |
| decision-critical fraction | 24.8% | — |
| assurance-critical fraction | 9.2% | — |
| conservative protected fraction | 68.6% | — |
| P0 recall / precision | 63.9% / 28.4% | [47.8%, 78.6%] / [22.6%, 33.4%] |
| oracle ceiling | 69.6% | [67.1%, 71.9%] |
| deployable ceiling | 31.4% | [26.9%, 36.6%] |
| extractor instability (all / held-out) | 14.4% / 35.3% | — |
| interaction-miss / redundancy-only | 7.2% / 3.1% | — |
| cache-adjusted net savings | 22.3% | — |

### By domain (not averaged away)

| domain | contexts | critical-union | oracle ceiling | deployable ceiling | P0 precision |
|---|---|---|---|---|---|
| cicd | 6 | 31.6% | 68.4% | 32.5% | 28.8% |
| database | 3 | 33.8% | 66.2% | 24.7% | 37.6% |
| iam | 6 | 25.0% | 75.0% | 36.7% | 15.3% |
| kubernetes | 6 | 39.9% | 60.1% | 33.0% | 36.9% |
| monitoring | 3 | 19.9% | 80.1% | 31.2% | 18.2% |
| network | 3 | 20.3% | 79.7% | 29.4% | 20.8% |
| repo | 3 | 24.6% | 75.4% | 26.6% | 25.5% |
| secrets | 6 | 34.1% | 65.9% | 29.4% | 34.4% |
| storage | 3 | 28.1% | 71.9% | 32.1% | 25.6% |
| terraform | 3 | 31.6% | 68.4% | 32.5% | 28.8% |

## AUTHORED_REALISTIC_CORPUS

**Verdict: `EXTRACTOR_NOT_RELIABLE`**  (scientific=False — naturalistic, not customer data)

- [AUTHORED_REALISTIC_CORPUS] naturalistic (NOT customer data; cannot emit REAL_CUSTOMER_VALIDATED). extractor instability 0.15 > 0.1

| metric | value | 95% CI |
|---|---|---|
| critical-union fraction | 39.4% | [34.5%, 43.5%] |
| decision-critical fraction | 27.8% | — |
| assurance-critical fraction | 9.5% | — |
| conservative protected fraction | 69.6% | — |
| P0 recall / precision | 63.2% / 35.8% | [47.6%, 77.6%] / [29.0%, 41.3%] |
| oracle ceiling | 60.6% | [56.5%, 65.5%] |
| deployable ceiling | 30.4% | [24.3%, 36.6%] |
| extractor instability (all / held-out) | 15.1% / 51.4% | — |
| interaction-miss / redundancy-only | 12.6% / 3.6% | — |
| cache-adjusted net savings | 21.3% | — |

### By domain (not averaged away)

| domain | contexts | critical-union | oracle ceiling | deployable ceiling | P0 precision |
|---|---|---|---|---|---|
| cicd | 4 | 37.4% | 62.6% | 29.5% | 37.5% |
| database | 3 | 33.6% | 66.4% | 17.4% | 30.9% |
| iam | 5 | 39.7% | 60.3% | 36.8% | 32.0% |
| kubernetes | 5 | 44.1% | 55.9% | 34.1% | 38.0% |
| monitoring | 4 | 28.2% | 71.8% | 25.2% | 27.0% |
| network | 3 | 27.5% | 72.5% | 29.0% | 28.0% |
| payments | 3 | 53.9% | 46.1% | 31.1% | 52.8% |
| secrets | 3 | 43.5% | 56.5% | 29.2% | 43.7% |
| storage | 2 | 36.5% | 63.5% | 33.7% | 24.6% |
| terraform | 3 | 36.5% | 63.5% | 29.8% | 32.0% |

## Annotation (two-pass) & context lengths

- Pass-1 declared vs pass-2 gate-derived agreement: **96.0%** (333 agree / 14 disagree / 0 uncertain over 347 annotated). Disagreements are recorded, not resolved.
- Context length (tokens): min 25, p25 54, median 66, p75 69, max 100, mean 62.6.

## By action type (heterogeneity)

| action type | critical-union | oracle ceiling | deployable ceiling |
|---|---|---|---|
| branch_protection | 24.6% | 75.4% | 26.6% |
| cloud_storage_delete | 31.0% | 69.0% | 32.7% |
| credential_scope_change | 24.2% | 75.8% | 45.0% |
| customer_data_export | 30.2% | 69.8% | 31.2% |
| database_migration | 33.7% | 66.3% | 21.7% |
| iam_grant | 35.3% | 64.7% | 30.7% |
| incident_mitigation | 25.0% | 75.0% | 15.9% |
| kubernetes_delete | 49.9% | 50.1% | 33.4% |
| kubernetes_deploy | 32.7% | 67.3% | 33.7% |
| monitoring_disable | 23.5% | 76.5% | 32.7% |
| network_policy | 23.4% | 76.6% | 29.2% |
| payment_refund | 53.9% | 46.1% | 31.1% |
| release_promotion | 35.3% | 64.7% | 38.5% |
| secret_export | 40.1% | 59.9% | 28.4% |
| service_rollback | 32.1% | 67.9% | 24.8% |
| terraform_apply | 33.9% | 66.1% | 31.2% |

_Naturalistic corpora may emit corpus-level opportunity verdicts but never REAL_CUSTOMER_VALIDATED. Real customer operational data is still required for a production decision._
