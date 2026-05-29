#!/usr/bin/env python3
# Phase 6K.14 — TRUE high-concurrency capacity SATURATION test.
#
# Supersedes the d6584d3 saturation driver, which could NOT validly test
# protected at B>8: the PagedKVWriter slot pool defaulted to 8 and never freed
# slots on completion, so any B>=9 (or any run with decode waves) died with
# "PagedKVWriter slot pool exhausted" long before the GPU saturated. That
# bookkeeping error — not capacity — is what 6K.13 hit. This driver runs on top
# of the 6K.14 fix (auto-bump $PHASE6_MAX_ACTIVE_SLOTS + evict-on-completion)
# AND pins $PHASE6_MAX_ACTIVE_SLOTS=B per worker, so a protected failure now
# means a REAL capacity limit (OOM / heavy preemption), making the
# protected/bf16 clean-max-B ratio a HONEST capacity number.
#
# The question it answers (the 6K.13 GATE input):
#   * int4_protected reports ~2x vLLM max_concurrency (it packs ~4x tokens/
#     block) but costs ~+4.7 GB total HBM (sidecar+graph tax). Is the 2x a NET
#     win or just bookkeeping the +4.7 GB eats?
#   * Fill prompts to ~0.8*mml and ramp B until a cell saturates. If protected
#     sustains a clean ~2x-higher B than bf16 -> capacity story demonstrated.
#     If it saturates at ~bf16's B -> bookkeeping; drop the capacity claim and
#     keep the (real) fidelity story.
#
# worker(cell, mml, B): B copies of a ~0.8*mml prompt, max_num_seqs=B; for int4
#   cells pins PHASE6_MAX_ACTIVE_SLOTS=B and installs its own precapture hook.
#   Records completed / oom / slot_exhausted / preempts / HBM / agg_tps /
#   max_active_slots / vLLM max_concurrency.
# driver: sweep B per cell; clean-max-B = largest B with all-complete, no OOM,
#   no preemption, no slot-exhaustion; report protected/bf16 ratio + validity.
#
# Usage:
#   python CTM_plus/Bench/scripts/phase6k14_saturation.py --selftest          # CPU
#   CELL=protected python CTM_plus/Bench/scripts/phase6k14_saturation.py \
#       --worker --mml 8192 --batch 112                                       # GPU
#   python CTM_plus/Bench/scripts/phase6k14_saturation.py --mml 8192 \
#       2>&1 | tee /tmp/phase6k14.log                                         # GPU

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CELLS = ["bf16", "protected"]        # add "naive" via --cells if wanted
NAIVE_MASK_DEFAULT = "/workspace/dev/build-logs/qwen2_5_7b_protect_mask_naive.pt"

# Default B sweeps per mml, straddling bf16(~55/26/12) and int4(~110/53/24)
# reported concurrency, so the clean-max-B for each cell lands inside the sweep.
DEFAULT_B = {
    8192:  [48, 56, 72, 96, 112, 128],
    16384: [24, 28, 40, 52, 60, 72],
    32768: [12, 16, 24, 28, 36],
}


