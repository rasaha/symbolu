# TAP-E1.1 — Latency & Cost Report

Quality gains (see the [comparison](./E1_1_COMPARISON.md)) must be weighed against
computational cost. This report separates the **model** cost from the **deterministic**
overhead.

## Measurement honesty

- No Anthropic API was called in this run (no key), so **wall-clock latency and true
  token usage were not measured**. Token counts are **estimates** (~4 chars/token) over
  the exact prompt and the produced JSON core. The `AnthropicModelClient` records real
  `usage.input_tokens` / `output_tokens` and latency when a key is present.
- Deterministic-layer overhead is real Python execution time on the cached cores and is
  negligible relative to any model call.

## Model cost (estimated, hidden eval, per case)

| item | value |
|---|---|
| prompt tokens / case | ~454 |
| completion tokens / case | ~121 |
| total tokens / case | ~575 |
| total tokens, 24 hidden cases | ~13,790 |
| model calls / case | **1** (all of B–F reuse one core) |

Baselines B, C, D, E, F cost the **same** model tokens — the interpretation core is
produced once; the deterministic layers are pure post-processing. Only baseline A uses
the model differently (free text), at similar token cost.

## Deterministic overhead (per case, cost of each frozen layer)

| layer | added model cost | added compute |
|---|---|---|
| schema fill (B) | 1 model call | trivial JSON coercion |
| deterministic extraction (C) | **0** | one regex pass over the request |
| provenance ledger (D) | **0** | O(#fields) dict ops |
| ambiguity/conflict (E) | **0** | a few regex passes |
| clarification policy (F) | **0** | O(#ambiguities) |

## Separation of quality from cost

- Going **A → B** (add schema) is the single largest quality/safety jump (severe
  failures 30 → 0 on eval) and costs no extra model tokens — it changes *how* the model
  is prompted, not *how much*.
- Going **B → D** (add extraction + provenance) raises provenance completeness 0 → 1.0
  and adds authoritative constraint spans at **zero** marginal model cost.
- Going **D → F** adds compute only and, on this corpus, *reduces* quality (F
  over-asks). More computation did not help.

**Conclusion:** the cost-effective configuration is **D** — one model call per request
plus microsecond deterministic post-processing — which is also the quality-selected
config. A real-API replication should record true latency/token usage to confirm.
