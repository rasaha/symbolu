# KVPro Mixed-Precision Scenario Test Plan (pre-registered)

**Internal engineering plan.** Purpose: find, *empirically*, the density-vs-quality frontier for KVPro
hot-tier KV across real-world workloads — and let the data choose the mixed-precision fraction rather
than assuming a value (e.g. "10%"). **Pre-registered:** the configs, sweep grid, metrics, equivalence
margins, and decision rule are fixed **before** any run, so the recommended fraction is *discovered*,
not fitted. Evidence labels: **MEASURED / MODELED / RESOURCE_BLOCKED**.

Status: **plan frozen, not yet executed.** Runnable slices and adds are called out in §11.

---

## 1. Question

For each real workload, what is the **cheapest** (highest-density) hot-tier KV configuration that still
meets a **pre-registered quality bar** — and does adding a small **recent-token BF16 window** on top of
KVPro's channel protection help, hurt, or do nothing?

## 2. Configurations under test

All relative to the reference. "Fraction" knobs are the **independent variables** (§5).

| Tag | Definition |
|---|---|
| **B0 — Baseline** | 100% BF16 KV (every channel, every token). The 1.00× reference. |
| **K(p) — KVPro today** | INT4 KV with **p% of channels** protected (per token). p ∈ {0, 2, 4, 8}. `K(0)` = plain INT4 (no protection). |
| **W(n) — Recent-window BF16** | last **n tokens** kept 100% BF16, older tokens INT4. n as tokens {0,32,128,256,512} and as % {0,1,2,5,10,20}. |
| **K(p)+W(n)** | combined: last-n tokens BF16, older tokens INT4 with p% channel protection. |
| **FP8 (ref)** | full-tensor FP8 KV — external **quality reference** only (the lossy incumbent). |

**Selection rule for W is STATIC recency** (last-n by position) — prefix-cache-safe. Dynamic
importance-based selection is **excluded** from the primary result (it breaks prefix reuse; may be a
separate labeled experiment).

## 3. Hypotheses (falsifiable)

- **H1.** On outlier-heavy models, `K(4)` meets the quality bar at every context; `K(0)` (plain INT4)
  fails long-context retrieval. *(re-confirms channel protection is load-bearing)*
- **H2.** A small static window `W(n)` **on top of** `K(4)` yields **≤ marginal** quality gain on the
  tested models (KVPro already near parity), at a **measurable density cost** (BF16 recent tokens are
  4× a compressed token). i.e. the recent-window knob is mostly redundant with channel protection.
- **H3.** The **density-optimal config that still passes** differs by workload — chat/recency-heavy
  tolerates a small window; long-context single-shot retrieval does not need one. **No single global
  fraction is optimal.**
- **H4.** Any config's **decode speed** is ≤ B0 (mixed precision never speeds decode up; more BF16
  tokens = more bytes read). Density and quality are the only axes where mixed precision can win.

The plan is designed so each hypothesis can be **falsified** by the measured frontier.

## 4. Scenarios (real workloads)

| # | Scenario | KVPro lever stressed | Dataset | Primary quality metric | Context |
|---|---|---|---|---|---|
| S1 | **Long-context retrieval** (quality tripwire) | quality-at-density | needle-in-haystack (have), passkey (have), RULER (add) | exact retrieval acc vs depth×context | 4K–64K |
| S2 | **Multi-turn chat** | recency window + density + prefix reuse | WildChat / LMSYS-Chat-1M / ShareGPT (add) | continuation exact-match + LLM-judge tie-rate | grows 2K–32K |
| S3 | **RAG QA** | prefix reuse + quality | LongBench (HotpotQA/2WikiMQA/NarrativeQA) (add) | answer EM / F1 | 8K–32K |
| S4 | **Agentic tool-use** | prefix reuse + quality cascade | tool-call traces (add) / synthetic | tool-call correctness / task completion | grows |
| S5 | **Code / repo-context** | long context + quality | HumanEval / MBPP + repo context (add) | pass@1 | 4K–32K |
| S6 | **High-concurrency serving** | density → throughput (not quality) | any long prompt set at saturation | sessions/GPU, tokens/s | 8K–32K |

**Start order:** S1 (tripwire) → S2 (the recency hypothesis) → S6 (density) → S3/S5 → S4.

## 5. Sweep grid (independent variables)

- **Channel-protect p:** {0, 2, 4, 8} %
- **Recent-window n:** {0, 32, 128, 256, 512} tokens  *(also expressed as % of context)*
- **Context length L:** {4K, 16K, 32K, 64K} (to model window)
- **Concurrency / batch:** {1, 8, max stable}
- **Models:** Mistral-7B-Instruct-v0.3 (have), **Qwen2.5-7B** (outlier-heavy), **Qwen3-8B** (clean QK-norm)
- **Seeds:** ≥3 for noisy/quality metrics

