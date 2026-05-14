# Continue Track B development — session N+3 prompt

**Repository:** `rasaha/symbolu`
**Branch:** `claude/safety-state-machine-EXAlZ`
**Latest commit:** `045e041` (feat(track-b): TurboQuant↔vLLM integration — Tier 1 CPU prototype)

## Current state — read this before suggesting code

Read **`CTM_plus/Bench/bench_out/PHASE4_GPU_FINDINGS.md`** end-to-end, paying particular attention to:

* **§13.3** — Phase 4 throughput closure (durable structural negative). The
  algorithm-quality win survives across five evictor implementations; the
  −20% throughput cost is structural at vLLM 0.7.3's Evictor-ABC patching
  layer.
* **§14** — Track B Tier 1 CPU prototype landed: integration shape validated,
  compression numbers measured on real-shape Qwen2.5-7B KV-block tensors,
  Tier 2 hook coordinates documented.

Key measured findings to preserve:

* **CTM+ Phase 4 algorithm:** **−11.1% swap_out / decode_token** vs LRU,
  reproduced across five evictor implementations (v5/v6/v8/v9/v10) with
  trig mechanism dominantly active (98.7–99.0%). Durable; partner-shareable.
* **Phase 4 throughput:** **−20% tokens/sec vs LRU on chat_32k** —
  structural at the patching layer. Three engineering generations
  (audit-summed 19–38pp recovery) collectively moved it by ~1pp. CLOSED.
