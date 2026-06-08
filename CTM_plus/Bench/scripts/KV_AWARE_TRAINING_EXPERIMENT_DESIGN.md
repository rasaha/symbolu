# KV-aware training experiment — does training for int4 KV remove the sidecar tax?

> **The unmeasured axis.** Every int4_protected / read-skip number is **inference**
> on a model whose weights were trained for full-precision, full-attention KV. The
> two biggest honest weaknesses — the **+4.7 GB sidecar tax** (which makes the
> backend footprint-*negative* vs bf16) and the **read-skip eviction quality
> gamble** — are plausibly *artifacts of being post-hoc*. This experiment measures
> the counterfactual we never ran: **train the model to tolerate int4 KV, and see
> whether the sidecars can go away without losing the fidelity they currently buy.**
> A single clean result here says more about the technology's ceiling than any
> further inference tuning.

## 1. Question & hypotheses

The sidecar tax has two parts (`MEMORY_STORY.md` §1):

| sidecar | ~GB (8K live) | what it is | knob |
|---|--:|---|---|
| `k_protect_ext` | ~1.0 | protected K channels kept at bf16 | `protect_fraction` |
| `k/v_scale` + `k/v_xmin` | ~3.4 | per-(block/token) int4 reconstruction metadata | `group_size` |
| **total Δ vs bf16** | **~4.7** | (overwhelms the int4 KV saving) | — |

The protect channels exist *because the frozen model can't tolerate quantizing its
high-magnitude K channels*. The fine scale/xmin grid exists *because coarse int4
groups lose too much fidelity on a model not adapted to them*. Both are crutches
for a model that never saw int4 KV in training. Hence:

- **H1 (protect).** A model fine-tuned with int4 KV in the loop holds bf16-level
  fidelity at **`protect_fraction = 0`** → removes the ~1.0 GB `k_protect_ext`.
- **H2 (groups).** The same training holds fidelity at a **coarse `group_size`**
  (32 → 128) → ~4× fewer scales/xmins → cuts a large share of the ~3.4 GB.
- **H3 (combined).** Trained 0-protect + coarse-group int4 reaches **bf16 footprint
  parity or better**, flipping the memory story from footprint-negative to neutral/
  positive — *while preserving most of the +20.4 pt token-agreement gain.*

The null (kill) hypothesis is equally valuable: if training does **not** beat
post-hoc at matched sidecar, the post-hoc lane is the ceiling and we stop pitching
a path to footprint parity.

## 2. Mechanism — KV-QAT with train==inference parity (the crux)

The experiment is only valid if the model trains against the **exact** distortion
it meets at serving time. We guarantee that by reusing the inference round-trip:

- `INT4CacheKVRouteA.round_trip_kv(key, value)` is the serving compress→decompress
  (the "lossy" K/V the kernel attends over).
- `kv_aware_qat.kv_qat_round_trip(manager, k, v)` (committed, CPU-self-tested) calls
  that same function inside the training forward and wraps it in a **straight-through
  estimator** (`round`/`clamp` have ~zero gradient; STE returns the lossy value
  forward, passes gradient identity backward). **Parity is by construction — no
  second quantizer.**

**Parity gate (must pass before any training run):** assert the train fake-quant
output is byte-identical to `round_trip_kv` on sampled `(K,V)` for every arm's
`(protect_fraction, group_size)`. If it ever diverges, the experiment is measuring
the wrong distortion and the result is void.

### Install sketch (HF attention forward; exact API is transformers-version-specific)

```python
# wrap Qwen2Attention.forward: after q/k/v proj + RoPE, before scores
from kv_policy.kv_aware_qat import kv_qat_round_trip
def patched_forward(self, hidden, *a, **kw):
    q, k, v = self.q_proj(hidden), self.k_proj(hidden), self.v_proj(hidden)
    q, k = apply_rotary(q, k, ...)                 # K is quantized POST-RoPE (matches serving)
    k, v = kv_qat_round_trip(self._kvqat_manager, k, v)   # <-- the only added line
    return _orig_attention(self, q, k, v, *a, **kw)
```

The `manager` is an `INT4CacheKVRouteA` configured with the arm's
`(protect_fraction, group_size, asymmetric, bits=4, sink_size)` — i.e. the serving
config under test — and `num_kv_heads` set so the 2-D layout reshapes.

## 3. Arms

Baselines (no training; **re-evaluated on the same harness** for apples-to-apples):

| id | KV at inference | note |
|---|---|---|
| **A0** | bf16 | quality ceiling |
| **A1** | int4 naive, 0% protect, g=32 | post-hoc floor |
| **A2** | int4_protected, 4% protect, g=32 | **the current product** |

Trained arms (KV-QAT fine-tune, then eval at the matching inference config):

| id | training fake-quant | eval KV | isolates |
|---|---|---|---|
| **B0** (control) | **none** (vanilla FT, same data) | int4 4% g=32 | "did the FT itself move quality?" — the confound |
| **B1** (H1) | int4 **0% protect** g=32 | int4 0% g=32 | the ~1.0 GB `k_protect_ext` |
| **B2** | int4 4% protect g=32 | int4 4% g=32 | headroom of train+protect over post-hoc A2 |
| **B3** (H2) | int4 0% protect **g=128** | int4 0% g=128 | the ~3.4 GB scale/xmin |

Guardrail (all trained models): also eval with **bf16 KV** → must not regress
general capability vs base (catastrophic-forgetting check).

