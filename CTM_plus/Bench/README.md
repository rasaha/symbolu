# CTM+ Tier-Aware Inference Benchmark

Mode A (synthetic, no GPU required). Mode B (vLLM real-model) is
a follow-up — only worth running once Mode A shows the directional
result.

## §1 What this answers

**One question:** when KV-cache pressure forces blocks out of HBM
into a slow tier (DRAM, NVMe, or HBF), does CTM+ reduce the bytes
read from the slow tier compared to LRU, by enough to matter?

Headline metric: `slow_tier_bytes_per_decode_token`. Reduction vs.
LRU is the number that goes in the report.

## §2 Quick start

```bash
# From the repository root.
cd CTM_plus/Bench

# Sanity-check / smoke run (small contexts, runs in seconds).
python -m ctm_bench --smoke

# Full sweep — 3 workloads × 3 policies × 1 tier config.
# Writes summary.json + report.md into ./out/
python -m ctm_bench --output-dir out

# Same sweep on the SanDisk-pitch tier configuration (HBM + HBF + NVMe).
python -m ctm_bench --tier-config hbm_hbf_nvme --output-dir out_hbf
```

If the `kv_policy` package (sibling `CTM_plus/KVPolicy/`) is not
installed, the CTM+ cells skip with a clear message; LRU + FIFO
cells still run.

```bash
# Install the sibling kv_policy package so the CTM+ adapter loads.
pip install -e ../KVPolicy
```

## §3 What it measures

Per (workload, policy, tier-config) cell, the runner reports:

* `bytes_read` per tier — the headline number for the
  NAND/HBF-pitch story.
* `bytes_written` per tier — eviction traffic.
* `accesses_served` per tier — hit-counter breakdown.
* `cumulative_latency_ns` per tier.
* `evictions_to_tier` — where evicted blocks landed.
* `hbm_hit_rate` — derived top-line.
* `slow_tier_bytes_per_decode_token` — the comparable headline.
* `avg_access_latency_ns` — derived top-line.
* `wall_clock_seconds` — runner overhead.

The summary roll-up also computes pairwise reductions vs. the
LRU baseline so a markdown table renders directly.

## §4 What it doesn't measure (yet)

State these so the harness doesn't get cited as something it
isn't:

* **Quality / accuracy** — this is a system benchmark. Recompute-
  on-evict is a rough proxy for quality but not a substitute for
  perplexity / accuracy measurement. Quality requires a separate
  harness.
* **Multi-GPU / tensor-parallel scaling** — out of scope.
* **Production serving overheads** (scheduling, batching, prefix
  caching, paged-attention block management) — explicitly absent
  in Mode A so the eviction effect is isolated.
* **CTM+ vs every known eviction policy** — only LRU + FIFO + CTM+
  are wired. ARC and S3FIFO are reasonable follow-ups.
* **Real-model latency** — Mode A reports modelled latency from
  the tier specs, not measured wall-clock TTFT/ITL on a real
  model. That's Mode B's job.

## §5 Workloads

Three patterns, each chosen for a specific NAND-tier characteristic:

| Workload | Pattern | NAND-tier characteristic |
|---|---|---|
| `agentic_64k` | Tool-use re-read of scratchpad blocks | Re-read sweet spot — tier-aware policy should win clearly |
| `rag_128k` | One-shot retrieval, no re-reads | Scan-resistance test — policy must not let one-hit-wonders evict useful blocks |
| `chat_32k` | Multi-turn, system prompt + recent turns re-read | Sink + entity classification test |

Override defaults via the CLI; pinned variants live in
`ctm_bench.workload.{AGENTIC_64K, RAG_128K, CHAT_32K}` and their
parameters are pinned by `tests/test_workload.py`.

## §6 Tier configurations

Two pinned configurations:

* `hbm_ddr_nvme` — HBM3e + DDR5 + NVMe Gen5. Conventional
  inference rig.
* `hbm_hbf_nvme` — HBM3e + High Bandwidth Flash (SanDisk-class
  AI flash) + NVMe Gen5. The "SanDisk pitch" cell.

Capacity, latency, and bandwidth numbers are pinned by
`tests/test_tier_model.py`. Updating them requires updating the
test in the same commit + a benchmark re-run.

## §7 File layout

```
CTM_plus/Bench/
├── README.md               # this document
├── setup.py
├── ctm_bench/
│   ├── __init__.py         # re-exports
│   ├── tier_model.py       # TierSpec + TieredCache + TierCounters
│   ├── policies.py         # LRU + FIFO + CTM+ adapter
│   ├── workload.py         # three patterns + pinned specs
│   ├── metrics.py          # RunResult + summarize + markdown_table
│   ├── runner_sim.py       # Mode A end-to-end runner
│   └── __main__.py         # CLI
└── tests/
    ├── test_tier_model.py  # pinned 2025 cost numbers + cache invariants
    ├── test_policies.py    # LRU + FIFO behaviour + adapter import path
    ├── test_workload.py    # generator determinism + spec pins
    └── test_runner_sim.py  # end-to-end smoke + summary roll-up
```

## §8 Reproducer for a published result

When you publish a benchmark cell in a deck or memo, include the
exact command + commit so the result can be re-run:

```
git rev-parse HEAD                                # commit pin
python -m ctm_bench \
    --workloads agentic_64k,rag_128k,chat_32k \
    --policies lru,fifo,ctm_plus \
    --tier-config hbm_hbf_nvme \
    --seed 42 \
    --output-dir bench_out_2026/
```

The seed + tier config + workload list fully determine the
result; the pinning tests in `tests/` ensure none of those drift
between runs.

## §9 Status

Mode A is in this commit (synthetic, runnable today). Mode B
(real model via vLLM) is a separate ticket — see
`Bench/README.md` §1 of the broader plan: don't burn GPU cost on
Mode B until Mode A shows a positive directional result.
