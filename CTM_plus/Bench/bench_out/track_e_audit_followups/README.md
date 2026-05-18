# `track_e_audit_followups/` — GPU-measured artefacts for §18, §19, §20

This directory holds the partner-shareable JSON artefacts referenced
by `PHASE4_GPU_FINDINGS.md` §18, §19, and §20. The §18/§19 files are
**measured** on Qwen2.5-7B-Instruct (May 2026 GPU runs); the §20 files
are **pending the next GPU session** (~$0.15 - $3.50 spend depending
on which axes you fill in).

## Files present today (§18/§19 — measured)

| File | What it measures | Section |
|---|---|---|
| `int3_mmlu_1000.json` | INT3 variant MMLU @ 1000q (memory-bound option) | §19.4 |
| `int3_perplexity.json` | INT3 perplexity | §19.4 |
| `int4_calibrated_failed.json` | Static GPTQ-style calibration (decisive negative) | §19.2 |
| `int4_generation_autoregressive.json` | Autoregressive 64% top-1 (the misleading number) | §19.3.1 |
| `int4_generation_teacher_forced.json` | Teacher-forced 96.4% top-1 (the partner-relevant number) | §19.3.2 |
| `int4_mmlu_1000.json` | INT4 KIVI MMLU @ 1000q: 69.30% (−0.90pt) | §19.4 |
| `int4_perplexity_after_packing.json` | INT4 KIVI perplexity 3.8036 (1.024×) | §19.1 |

## Files pending GPU run (§20 — harness landed)

| Expected file | Producer | Section |
|---|---|---|
| `int4_throughput_hf.json` | `python -m ctm_bench.scripts.track_e_throughput --output ...` | §20.1 cells C+D |
| `fp8_int4_comparison.json` | `python -m ctm_bench.scripts.compose_throughput_comparison --json-output ...` (composed from cells A/B/C/D) | §20.1 |
| `sink_fp16_sweep.json` | `python -m ctm_bench.scripts.sink_fp16_sweep --output ...` (single-load sweep over sink ∈ {0, 4, 16, 64}) | §20.2 |
| `sink_fp16_summary.json` | `python -m ctm_bench.scripts.compose_sink_fp16_summary --json-output ...` (composed `§20.2.v1` artefact with GREEN/YELLOW/RED verdict) | §20.2 |
| per-model `results.json` under `bench_out/multi_model/<model_tag>/` | `track_e_quality_eval --model ... --output-dir ...` (one bash-loop invocation per model — Llama-3-8B + Mistral-7B) | §20.3 |
| `multi_model_summary.json` | `python -m ctm_bench.scripts.compose_multi_model_summary --json-output ...` (composed `§20.3.v1` artefact with cross-model GREEN/YELLOW/RED verdict) | §20.3 |
| `long_context.json` | `python -m ctm_bench.scripts.track_e_long_context --output ...` (perplexity sweep + needle-in-haystack in one model load) | §20.4 |
| `long_context_summary.json` | `python -m ctm_bench.scripts.compose_long_context_summary --json-output ...` (composed `§20.4.v1` artefact with combined GREEN/YELLOW/RED verdict) | §20.4 |

The two vLLM cells (A, B) produce `streaming_summary.json` under
`bench_out/fp8_int4_throughput/{vllm_fp16, vllm_fp8}/` per the
runbook. The composer reads them in place; we don't move the files.

## Once §20 cells land

Run the composer:

```bash
cd CTM_plus/Bench
python -m ctm_bench.scripts.compose_throughput_comparison \
    --json-output bench_out/track_e_audit_followups/fp8_int4_comparison.json \
    > /tmp/section_20_1_table.md
```

Then drop `/tmp/section_20_1_table.md` into `PHASE4_GPU_FINDINGS.md`
§20.1 in place of the placeholder table. The composer also writes a
merged JSON that's safe to publish as the partner-shareable §20.1
artefact (schema version pinned at `§20.1.v1`).

## Schema notes

All files in this directory follow one of three schemas:

* **`track_e_quality_eval` output** (perplexity / MMLU / generation):
  top-level `model_id`, `dtype`, `eval_kinds`, `turboquant_config`,
  with per-eval sublists (`perplexity`, `mmlu`, `generation`) and a
  `deltas` block.
* **`track_e_throughput` output** (HF throughput): top-level
  `model_id`, `dtype`, `device`, `config`, with `cells` (per-trial)
  and `aggregates` (per-cell, per-prefill-length best-of-N).
* **`compose_throughput_comparison` output** (the §20.1 merged
  artefact): top-level `schema_version: "§20.1.v1"`, `cells.{A,B,C,D}`
  with `tokens_per_second`, `ratios.{B_over_A, D_over_C, D_over_A}`,
  and `verdicts` against the runbook's decision trees.

Schemas are pinned by the regression tests in `Bench/tests/`. Adding
a field to any schema requires a test update so the partner-shareable
artefact surface stays stable.
