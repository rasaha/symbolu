# Low-Compute Enterprise Long-Context Ladder — A / B / C Falsification

**No quadratic attention is used, benchmarked, or compared against anywhere in this phase.**
Executed experiment; code + raw metrics under `experiments/phase_lc/`. Discipline: prove
**B−A (Phase over window)** before **C−B (bounded slots over Phase)**.

> HARDWARE CEILING (unchanged): 4 CPU cores, 15 GB RAM, no GPU. Micro scale (~2.0M params,
> d=128, 4 layers, window=64, train ctx 160, eval to 512). By protocol, no verdict here can
> be PROVEN; the labels available are PROVISIONALLY SUPPORTED / ARCHITECTURALLY PLAUSIBLE /
> NOT SUPPORTED / FALSIFIED AT TESTED SCALE.

## 2. Environment & hardware
CPU-only (4 cores), torch 2.13 CPU, fp32, 3 seeds. Corpus: repo enterprise English prose
(`bounded_shadow_pilot` + `evidence_assurance`), ~55K tokens, word vocab ≈1290.

## 3. Repository audit (long-context components)

| Component | Implemented | Complexity | Bounded state | Uses N×N scores | Tested | Suitable for this phase |
|---|---|---|---|---|---|---|
| Sliding-window attn (`LocalWindowAttention`, `SoftmaxAttn`) | yes | O(N·w) | n/a | banded only | yes | **yes → A** |
| Phase recurrent (`PhaseAttentionLayer`/`BindingCachePhaseState`) | yes | O(N·d) | yes (d/layer) | no | yes | **yes → B** |
| `BindingCacheQuadQuery` | yes | **O(N²) scores** | no | **YES** | yes | **REJECTED (quadratic)** |
| `SlotMemoryGCT` | yes | O(N·M) | yes (M·d) | no | partial | design reused, but coupled to controller machinery |
| Fresh `BindingSlots` (this work) | yes | O(N·M) | yes (M·d) | **no (hook-verified)** | yes | **yes → C** |

The repo's own "binding cache" reader (`BindingCacheQuadQuery`) materialises a full
`[B,H,N,N]` score matrix — it is **excluded** per the no-quadratic rule. C therefore uses a
fresh, auditable bounded slot memory.

## 4. Exact definitions of A, B, C

Shared skeleton: token+abs-pos embedding → 4 pre-norm blocks → GELU FFN → tied LM head.
Blocks differ only in the mixer (protected additive fusion). FFN width auto-tuned so total
params match to <0.05%.

- **A — window only:** `out = Window(x)` (causal sliding window, w=64).
- **B — window + Phase:** `out = Window(x) + Phase(x)`. Phase update (per head, per channel):
  `k = a_k·e^{-iφ_k}, q = a_q·e^{+iφ_q}; state_t = Σ_{s≤t} γ^{t-s} k_s v_s; out_t = Re(q_t·state_t)`.
  Bounded state = d complex numbers/layer; per-token compute O(d); **no score matrix, no
  token cache, no full-prefix replay** (parallel prefix-sum for training; O(1) state recurrence
  for decode).
- **C — window + Phase + bounded slots:** `out = Window(x) + Phase(x) + Slots(x)`. Slots:
  `addr_t = softmax((W_wk x_t)·SlotKeys^T)`, gated write `w_t = σ(gate)·addr_t`, causal
  `slot_t = Σ_{s≤t} w_s v_s / Σ_{s≤t} w_s` (M slots), read `out_t = W_o Σ_m softmax((W_rq x_t)·SlotKeys^T)_m · slot_{t,m}`.
  M=32 slots, key-dim 64. Complexity O(N·M·d). Bounded slot state = M·d/layer.

## 5. Proof that no quadratic sequence attention is present

`assert_no_nxn()` registers forward hooks on every Phase and Slots module and fails if any
produces a tensor whose last two dims are both N. **Result across all runs: `phase_builds_NN
= False`, `slots_builds_NN = False`.** The only `[N,N]` object anywhere is the window
attention's banded score, which is masked to width w=64 (O(N·w)); no global token-pair
attention exists in A, B, or C. (Raw flags in `results/abc.json`.)

## 6. Parameter & compute fairness
Params matched to <0.05% via FFN auto-tune (A≈B≈C≈2.00M; exact counts in results). Identical
tokenizer, corpus, data-order RNG per seed, optimizer (AdamW lr 2e-3, warmup+constant),
batch 24, 1800 steps, fp32, seeds {0,1,2}. Added-parameter control: because B and C spend
their extra mixer params but FFN is shrunk to compensate, the comparison is same-total-param;
per-token active params are ~equal. Latency/throughput and bounded-state sizes reported per
arm (§16).

## 7. Training data & 8. Objectives
Mixture: 20% real-language LM (full-sequence CE) + 80% enterprise tasks rendered in natural
language (needle 20 / binding 20 / supersession 15 / source 15 / multihop 10). Task examples
use answer-token supervision (a combined L_retrieval+L_binding+L_source+L_version signal),
applied identically to every arm — the prior phase showed no arm learns retrieval under
LM-only loss at this scale, so the LM-only-vs-aux question is answered "aux is required" and
aux is held constant across A/B/C to keep B−A and C−B clean.

<!-- Sections 9-20 filled from results/abc_tables.md after the run completes. -->
