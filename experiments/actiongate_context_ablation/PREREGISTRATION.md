# PREREGISTRATION — ActionGate Context Span-Ablation Feasibility

**Status:** FROZEN before any real-provenance run. These thresholds are chosen
from first principles, not tuned against results. The synthetic corpus shipped
here CANNOT emit a scientific verdict (origin lock), so nothing below has been or
can be back-fitted to the fixtures. The constants are mirrored in
`actiongate_context_ablation/verdict.py` and `economics.py`.

## Question

> Is the genuinely action-relevant fraction of realistic agent context small
> enough — and detectable reliably enough, net of prompt caching and compressor
> overhead — that protected-context compression could produce useful token
> savings *without changing any ActionGate decision*?

This experiment measures the **opportunity boundary** only. It does not build a
compressor and does not claim compressor performance. A positive result must not
be forced; the experiment is successful if it cheaply shows the product should
**not** be built.

## Frozen thresholds

| Symbol | Constant | Value | Rationale |
|---|---|---|---|
| `MIN_P0_RECALL` | min protected-unit recall | **1.00** | A single dropped critical unit can flip a real action; safety is not an average. |
| `MIN_DEPLOYABLE_CEILING` | min deployable compression ceiling | **0.25** | Below ~25% token removal, a compressor rarely beats prompt caching + overhead. |
| `MAX_EXTRACTOR_INSTABILITY` | max `r_F` | **0.10** | If >10% of ablations are attributable to F instability, causal labels aren't trustworthy. |
| `MAX_INTERACTION_MISS` | max interaction-miss rate | **0.05** | If >5% of critical units are found only by group/redundancy/pair ablation, single-ablation labeling is inadequate. |
| `MIN_ORACLE_CEILING_NOT_DENSE` | density cutoff | **0.40** | If the true critical fraction exceeds 60% (oracle ceiling < 40%), the workload is intrinsically dense. |
| `min_net_savings_ratio` | economic floor | **0.15** | Cache-adjusted net savings below 15% of baseline cost do not justify a compressor + validator in the loop. |

## Economic assumptions (frozen defaults)

| Assumption | Value | Rationale |
|---|---|---|
| `cacheable_fraction` | 0.50 | Half of enterprise agent context (schemas, policies, unchanged state) is stable/repeated and already cache-cheap. |
| `cache_cost_multiplier` | 0.10 | Cached tokens are ~10% the price of uncached (provider-typical). |
| `overhead_ratio` | 0.05 | Compressor extraction + validation overhead as a fraction of original tokens. |

These are sensitivity parameters, reported alongside results; the demos vary them
to show the break-even behaviour.

## Mechanical outcomes (precedence order)

Emitted ONLY for real-provenance runs (`origin.run_is_scientific`). Precedence:

1. `NOT_ELIGIBLE` — insufficient/invalid data.
2. `EXTRACTOR_NOT_RELIABLE` — `r_F > MAX_EXTRACTOR_INSTABILITY`.
3. `SINGLE_ABLATION_INADEQUATE` — interaction-miss > `MAX_INTERACTION_MISS`.
4. `CONTEXT_INTRINSICALLY_DENSE` — oracle ceiling < `MIN_ORACLE_CEILING_NOT_DENSE`.
5. `DETECTOR_PRECISION_BOTTLENECK` — recall < 1.0 OR deployable ceiling < `MIN_DEPLOYABLE_CEILING`.
6. `ECONOMICS_NOT_SUPPORTED` — cache-adjusted savings < `min_net_savings_ratio`.
7. `ABLATION_OPPORTUNITY_SUPPORTED` — all gates pass.

Synthetic/mock corpora may emit ONLY: `PIPELINE_PATH_VERIFIED`,
`SYNTHETIC_NO_SCIENTIFIC_VERDICT`, or `MOCK_NO_SCIENTIFIC_VERDICT`. The scientific
verdict is computed as *indicative-only* and clearly marked non-authoritative.

## What would make this study real

Replace the authored fixtures with a `NATURALISTIC_REPO` / `FIELD_REAL` corpus of
licensed, provenance-documented action contexts, keep a held-out split untouched,
and re-run. Only then does a mechanical verdict carry weight. No thresholds may be
changed at that point.