* **TurboQuant Tier 1 CPU on Qwen2.5-7B shape:** **3.58× compression at
  cosine 0.965** against the FP16 source that vLLM 0.7.3 actually uses
  (7.15× against FP32 if that's the partner-relevant reference dtype).
  CPU write latency ~2.1ms/block — catastrophic on full cache by design.
* **Bench tests:** 290 passed, 38 skipped, 0 failed. `tests/
  test_turboquant_kvstore.py` pins the round-trip contract.

The `TurboQuantKVStore` wrapper, the Cython evictor, the fast-hooks path,
and the Phase 4 algorithm are all production-ready code shapes. The gaps
are: real GPU compression path (Tier 2), and combined-stack measurement.

## Three tracks for this session

### Track B Tier 2 — PyTorch-ops GPU port of TurboQuant + real `cache_kv` hook (Recommended primary)

**Why:** Tier 1 closed the integration-shape question on CPU. Tier 2 is
what makes TurboQuant actually usable on a real workload — re-implement
PolarQuant's `compress_batch`/`decompress_batch` in pure PyTorch ops so
it runs on GPU without writing CUDA, then monkey-patch the documented
`cache_kv` site so every KV write goes through it.

**Sized:** ~3–5 days code + ~$0.20 GPU validation. Output:

1. **`CTM_plus/KVPolicy/kv_policy/turboquant_gpu.py`** — PyTorch-ops
   re-implementation of the polar transform. Operations needed:
   - `torch.atan2` / `torch.cos` / `torch.sin` for the recursive polar
     decomposition.
   - `torch.bucketize` for angle-index quantisation.
   - `torch.bitwise_or` + `torch.bitwise_left_shift` for bit-packing
     to `angle_bits`-width.
   - QJL residual sign encoding via `torch.sign` + `torch.packbits`.
   Numerical-equivalence test against the NumPy implementation in
   `CTM_plus/DeepSpeed/ctm_plus_deepspeed/turboquant_offload.py` (cosine
   ≥ 0.999 vs the CPU result on the same input, NOT against the original
   tensor — the polar pass introduces the same quantisation noise either
   way; we're checking the PyTorch port is bit-equivalent to the
   reference).

2. **`cache_kv` monkey-patch** at the coordinates documented in
   `PHASE4_GPU_FINDINGS.md` §14.3:
   - File: `vllm/attention/backends/flash_attn.py`
   - Function: `FlashAttentionImpl.forward`
   - Tensor layout: `[2, num_blocks, block_size, num_kv_heads, head_dim]`
     BF16/FP16 on GPU.
   - Per-block compression on write; per-block decompression on read.
   Patch installs via the `install_turboquant_kvstore(model=..., ...)`
   stub in `kv_policy/turboquant_kvstore.py` (signature already reserved
   for this purpose; just needs the body filled in).

3. **CPU regression tests** (no torch needed):
   - PyTorch path equivalence test (against the NumPy reference, gated
     on `pytest.importorskip("torch")`).
   - Round-trip preserves shape + dtype across BF16/FP16/FP32 inputs.

4. **One GPU validation cell** (Qwen2.5-7B + chat_32k + `--ctm-plus
   --phase4-cython-evictor --phase4-fast-hooks --turboquant-kv`).
   Headline measurements:
   - Tokens/sec with Tier-2 TurboQuant ON vs OFF (both with CTM+ Phase 4).
   - Effective KV-cache capacity expansion (peak_kv_blocks_used /
     real_blocks_allocated).
   - Compression ratio + cosine ≥ 0.95 reproduced on real-model KV.
   - Combined-stack effect: **first time CTM+ × TurboQuant are measured
     together**.

5. **`PHASE4_GPU_FINDINGS.md` §15** with the Tier-2 result table + the
   honest combined-stack framing.

**Validation criterion (the headline that lands a partner pitch):**

> "TurboQuant × CTM+ Phase 4 combined: X× effective KV capacity at Y%
> throughput cost on Qwen2.5-7B + chat_32k. Cosine 0.96 on per-block
> round-trip; quality on downstream metrics not yet measured."

**Critical NOT-to-overclaim discipline:** the combined-stack result is
TurboQuant × CTM+ algorithm, NOT × CTXL. CTXL tiering remains
projection-only. The architecture doc's 8.8× claim still has the third
layer unmeasured. Refresh the §7-style honest-scope table in §15.

### Track E — Downstream-quality measurement (MMLU / perplexity)

**Why:** Tier 1 measured **cosine** as the quality proxy. Cosine 0.965 is
the architecture-doc's target, but it's a proxy — the partner-relevant
question is "does generation quality degrade?" Before Tier 2 commits 3–5
days of engineering on a compressed-KV path, half a day on a quality
sanity check de-risks the whole work-track.

**Sized:** ~half a GPU-day + ~$0.05–0.10 spot. Could run *before* Tier 2
as a gate (Recommended if no Tier 2 has been started), or *after* Tier 2
as part of the partner-pitch evidence.

**Setup:**

1. MMLU subset (the standard 5-shot eval over ~10 subjects from the
   MMLU validation split — ~500 questions; fast on Qwen2.5-7B).
2. Run twice: baseline (no TurboQuant, no CTM+) vs `--turboquant-kv
   --ctm-plus --phase4-cython-evictor`.
3. Compare per-subject scores. Target: within ±0.5 absolute points of
   baseline. If TurboQuant alone degrades > 1 pt, that changes Tier 2's
   priority entirely.

**Trigger:** prefer this over Tier 2 if a partner conversation is close
and they'll ask "but what about quality?" — that's an answerable
question with this cell and unanswerable without it.

### Track C — Decision-quality on `agentic_clustered_64k` / `rag_128k` (carry-forward alternate)

Still relevant from the prior session's handoff: chat_32k has
`swap_in_blocks = 0` so the Phase 4 −11.1% swap_out/decode_token result
proves "fewer evicts per token" but not "evicts the RIGHT blocks." A
workload where `swap_in > 0` lets us measure decision quality directly.

**Sized:** ~$0.05–0.10 + half-day plumbing. Single GPU cell.

**Trigger:** prefer over Tier 2 only if a partner specifically wants
agentic / RAG decision-quality evidence. Otherwise Tier 2 is more
strategic.

## Recommended starting point

**Start with Track E (MMLU quality check), THEN Track B Tier 2.**

Reasons for that order:

1. **Track E is half a day. Tier 2 is 3–5 days.** If TurboQuant's cosine
   0.96 quality doesn't translate to acceptable downstream quality on
   Qwen2.5-7B, Tier 2 is a 3-day waste. The half-day Track E cell
   de-risks the 3-day commitment.
2. Track E's output is *itself* partner-shareable: "TurboQuant compresses
   the KV cache 3.5× at zero MMLU regression." That's a concrete claim
   you can ship without Tier 2 at all.
3. After Track E confirms the quality story, Tier 2 has a clean
   pre-committed gate: "if MMLU was within ±0.5pt, Tier 2 ships the
   throughput cost too. If MMLU degrades > 1pt, Tier 2 pauses and we
   investigate why before integrating."

**Switch to Tier 2 first if:** a partner specifically wants the
combined-stack throughput / capacity claim and is willing to accept
quality measurement as a follow-on. Or if you want the harder engineering
work first and trust the cosine-0.965 proxy enough to defer the eval.

**Switch to Track C if:** partner conversation is agentic/RAG-heavy.

## What to NOT do

* **Don't iterate on Phase 4 throughput.** Closed at §13.3. New work
  there requires new evidence (different vLLM version, different
  integration point, different workload class).
* **Don't claim combined 8.8× capacity** even after Tier 2 lands. The
  third layer (CTXL tiering HBM→CXL→NVMe) has zero runtime measurement.
  Honest framing after Tier 2: "CTM+ × TurboQuant: X× capacity at Y%
  throughput cost. CTXL projection remains separate."
* **Don't skip Track E.** Even if Tier 2 lands a beautiful combined
  result, a partner will ask "does generation quality hold up?" — and
  the only honest answer without Track E is "we measured cosine, not
  downstream quality." That's a weak landing.
* **Don't write a CUDA kernel** for TurboQuant. Tier 2 is intentionally
  PyTorch-ops only. The Triton/CUDA kernel is Tier 3, weeks of work,
  not for this session.
* **Don't tune TurboQuant config parameters** (angle_bits / segment_dim /
  enable_qjl) in this session. The 3-bit + 128-segment + QJL-on default
  is the architecture-doc target; sweep is a Tier-2.5 ablation if
  the headline isn't sharp enough.

