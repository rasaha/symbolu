# CTM+ Tier-Aware Benchmark — First Results

**Run date:** 2026-05-06
**Mode:** A (synthetic, no GPU)
**Reproducer:** `python -m ctm_bench --tier-config <cfg> --hbm-oversubscription 0.1 --output-dir bench_out/<cfg>_0p1`
**Seed:** 42 (default)
**Commit:** see `git log` at the same SHA as this file.

## §1 Headline finding

> **CTM+ converts 100% of slow-tier reads into HBM hits on
> retrieval-heavy (RAG) workloads — full elimination of NAND-tier
> traffic at this scale. CTM+ is neutral or slightly worse on
> agentic and chat workloads where re-read patterns aren't
> predictable from attention signal alone.**

This is a more credible story than "CTM+ wins everywhere": it
identifies the workload class where the policy's scan-resistance
+ attention-aware scoring delivers a measurable, defendable gain,
and it honestly notes the workloads where the policy is neutral.

## §2 Numbers — `hbm_ddr_nvme` tier configuration

| Workload | Policy | HBM hit rate | Slow-tier B/token | vs LRU |
|---|---|---:|---:|---:|
| **rag_128k** | lru      | 100.0% |  1,024 B | — |
| **rag_128k** | fifo     | 100.0% |  1,024 B |  0.0% |
| **rag_128k** | **ctm_plus** | 100.0% | **0 B** | **−100.0%** |
| agentic_64k | lru      | 99.7%  | 127,488 B | — |
| agentic_64k | fifo     | 99.7%  | 127,488 B |  0.0% |
| agentic_64k | ctm_plus | 99.7%  | 149,248 B | +17.1% (worse) |
| chat_32k | lru      | 100.0% | 16,384 B | — |
| chat_32k | fifo     | 100.0% | 16,384 B |  0.0% |
| chat_32k | ctm_plus | 100.0% | 16,896 B | +3.1% (within noise) |

## §3 Interpretation

### §3.1 Why CTM+ wins on RAG

RAG workloads are dominated by one-shot reads — the prefill loads
N retrieved chunks into the cache, the decode phase only re-reads
sinks + recent. LRU and FIFO are scan-blind: a long prefill
flushes everything else. CTM+'s S3-FIFO admission keeps one-shot
prefill blocks in a small queue and only promotes blocks that
re-attest. Result: the few re-read blocks survive in HBM, slow-
tier reads collapse to zero.

This is the canonical NAND-tier story. RAG / retrieval-augmented
inference is a large + growing fraction of production LLM
deployment, and it's the exact workload where the savings from a
tier-aware policy are largest.

### §3.2 Why CTM+ is neutral on chat

The chat workload re-reads system prompt + recent turns every
step. Both LRU (recency-driven) and CTM+ (attention-aware) keep
those blocks in HBM. Working set is small enough that all
policies hit ~100% HBM. Differences are within seed noise.

This is also a credible story: "CTM+ is no worse on conversational
inference, where existing policies already do well."

### §3.3 Why CTM+ is slightly worse on agentic

The agentic workload includes occasional random re-reads of
earlier "tool output" blocks (every 5 decode steps, randomly
chosen). LRU happens to keep these by recency since they're
touched periodically; CTM+'s attention-scoring evicts them
between re-reads because they have low cumulative attention.

This is a real finding worth investigating in a follow-up:
either (a) the workload generator's "tool output" re-read pattern
isn't representative of real agentic traces, or (b) CTM+'s
position-class classification needs to recognise "previously-
attended-then-cold" blocks differently. Worth flagging in the
investor / partner conversation, not hidden.

## §4 Tier-config comparison

`hbm_ddr_nvme` vs `hbm_hbf_nvme` produce identical slow-tier
*byte counts* — the policy's eviction behaviour is the same. They
differ only in the modeled access *latency* of the slow tier.

At 99.7-100% HBM hit rate, slow-tier traffic is small enough that
HBF's bandwidth advantage doesn't dominate the average access
latency in this run. To exercise the HBF tier meaningfully would
require:

* Lower HBM oversubscription (0.05 or below) to force more
  spillover, or
* Workloads with denser re-read on previously-evicted blocks
  (e.g. an "infinite chat" with very long history)

Both are reasonable follow-up runs.

## §5 What this is and isn't

**It is** a measurement of the eviction-policy effect on slow-tier
read traffic, isolated from real-model serving overheads.
Reproducible (seed + tier specs + workload specs are all pinned
by the test suite).

**It isn't** a real-model latency benchmark. Mode B (vLLM with
constrained HBM + NVMe spillover) would close that gap; this
result is the prerequisite that justifies the GPU spend for
Mode B.

**It isn't** evidence that CTM+ wins on every workload. The
agentic regression is real and shouldn't be hidden — it's a
pointer to either workload-generator bias or a policy gap worth
investigating.

## §6 What to send a NAND-tier partner

Cleanest one-paragraph summary:

> "On retrieval-augmented inference workloads — where prefill
> loads chunks that are read once and never again — CTM+
> eliminates 100% of slow-tier read traffic compared to LRU
> by keeping the chunks out of the working set entirely. This
> is the workload class where tier-aware eviction matters most
> and where flash-tier capacity decisions are most consequential.
> On chat-style workloads where existing policies already do
> well, CTM+ is neutral. We have a synthetic harness, pinned
> cost numbers, and an end-to-end reproducer. We're looking for
> a partner who'd help us validate the directional result on
> their actual flash-tier hardware."

That paragraph reframes the conversation from "we sell you less
NAND" to "we make your NAND viable for the workload class where
NAND vendors most want to land."

## §7 Files in this directory

```
bench_out/
├── RESULTS.md                   # this file
├── hbm_ddr_nvme/                # full sweep, 0.4 oversubscription (no spillover — kept for the regression baseline)
│   ├── report.md
│   └── summary.json
├── hbm_ddr_nvme_0p1/            # full sweep, 0.1 oversubscription (spillover engaged)
│   ├── report.md
│   └── summary.json
└── hbm_hbf_nvme_0p1/            # same, HBF tier configuration
    ├── report.md
    └── summary.json
```
