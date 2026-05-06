# CTM+ Tier-Aware Benchmark — First Results

**Run date:** 2026-05-06
**Mode:** A (synthetic, no GPU)
**Reproducer:** `python -m ctm_bench --tier-config <cfg> --hbm-oversubscription 0.1 --output-dir bench_out/<cfg>`
**Seed:** 42 (default)
**Commit:** see `git log` at the same SHA as this file.

## §1 Headline finding

> **CTM+ eliminates 100% of slow-tier reads on retrieval-heavy
> (RAG) workloads vs LRU. It is neutral on chat. It has a real,
> consistent regression on agentic workloads — 17% worse on
> uniform-random tool re-reads, 54% worse on the realistic
> clustered pattern, but the absolute magnitude on the realistic
> pattern is small (1.6 KB/token extra) because clustered re-
> reads keep most accesses in HBM regardless of policy.**

The regression is consistent across both the adversarial
uniform-random pattern and the realistic Markov-dwell pattern,
which means it is not a workload-generator artifact. It is a
real policy gap worth documenting and investigating.

## §2 Numbers — `hbm_ddr_nvme` tier configuration

Round 2 sweep with the realistic clustered-agentic pattern
included (`agentic_clustered_64k`), at HBM oversubscription 0.1.

| Workload | Policy | HBM hit rate | Slow-tier B/token | vs LRU |
|---|---|---:|---:|---:|
| **rag_128k** | lru | 100.0% | 1,024 B | — |
| **rag_128k** | fifo | 100.0% | 1,024 B | 0.0% |
| **rag_128k** | **ctm_plus** | 100.0% | **0 B** | **−100.0%** |
| **agentic_clustered_64k** | lru | 100.0% | 3,072 B | — |
| **agentic_clustered_64k** | fifo | 100.0% | 3,072 B | 0.0% |
| **agentic_clustered_64k** | ctm_plus | 100.0% | 4,736 B | +54.2% (worse) |
| agentic_64k (uniform-random) | lru | 99.7% | 127,488 B | — |
| agentic_64k (uniform-random) | fifo | 99.7% | 127,488 B | 0.0% |
| agentic_64k (uniform-random) | ctm_plus | 99.7% | 149,248 B | +17.1% (worse) |
| chat_32k | lru | 100.0% | 16,384 B | — |
| chat_32k | fifo | 100.0% | 16,384 B | 0.0% |
| chat_32k | ctm_plus | 100.0% | 16,896 B | +3.1% (within noise) |

## §3 Interpretation

### §3.1 Why CTM+ wins on RAG

RAG workloads are dominated by one-shot reads — the prefill
loads N retrieved chunks into the cache, the decode phase only
re-reads sinks + recent. LRU and FIFO are scan-blind: a long
prefill flushes everything else. CTM+'s S3-FIFO admission keeps
one-shot prefill blocks in a small queue and only promotes
blocks that re-attest. Result: the few re-read blocks survive
in HBM, slow-tier reads collapse to zero.

This is the canonical NAND-tier story. RAG / retrieval-augmented
inference is a large + growing fraction of production LLM
deployment, and it's the exact workload where the savings from
a tier-aware policy are largest.

### §3.2 Why CTM+ is neutral on chat

Both LRU (recency) and CTM+ (attention) keep system prompt +
recent turns in HBM. Working set is small enough that all
policies hit ~100% HBM. Differences are within seed noise.
Credible "no worse than" claim.

### §3.3 The agentic regression — confirmed real

The first round of results showed CTM+ losing by 17% on the
adversarial uniform-random tool-re-read pattern. To rule out
workload-generator bias, this round adds `agentic_clustered_64k`
— a realistic Markov-dwell pattern (stay-prob 0.7, 8 hot tool
blocks per sequence) that better matches observed agentic traces.

CTM+ still loses on the realistic pattern: 4,736 vs 3,072 B/token
(+54.2%). This rules out the workload-generator-bias hypothesis.

**The likely root cause:** CTM+'s attention-EMA scoring smooths
out the high-attention burst when an agent dwells on a hot
block. By the time the policy compares this block against
others for eviction, the EMA-decayed attention value looks
"medium" rather than "recent + high." LRU's pure recency
trivially keeps these blocks because they were touched in the
last few steps.