def _long_prompt(target_tokens):
    # ~16 tokens/sentence; the worker also truncates to fit under mml.
    n = max(20, target_tokens // 16)
    return "Document: " + " ".join(
        f"Fact {i}: the town ledger recorded routine activity that week."
        for i in range(n)
    ) + "\n\nSummarize the document in one sentence."


def _sched_counters(llm):
    """Best-effort cumulative preemption count from the vLLM scheduler."""
    try:
        sched = llm.llm_engine.scheduler[0]
        for attr in ("num_cumulative_preemption", "num_preempted", "preemption_count"):
            v = getattr(sched, attr, None)
            if isinstance(v, int):
                return v
    except Exception:
        pass
    return 0


def _max_concurrency(llm, mml):
    try:
        cc = llm.llm_engine.cache_config
        nb = getattr(cc, "num_gpu_blocks", None)
        bs = getattr(cc, "block_size", None)
        if nb and bs:
            return round(nb * bs / mml, 1)
    except Exception:
        pass
    return None


def _writer_max_active_slots(llm):
    """Read back the slot-pool cap that actually took effect on a writer —
    confirms PHASE6_MAX_ACTIVE_SLOTS / auto-bump sized the pool to B."""
    try:
        from kv_policy.phase6b2_precapture_hook import (
            _collect_writers, _resolve_inner_model)
        ws = _collect_writers(_resolve_inner_model(llm))
        for w in ws:
            cap = getattr(w, "_max_active_slots", None)
            if cap is not None:
                return int(cap)
    except Exception:
        pass
    return None


def _classify_error(msg):
    """Distinguish the three failure modes that matter for a capacity verdict."""
    low = (msg or "").lower()
    return {
        "oom": "out of memory" in low or "outofmemory" in low,
        "slot_exhausted": "slot pool exhausted" in low,
    }


def run_worker(mml, batch, max_tokens=8):
    import torch
    cell = os.environ.get("CELL", "protected")
    eager = os.environ.get("ENFORCE_EAGER", "0").strip() in ("1", "true", "yes")
    os.environ.pop("PHASE6B3_FORCE_EAGER", None)

    if cell == "naive":
        os.environ["PHASE6J_NAIVE_FORCE_ZERO"] = "1"
        os.environ["PROTECT_MASK_PATH"] = os.environ.get("NAIVE_MASK_PATH", NAIVE_MASK_DEFAULT)
    elif cell == "protected":
        os.environ["PHASE6J_NAIVE_FORCE_ZERO"] = "0"
        os.environ.pop("PROTECT_MASK_PATH", None)

    if cell != "bf16":
        # Phase 6K.14: pin the slot pool to B so the pool can hold every
        # concurrent decode slot (belt-and-suspenders with runtime auto-bump).
        # MUST be set BEFORE the writer is constructed (first forward).
        os.environ["PHASE6_MAX_ACTIVE_SLOTS"] = str(batch)
        # Evict-on-completion is the fix; default on. EVICT_ON_DECODE=0 flips
        # it off to reproduce the pre-fix leak for an A/B control cell.
        os.environ["PHASE6K14_EVICT_ON_DECODE"] = os.environ.get("EVICT_ON_DECODE", "1")
        # Bench owns hook installation -> disable the factory auto-hook.
        os.environ["PHASE6K10_AUTO_HOOK"] = "0"
        os.environ.setdefault("PHASE6E_FUSED_WRITER", "1")

    util = float(os.environ.get("GPU_UTIL", "0.5"))
    out = os.environ.get("OUTPUT", f"/tmp/phase6k14_{cell}_mml{mml}_B{batch}.json")
    rec = {"cell": cell, "mml": mml, "batch": batch, "gpu_util": util,
           "max_tokens": max_tokens,
           "oom": False, "slot_exhausted": False, "completed": 0, "preempts": 0,
           "hbm_gb": None, "agg_tps": None, "max_concurrency": None,
           "max_active_slots": None, "prompt_tokens": None,
           "evict_on_decode": os.environ.get("PHASE6K14_EVICT_ON_DECODE", "1")
           if cell != "bf16" else None,
           "error": None}

    from vllm import SamplingParams
    try:
        if cell == "bf16":
            from vllm import LLM
            llm = LLM(model="Qwen/Qwen2.5-7B-Instruct", max_model_len=mml,
                      gpu_memory_utilization=util, dtype="bfloat16",
                      max_num_seqs=batch, enforce_eager=eager)
        else:
            from kv_policy.int4_protected import Int4ProtectedLLM
            from kv_policy.phase6b2_precapture_hook import (
                install_int4_protected_precapture_hook, _collect_writers,
                _collect_impls, _resolve_inner_model, _resolve_model_runner)
            llm = Int4ProtectedLLM(model="Qwen/Qwen2.5-7B-Instruct", max_model_len=mml,
                                   gpu_memory_utilization=util, max_num_seqs=batch,
                                   enforce_eager=eager)
            try:
                m = _resolve_inner_model(llm)
                install_int4_protected_precapture_hook(
                    _resolve_model_runner(llm), _collect_writers(m), impls=_collect_impls(m))
            except Exception as e:
                rec["error"] = f"hook: {type(e).__name__}: {e}"
    except Exception as exc:
        rec.update(_classify_error(str(exc)))
        rec["error"] = f"init: {str(exc)[:160]}"
        Path(out).write_text(json.dumps(rec, indent=2))
        print(f"[6k14 {cell} mml{mml} B{batch}] INIT FAIL oom={rec['oom']} "
              f"slot_exhausted={rec['slot_exhausted']} {rec['error']}", flush=True)
        return 0

    rec["max_concurrency"] = _max_concurrency(llm, mml)
    if cell != "bf16":
        rec["max_active_slots"] = _writer_max_active_slots(llm)
    # max_tokens drives saturation: short gen (8) is throughput-only and lets
    # vLLM queue-drain B in waves WITHOUT memory pressure (so nothing ever
    # saturates); long gen (e.g. 512-1024) makes admitted batches GROW during
    # decode, forcing real preemption/OOM at B>max_concurrency -> a DEMONSTRATED
    # max-B. Use a long value to actually answer the capacity question.
    sp = SamplingParams(temperature=0.0, max_tokens=max_tokens)
    prompt = _long_prompt(int(mml * 0.8))
    # Truncate the prompt to fit (prompt + gen) under mml regardless of the
    # token estimate — vLLM errors on over-length prompts otherwise.
    try:
        tk = llm.get_tokenizer()
        ids = tk.encode(prompt)
        cap = mml - sp.max_tokens - 64
        if len(ids) > cap:
            ids = ids[:cap]
            prompt = tk.decode(ids)
        rec["prompt_tokens"] = len(ids)
    except Exception:
        pass

    pre = _sched_counters(llm)
    try:
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        outs = llm.generate([prompt] * batch, sp)
        dt = time.time() - t0
        rec["completed"] = sum(1 for o in outs if o.outputs and o.outputs[0].text)
        n_out = sum(len(o.outputs[0].token_ids) for o in outs if o.outputs)
        rec["agg_tps"] = round(n_out / dt, 1) if dt > 0 else None
        rec["hbm_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
        rec["preempts"] = _sched_counters(llm) - pre
    except Exception as exc:
        rec.update(_classify_error(str(exc)))
        rec["error"] = f"gen: {str(exc)[:160]}"

    Path(out).write_text(json.dumps(rec, indent=2))
    print(f"[6k14 {cell} mml{mml} B{batch} gen{max_tokens}] "
          f"prompt_tok={rec['prompt_tokens']} "
          f"completed={rec['completed']}/{batch} oom={rec['oom']} "
          f"slot_exhausted={rec['slot_exhausted']} preempts={rec['preempts']} "
          f"hbm={rec['hbm_gb']} tps={rec['agg_tps']} max_conc={rec['max_concurrency']} "
          f"slots={rec['max_active_slots']}", flush=True)
    return 0


def _analyze(rows):
    """Pure analysis (CPU-testable). Reports:
      * clean_maxB[cell] — largest B that completed fully with no OOM, no
        preemption, no slot-exhaustion.
      * ceiling_not_reached — cells whose LARGEST tried B was still clean, i.e.
        the sweep never saturated them (e.g. short-gen workloads queue-drain
        without memory pressure). For those, clean-max-B is only a floor, so the
        clean-max-B ratio is unreliable and the run is NOT 'demonstrated'.
      * density[cell] — vLLM max_concurrency / total HBM (seq/GB). An ESTIMATE
        from vLLM's block budget (not a demonstrated load) but apples-to-apples
        across cells and net of the sidecar tax (it's in the GB denominator).
      * ratio (clean-max-B) + density_ratio (conc/GB), protected/bf16.
      * valid — no slot-exhaustion anywhere (else the cap was mis-sized: a
        6K.14 regression, reported separately).
      * demonstrated — saturated AND valid (i.e. the clean-max-B ratio means
        something)."""
    clean_maxB, slot_exhausted_at, by_cell = {}, {}, {}
    for r in rows:
        cell, B = r.get("cell"), r.get("batch")
        if cell is None or B is None:
            continue
        by_cell.setdefault(cell, []).append(r)
        if r.get("slot_exhausted"):
            slot_exhausted_at.setdefault(cell, []).append(B)
        clean = (
            not r.get("oom")
            and not r.get("slot_exhausted")
            and r.get("completed") == B
            and (r.get("preempts") or 0) == 0
            and not r.get("error")
        )
        if clean:
            clean_maxB[cell] = max(clean_maxB.get(cell, 0), B)

    max_B_tried = {c: max(r["batch"] for r in rs) for c, rs in by_cell.items()}
    ceiling_not_reached = sorted(
        c for c, mb in clean_maxB.items() if mb == max_B_tried.get(c))

    density = {}
    for c, rs in by_cell.items():
        for r in sorted(rs, key=lambda x: x["batch"], reverse=True):
            if r.get("max_concurrency") and r.get("hbm_gb"):
                density[c] = {
                    "conc": r["max_concurrency"], "hbm_gb": r["hbm_gb"],
                    "conc_per_gb": round(r["max_concurrency"] / r["hbm_gb"], 3),
                }
                break

    out = {"clean_maxB": clean_maxB, "slot_exhausted_at": slot_exhausted_at,
           "ceiling_not_reached": ceiling_not_reached, "density": density,
           "ratio": None, "density_ratio": None,
           "valid": not slot_exhausted_at,
           "demonstrated": not ceiling_not_reached and not slot_exhausted_at}
    if clean_maxB.get("bf16") and clean_maxB.get("protected"):
        out["ratio"] = round(clean_maxB["protected"] / clean_maxB["bf16"], 2)
    if density.get("bf16") and density.get("protected"):
        out["density_ratio"] = round(
            density["protected"]["conc_per_gb"] / density["bf16"]["conc_per_gb"], 2)
    return out


def run_driver(mml, cells, b_list, max_tokens=8):
    rows = []
    for cell in cells:
        for B in b_list:
            out = f"/tmp/phase6k14_{cell}_mml{mml}_B{B}.json"
            env = dict(os.environ)
            env.update({"CELL": cell, "OUTPUT": out})
            env.setdefault("PHASE6E_FUSED_WRITER", "1")
            env.pop("PHASE6B3_FORCE_EAGER", None)
            print(f"\n=== 6k14: cell={cell} mml={mml} B={B} gen={max_tokens} ===", flush=True)
            subprocess.run([sys.executable, __file__, "--worker",
                            "--mml", str(mml), "--batch", str(B),
                            "--max-tokens", str(max_tokens)], env=env, check=False)
            try:
                rows.append(json.loads(Path(out).read_text()))
            except Exception as e:
                rows.append({"cell": cell, "batch": B, "error": str(e)[:60]})

    a = _analyze(rows)
    print("\n" + "=" * 100)
    print(f"PHASE 6K.14 — capacity saturation (mml={mml}, prompt~0.8*mml, "
          f"gpu_util={os.environ.get('GPU_UTIL','0.5')})")
    print("=" * 100)
    print(f"  {'cell':>10} {'B':>5} | {'done':>7} {'oom':>5} {'slotX':>5} "
          f"{'preempt':>7} {'HBM GB':>7} {'tps':>7} {'conc':>6} {'slots':>6}")
    print("  " + "-" * 90)
    for r in rows:
        cell, B = r.get("cell", "?"), r.get("batch", "?")
        if r.get("error") and r.get("completed", 0) == 0 and not (
                r.get("oom") or r.get("slot_exhausted")):
            print(f"  {cell:>10} {B:>5} | ERROR {r['error']}")
            continue
        tag = ("  <-- OOM" if r.get("oom")
               else "  <-- SLOT-EXHAUSTED (6K.14 regression!)" if r.get("slot_exhausted")
               else "  <-- preempt" if (r.get("preempts") or 0) > 0 else "")
        print(f"  {cell:>10} {B:>5} | {str(r.get('completed'))+'/'+str(B):>7} "
              f"{str(bool(r.get('oom'))):>5} {str(bool(r.get('slot_exhausted'))):>5} "
              f"{r.get('preempts') or 0:>7} {(r.get('hbm_gb') or 0):>7} "
              f"{(r.get('agg_tps') or 0):>7} {(r.get('max_concurrency') or 0):>6} "
              f"{(r.get('max_active_slots') or 0):>6}{tag}")

    print("\n  clean max-B (all complete, no OOM/preempt/slot-exhaustion):", a["clean_maxB"])
    if a["slot_exhausted_at"]:
        print("  !! SLOT-EXHAUSTED at:", a["slot_exhausted_at"])
        print("  !! INVALID capacity test — cap < B. Re-run on the 6K.14 fix "
              "(PHASE6_MAX_ACTIVE_SLOTS auto-bump / set to B).")
    if a["ceiling_not_reached"]:
        print(f"  !! CEILING NOT REACHED for {a['ceiling_not_reached']} — the "
              "largest tried B was still clean, so NOTHING saturated.")
        print("  !! The clean-max-B ratio is UNRELIABLE here. Raise --b-list "
              "and/or --max-tokens (short gen queue-drains in waves with no "
              "memory pressure; use --max-tokens 512+ to force preemption).")

    if a["density"]:
        print("\n  concurrency density (vLLM max_conc / total HBM) — budget "
              "estimate, net of sidecar tax:")
        for c, d in a["density"].items():
            print(f"     {c:>10}: conc={d['conc']} / {d['hbm_gb']}GB "
                  f"= {d['conc_per_gb']} seq/GB")
        if a["density_ratio"] is not None:
            print(f"   density ratio (protected/bf16) = {a['density_ratio']}x "
                  "(estimated concurrent max-len seqs per GB)")

    if a["ratio"] is not None:
        caveat = "" if a["demonstrated"] else "   [NOT saturated -> unreliable]"
        print(f"\n  clean-max-B ratio (protected/bf16) = {a['ratio']}x{caveat}")
        if a["demonstrated"]:
            print("   ~2x  => DEMONSTRATED net capacity win (real capacity story).")
            print("   ~1x  => bookkeeping; the +4.7 GB sidecar tax eats the budget "
                  "(drop the capacity claim; keep the fidelity story).")
    print("=" * 100, flush=True)
    return 0


def _selftest():
    # 1. Prompt sizing stays under mml.
    for mml in (8192, 16384):
        p = _long_prompt(int(mml * 0.8))
        assert "Summarize" in p
        print(f"  long_prompt(mml={mml}): chars={len(p)} ~tok={len(p)//4}")

    # 2. Error classification.
    assert _classify_error("CUDA out of memory. Tried to allocate")["oom"]
    assert _classify_error("RuntimeError: PagedKVWriter slot pool exhausted "
                           "(max_active_slots=8)")["slot_exhausted"]
    assert not _classify_error("some other error")["oom"]
    print("  error classification: PASS")

    # 3. Analysis core on synthetic rows.
    rows_valid = [
        {"cell": "bf16", "batch": 48, "completed": 48, "preempts": 0},
        {"cell": "bf16", "batch": 56, "completed": 30, "oom": True},
        {"cell": "protected", "batch": 96, "completed": 96, "preempts": 0},
        {"cell": "protected", "batch": 112, "completed": 90, "preempts": 4},
    ]
    a = _analyze(rows_valid)
    assert a["clean_maxB"] == {"bf16": 48, "protected": 96}, a["clean_maxB"]
    assert a["ratio"] == 2.0, a["ratio"]
    assert a["valid"] is True
    assert a["ceiling_not_reached"] == [], a["ceiling_not_reached"]
    assert a["demonstrated"] is True            # both cells saturated

    rows_invalid = [
        {"cell": "protected", "batch": 9, "completed": 0, "slot_exhausted": True,
         "error": "init: slot pool exhausted"},
        {"cell": "bf16", "batch": 9, "completed": 9, "preempts": 0},
    ]
    a2 = _analyze(rows_invalid)
    assert a2["valid"] is False
    assert a2["slot_exhausted_at"] == {"protected": [9]}, a2["slot_exhausted_at"]
    assert "protected" not in a2["clean_maxB"]
    assert a2["demonstrated"] is False
    print("  analysis core (valid + invalid): PASS")

    # 4. Ceiling-not-reached (the actual mml=8192 short-gen run): every tried B
    # was clean for both cells -> ratio is 1.0x but NOT demonstrated, and the
    # real signal is the concurrency density (~1.8x).
    rows_ceiling = [
        {"cell": "bf16", "batch": 96, "completed": 96, "preempts": 0,
         "max_concurrency": 55.3, "hbm_gb": 42.15},
        {"cell": "bf16", "batch": 128, "completed": 128, "preempts": 0,
         "max_concurrency": 55.3, "hbm_gb": 42.15},
        {"cell": "protected", "batch": 96, "completed": 96, "preempts": 0,
         "max_concurrency": 110.6, "hbm_gb": 46.55},
        {"cell": "protected", "batch": 128, "completed": 128, "preempts": 0,
         "max_concurrency": 110.6, "hbm_gb": 46.55},
    ]
    a3 = _analyze(rows_ceiling)
    assert a3["ceiling_not_reached"] == ["bf16", "protected"], a3["ceiling_not_reached"]
    assert a3["demonstrated"] is False
    assert a3["ratio"] == 1.0, a3["ratio"]                       # the misleading number
    assert a3["density"]["protected"]["conc_per_gb"] == round(110.6 / 46.55, 3)
    assert abs(a3["density_ratio"] - 1.81) < 0.02, a3["density_ratio"]  # the real signal
    print("  analysis core (ceiling-not-reached + density): PASS")
    print("SELFTEST PASS")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mml", type=int, default=8192)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--cells", default=",".join(CELLS))
    ap.add_argument("--b-list", default="", help="comma list; default per-mml sweep")
    ap.add_argument("--max-tokens", type=int, default=8,
                    help="gen length per seq. 8=throughput probe (won't "
                         "saturate); 512+ forces preemption for a real max-B.")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()
    if args.worker:
        return run_worker(args.mml, args.batch, args.max_tokens)
    b_list = [int(x) for x in args.b_list.split(",")] if args.b_list \
        else DEFAULT_B.get(args.mml, [32, 48, 64])
    return run_driver(args.mml, args.cells.split(","), b_list, args.max_tokens)


if __name__ == "__main__":
    raise SystemExit(main())
