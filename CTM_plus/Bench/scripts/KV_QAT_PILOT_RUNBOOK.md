# KV-aware fine-tune PILOT — runbook

Tests whether training Qwen2.5-7B for int4 KV recovers the fidelity that the
**+4.7 GB protect sidecar** buys post-hoc. **Needs a GPU** (A100-class). The hook
mechanism is already de-risked on CPU (`kv_qat_hook_smoketest.py: PASS`).

## Arms — the headline is the DELTA, not an absolute

| arm | what | role |
|---|---|---|
| **A0** | base model, **no training** | eval baseline (no run — just eval the base model) |
| **B0** | LoRA FT, **no** fake-quant | control: captures fine-tune *drift* |
| **B1** | LoRA FT, **post-RoPE KV fake-quant** | the treatment |

**The result is `B1 − B0`**, not B1's absolute score. B0 subtracts off "the model
changed because we fine-tuned at all"; only `B1 − B0` is attributable to
KV-awareness. (`--group-size 128` makes B1 the coarse-group B3 arm.)

## Pipeline & gates (run in order; each gate is a STOP)

```
smoke  →  overfit  →  train B0 + B1  →  eval (B1−B0)  →  sidecar sweep
  │          │              │               │                 │
  └ hook ok? └ learns?      └ diverges?      └ improves?       └ protect-dep reduced?
```

### Stage 1 — `--smoke` (real 7B, ~1 min): is the hook wired right?

```bash
cd /workspace/symbolu && git pull origin claude/bold-johnson-rXAd4 && cd CTM_plus
pip install -q peft datasets
PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_pilot.py --arm b1 --smoke
```

Expected (Qwen2.5-7B = 28 layers, so 28 fires/step × 2 steps = 56):
```
--- hook report ---
  location           : post-RoPE
  layers (cfg)       : 28
  V hooks installed  : 28
  fired              : K=56  V=56
  K shape/dtype      : (<tokens>, 4, 128)  ('torch.bfloat16', 'torch.bfloat16')
  V shape/dtype      : (<tokens>, 512)     ('torch.bfloat16', 'torch.bfloat16')
  mean |perturbation|: K=0.0xxxx  V=0.0xxxx
--- smoke checks ---
  [PASS] K fired every layer/step
  [PASS] V fired every layer/step
  [PASS] V hooks == n_layers
  [PASS] K perturbation > 0
  [PASS] V perturbation > 0
  [PASS] K dtype preserved
  [PASS] V dtype preserved
kv_qat_pilot SMOKE (b1): PASS
```

**KILL GATE 1:** any `FAIL` (esp. perturbation = 0 → no-op hook, or `fired < 56` →
some layers missed) → **fix the hook, do NOT train.** Re-run with `--pre-rope` to
confirm the rest of the harness works, paste me the report, and I fix the post-RoPE
wrap. A real result *requires* post-RoPE (pre-RoPE quantizes K before rotation —
not what the cache stores).

### Stage 2 — `--overfit` (real 7B, ~3 min): does it actually learn?

```bash
PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_pilot.py --arm b1 --overfit
```

40 steps on 16 fixed synthetic examples. Expected:
```
--- overfit sanity ---  loss 11.0xx -> <lower>
  [PASS] loss decreased
  [PASS] LoRA weights updated
  [PASS] hook fired every step (b1) / none (b0)
kv_qat_pilot OVERFIT (b1): PASS
```

**KILL GATE 2:** loss flat / LoRA static / hook gaps → the gradient path or optimizer
is broken; fix before spending on a real run.

### Stage 3 — train B0 (control) then B1

Long-context-inclusive data matters (the int4 distortion compounds with length).

```bash
PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_pilot.py --arm b0 \
  --steps 200 --max-seq-len 4096 --merge --output kv_qat_b0
PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_pilot.py --arm b1 \
  --steps 200 --max-seq-len 4096 --merge --output kv_qat_b1
```

**KILL GATE 3:** if B1's training loss **diverges vs B0** (NaN, or trends up while B0
trends down) → the fake-quant is destabilizing training → kill / reduce lr / widen
LoRA before continuing. (B1's loss should track B0's, just slightly higher.)

### Stage 4 — eval: token-agreement, the `B1 − B0` effect

Reuse `phase6j_quality_comparison.py` (post-hoc baselines: naive int4 **0.533**,
protected int4 **0.737** vs bf16). Run it on each merged model at the naive (0%
protect) int4 path:

