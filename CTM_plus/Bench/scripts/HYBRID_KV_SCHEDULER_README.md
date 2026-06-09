# Hybrid bf16 / int4_protected KV scheduler — cost-model harness

> **One-liner.** A CPU-only decision tool that tells you **where** int4_protected
> starts beating bf16 (the per-sequence crossover length), **how much** a hybrid
> scheduler saves on a real workload, and **whether** the "never worse than bf16"
> guarantee holds — *before* anyone writes the vLLM mixed-dtype-pool plumbing.
> It is the "is this worth building, and where do we set the threshold?" step
> from the operational (#4/#6) memory path.

Files: `hybrid_kv_scheduler.py` (model + CLI), `../tests/test_hybrid_kv_scheduler.py`
(invariant gates). Pure stdlib — runs anywhere.

## The finding it encodes (why a hybrid is even a thing)

On the axis a scheduler actually uses — **same workload, per sequence** —
int4_protected is **~0.55× bf16 per token** (the audited ~1.8× net density,
`MEMORY_STORY.md` §1/§4). So it *wins* on long sequences outright. The measured
**"+4.68 GB more at equal `gpu_util`"** is **not** a same-workload penalty; it's the
cost of int4 serving ~2× the load in that experiment.

The only thing that makes int4 *lose* at short length is the **length-independent
overhead**: a fixed CUDA-graph/kernel tax + a **per-active-slot staging pool**.
Those set the crossover. So the harness models them explicitly:

```
bf16  per seq:           c · L                       (c = bf16 KV bytes/token, exact)
int4  per seq (marginal): stage_per_slot + frac · c · L   (+ one-time fixed pool tax)
crossover  L* = stage_per_slot / ((1 − frac) · c)
```

`L*` depends on the per-slot staging pool and **not** on batch — short sequences are
cheaper in bf16, long ones in int4.

## The four policies (and their guarantees)

| policy | what it does | guarantee |
|---|---|---|
| `bf16-only` | baseline | — |
| `int4-only` | everything int4 | ≤ bf16 **only above** the load crossover; **loses at short ctx** |
| `hybrid two-pool (#4)` | both pools open; route each seq to its cheaper pool | **NOT** unconditional — loses by ≤ fixed_tax when too little long load amortizes opening the int4 pool |
| `hybrid guarded (#4*)` | `min(bf16, two-pool)` — open int4 pool only if net-positive | **≤ bf16 always** ✅ |
| `load-switch (#6)` | `min(bf16-only, int4-only)` — one pool at a time | **≤ bf16 always** ✅, but **cannot mix** (short seqs pay int4 when the system has flipped) |

The guarded hybrid (#4*) is the one that delivers the user's stated goal —
**footprint never worse than bf16, in every regime** — and it *mixes*, so on genuinely
mixed workloads it beats the all-or-nothing load-switch (#6).

## Headline numbers (default calibration)

Crossover (per-slot staging estimate = 24 MB):

| model | bf16 KV/token | crossover L* |
|---|---:|---:|
| Qwen2.5-7B (4 KV heads) | 56 KB | **986 tok** |
| Llama-3.1-8B (8 KV heads) | 128 KB | **431 tok** |

(8 KV heads → heavier bf16 KV → int4 overtakes the fixed staging *sooner* — the same
GQA-width effect that makes read-skip cross earlier on Llama/Mistral.)

Mean-length sweep, Qwen2.5-7B, concurrency 64 (best policy vs bf16):

| mean len | int4-only | guarded hybrid | best saved |
|---:|---:|---:|---:|
| 256 | **loss** (17.8 vs 16.2 GB) | = bf16 | 0.0 % |
| 1 024 | ~par | = bf16 | 0.4 % |
| 2 048 | win | win | 7.4 % |
| 8 192 | win | win | 26.4 % |
| 32 768 | win | win | **38.6 %** |

The shape is the whole point: **flat (no loss) on short context, growing win on long
context** — int4_protected's footprint becomes a *win* exactly in the long-context
regime read-skip already targets, and the guard makes it costless everywhere else.

## The honest caveats

1. **The naïve two-pool (#4) is not a free guarantee.** A few sequences just past
   `L*` open the int4 pool but don't save enough to cover its fixed tax → you can end
   up *above* bf16. Use the **guarded** form (`min(bf16, two-pool)`), which the tests
   enforce ≤ bf16 over 400 random workloads.
2. **Load-switch (#6) can't mix.** On a 70/30 short/long workload it picks one dtype
   for the whole resident set, so it slightly trails the mixing hybrid (measured here:
   39.7 % vs 40.0 %).
3. **One input is not yet measured: `stage_per_slot_mb`.** It is the crossover driver
   and is currently an *estimate*. `L*` ranges 329 → 3 945 tok as the staging pool goes
   8 → 96 MB/slot (see `--crossover`). Everything else (bf16 per-token exact; int4
   per-token from the §1/§4 audit) is grounded.

## Next step to make it exact (one pod measurement)

`measure_stage_pool()` documents the procedure: on the GPU pod (venv-vllm), load the
int4_protected backend, snapshot `torch.cuda.memory_allocated()`, admit one max-len
sequence, snapshot again; the delta minus `frac·c·L` is the per-slot staging (run at
two batch sizes to separate `fixed_tax` from per-slot). Feed the result via
`--stage-per-slot-mb` / `--fixed-tax-gb` for an exact crossover. That single number
turns this from a calibrated estimate into a measured decision.

## Run

```bash
python Bench/scripts/hybrid_kv_scheduler.py --selftest                 # invariant gates
python Bench/scripts/hybrid_kv_scheduler.py --model llama-3.1-8b --crossover
python Bench/scripts/hybrid_kv_scheduler.py --sweep                    # mean-length sweep
python Bench/scripts/hybrid_kv_scheduler.py --workload mix:0.7:256:40000:100
python Bench/tests/test_hybrid_kv_scheduler.py                         # regression
```

## Scope

This is the **cost model**, not the serving change. It justifies and sizes the real
work (mixed-dtype paged KV pools + a length/load-aware admission policy in vLLM), and
gives the threshold to configure it with. It does **not** itself reduce memory — it
tells you the hybrid's ceiling so you can decide whether the engineering earns it.
```