Full grid is large; run **fractional-factorial**: fix L=32K, batch=1 for the quality sweep over (p,n);
fix p=4%, n∈{0,256} for the context/concurrency sweep. Expand only where the frontier is close to a gate.

## 6. Metrics (dependent variables)

- **Quality:** the per-scenario metric in §4 (and PPL as a secondary continuous signal).
- **Density (MEASURED):** real KV bytes/token; resident sessions/GPU (via `gpu_mem_speed_capture.py` +
  writer accounting).
- **Decode:** tokens/s, per-token latency P50/P95 (via `e2e_decode_bench.py`).
- **Prefill / reuse:** TTFT **with and without** prefix reuse (S2/S3 especially).
- **Peak GPU memory.**

## 7. Pre-registered equivalence gates (locked at plan freeze)

A config **PASSES** a scenario at a context length iff it meets **all** applicable gates vs **B0**:

| Metric | Gate (vs 100% BF16) |
|---|---|
| Retrieval / needle / passkey exact acc | ≥ B0 − 1 point **and** ≥ 98% of B0 |
| Perplexity | ≤ B0 × 1.01 (+1%) |
| Chat LLM-judge | tie-or-better rate ≥ 95%; mean score Δ within seed-noise 95% CI |
| RAG EM/F1 | ≥ B0 − 1 point |
| Code pass@1 | ≥ B0 − 1 point |

These margins are **fixed now**; no post-hoc adjustment. FP8 is charted alongside as the lossy reference
(expected to fail S1), not as a gate.

## 8. Decision rule (how the fraction is chosen — not assumed)

For each **(scenario, model, context)**:
1. Keep only configs that **PASS** all §7 gates.
2. Among passing configs, pick the one with **minimum KV bytes** (max density) → that is the
   **recommended config** for that cell. Its (p, n) *is* the discovered fraction.
3. If `K(4)` alone passes and no `+W(n)` improves density while passing → **recommend plain KVPro**
   (H2 confirmed) and report the recent-window knob as **not worth it** for that workload.
4. Report the full **density-vs-quality Pareto per workload**; **no single global fraction** is claimed.

## 9. Confounders & controls

Held identical across configs: model weights, tokenizer, prompts, seeds, calibration mask, INT4
quantizer, page/block size, kernel path. **Prefill and decode measured separately.** Every quality run
labeled **fake-quant reference** vs **production kernel** (don't conflate). Static-recency window only in
the primary result; any dynamic-selection run is a **separate, labeled** experiment (prefix-cache
impact noted).

## 10. Honesty guardrails (no cherry-picking)

The frontier must include the **weak cases**, reported alongside the wins:
- **single latency-critical interactive stream** (decode 0.13–0.67× penalty shows here), and
- **long chain-of-thought generation** (KVPro's least-favorable regime).
Deliverable states "helps / neutral / costs" per workload — not wins only.

## 11. Runnable now vs needs adding

- **Now (pod, existing tooling):** S1 (needle + passkey) and the (p, n) quality sweep on Mistral via the
  `p8_gate` fake-quant path + `gpu_mem_speed_capture.py` (density) + `e2e_decode_bench.py` (speed). A
  first real Pareto in hours. *(The recent-window `W(n)` variant needs a small addition to the
  fake-quant reconstruct path — token-position mask alongside the channel mask.)*
- **Needs a dataset/harness add:** S2 chat (WildChat/LMSYS), S3 RAG (LongBench), S4 tool traces,
  S5 code (HumanEval). Small, well-scoped harness work.
- **RESOURCE_BLOCKED without a GPU pod:** all quality/density/speed measurement (this plan is authored
  CPU-only; execution is pod-only).

## 12. Deliverables

`docs/KVPRO_MIXED_PRECISION_SCENARIO_RESULTS.md` + `artifacts/mixed_precision/`:
`pareto_<scenario>.csv` (per-config density, quality, decode), `recommended_config.json` (the discovered
(p, n) per workload), `weak_case_frontier.csv`, `environment.json`. Each row labeled MEASURED / MODELED.

## 13. Success = a decision, not a number

The plan succeeds when it produces, per workload, a **Pareto-backed recommended config** with an honest
"where it helps / is neutral / costs" frontier — including the case where the answer is "plain KVPro
channel-protection, no recent window." We fund the measurement and accept whichever fraction the data
returns.