```bash
python Bench/scripts/phase6j_quality_comparison.py --model ./kv_qat_b1 ...   # B1
python Bench/scripts/phase6j_quality_comparison.py --model ./kv_qat_b0 ...   # B0 (control)
python Bench/scripts/phase6j_quality_comparison.py --model Qwen/Qwen2.5-7B-Instruct ...  # A0
```

> **Eval reference:** token-agreement is each model's int4-KV vs **its own bf16**
> output. Separately run a **bf16-KV guardrail** (B1 bf16 vs base bf16) + a small
> MMLU check — if B1's bf16 behavior drifted, the "fidelity" win is hollow.

**KILL GATE 4:** if **`B1 − B0 ≤ 0`** (KV-QAT doesn't beat the plain-FT control) →
training does not help → KILL, bank the inference story. Pilot success bar:
`B1 ≥ ~0.635` (halfway A1→A2 = 0.533→0.737) **with B0 flat near 0.533**.

### Stage 5 — sidecar-reduction sweep: does KV-QAT reduce protect DEPENDENCE?

This is the question that decides whether the tax is *solved* or merely *softened*.
Eval B1 with the serving protect knob swept down — recalibrate the mask per level:

```bash
for NP in 5 3 0; do
  python Bench/scripts/calibrate_phase5b_protect_mask.py --model ./kv_qat_b1 \
    --output kv_qat_b1_protect${NP}.pt --protect-fraction $(python -c "print($NP/128)")
  # then run token-agreement on ./kv_qat_b1 at this n_protect (mask above)
done
```

Compare against A0 (base) swept the same way:

| reading | meaning |
|---|---|
| B1 holds agreement at **n_protect=0** ≈ base at n_protect=5 | **TAX SOLVED** — the ~1.0 GB `k_protect_ext` can go; this flips the memory story |
| B1 holds only at **n_protect=5**, collapses at 3/0 | **softened, NOT solved** — KV-QAT improved tolerance at fixed protect but did not remove the sidecar. Record as a useful quality result, not a footprint win |
| B1 holds at **n_protect=3** but not 0 | partial — sidecar shrinks (~0.4 GB via the 5→3 diet), not eliminated |

**KILL GATE 5 (soft):** if B1 cannot reduce protect dependence (needs n_protect=5),
do **not** claim the tax is solved — log it as "improves int4 tolerance" and stop.

> ⚠ **PARITY CAVEAT (read before trusting Stage 5).** The pilot trains against
> `round_trip_kv` (the **dequant_fallback** path: per-channel K @ group-32 + per-token
> V). The protect sweep runs the **fused_v2** serving path (per-token K @ group-1 +
> protect channels). If those K/V quantizations differ, B1 was adapted to a
> *different* distortion than the sweep applies, and the transfer is not clean. Before
> trusting Stage 5: confirm fused_v2's K/V quantization matches `round_trip_kv` for
> `n_protect=0`, OR retarget the training fake-quant to the fused_v2 distortion. (Stage
> 4, which evals on the same dequant_fallback path it trained against, does not have
> this gap.)

## Kill gates (summary)

1. **smoke FAIL** → fix hook, do not train.
2. **overfit FAIL** (no loss drop / no weight move / hook gaps) → fix gradient path.
3. **B1 loss diverges vs B0** → kill (instability).
4. **`B1 − B0 ≤ 0`** token-agreement → kill (no KV-awareness benefit).
5. **B1 can't reduce protect dependence** → record "useful tolerance, NOT tax-solving"; stop.

## Cost

~1–2 A100-h per training arm (LoRA, 200 steps, seq 4096, 7B). Smoke ~1 min, overfit
~3 min. Scale `--steps`/`--max-seq-len`/`--lora-rank` only after movement shows.

## Pointers

| thing | where |
|---|---|
| Experiment design (full arms A0–B3) | `KV_AWARE_TRAINING_EXPERIMENT_DESIGN.md` |
| Fake-quant core (STE + parity) | `KVPolicy/kv_policy/kv_aware_qat.py` |
| Hook de-risk (CPU, PASS) | `Bench/scripts/kv_qat_hook_smoketest.py` |
| Inference distortion reused | `INT4CacheKVRouteA.round_trip_kv` |
| Token-agreement eval | `Bench/scripts/phase6j_quality_comparison.py` |
| Protect-mask calibration | `Bench/scripts/calibrate_phase5b_protect_mask.py` |
| Memory verdict this can overturn | `MEMORY_STORY.md` §6 |
