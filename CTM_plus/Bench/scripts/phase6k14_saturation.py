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
    """Cumulative preemption count + the source attribute(s) used (or None).

    Robust across vLLM builds: scans every scheduler's __dict__ for int
    attributes whose name contains 'preempt' and sums them. Returns
    (total, source) — source is a comma-joined list of the attrs found, or
    None if the counter is UNAVAILABLE (in which case 'preempts=0' is
    meaningless and saturation cannot be inferred from it)."""
    try:
        scheds = llm.llm_engine.scheduler
        if not isinstance(scheds, (list, tuple)):
            scheds = [scheds]
    except Exception:
        return 0, None
    total, srcs = 0, []
    for sched in scheds:
        try:
            d = vars(sched)
        except Exception:
            continue
        for k, v in d.items():
            if "preempt" in k.lower() and isinstance(v, int) and not isinstance(v, bool):
                total += v
                if k not in srcs:
                    srcs.append(k)
    return total, (",".join(srcs) if srcs else None)


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


class _StepProbe:
    """Per-step scheduler instrumentation. Wraps ``LLMEngine.step`` to sample,
    after every engine step, the LIVE (running) sequence count, the waiting
    queue, and KV-block usage — so we OBSERVE resident concurrency and block
    utilization directly instead of inferring saturation from submitted B
    (which offline generate() never reveals: it queue-drains in waves).

    Best-effort + fully guarded (vLLM internals vary by build); whatever it
    can't read stays None and is reported as such."""

    def __init__(self, llm):
        self.llm = llm
        self.peak_live = 0
        self.sum_live = 0
        self.n_steps = 0
        self.max_waiting = 0
        self.total_blocks = None
        self.peak_used_blocks = None
        self.block_src = None
        self._orig = None
        self._scheds = []

    def _scheds_list(self):
        try:
            s = self.llm.llm_engine.scheduler
            return list(s) if isinstance(s, (list, tuple)) else [s]
        except Exception:
            return []

    def _free_blocks(self, scheds):
        free, got = 0, False
        for s in scheds:
            bm = getattr(s, "block_manager", None)
            if bm is None:
                continue
            fn = getattr(bm, "get_num_free_gpu_blocks", None)
            if callable(fn):
                try:
                    free += int(fn()); got = True
                    self.block_src = "block_manager.get_num_free_gpu_blocks"
                    continue
                except Exception:
                    pass
            alloc = getattr(bm, "gpu_allocator", None) or getattr(bm, "block_allocator", None)
            g = getattr(alloc, "get_num_free_blocks", None)
            if callable(g):
                try:
                    free += int(g()); got = True
                    self.block_src = "gpu_allocator.get_num_free_blocks"
                except Exception:
                    pass
        return free if got else None

    def _sample(self):
        live = waiting = 0
        for s in self._scheds:
            try:
                live += len(s.running)
            except Exception:
                pass
            try:
                waiting += len(s.waiting)
            except Exception:
                pass
        self.peak_live = max(self.peak_live, live)
        self.sum_live += live
        self.n_steps += 1
        self.max_waiting = max(self.max_waiting, waiting)
        if self.total_blocks:
            free = self._free_blocks(self._scheds)
            if free is not None:
                used = self.total_blocks - free
                self.peak_used_blocks = used if self.peak_used_blocks is None \
                    else max(self.peak_used_blocks, used)

    def install(self):
        eng = getattr(self.llm, "llm_engine", None)
        if eng is None or not hasattr(eng, "step"):
            return self
        self._scheds = self._scheds_list()
        try:
            self.total_blocks = int(eng.cache_config.num_gpu_blocks)
        except Exception:
            self.total_blocks = None
        self._orig = eng.step

        def _wrapped(*a, **k):
            out = self._orig(*a, **k)
            try:
                self._sample()
            except Exception:
                pass
            return out

        try:
            eng.step = _wrapped
        except Exception:
            self._orig = None
        return self

    def teardown(self):
        if self._orig is not None:
            try:
                self.llm.llm_engine.step = self._orig
            except Exception:
                pass
            self._orig = None

    @property
    def avg_live(self):
        return round(self.sum_live / self.n_steps, 1) if self.n_steps else None

    @property
    def peak_util(self):
        if self.total_blocks and self.peak_used_blocks is not None:
            return round(self.peak_used_blocks / self.total_blocks, 3)
        return None