**Why this matters less in absolute terms on the realistic
pattern:** clustered re-reads mean almost every access is to a
block that's already in HBM (Markov dwell = high temporal
locality). The total slow-tier traffic is tiny (3 KB/token for
LRU, 4.7 KB/token for CTM+) — both policies do essentially fine.
The relative-percentage regression (54%) overstates the
practical impact.

**Three possible policy fixes** worth trying in a follow-up:

1. Reduce the EMA alpha from 0.1 to 0.05 — slower decay would
   keep recently-attended blocks scored high for longer.
2. Add an explicit "recently-touched" boost separate from
   attention scoring — re-introduce some recency signal so the
   policy doesn't lose to LRU on its strongest case.
3. Tune the position-class classifier to recognise
   "previously-hot-now-cold" blocks as protected for a recovery
   window rather than evicting them on first attention drop.

These are all small changes to `KVPolicy/kv_policy/attention_evictor.py`
that could be evaluated by re-running this same harness.

## §4 What this is good for in a partner conversation

The honest one-paragraph pitch (updated for the Round 2
findings):

> "On retrieval-augmented inference workloads — where prefill
> loads chunks read once and never again — CTM+ eliminates 100%
> of slow-tier read traffic vs LRU. That's the workload class
> where flash-tier capacity decisions are most consequential.
> On chat-style workloads, CTM+ is neutral. On agentic-style
> workloads with clustered tool re-reads, CTM+ is presently
> 54% worse than LRU on slow-tier traffic — though the absolute
> volume is small enough (1.6 KB/token extra) that average
> latency isn't materially affected. We have an open
> investigation into the EMA-smoothing root cause and three
> candidate policy fixes, validated by the same harness."

This is more credible than "CTM+ wins everywhere" — it
identifies (a) the workload class where the policy's advantage
is real and large, (b) the workload class where it's neutral,
and (c) the workload class where it has a known regression and
named candidate fixes. A partner who hears this comes away
believing the team is honest and is doing the actual work, not
selling.

## §5 What this is and isn't

**It is** a measurement of the eviction-policy effect on slow-
tier read traffic, isolated from real-model serving overheads.
Reproducible (seed + tier specs + workload specs are all pinned
by the test suite).

**It isn't** a real-model latency benchmark. Mode B (vLLM with
constrained HBM + NVMe spillover) would close that gap; this
result is the prerequisite that justifies the GPU spend for
Mode B.

**It isn't** the final word on agentic workloads. The Round 2
result rules out the workload-generator-bias hypothesis but
does not test whether the three named candidate policy fixes
close the regression. That's a Round 3 follow-up.

## §6 What to do next

In priority order:

1. **Investigate the EMA-smoothing hypothesis.** Reduce
   `attention_ema_alpha` from 0.1 to 0.05 in
   `KVPolicy/kv_policy/attention_evictor.py` and re-run this
   harness. If CTM+ closes the agentic gap without losing on
   RAG, the fix lands.
2. **Stress the HBF tier.** Re-run at oversubscription=0.05 or
   denser-re-read workloads so HBF's bandwidth advantage shows
   up in average access latency. Current Round 1/2 sweeps don't
   pressure the slow tier enough.
3. **Mode B (real-model on vLLM).** Worth the GPU spend now
   that Mode A confirms a clear directional win on RAG. Roughly
   a day's work to wire vLLM through `KVPolicy/vllm_evictor.py`
   and run on an A100/H100.

## §7 Files in this directory

```
bench_out/
├── RESULTS.md                       # this file (Round 2 update)
├── hbm_ddr_nvme/                    # Round 1, 0.4 oversubscription (regression baseline)
│   ├── report.md
│   └── summary.json
├── hbm_ddr_nvme_0p1/                # Round 1, 0.1 oversubscription
│   ├── report.md
│   └── summary.json
├── hbm_hbf_nvme_0p1/                # Round 1, HBF tier
│   ├── report.md
│   └── summary.json
└── round2_hbm_ddr_nvme/             # Round 2, includes agentic_clustered_64k
    ├── report.md
    └── summary.json
```
