#!/usr/bin/env python3
# Phase 6K.6 — why does flash_attn_with_int4_kvcache return an exact ZERO tensor?
#
# 6K.5 proved: writer is correct (INT4 dequant cos 0.987 vs bf16 ground truth),
# but the kernel output is norm=0.0 with NO NaN. That rules out the OOB / score-
# mask theories and points at one of:
#   (1) the int4_packed compute/epilogue never runs -> output stays zero-init, OR
#   (2) a short-sequence guard masks ALL columns (incl. valid) for s_curr < S_max.
#
# This probe re-invokes the REAL kernel on CLONED inputs (so the live generation
# is untouched) while sweeping cache_seqlens, and tries to pull back softmax_lse.
# Interpretation:
#   * zero for ALL cache_seqlens (incl. == S_max)  -> (1) dispatch/epilogue bug;
#     the int4_packed path isn't writing the output accumulator at all.
#   * zero for small s_curr, NON-zero near S_max    -> (2) the length-mask path
#     zeros valid columns for short sequences; find the threshold.
#   * softmax_lse == -inf                            -> all columns masked.
#     softmax_lse finite but out==0                  -> accumulation/epilogue bug.
#
# Run:
#   export PYTHONPATH=/workspace/symbolu/CTM_plus/KVPolicy:$PYTHONPATH
#   PHASE6E_FUSED_WRITER=0 python CTM_plus/Bench/scripts/phase6k6_zero_output_probe.py 2>&1 | tee /tmp/phase6k6.log

import torch

CAPTURE = {"first_call": True, "decode_calls": 0}


def _clone(x):
    return x.clone() if torch.is_tensor(x) else x


def _onorm(o):
    """Return (norm, nan, nonzero_count) for a kernel output that may be a
    tensor or a (out, lse, ...) tuple. Prints lse stats if present."""
    lse_info = ""
    if isinstance(o, (tuple, list)):
        out = o[0]
        for extra in o[1:]:
            if torch.is_tensor(extra) and extra.is_floating_point():
                ninf = int(torch.isneginf(extra).sum())
                lse_info = (f"  lse: shape={tuple(extra.shape)} "
                            f"min={extra.float().min():.3f} max={extra.float().max():.3f} "
                            f"neg_inf={ninf}")
                break
    else:
        out = o
    out = out.float()
    return out.norm().item(), int(torch.isnan(out).sum()), int((out != 0).sum()), lse_info


def probe(args, kwargs, out0):
    real_fn = REAL["fn"]          # the unwrapped kernel captured at install()

    cs = kwargs["cache_seqlens"]
    s_curr = int(cs[0].item())
    S_max = kwargs["k_packed_int4"].shape[1]

    print("\n" + "=" * 80)
    print("PHASE 6K.6 — ZERO-OUTPUT PROBE")
    print("=" * 80)
    n, nan, nz, lse = _onorm(out0)
    print(f"  baseline (cache_seqlens={s_curr}): norm={n:.4f} nan={nan} nonzero={nz}{lse}")
    print(f"  S_max (buffer positions) = {S_max}")

    # (A) Try to retrieve softmax_lse via common kwarg spellings.
    print("\n  --- (A) attempt to retrieve softmax_lse ---")
    got_lse = False
    for kw in ("return_softmax_lse", "return_attn_probs", "return_softmax"):
        try:
            a2 = [_clone(x) for x in args]
            k2 = {k: _clone(v) for k, v in kwargs.items()}
            k2[kw] = True
            o = real_fn(*a2, **k2)
            n, nan, nz, lse = _onorm(o)
            print(f"    {kw}=True -> out norm={n:.4f} nan={nan} nonzero={nz}{lse}"
                  + ("" if lse else "  (no lse in return)"))
            got_lse = True
            break
        except Exception as e:
            print(f"    {kw}=True -> not supported ({type(e).__name__})")
    if not got_lse:
        print("    (kernel does not expose softmax_lse via these kwargs)")

    # (B) cache_seqlens sweep on CLONED inputs (live generation untouched).
    print("\n  --- (B) cache_seqlens sweep (cloned inputs) ---")
    sweep = sorted({1, 2, 4, 8, max(1, s_curr - 1), s_curr, s_curr + 1,
                    16, S_max - 1, S_max})
    sweep = [s for s in sweep if 1 <= s <= S_max]
    for sc in sweep:
        try:
            a2 = [_clone(x) for x in args]
            k2 = {k: _clone(v) for k, v in kwargs.items()}
            k2["cache_seqlens"] = torch.full_like(cs, sc)
            o = real_fn(*a2, **k2)
            n, nan, nz, _ = _onorm(o)
            tag = "  <== ZERO" if n == 0.0 else ""
            print(f"    cache_seqlens={sc:3d}: norm={n:9.4f} nan={nan} nonzero={nz}{tag}")
        except Exception as e:
            print(f"    cache_seqlens={sc:3d}: ERROR {type(e).__name__}: {e}")

    # (C) toggle causal (decode normally uses causal=False).
    print("\n  --- (C) causal toggle ---")
    for cz in (False, True):
        try:
            a2 = [_clone(x) for x in args]
            k2 = {k: _clone(v) for k, v in kwargs.items()}
            k2["causal"] = cz
            o = real_fn(*a2, **k2)
            n, nan, nz, _ = _onorm(o)
            print(f"    causal={cz!s:5s}: norm={n:9.4f} nan={nan} nonzero={nz}")
        except Exception as e:
            print(f"    causal={cz!s:5s}: ERROR {type(e).__name__}: {e}")

    print("\n  READ: if every cache_seqlens (incl. S_max) gives norm 0, the")
    print("  int4_packed compute/epilogue never writes the output accumulator")
    print("  (dispatch/epilogue bug). If norm becomes non-zero as cache_seqlens")
    print("  -> S_max, the short-sequence length-mask is zeroing valid columns.")
    print("=" * 80 + "\n", flush=True)


REAL = {}


def install():
    from vllm import vllm_flash_attn
    REAL["fn"] = vllm_flash_attn.flash_attn_with_int4_kvcache

    def wrapped(*args, **kwargs):
        CAPTURE["decode_calls"] += 1
        out = REAL["fn"](*args, **kwargs)
        if CAPTURE["first_call"]:
            CAPTURE["first_call"] = False
            try:
                probe(args, kwargs, out)
            except Exception as e:
                import traceback
                print(f"[6k6] probe failed: {type(e).__name__}: {e}")
                traceback.print_exc()
        return out

    vllm_flash_attn.flash_attn_with_int4_kvcache = wrapped
    from vllm.vllm_flash_attn import flash_attn_interface
    flash_attn_interface.flash_attn_with_int4_kvcache = wrapped
    print("[patch] kernel wrapped (6K.6 zero-output probe).", flush=True)


def main():
    install()
    from kv_policy.int4_protected import Int4ProtectedLLM
    from vllm import SamplingParams
    print("\n[run] Loading Qwen2.5-7B-Instruct (eager)...", flush=True)
    llm = Int4ProtectedLLM(
        model="Qwen/Qwen2.5-7B-Instruct",
        max_model_len=8192, gpu_memory_utilization=0.5,
        max_num_seqs=8, enforce_eager=True,
    )
    sp = SamplingParams(temperature=0.0, max_tokens=4)
    print("\n[run] generate()...", flush=True)
    out = llm.generate(["List three primary colors and their names."], sp)
    print(f"\n[run] Output text: {out[0].outputs[0].text!r}")


if __name__ == "__main__":
    main()
