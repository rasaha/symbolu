# KVPro V3 Step-0 — Part H: correctness gate for the selected kernel project

Do **not** implement the kernel yet. This is the gate any of the candidate projects (in-kernel gather,
store-as-consumed, dense/coalesced protected stream, protected-INT8) must pass. For a **quality-neutral
layout/gather change** the end-to-end result must be **identical within deterministic tolerance** to the
current affine + bf16-protected path — a layout change that moves a needle/hard-needle answer is a bug,
not a tradeoff. (Protected-INT8 is the one exception: it is a *format* change, gated by Part F quality.)

## Oracles (all in-repo, reuse — do not rebuild)

- **CPU numeric reference (full attention):** `CTM_plus/KVPolicy/kv_policy/int4_fused_attention_sketch.py:174`
  `fused_int4_attention_reference` (protected overlay `:243`, dequant `:296`).
- **CPU dequant reference (K/V):** `CTM_plus/KVPolicy/kv_policy/phase6f_read_fusion.py:85` `dequant_k_reference`,
  `:143` `dequant_v_reference`; `unpack_nibbles:50` / `pack_nibbles:64`.
- **Attention-chain tolerance:** `experiments/kvpro_v3_symmetric_residual/metrics.py::attention_metrics`
  (logit MSE, softmax KL/JS, attn-output cos/MSE) + `attention_error_eval.py`.
- **Retrieval / knowledge regressions:** `needle_driver.py` / `hard_needle_driver.py` / `mmlu_driver.py`
  + `gates.py` (no new regressions vs the affine cell).
- **Snapshot/WarmTier format:** `CTM_plus/KVPolicy/kv_policy/tier5b_snapshot.py` `_TENSOR_KEYS:32` +
  `verify_roundtrip:156`; `scripts/verify_kvpro_snapshot_roundtrip.py`.

## Required checks

| Check | Oracle | Tolerance |
|-------|--------|-----------|
| Packed/dequant **K** equivalence | `phase6f_read_fusion.dequant_k_reference` vs kernel K̂ | bit-exact codes; dequant ≤ 1 ulp fp |
| Packed/dequant **V** equivalence | `dequant_v_reference` vs kernel V̂ | bit-exact codes; dequant ≤ 1 ulp fp |
| **Protected-value** equivalence | writer `k_protect_ext` overlay vs kernel `tl.where` output | bf16: exact; **P8: gated by Part F** |
| Attention-**logit** tolerance | `attention_metrics.logit_mse` (kernel vs reference) | ≤ 1e-3 (layout change: ~0) |
| **Softmax**-distribution tolerance | `attention_metrics.softmax_kl_max` | ≤ 1e-4 (layout change: ~0) |
| Final attention-**output** tolerance | `attention_metrics.attn_out_cos/mse` | cos ≥ 0.9999 (layout change: ~1.0) |
| Block-table semantics | drive route-A vs production on identical `block_tables` | identical gathered KV |
| **Partial-tail** semantics | full-block-only workload vs a `%BS != 0` workload | tail block matches `_splice_k_partial_tail` |
| Snapshot/WarmTier compat | `tier5b_snapshot.verify_roundtrip` on the new layout | byte-roundtrip PASS |
| No new retrieval regressions | needle+hard-needle+MMLU vs affine (Gate-1 harness) | 0 regressions (deterministic) |

## Gate procedure

1. **CPU equivalence first** (no GPU): new dequant/layout logic vs `phase6f_read_fusion` + sketch
   references, bit-exact on codes. This is CI-able and catches most layout bugs before a kernel exists.
2. **GPU numeric** (pod): kernel output vs `fused_int4_attention_reference` on captured Q/K/V, within the
   tolerances above. For a layout/gather change the deltas must be ~0 (deterministic), not merely "small".
3. **End-to-end quality** (pod): the Gate-1 drivers, affine vs new-kernel cell, **0 regressions**. A
   layout/gather change that changes any needle/hard-needle/MMLU answer fails the gate.
4. **Snapshot/WarmTier**: `verify_roundtrip` must pass on the new stored layout (store-as-consumed changes
   the byte order — the snapshot `_TENSOR_KEYS` contract must still round-trip).

**Expected result for a quality-neutral change:** every quality metric identical within deterministic
tolerance; the only intended delta is throughput. Anything else is a correctness failure to fix before merge.