## 4. Measurements — reuse the existing eval scripts (comparability is the point)

- **Token-agreement vs bf16** — `phase6j_quality_comparison.py` (the primary fidelity
  metric; A2 post-hoc = 0.737). This is the headline number per arm.
- **Hard needle** (60 items, distractors) — `phase6k12_hard_needle.py`.
- **Easy needle + MMLU subset** — `phase6k11_needle_failuremode.py`, the 6N MMLU runner
  (rules out compensating flips / forgetting).
- **Sidecar GB** — deterministic from `(protect_fraction, group_size, model dims)` via
  the 6G audit math; report **Δ HBM vs bf16** per arm. (Inference throughput is
  unchanged by training — same kernel — so it is *not* re-measured.)

Report each arm as `(token_agreement, hard_needle, mmlu_Δ, sidecar_GB, ΔHBM_vs_bf16)`.

## 5. Decision criteria (pre-registered)

- **P1 (protect removable):** `B1.token_agreement ≥ A2.token_agreement − ε` (ε = noise
  band, ~0.01) → training removes the protect sidecar (~1.0 GB) at no quality cost.
- **P2 (the big one):** `B3.token_agreement ≥ A2.token_agreement − ε` → training also
  tolerates coarse groups → cuts scale/xmin → **plausible bf16 footprint parity.**
- **Attribution:** the gain must exceed the **B0 control** (else it's just "more
  training," not KV-awareness).
- **Guardrail:** trained models' **bf16-KV MMLU within ~1 pt** of base (no forgetting).
- **KILL:** if `B1,B2 ≤ A2` (no gain over post-hoc) after the control adjustment → the
  post-hoc sidecar is *not* a training artifact; stop; report the negative and keep the
  honest "density-not-footprint, fidelity-per-GB" framing.

## 6. Cost & staging (gate the expensive part)

- **Pilot (~1–2 A100-days, cheap, derisks everything):** LoRA on Qwen2.5-7B attention
  projections (q/k/v/o), a **long-context-inclusive** corpus (see §7), arms **B0 + B1
  only**, eval token-agreement + hard needle. **Gate:** proceed only if B1 moves
  materially toward A2 (≥ halfway from A1→A2).
- **Full (gated on pilot):** add **B2, B3**; escalate LoRA→full-FT if LoRA is too weak;
  add MMLU + easy needle + the bf16 guardrail; then cross-family (Mistral-7B,
  Llama-3.1-8B) to mirror the post-hoc portfolio.

## 7. Threats to validity & controls

1. **Train/inference parity** — reuse `round_trip_kv` + the §2 byte-parity gate. The
   single most important property.
2. **FT-itself confound** — the **B0 control** (same data, no fake-quant) separates
   KV-awareness from generic fine-tuning drift.
3. **Catastrophic forgetting** — the bf16-KV guardrail eval; if general capability
   drops, the "fidelity" gain is illusory.
4. **Long-context coverage** — the int4 distortion compounds with sequence length, and
   the *whole* post-hoc quality story is long-context. The training corpus **must**
   include long sequences (≥ several-K tokens), or the adaptation won't cover the
   regime that matters. (Easy to get wrong; high-impact.)
5. **LoRA capacity** — adapting to a *distributional* change in KV may exceed LoRA's
   rank; escalation to full-FT is pre-planned, not a surprise.
6. **STE bias** — STE is a gradient approximation; if training is unstable, anneal the
   quant strength (start near-bf16, ramp to int4) or widen LoRA rank before abandoning.
7. **Model-specificity** — pilot is Qwen-7B only; cross-family is the generalization
   step (mirrors the post-hoc 4-model result), not assumed.

## 8. What the result means for the brief

- **Positive (P1 and/or P2, control-adjusted, guardrail intact):** the footprint-negative
  verdict is a **post-hoc artifact**; the *trained* backend is footprint-neutral/positive
  at preserved fidelity. This **flips the memory story** — update `MEMORY_STORY.md` and the
  VC brief from "density-not-footprint" to "footprint parity via KV-aware fine-tune," and
  it changes the competitive picture vs fp8 (now potentially *cheaper* AND higher quality).
- **Negative (kill):** post-hoc is the ceiling. The honest current framing stands; stop
  chasing footprint via tuning; the durable path is model+cache **co-design** (sliding-
  window / SSM / trained sparse attention), a different and larger program.

Either outcome is high-information and cheap to *start* (the LoRA pilot). This is the one
experiment that tells us whether int4_protected's central weakness is fundamental or just
the price of refusing to retrain.

## Pointers

| thing | where |
|---|---|
| Train fake-quant primitive (STE + parity) | `CTM_plus/KVPolicy/kv_policy/kv_aware_qat.py` (CPU self-test: PASS) |
| Inference round-trip it mirrors | `INT4CacheKVRouteA.round_trip_kv` (`int4_cache_kv_route_a.py:607`) |
| int4 quantizers | `int4_per_channel_kv.py` (`quantize_per_channel_int4`, `quantize_per_token_int4`) |
| Sidecar accounting | `audit_phase6g_sidecar_overhead.py`; `MEMORY_STORY.md` §1 |
| Reused eval scripts | `phase6j_quality_comparison.py`, `phase6k12_hard_needle.py`, `phase6k11_needle_failuremode.py`, 6N MMLU runner |
| Honest memory verdict this overturns-or-confirms | `MEMORY_STORY.md` §6; `INT4_PROTECTED_VC_BRIEF.md` Page 6 |
