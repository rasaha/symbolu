# BASELINE_RESULTS — SEEB v1.0.0

**Official Version 1 baseline: the frozen deterministic keyword/sentence
extractor (`InHouseExtractor`).**

> These are **reference numbers only**. They are the fixed point future extractors
> are compared against. They are **NOT enterprise-readiness targets** and they do
> **NOT** indicate the architecture's ceiling — they are the floor a naive
> keyword extractor establishes on synthetic data.

- Benchmark: Sovereign Evidence Extraction Benchmark (SEEB) v1.0.0
- Extractor under test: `InHouseExtractor` (deterministic, keyword/sentence)
- Corpora: 16 synthetic adversarial cases + full fault-injection on 2 control cases
- Runs: 42 evaluation runs per configuration
- Data: **SYNTHETIC**. Reproducible and deterministic (verified).

## Headline — independent validation vs frozen gates alone

| Configuration | Unsafe Handover Rate  P(accept \| decisive missing) |
|---|---|
| Frozen gates only | **65.2% (15/23)** |
| Gates + independent validators | **17.4% (4/23)** |

Independent validation reduces unsafe handovers by ~3.7×, but does **not** reach
zero. The residual is the honest falsification signal.

## Baseline metrics

| Metric | gates_only | augmented |
|---|---|---|
| Critical Evidence Recall | 77.8% (56/72) | 77.8% (56/72) |
| Defeater Recall | 60.0% (3/5) | 60.0% (3/5) |
| Definition Recall | 0.0% (0/2) | 0.0% (0/2) |
| Precedence Recall | 52.9% (9/17) | 52.9% (9/17) |
| Packet Sufficiency | 59.5% (25/42) | 59.5% (25/42) |
| **Unsafe Handover Rate** | **65.2% (15/23)** | **17.4% (4/23)** |
| Unsupported Claim Rate | 9.9% (14/141) | 9.9% (14/141) |
| Coverage Completeness | 76.2% (32/42) | 76.2% (32/42) |
| Routing Accuracy | 66.7% (28/42) | 83.3% (35/42) |
| Fail-closed Rate | 35.0% (7/20) | 85.0% (17/20) |

(Recall / completeness metrics are identical across configs by construction — the
validators change *acceptance/routing*, not what the extractor retrieved.)

## Verdict: **PARTIALLY VALIDATED — not enterprise-ready**

Metrics preventing a stronger verdict (augmented config):
- Unsafe Handover Rate = 17.4% (must be 0 — must fail closed)
- Fail-closed Rate = 85.0% (accepted packets it should have refused)
- Defeater Recall = 60.0% (missed exceptions/overrides)
- Critical Evidence Recall = 77.8%
- Coverage Completeness = 76.2%

## Residual unsafe handovers (augmented)
| Case / injector | Root cause |
|---|---|
| `conflicting_definitions` | definitions carry no domain keyword; no validator enforces definition completeness |
| `inconsistent_numbering` | precedence relationship not recorded; no validator enforces precedence completeness |
| `policy_override` | cross-doc precedence not recorded; verdict wrong but packet "accepted" |
| `later_amendment_override` + `DropPrecedenceRule` | dropped supersession not detected as missing |

Recurring failure classes: **missed definitions** (`conflicting_definitions`),
**missed defeaters** (`buried_exception`, `order_of_precedence`), **missed
precedence** (multiple).

## Confidence-calibration observation
The baseline emits a constant `confidence = 0.96` on all spans. No calibration
signal exists; abstention is entirely validator-driven, not confidence-driven.
Future extractors SHOULD emit calibrated confidence so routing can use it.

## How to regenerate
```bash
python -m agentic.hybrid_handover.evaluation.integrity     # must print OK
python -m agentic.hybrid_handover.evaluation.run_eval      # writes reports/
```
Output is deterministic; these numbers reproduce exactly on any machine.