def run_worker(mml, batch, max_tokens=8, prompt_frac=0.95, gpu_util=None,
               resident_pressure=False):
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

    util = gpu_util if gpu_util is not None else float(os.environ.get("GPU_UTIL", "0.5"))
    out = os.environ.get("OUTPUT", f"/tmp/phase6k14_{cell}_mml{mml}_B{batch}.json")
    rec = {"cell": cell, "mml": mml, "batch": batch, "gpu_util": util,
           "max_tokens": max_tokens, "prompt_frac": prompt_frac,
           "resident_pressure": resident_pressure,
           "oom": False, "slot_exhausted": False, "completed": 0,
           "preempts": 0, "preempt_src": None,
           "hbm_gb": None, "agg_tps": None, "max_concurrency": None,
           "max_active_slots": None, "prompt_tokens": None,
           # live-concurrency instrumentation (resident-pressure mode):
           "peak_live": None, "avg_live": None, "n_steps": None,
           "max_waiting": None, "total_blocks": None, "peak_used_blocks": None,
           "peak_util": None, "resident_fit": None, "saturation_observed": None,
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
    # Fill prompts to EXACTLY the cap so the admitted set really fills the KV
    # pool (the template tokenizes shorter than the rough estimate, so a bare
    # target under-fills and leaves growth headroom -> never saturates, Runs
    # 1-3). Over-request then truncate down to the cap. cap also guarantees
    # prompt + gen <= mml.
    cap = min(mml - sp.max_tokens - 64, int(mml * prompt_frac))
    prompt = _long_prompt(int(cap * 1.4))
    try:
        tk = llm.get_tokenizer()
        ids = tk.encode(prompt)
        if len(ids) > cap:
            ids = ids[:cap]
            prompt = tk.decode(ids)
        rec["prompt_tokens"] = len(ids)
    except Exception:
        pass
    # resident_fit: how many of THESE prompts vLLM can hold resident at once
    # (the real concurrency limit for this workload). B beyond it must queue or
    # preempt -> the saturation signal.
    try:
        import math
        bs = int(llm.llm_engine.cache_config.block_size)
        nb = int(llm.llm_engine.cache_config.num_gpu_blocks)
        rec["total_blocks"] = nb
        if rec["prompt_tokens"]:
            rec["resident_fit"] = int(nb // math.ceil(rec["prompt_tokens"] / bs))
    except Exception:
        pass

    probe = _StepProbe(llm).install() if resident_pressure else None
    pre, _ = _sched_counters(llm)
    try:
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        outs = llm.generate([prompt] * batch, sp)
        dt = time.time() - t0
        rec["completed"] = sum(1 for o in outs if o.outputs and o.outputs[0].text)
        n_out = sum(len(o.outputs[0].token_ids) for o in outs if o.outputs)
        rec["agg_tps"] = round(n_out / dt, 1) if dt > 0 else None
        rec["hbm_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
        post, src = _sched_counters(llm)
        rec["preempts"] = post - pre
        rec["preempt_src"] = src
    except Exception as exc:
        rec.update(_classify_error(str(exc)))
        rec["error"] = f"gen: {str(exc)[:160]}"
    finally:
        if probe is not None:
            probe.teardown()
            rec["peak_live"] = probe.peak_live
            rec["avg_live"] = probe.avg_live
            rec["n_steps"] = probe.n_steps
            rec["max_waiting"] = probe.max_waiting
            rec["peak_used_blocks"] = probe.peak_used_blocks
            rec["peak_util"] = probe.peak_util
            if not rec.get("total_blocks"):
                rec["total_blocks"] = probe.total_blocks

    # Saturation OBSERVED iff the scheduler actually hit the block limit (peak
    # util high) OR preempted OR OOM'd — NOT merely "B was large". peak_live <
    # submitted B with high util means the cell could not hold all B resident:
    # peak_live IS the demonstrated max live concurrency.
    pu = rec.get("peak_util") or 0
    rec["saturation_observed"] = bool(
        pu >= 0.90 or (rec.get("preempts") or 0) > 0 or rec.get("oom"))

    Path(out).write_text(json.dumps(rec, indent=2))
    print(f"[6k14 {cell} mml{mml} B{batch} gen{max_tokens} pf{prompt_frac} "
          f"util{util}] ptok={rec['prompt_tokens']} fit={rec['resident_fit']} "
          f"done={rec['completed']}/{batch} oom={rec['oom']} "
          f"slotX={rec['slot_exhausted']} preempt={rec['preempts']}"
          f"({rec['preempt_src']}) live={rec['peak_live']} util={rec['peak_util']} "
          f"sat={rec['saturation_observed']} hbm={rec['hbm_gb']} "
          f"tps={rec['agg_tps']} conc={rec['max_concurrency']}", flush=True)
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

    # Resident-pressure (DIRECT) capacity proof: peak LIVE sequences the cell
    # held resident, and whether the KV block limit was actually reached. This
    # does NOT depend on an OOM cliff — peak_live at high peak_util is the
    # demonstrated max live concurrency. peak_live[cell] = max over rows that
    # saturated (block limit hit / preempt / oom); falls back to overall max.
    peak_live, saturated, counter_seen = {}, {}, False
    for c, rs in by_cell.items():
        if any(r.get("preempt_src") for r in rs):
            counter_seen = True
        sat_rows = [r for r in rs if r.get("saturation_observed")]
        saturated[c] = bool(sat_rows)
        pls = [r.get("peak_live") for r in (sat_rows or rs) if r.get("peak_live")]
        if pls:
            peak_live[c] = max(pls)

    out = {"clean_maxB": clean_maxB, "slot_exhausted_at": slot_exhausted_at,
           "ceiling_not_reached": ceiling_not_reached, "density": density,
           "ratio": None, "density_ratio": None,
           "peak_live": peak_live, "saturated": saturated,
           "live_ratio": None,
           "preempt_counter_available": counter_seen,
           "valid": not slot_exhausted_at,
           "demonstrated": not ceiling_not_reached and not slot_exhausted_at,
           # DIRECT demonstration: both cells actually hit the block limit.
           "live_demonstrated": bool(saturated.get("bf16") and saturated.get("protected"))}
    if clean_maxB.get("bf16") and clean_maxB.get("protected"):
        out["ratio"] = round(clean_maxB["protected"] / clean_maxB["bf16"], 2)
    if density.get("bf16") and density.get("protected"):
        out["density_ratio"] = round(
            density["protected"]["conc_per_gb"] / density["bf16"]["conc_per_gb"], 2)
    if peak_live.get("bf16") and peak_live.get("protected"):
        out["live_ratio"] = round(peak_live["protected"] / peak_live["bf16"], 2)
    return out


def run_driver(mml, cells, b_list, max_tokens=8, prompt_frac=0.95,
               gpu_util=None, resident_pressure=False):
    rows = []
    for cell in cells:
        for B in b_list:
            out = f"/tmp/phase6k14_{cell}_mml{mml}_B{B}.json"
            env = dict(os.environ)
            env.update({"CELL": cell, "OUTPUT": out})
            env.setdefault("PHASE6E_FUSED_WRITER", "1")
            env.pop("PHASE6B3_FORCE_EAGER", None)
            print(f"\n=== 6k14: cell={cell} mml={mml} B={B} gen={max_tokens} "
                  f"pf={prompt_frac} util={gpu_util or 'env'} "
                  f"resident_pressure={resident_pressure} ===", flush=True)
            cmd = [sys.executable, __file__, "--worker",
                   "--mml", str(mml), "--batch", str(B),
                   "--max-tokens", str(max_tokens),
                   "--prompt-frac", str(prompt_frac)]
            if gpu_util is not None:
                cmd += ["--gpu-util", str(gpu_util)]
            if resident_pressure:
                cmd += ["--resident-pressure"]
            subprocess.run(cmd, env=env, check=False)
            try:
                rows.append(json.loads(Path(out).read_text()))
            except Exception as e:
                rows.append({"cell": cell, "batch": B, "error": str(e)[:60]})

    a = _analyze(rows)
    print("\n" + "=" * 104)
    print(f"PHASE 6K.14 — capacity saturation (mml={mml}, prompt~{prompt_frac}*mml, "
          f"gen={max_tokens}, gpu_util={gpu_util or os.environ.get('GPU_UTIL','0.5')}, "
          f"resident_pressure={resident_pressure})")
    print("=" * 104)
    print(f"  {'cell':>10} {'B':>5} | {'done':>7} {'oom':>4} {'preempt':>7} "
          f"{'fit':>5} {'live':>5} {'util':>5} {'sat':>5} {'HBMGB':>6} "
          f"{'tps':>6} {'conc':>6}")
    print("  " + "-" * 92)
    for r in rows:
        cell, B = r.get("cell", "?"), r.get("batch", "?")
        if r.get("error") and r.get("completed", 0) == 0 and not (
                r.get("oom") or r.get("slot_exhausted")):
            print(f"  {cell:>10} {B:>5} | ERROR {r['error']}")
            continue
        tag = ("  <-- OOM" if r.get("oom")
               else "  <-- SLOT-EXHAUSTED (6K.14 regression!)" if r.get("slot_exhausted")
               else "  <-- preempt" if (r.get("preempts") or 0) > 0
               else "  <-- SATURATED" if r.get("saturation_observed") else "")
        print(f"  {cell:>10} {B:>5} | {str(r.get('completed'))+'/'+str(B):>7} "
              f"{str(bool(r.get('oom'))):>4} {r.get('preempts') or 0:>7} "
              f"{(r.get('resident_fit') or 0):>5} {(r.get('peak_live') or 0):>5} "
              f"{(r.get('peak_util') or 0):>5} {str(bool(r.get('saturation_observed'))):>5} "
              f"{(r.get('hbm_gb') or 0):>6} {(r.get('agg_tps') or 0):>6} "
              f"{(r.get('max_concurrency') or 0):>6}{tag}")

    if a["slot_exhausted_at"]:
        print("\n  !! SLOT-EXHAUSTED at:", a["slot_exhausted_at"],
              "— INVALID (cap < B; a 6K.14 regression).")

    # --- DIRECT capacity proof (resident-pressure): peak live + block util ---
    if a["peak_live"]:
        print("\n  DEMONSTRATED max live concurrency (peak resident seqs; "
              "saturation = block-limit hit / preempt / OOM):")
        for c in ("bf16", "protected", "naive"):
            if c in a["peak_live"]:
                print(f"     {c:>10}: peak_live={a['peak_live'][c]} "
                      f"saturated={a['saturated'].get(c)}")
        if a["live_ratio"] is not None:
            verdict = "DEMONSTRATED" if a["live_demonstrated"] else "NOT yet demonstrated"
            print(f"   live-concurrency ratio (protected/bf16) = {a['live_ratio']}x "
                  f"[{verdict}]")
            if not a["live_demonstrated"]:
                print("   (a cell never hit the block limit — raise B / "
                      "--max-tokens / --prompt-frac, or lower --gpu-util.)")
    if a["peak_live"] and not a.get("preempt_counter_available"):
        print("  note: preempt counter was UNREADABLE this run (preempt_src=None) "
              "— saturation judged by peak block utilization, not preempts.")

    # --- ESTIMATED density (always available; from vLLM block budget) ---
    if a["density"]:
        print("\n  ESTIMATED concurrency density (vLLM max_conc / total HBM, "
              "net of sidecar tax):")
        for c, d in a["density"].items():
            print(f"     {c:>10}: conc={d['conc']} / {d['hbm_gb']}GB "
                  f"= {d['conc_per_gb']} seq/GB")
        if a["density_ratio"] is not None:
            print(f"   density ratio (protected/bf16) = {a['density_ratio']}x (estimate)")

    # --- clean-max-B (only meaningful once saturated) ---
    print("\n  clean max-B (no OOM/preempt/slot-exhaustion):", a["clean_maxB"])
    if a["ceiling_not_reached"]:
        print(f"  !! CEILING NOT REACHED for {a['ceiling_not_reached']} — largest "
              "tried B still clean. Offline generate() queue-drains in waves, so "
              "B-ramp alone can't cliff; use --resident-pressure + peak_live above.")
    if a["ratio"] is not None and a["demonstrated"]:
        print(f"  clean-max-B ratio (protected/bf16) = {a['ratio']}x [demonstrated]")
    print("=" * 104, flush=True)
    return 0


def _selftest():
    # 1. Prompt sizing + the fill lever (higher frac -> longer prompt -> tighter
    #    KV budget so concurrency binds and the sweep can saturate).
    for mml in (8192, 16384):
        p = _long_prompt(int(mml * 0.95))
        assert "Summarize" in p
        assert len(_long_prompt(int(mml * 0.95))) > len(_long_prompt(int(mml * 0.8)))
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

    # 5. Resident-pressure DIRECT proof: peak_live at block saturation. bf16
    # held ~55 resident at util~0.97 (saturated); protected ~110 -> live ratio
    # 2.0x, demonstrated because BOTH actually hit the block limit. completed==B
    # throughout (offline generate always finishes) — saturation comes from
    # peak_util, not from completion failure.
    rows_live = [
        {"cell": "bf16", "batch": 96, "completed": 96, "preempts": 3,
         "preempt_src": "num_cumulative_preemption", "peak_live": 55,
         "peak_util": 0.97, "saturation_observed": True},
        {"cell": "bf16", "batch": 160, "completed": 160, "preempts": 20,
         "preempt_src": "num_cumulative_preemption", "peak_live": 55,
         "peak_util": 0.98, "saturation_observed": True},
        {"cell": "protected", "batch": 96, "completed": 96, "preempts": 0,
         "preempt_src": "num_cumulative_preemption", "peak_live": 96,
         "peak_util": 0.82, "saturation_observed": False},
        {"cell": "protected", "batch": 160, "completed": 160, "preempts": 12,
         "preempt_src": "num_cumulative_preemption", "peak_live": 110,
         "peak_util": 0.97, "saturation_observed": True},
    ]
    a4 = _analyze(rows_live)
    assert a4["peak_live"] == {"bf16": 55, "protected": 110}, a4["peak_live"]
    assert a4["saturated"] == {"bf16": True, "protected": True}, a4["saturated"]
    assert a4["live_ratio"] == 2.0, a4["live_ratio"]
    assert a4["live_demonstrated"] is True
    assert a4["preempt_counter_available"] is True
    # Counter-unavailable variant: saturation still detectable via peak_util.
    rows_noctr = [
        {"cell": "bf16", "batch": 96, "completed": 96, "peak_live": 55,
         "peak_util": 0.95, "saturation_observed": True},
        {"cell": "protected", "batch": 96, "completed": 96, "peak_live": 110,
         "peak_util": 0.96, "saturation_observed": True},
    ]
    a5 = _analyze(rows_noctr)
    assert a5["preempt_counter_available"] is False
    assert a5["live_demonstrated"] is True            # peak_util carried it
    assert a5["live_ratio"] == 2.0
    print("  analysis core (resident-pressure live proof): PASS")
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
                         "saturate); 256-512 forces preemption for a real max-B.")
    ap.add_argument("--prompt-frac", type=float, default=0.95,
                    help="fill prompts to this fraction of mml (default 0.95). "
                         "High fill makes concurrency the binding constraint so "
                         "the sweep saturates near max_concurrency; the old 0.8 "
                         "under-filled and queue-drained without saturating.")
    ap.add_argument("--gpu-util", type=float, default=None,
                    help="gpu_memory_utilization override (else $GPU_UTIL or "
                         "0.5). Lower (0.35-0.4) shrinks the pool to force "
                         "saturation at smaller B if needed.")
    ap.add_argument("--resident-pressure", action="store_true",
                    help="capacity-PROOF mode: instrument vLLM per-step to "
                         "record peak LIVE (resident) sequences + peak KV-block "
                         "utilization, so saturation is OBSERVED directly "
                         "(block limit hit) rather than inferred from submitted "
                         "B. Pair with long --max-tokens + high --prompt-frac.")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()
    if args.worker:
        return run_worker(args.mml, args.batch, args.max_tokens,
                          args.prompt_frac, args.gpu_util, args.resident_pressure)
    b_list = [int(x) for x in args.b_list.split(",")] if args.b_list \
        else DEFAULT_B.get(args.mml, [32, 48, 64])
    return run_driver(args.mml, args.cells.split(","), b_list,
                      args.max_tokens, args.prompt_frac, args.gpu_util,
                      args.resident_pressure)


if __name__ == "__main__":
    raise SystemExit(main())