## File pointers for fast onboarding

| Path | Purpose |
|---|---|
| `CTM_plus/Bench/bench_out/PHASE4_GPU_FINDINGS.md` §13.3 + §14 | Phase 4 closure + Track B Tier 1 result; the canonical context entering this session |
| `CTM_plus/KVPolicy/kv_policy/turboquant_kvstore.py` | **Tier 2 target** — wrapper to extend with GPU compression path + real `cache_kv` install |
| `CTM_plus/DeepSpeed/ctm_plus_deepspeed/turboquant_offload.py` | NumPy reference for the polar transform (~1900 LOC); Tier 2's `turboquant_gpu.py` must produce bit-equivalent output |
| `CTM_plus/Bench/tests/test_turboquant_kvstore.py` | CPU test contract Tier 2 must keep green + extend with PyTorch-ops equivalence tests |
| `CTM_plus/Bench/ctm_bench/scripts/run_streaming.py` | `--turboquant-kv` already wired (Tier 1 stub); Tier 2 replaces the no-op install with a real one |
| `CTM_plus/TURBOQUANT_CTXL_IMPLEMENTATION_OVERVIEW.md` | Architecture doc with the 8.8× claim + the honest-scope downgrade banner |
| `CTM_plus/Bench/bench_out/PARTNER_VALIDATION_NOTE.md` | Partner-facing framing; needs a §-Track-B update after Tier 2 lands (or after Track E lands, whichever first) |
| `vllm/attention/backends/flash_attn.py` (in the vLLM install on the GPU pod) | The Tier 2 hook target. Inspect `FlashAttentionImpl.forward` for the `cache_kv` call site shape; the monkey-patch hangs off that. |

## Open the session by asking the user

1. "Which track — E (MMLU quality, recommended first), B Tier 2 (GPU port + real hook), or C (decision-quality on agentic/RAG)?"
2. "GPU spend budget? E is ~$0.05–0.10; B Tier 2 is ~$0.20 for one validation cell after the code lands; C is ~$0.05–0.10."
3. "Any partner-specific direction — particular workload class, model architecture, vLLM version constraint, or a deployment timeline pushing toward a specific evidence type?"
