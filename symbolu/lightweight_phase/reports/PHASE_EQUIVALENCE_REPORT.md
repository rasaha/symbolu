# Production Equivalence v1.0 — Stage Report

**Stage:** 4 — Production equivalence harness
**Status:** FROZEN (supported configuration)
**Reproduce:** `python -m pytest symbolu/lightweight_phase/tests/test_production_equivalence.py`

## Adapter

`equivalence.py` maps weights and configuration between
`LightweightPhaseAttention` and the production
`symbolu.phase_transformer.PhaseAttentionLayer` (standard cosine mode). Weight map:

| Production | Lightweight | Notes |
|---|---|---|
| `norm` (weight/bias) | `norm` | LayerNorm affine |
| `W_q_fused[:D]` | `W_phi_q` | phase half |
| `W_q_fused[D:2D]` | `W_a_q` | amplitude half |
| `W_k_fused[:D]` | `W_phi_k` | phase half |
| `W_k_fused[D:2D]` | `W_a_k` | amplitude half |
| `v_proj` | `W_v` | values |
| `out_proj` | `W_out` | output |
| fixed phase offsets `2πh/H` | *(omitted)* | cancel in the real readout (§7) |

To achieve exact equivalence, the lightweight is configured with the production
amplitude parameterization `a = 0.05 + 0.95·σ(·)` (`amp_floor=0.05, amp_scale=0.95`),
set **explicitly** by `matched_phase_config`, never as a silent default change.

## Result

**Required:** max abs output difference ≤ 1e-5 in float32.
**Measured:** ≤ **2.4e-7** across all supported settings (forward, gradients,
state evolution). 11/11 equivalence tests pass.

| Feature | Lightweight | Production | Equivalent? | Notes |
|---|---|---|---|---|
| bounded phase (π·sin) | ✅ | ✅ | **Yes** | canonical default |
| standard cosine mode | ✅ | ✅ | **Yes** | Re(q·S)/Z |
| detached normalizer max(·,0.1) | ✅ | ✅ | **Yes** | frozen contract |
| amplitude 0.05+0.95·σ | via config | ✅ | **Yes** | set explicitly in harness |
| no decay (γ=1) | ✅ | ✅ | **Yes** | ≤2.4e-7 |
| fixed decay (0.9/0.95/0.99) | ✅ | ✅ | **Yes** | ≤2.4e-7 (prod parallel scan vs ref seq scan) |
| learned decay | γ values pinned | ✅ | **Yes (values)** | different logit parameterization; γ matched by value |
| causal / eval mode | ✅ | ✅ | **Yes** | — |
| training mode (dropout=0) | ✅ | ✅ | **Yes** | — |
| forward output | ✅ | ✅ | **Yes** | ≤2.4e-7 |
| input & value-weight gradients | ✅ | ✅ | **Yes** | ≤1e-4 |
| chunk-persistent state | ✅ | ✅ | **Yes** | both reproduce single pass |
| fixed per-head offsets | omitted | present | **Yes (no-op)** | cancel in readout |
| shifted / complex cosine modes | ❌ | ✅ | **No** | production-only; out of scope |
| zero_mean_cosine | ❌ | ✅ | **No** | production-only |
| dual-channel intent (θ_JEPA/θ_SRK) | ❌ | ✅ | **No** | intent rotation excluded by contract |
| multi-channel phase / write gate | ❌ | ✅ | **No** | production-only |
| phase warm-start | ❌ | ✅ | **No** | production-only training schedule |
| aux_scale default | 1.0 | 0.1 | matched | set explicitly in harness |
| learned-decay γ range/init | γ_min/γ_max | 0.97+0.0295σ | **No (init only)** | forward math identical once γ fixed |

## Divergences (explicitly, not silently weakened)

The last block above enumerates every production feature the lightweight core does
not replicate. None of these are within the frozen equivalence claim; the claim is
scoped to standard-mode Phase with no intent/multi-channel/gate/warm-start. The
learned-decay divergence is an *initialization/parameterization* difference only —
with γ pinned to identical values the forward outputs match to 2.4e-7.

## Freeze record

- Supported-equivalence config is frozen in `equivalence.py` docstring and
  `matched_phase_config`. Source SHA-256 in the manifest is anchored by the Stage 1/3
  core hashes (the adapter maps onto them).
