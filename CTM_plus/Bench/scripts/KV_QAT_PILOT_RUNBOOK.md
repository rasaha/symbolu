# KV-aware fine-tune PILOT — runbook

Runs the pilot stage of `KV_AWARE_TRAINING_EXPERIMENT_DESIGN.md`: does training
Qwen2.5-7B for int4 KV recover the fidelity that the **+4.7 GB protect sidecar**
currently buys post-hoc? Pilot = **B0 (control) + B1 (0%-protect KV-QAT)** only;
the B2/B3 sweep is gated on a positive pilot.

**Needs a GPU** (A100-class; the smoke test was CPU, the fine-tune is not).
`kv_qat_pilot.py` is committed; the hook mechanism is already de-risked
(`kv_qat_hook_smoketest.py: PASS`).

## 0. Prereqs (on the GPU pod)

```bash
cd /workspace/symbolu && git pull origin claude/bold-johnson-rXAd4 && cd CTM_plus
pip install -q peft datasets        # if not already present (transformers/torch are)
```

## 1. Smoke — validate the REAL-7B wiring (~1 min) BEFORE a real run

Loads the actual 7B + LoRA + the post-RoPE hook, runs 2 synthetic steps, asserts
the fake-quant fired. This catches the one fragile thing (the post-RoPE rotary
wrap on transformers 5.10.2) cheaply.

```bash
PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_pilot.py --arm b1 --smoke
```

- **`kv_qat_pilot SMOKE (b1): PASS`** with `hook_fired k>0 v>0` → wiring good, proceed.
- **`AssertionError ... hooks never fired`** or a rotary error → the post-RoPE wrap
  didn't match this transformers version. Re-run with **`--pre-rope`** to confirm
  the rest of the harness works, then paste me the error — the post-RoPE hook is
  the part to fix (a real result REQUIRES post-RoPE; pre-RoPE quantizes K before
  rotation, which is not what the cache stores at inference).

Also smoke b0 (should run with no hooks):
```bash
PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_pilot.py --arm b0 --smoke
```

## 2. Train the two arms

Long-context-inclusive data matters — the int4 distortion compounds with length,
so `--max-seq-len` should be several-K (default 4096). Start small (200 steps) to
see movement; scale up if the signal is there.

```bash
# B0 — CONTROL (vanilla LoRA, no fake-quant): isolates fine-tune drift
PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_pilot.py --arm b0 \
  --steps 200 --max-seq-len 4096 --merge --output kv_qat_b0

# B1 — KV-QAT, 0% protect (the key arm): trains against the int4 distortion
PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_pilot.py --arm b1 \
  --steps 200 --max-seq-len 4096 --merge --output kv_qat_b1
```

(`--group-size 128` turns B1 into the coarse-group B3 arm — run it too if B1 is
positive, to attack the ~3.4 GB scale/xmin sidecar.)

`--merge` folds LoRA into the base weights and saves a plain HF model, so the eval
can load it straight into the int4 inference path.

## 3. Eval — token-agreement vs bf16 (reuses the existing harness)

The metric is `phase6j_quality_comparison.py` (post-hoc baselines: naive int4
**0.533**, protected int4 **0.737** vs base bf16). Run it on each merged model with
the **naive** int4 path (0% protect — what B1 was trained for):

```bash
# baseline (base model): reproduces naive 0.533 / protected 0.737
python Bench/scripts/phase6j_quality_comparison.py --model Qwen/Qwen2.5-7B-Instruct ...
# the trained arms (point --model at the merged dirs):
python Bench/scripts/phase6j_quality_comparison.py --model ./kv_qat_b1 ...   # B1 naive int4
python Bench/scripts/phase6j_quality_comparison.py --model ./kv_qat_b0 ...   # B0 naive int4 (control)
```

(Check the script's exact flags with `--help`; pass the same mml/seeds as the
brief's runs so numbers are comparable.)

> **Eval subtlety — get the bf16 reference right.** Token-agreement is int4-KV vs
> bf16-KV. For a *trained* model, compare its int4 output to **its own bf16**
> output (does int4 KV degrade *this* model?), not to the base model's bf16
> (fine-tuning legitimately changed behavior). Separately run a **bf16-KV
> guardrail**: B1's bf16 output vs the *base* bf16 — if it drifted a lot, the FT
> hurt general capability and the "fidelity" win is hollow (this is what the B0
> control + a small MMLU check are for).

## 4. The gate / decision

| outcome | read |
|---|---|
| **B1 naive-int4 agreement ≥ A2's 0.737**, and **≫ B0's** (control), guardrail intact | **H1 confirmed** — training removes the ~1.0 GB protect sidecar at no quality cost. Run B3 (`--group-size 128`) for the ~3.4 GB scale/xmin. This is the result that flips the memory story. |
| B1 ≈ B0 ≈ 0.533 (no lift over naive) | KILL — training (at this scale) doesn't remove the sidecar; post-hoc is the ceiling. Valuable negative; bank the inference story. |
| B1 lifts but < 0.737 | partial — scale up steps/data/full-FT before concluding; the pilot's job is to show *movement* (≥ halfway A1→A2 = 0.533→0.737, i.e. ≳0.635). |

**Pilot success bar:** B1 ≥ ~0.635 (halfway) with B0 flat → justifies the full sweep
(B2/B3, full-FT, cross-family). Below that → stop.

## 5. Cost & knobs

- Pilot as written (LoRA, 200 steps, seq 4096, 7B): roughly **1–2 A100-hours/arm**.
  Scale `--steps` / `--max-seq-len` / `--lora-rank` up only after seeing movement.
- `--pre-rope` runs the proven-but-invalid hook (wiring/debug only).
- `--dataset/--dataset-config/--text-column` to swap corpora (default
  wikitext-103; for a stronger long-context signal use a long-document set).

## Pointers

| thing | where |
|---|---|
| Experiment design (arms, hypotheses, decision) | `KV_AWARE_TRAINING_EXPERIMENT_DESIGN.md` |
| Fake-quant core (STE + parity) | `KVPolicy/kv_policy/kv_aware_qat.py` |
| Hook de-risk (CPU, PASS) | `Bench/scripts/kv_qat_hook_smoketest.py` |
| Inference distortion the hook reuses | `INT4CacheKVRouteA.round_trip_kv` |
| Token-agreement eval | `Bench/scripts/phase6j_quality_comparison.py` |
| Memory verdict this can overturn | `MEMORY_STORY.md` §6 |
