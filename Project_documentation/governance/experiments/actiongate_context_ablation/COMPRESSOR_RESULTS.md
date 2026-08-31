# COMPRESSOR_RESULTS — ActionGate Context Minimization prototype

> Extractive-only (no rewrite/paraphrase/summarize). Objective: maximize token reduction subject to 100% protected recall AND ActionGate decision invariance, fail-closed. Reuses the frozen detector, extractor, and gate; corpus unchanged.

- Corpus: **77** contexts. Detector precision 100.0%. Max safely-removable fraction (non-protected) ≈ **66.0%**.

## Recommendation: **`LIMITED_GO`**

- `all_decision_invariant` = True
- `all_protected_recall_100` = True
- `task_decision_preserved_PROXY` = True
- `cache_adjusted_savings_gt_5pct` = True
- `max_safe_reduction` = 0.659609796596098
- `task_is_llm_proxy_not_real_llm` = True
- `generic_unaware_breaks_decisions` = True

## Budget sweep (target → measured)

| target | actual reduction | decision preserved | protected recall | restored | fallback | task-decision (proxy) | task-incidental (proxy) | latency ms | cost↓ (naive) | cost↓ (cache-adj) |
|---|---|---|---|---|---|---|---|---|---|---|
| 10% | 29.8% | 100.0% | 100.0% | 0 | 0.0% | 100.0% | 55.7% | 7.0 | 29.8% | 14.9% |
| 20% | 30.8% | 100.0% | 100.0% | 0 | 0.0% | 100.0% | 54.4% | 7.0 | 30.8% | 15.4% |
| 30% | 45.6% | 100.0% | 100.0% | 0 | 0.0% | 100.0% | 31.6% | 7.3 | 45.6% | 22.8% |
| 40% | 50.6% | 100.0% | 100.0% | 0 | 0.0% | 100.0% | 23.9% | 7.5 | 50.6% | 25.3% |
| 50% | 62.8% | 100.0% | 100.0% | 0 | 0.0% | 100.0% | 6.4% | 7.3 | 62.8% | 31.4% |
| 60% | 67.7% | 100.0% | 100.0% | 0 | 0.0% | 100.0% | 0.0% | 7.1 | 67.7% | 33.9% |
| 70% | 67.7% | 100.0% | 100.0% | 0 | 0.0% | 100.0% | 0.0% | 7.3 | 67.7% | 33.9% |

## Baselines

| baseline | token reduction | decision preservation |
|---|---|---|
| no_compression | 0.0% | 100.0% |
| structural_only | 1.8% | 100.0% |
| protected_only_max | 67.7% | 100.0% |
| generic_unaware_30 | 46.1% | 98.7% |
| generic_unaware_50 | 65.4% | 88.3% |
| generic_unaware_70 | 79.4% | 49.4% |

**Key comparison:** a protection-*unaware* extractive compressor (a stand-in for LLMLingua-2-style selection — the actual model is not installed here) changes the ActionGate decision in a growing share of contexts as it compresses (1.3% → 50.6% of contexts at 30%→70%), while the protected prototype changes **zero** decisions.

## Adversarial fail-closed test

- Injected a NON-protected span carrying a decisive `sink_approved` fact (a deliberate detector miss). Result: invariant after fail-closed = **True**, span restored or fell back = **True** (full fallback = False). Fail-closed catches the miss the detector made.

## Honest caveats (no claim inflation)

- **Zero decision changes / 100% precision partly reflect corpus structure.** Here filler spans carry no envelope contribution, so removing them is *trivially* decision-invariant, and fact-bearing spans map cleanly onto source types. Real customer context mixes decisive and incidental content within a span/type; invariance will require the fail-closed loop to fire for real, and precision will drop.
- **Budget control is coarse (span-granular).** Whole-span removal means low targets overshoot; the meaningful operating point is essentially binary — the `protected_only_max` point (~66.0% reduction).
- **Task quality is a deterministic information-preservation PROXY, not a real LLM.** No runnable open-weights model is present (no transformers/checkpoints). Decision-relevant information is fully preserved; incidental detail is lost with compression (that is the point). A real LLM benchmark is required to confirm answer-correctness/latency/cost and is the gate to an unconditional GO.
- **Economics use the naturalistic-study assumptions.** Extractive compression adds no tokens (overhead is ~7ms CPU, no LLM calls), so net token savings are positive; but cache-adjusted savings depend on real cache behaviour and real workloads.

## Recommendation narrative

The mechanism **works and is safe on naturalistic data**: up to ~66.0% token reduction at **100% decision invariance and 100% protected recall**, with fail-closed catching an adversarial detector miss, and a protection-unaware compressor demonstrably corrupting decisions where ours does not. This clears every success criterion **on this corpus with a proxy task**. It does not yet clear them on real customer data with a real LLM. **`LIMITED_GO`: proceed to a real-LLM + real-customer-data validation of exactly this pipeline; do not ship a general product on these numbers.** If that validation shows precision collapse or no net economic benefit after prompt caching, STOP.
