"""Phase 6 long-context HBM crossover bench.

Goal: find the max_model_len at which int4_protected captured becomes
HBM-cheaper than stock vLLM bf16, if such a crossover exists.

Two cells:
  bf16     : stock vLLM, bf16 KV cache, CUDA graphs enabled by default.
  captured : Int4ProtectedLLM with PHASE6E_FUSED_WRITER=1 (the Phase 6E
             fused kernels). enforce_eager=False; 6B.2 precapture hook
             installed; graphs capture all decode shapes at engine init.

Sweep:
  max_model_len   : 8192, 16384, 32768 (configurable via --max-model-lens).
  batch sizes     : 1, 2, 4, 8 (skip B > max_concurrency to avoid noise).

Per (cell, max_model_len, B) the bench captures:
  - Peak HBM (torch.cuda.max_memory_allocated/reserved + mem_get_info).
  - vLLM cache config: num_gpu_blocks, block_size, max_concurrency
    (= num_gpu_blocks * block_size / max_model_len; the "Y x" number
    that vLLM prints at engine init: "Maximum concurrency for N tokens
    per request: Y x").
  - Throughput: median wall_s + n_output_tokens over n_runs.
  - Preemption events: RequestOutput.metrics.preempted_count summed
    across the batch (when exposed by vLLM; falls back to a 0).
  - Quality sanity: long prompt has a key fact embedded near the end
    ("the year 1742"); the bench checks the output text for that token.
    A miss flags possible long-context-degradation; not a hard gate
    (greedy decode at max_tokens=16 may not always reach "1742").

Decision criteria (per user spec; encoded in the report verdict):
  - If int4 captured HBM at max_model_len=16K or 32K is BELOW bf16's
    AND quality sanity passes for that (cell, max_model_len), then
    Phase 6F kernel optimization is JUSTIFIED.
  - If int4 NEVER beats bf16 on HBM across the sweep, the verdict is
    NOT_JUSTIFIED — do not pursue heavy kernel work yet.
  - If int4 wins HBM but stays slow, the verdict frames it as a
    long-context quality/memory backend (NOT_THROUGHPUT_ACCELERATOR).

Run:
  python CTM_plus/Bench/scripts/bench_phase6_long_context_gpu.py

For a single (cell, max_model_len) worker (internal):
  python CTM_plus/Bench/scripts/bench_phase6_long_context_gpu.py \
    --worker --cell captured --max-model-len 16384 --output /tmp/x.json
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_CANDIDATES = [
    Path("/workspace/symbolu/CTM_plus"),
    Path("/home/user/symbolu/CTM_plus"),
    Path(__file__).resolve().parent.parent.parent,
]
for _root in ROOT_CANDIDATES:
    kvp = _root / "KVPolicy"
    if kvp.is_dir() and str(kvp) not in sys.path:
        sys.path.insert(0, str(kvp))
        break


CELL_BF16     = "bf16"
CELL_CAPTURED = "captured"
CELLS = [CELL_BF16, CELL_CAPTURED]

DEFAULT_MAX_MODEL_LENS = [8192, 16384, 32768]
DEFAULT_BATCH_SIZES   = [1, 2, 4, 8]
DEFAULT_N_RUNS        = 3       # fewer than the throughput bench; load time dominates
DEFAULT_MAX_TOKENS    = 16      # decode work but small so wall is mostly prompt-pass

# Quality-sanity check: the long prompt embeds this string as the
# answer; we check the output contains it. Greedy decode + 16 output
# tokens may not reach the answer for every batch position, so we
# accept "any seq in the batch contains it" as a soft pass.
QUALITY_FACT_ANSWER = "1742"

# Building blocks for the long synthetic prompt. We compose a prompt
# whose token length scales with max_model_len. The embedded key fact
# sits near the very end so a greedy decode of 16 tokens has a fighting
# chance of producing it.
PROMPT_INTRO = (
    "Below is a long document about a small fictional town. "
    "After the document, answer the question concisely.\n\n"
    "Document:\n"
)
PROMPT_FILLER = (
    "Greendell is nestled between two rivers and has a population of "
    "just over four thousand. Its main industries are pottery, honey "
    "production, and the seasonal wool trade. The annual harvest "
    "festival in early autumn draws visitors from across the region. "
    "The two rivers meet at the southern edge of town near the old mill. "
    "The town council meets the first Thursday of every month. "
    "The market square hosts a weekly produce fair on Saturdays. "
    "Local potters glaze in earth tones inspired by the river clay. "
    "Honey harvest peaks in late summer when the wildflower meadows "
    "around Greendell are at their fullest bloom. "
)
PROMPT_FACT = (
    "The oldest building in town is a stone library founded in 1742, "
    "originally as a granary and converted to a library in 1810. "
)
PROMPT_QUESTION = (
    "\n\nQuestion: What year was the oldest building in Greendell founded?\n"
    "Answer:"
)


def _make_long_prompt(target_tokens: int) -> str:
    """Construct a long prompt that, at default model tokenizers, runs
    approximately to target_tokens. Heuristic 4 chars/token for English;
    the actual prompt token count is logged for verification.

    Layout: intro + N reps of filler + fact + question. Putting the fact
    just before the question maximizes the chance that a greedy decode
    of 16 tokens can reach the answer (so the quality sanity check
    measures KV cache fidelity, not the model's needle-in-haystack
    ability).
    """
    target_chars = max(0, target_tokens * 4)
    fixed_chars = len(PROMPT_INTRO) + len(PROMPT_FACT) + len(PROMPT_QUESTION)
    filler_chars = max(0, target_chars - fixed_chars)
    n_reps = max(1, filler_chars // len(PROMPT_FILLER))
    long_text = PROMPT_FILLER * n_reps
    return PROMPT_INTRO + long_text + PROMPT_FACT + PROMPT_QUESTION


def _check_environment(require_int4: bool) -> Tuple[bool, str]:
    try:
        import torch
        if not torch.cuda.is_available():
            return False, "torch.cuda.is_available() is False"
    except ImportError as exc:
        return False, f"torch import failed: {exc}"
    try:
        import vllm  # noqa: F401
    except ImportError as exc:
        return False, f"vllm import failed: {exc}"
    if require_int4:
        try:
            from kv_policy import int4_protected  # noqa: F401
        except ImportError as exc:
            return False, f"kv_policy.int4_protected import failed: {exc}"
    return True, "OK"


def _find_inner_model(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
        lambda x: x.model_executor.driver_worker.model_runner.model,
    ]
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError):
            continue
    return None


def _find_model_runner(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner,
        lambda x: x.model_executor.driver_worker.model_runner,
    ]
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None:
                return m
        except (AttributeError, IndexError):
            continue
    return None


def _reset_all_writers(inner_model) -> int:
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    n = 0
    for _, sub in inner_model.named_modules():
        impl = getattr(sub, "impl", None)
        if not isinstance(impl, Int4ProtectedAttentionImpl):
            continue
        w = getattr(impl, "_phase5b_paged_writer", None)
        if w is not None and getattr(w, "_allocated", False):
            w.reset_sequence("all")
            n += 1
    return n


def _hbm_snapshot() -> Dict[str, float]:
    import torch
    free, total = torch.cuda.mem_get_info()
    return {
        "allocated_gb":     torch.cuda.memory_allocated()     / (1024**3),
        "reserved_gb":      torch.cuda.memory_reserved()      / (1024**3),
        "max_allocated_gb": torch.cuda.max_memory_allocated() / (1024**3),
        "max_reserved_gb":  torch.cuda.max_memory_reserved()  / (1024**3),
        "free_gb":          free  / (1024**3),
        "total_gb":         total / (1024**3),
        "used_gb":          (total - free) / (1024**3),
    }


def _kv_cache_config(llm) -> Dict[str, Any]:
    """Extract vLLM's KV cache sizing decisions for this engine.

    Returns:
      num_gpu_blocks   : total int4/bf16 cache blocks vLLM allocated.
      block_size       : tokens per block (BS in our writer).
      max_model_len    : max tokens per request (the engine's setting).
      max_concurrency  : num_gpu_blocks * block_size / max_model_len
                         — how many max-len requests can run concurrently.
      kv_cache_dtype   : "int4_protected" or "auto" (bf16).

    Mirrors the "Maximum concurrency for N tokens per request: Y x" log line.
    """
    info: Dict[str, Any] = {
        "num_gpu_blocks":  None,
        "block_size":      None,
        "max_model_len":   None,
        "max_concurrency": None,
        "kv_cache_dtype":  None,
    }
    try:
        engine = llm.llm_engine
        cfg = engine.cache_config
        info["num_gpu_blocks"] = int(getattr(cfg, "num_gpu_blocks", 0) or 0)
        info["block_size"]     = int(getattr(cfg, "block_size", 0) or 0)
        info["kv_cache_dtype"] = str(getattr(cfg, "cache_dtype", "") or "")
        mcfg = getattr(engine, "model_config", None)
        if mcfg is not None:
            mml = getattr(mcfg, "max_model_len", None)
            if mml is not None:
                info["max_model_len"] = int(mml)
        if info["num_gpu_blocks"] and info["block_size"] and info["max_model_len"]:
            info["max_concurrency"] = (
                info["num_gpu_blocks"] * info["block_size"] / info["max_model_len"]
            )
    except (AttributeError, TypeError, ValueError):
        pass
    return info


def _scheduler_stats(llm) -> Dict[str, Any]:
    """Best-effort capture of preemption / swap event counters from
    vLLM's scheduler. The fields exposed differ across vLLM versions;
    we capture what we find and ignore the rest. All zeros if the
    engine doesn't expose these.
    """
    out: Dict[str, Any] = {
        "num_preempted":    0,
        "num_swapped":      0,
        "num_aborted":      0,
        "stats_available":  False,
    }
    try:
        engine = llm.llm_engine
        scheduler = getattr(engine, "scheduler", None)
        if scheduler is None:
            return out
        if isinstance(scheduler, list):
            scheduler = scheduler[0]
        for attr, key in (
            ("num_cumulative_preemption",      "num_preempted"),
            ("preemption_count",               "num_preempted"),
            ("num_swap_out_seqs",              "num_swapped"),
            ("num_aborted_seq_groups",         "num_aborted"),
        ):
            v = getattr(scheduler, attr, None)
            if v is not None:
                try:
                    out[key] = int(v)
                    out["stats_available"] = True
                except (TypeError, ValueError):
                    pass
    except AttributeError:
        pass
    return out


def _bench_one_B(
    llm,
    inner,
    B: int,
    sampling,
    n_runs: int,
    prompt: str,
) -> Dict[str, Any]:
    """Run [prompt]*B through llm.generate, n_runs times, report median.

    inner may be None for the bf16 cell (no writer state to reset).
    """
    import torch
    prompts = [prompt] * B
    times: List[float] = []
    out_lens: List[int] = []
    last_text: Optional[str] = None
    quality_passes: int = 0
    for _ in range(n_runs):
        if inner is not None:
            _reset_all_writers(inner)
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        outs = llm.generate(prompts, sampling)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
        n_out = sum(len(o.outputs[0].token_ids) for o in outs)
        out_lens.append(n_out)
        last_text = outs[0].outputs[0].text
        # Quality sanity: any batch position contains the answer?
        run_pass = any(
            QUALITY_FACT_ANSWER in (o.outputs[0].text or "") for o in outs
        )
        if run_pass:
            quality_passes += 1
    times.sort()
    out_lens.sort()
    median_t   = times[len(times) // 2]
    median_out = out_lens[len(out_lens) // 2]
    return {
        "B":                  B,
        "n_runs":             n_runs,
        "all_wall_s":         times,
        "wall_s":             median_t,
        "all_output_tok":     out_lens,
        "n_output_tokens":    median_out,
        "wall_s_per_seq":     median_t / B if B > 0 else 0.0,
        "agg_tps":            median_out / median_t if median_t > 0 else 0.0,
        "per_seq_tps":        (median_out / median_t / B) if median_t > 0 and B > 0 else 0.0,
        "sample_output":      (last_text or "")[:200],
        "quality_passes":     quality_passes,
        "quality_total_runs": n_runs,
    }


def run_worker(
    cell: str,
    max_model_len: int,
    output_path: Path,
    *,
    model: str,
    max_tokens: int,
    gpu_memory_utilization: float,
    n_runs: int,
    batch_sizes: List[int],
    max_num_seqs: int,
) -> int:
    if cell not in CELLS:
        print(f"FAIL: unknown cell {cell!r}")
        return 1

    if cell == CELL_CAPTURED:
        os.environ["PHASE6E_FUSED_WRITER"] = "1"
        # Auto-bump max active slots for B > 8 (matches throughput bench).
        user_provided = os.environ.get("PHASE6_MAX_ACTIVE_SLOTS")
        if not (user_provided and user_provided.strip()):
            required_slots = max(batch_sizes) * 2
            os.environ["PHASE6_MAX_ACTIVE_SLOTS"] = str(required_slots)

    require_int4 = (cell != CELL_BF16)
    ok, diag = _check_environment(require_int4=require_int4)
    if not ok:
        print(f"FAIL: {diag}")
        return 2

    import torch
    from vllm import SamplingParams

    # Reset peak memory tracking so max_memory_{allocated,reserved}
    # reflects this run only.
    torch.cuda.reset_peak_memory_stats()
    hbm_before_load = _hbm_snapshot()
    print(f"[cell={cell} max_model_len={max_model_len}] "
          f"HBM before load: used={hbm_before_load['used_gb']:.2f} GB / "
          f"{hbm_before_load['total_gb']:.2f} GB total")

    print(f"[cell={cell}] Loading {model} (max_model_len={max_model_len})...")
    t0 = time.time()

    inner = None
    model_runner = None
    hook = None
    writers, impls = [], []

    if cell == CELL_BF16:
        from vllm import LLM
        llm = LLM(
            model=model,
            max_model_len=max_model_len,
            gpu_memory_utilization=gpu_memory_utilization,
            dtype="bfloat16",
            # Bound captured batch shapes to the actual workload.
            # vLLM's default (256) captures many shapes we don't need
            # and the captured-graph intermediate at long context can
            # OOM at high B. The bench only sweeps B<=8, so 16 is
            # plenty.
            max_num_seqs=max_num_seqs,
        )
        torch.cuda.synchronize()
    else:
        import kv_policy.int4_protected   # noqa: F401
        from kv_policy.int4_protected import Int4ProtectedLLM
        from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
        from kv_policy.phase6b2_precapture_hook import (
            install_int4_protected_precapture_hook,
        )
        llm = Int4ProtectedLLM(
            model=model,
            max_model_len=max_model_len,
            gpu_memory_utilization=gpu_memory_utilization,
            max_num_seqs=max_num_seqs,
        )
        torch.cuda.synchronize()

    t_load = time.time() - t0
    hbm_after_init = _hbm_snapshot()
    kv_cfg = _kv_cache_config(llm)
    print(f"[cell={cell}] Loaded in {t_load:.1f}s. "
          f"HBM after init: {hbm_after_init['used_gb']:.2f} GB  "
          f"(peak: {hbm_after_init['max_allocated_gb']:.2f} GB)")
    print(f"[cell={cell}] KV cache: blocks={kv_cfg['num_gpu_blocks']}, "
          f"block_size={kv_cfg['block_size']}, "
          f"max_model_len={kv_cfg['max_model_len']}, "
          f"max_concurrency={kv_cfg['max_concurrency']:.2f}"
          if kv_cfg['max_concurrency'] else
          f"[cell={cell}] KV cache: blocks={kv_cfg['num_gpu_blocks']} (concurrency n/a)")

    # Build the long synthetic prompt. Target ~50% of max_model_len to
    # leave room for the engine's prefill scheduling + output.
    target_prompt_tokens = max_model_len // 2
    prompt = _make_long_prompt(target_prompt_tokens)
    print(f"[cell={cell}] Long prompt: target={target_prompt_tokens} tokens, "
          f"{len(prompt)} chars.")

    print(f"[cell={cell}] Warmup (1 short generate)...")
    llm.generate([prompt], SamplingParams(temperature=0.0, max_tokens=4))

    if cell != CELL_BF16:
        inner = _find_inner_model(llm)
        model_runner = _find_model_runner(llm)
        if inner is None or model_runner is None:
            print(f"FAIL: cannot locate inner model or model_runner")
            return 2
        for _, sub in inner.named_modules():
            impl = getattr(sub, "impl", None)
            if isinstance(impl, Int4ProtectedAttentionImpl):
                impls.append(impl)
                w = getattr(impl, "_phase5b_paged_writer", None)
                if w is not None:
                    writers.append(w)
        print(f"[cell={cell}] Collected {len(writers)} writers + {len(impls)} impls.")
        hook = install_int4_protected_precapture_hook(
            model_runner, writers, impls=impls,
        )
        print(f"[cell={cell}] Hook: enabled={hook.enabled}, target={hook.hook_target_name}")

    sampling = SamplingParams(temperature=0.0, max_tokens=max_tokens)

    # Reset peak again so the per-B bench measures incremental overhead.
    torch.cuda.reset_peak_memory_stats()

    per_b_results: Dict[int, Dict[str, Any]] = {}
    sched_before = _scheduler_stats(llm)
    for B in batch_sizes:
        # Skip B values that exceed the engine's max concurrency for
        # this max_model_len — the request would just block or fail.
        mc = kv_cfg.get("max_concurrency")
        if mc is not None and B > mc:
            per_b_results[B] = {
                "B":               B,
                "skipped_reason":  f"B={B} > max_concurrency={mc:.2f} for "
                                   f"max_model_len={max_model_len}",
                "wall_s":          float("inf"),
                "n_output_tokens": 0,
                "agg_tps":         0.0,
                "per_seq_tps":     0.0,
            }
            print(f"[cell={cell}] B={B}: SKIPPED ({per_b_results[B]['skipped_reason']})")
            continue
        print(f"[cell={cell}] Running B={B} x {n_runs} runs at "
              f"max_model_len={max_model_len}...")
        try:
            r = _bench_one_B(llm, inner, B, sampling, n_runs=n_runs, prompt=prompt)
            per_b_results[B] = r
            print(f"[cell={cell}] B={B}: median wall {r['wall_s']:.3f}s  "
                  f"out_tok={r['n_output_tokens']}  "
                  f"agg_tps={r['agg_tps']:.1f}  per_seq_tps={r['per_seq_tps']:.1f}  "
                  f"quality={r['quality_passes']}/{r['quality_total_runs']}")
        except torch.cuda.OutOfMemoryError as exc:
            per_b_results[B] = {
                "B":               B,
                "n_runs":          0,
                "wall_s":          float("inf"),
                "n_output_tokens": 0,
                "wall_s_per_seq":  float("inf"),
                "agg_tps":         0.0,
                "per_seq_tps":     0.0,
                "sample_output":   "",
                "oom_error":       str(exc)[:200],
            }
            print(f"[cell={cell}] B={B}: OOM ({str(exc)[:100]})")
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
        except Exception as exc:  # noqa: BLE001
            per_b_results[B] = {
                "B":               B,
                "n_runs":          0,
                "wall_s":          float("inf"),
                "n_output_tokens": 0,
                "wall_s_per_seq":  float("inf"),
                "agg_tps":         0.0,
                "per_seq_tps":     0.0,
                "sample_output":   "",
                "error":           f"{type(exc).__name__}: {str(exc)[:200]}",
            }
            print(f"[cell={cell}] B={B}: ERROR {type(exc).__name__}: {str(exc)[:120]}")

    sched_after = _scheduler_stats(llm)
    hbm_peak_during_sweep = _hbm_snapshot()

    payload: Dict[str, Any] = {
        "cell":                       cell,
        "model":                      model,
        "max_model_len":              max_model_len,
        "max_tokens":                 max_tokens,
        "gpu_memory_utilization":     gpu_memory_utilization,
        "load_seconds":               t_load,
        "batch_sizes":                batch_sizes,
        "n_runs_per_B":               n_runs,
        "prompt_char_len":            len(prompt),
        "target_prompt_tokens":       target_prompt_tokens,
        "hook_enabled":               hook.enabled if hook else False,
        "hook_target_name":           hook.hook_target_name if hook else "n/a (bf16)",
        "hook_total_stash_calls":     hook.stash_call_count if hook else 0,
        "hbm_before_load":            hbm_before_load,
        "hbm_after_init":             hbm_after_init,
        "hbm_peak_during_sweep":      hbm_peak_during_sweep,
        "capture_overhead_gb":        hbm_after_init["used_gb"] - hbm_before_load["used_gb"],
        "kv_cache_config":            kv_cfg,
        "scheduler_before_sweep":     sched_before,
        "scheduler_after_sweep":      sched_after,
        "preemption_events":          (
            sched_after.get("num_preempted", 0) - sched_before.get("num_preempted", 0)
        ),
        "swap_events": (
            sched_after.get("num_swapped", 0) - sched_before.get("num_swapped", 0)
        ),
        "per_b": per_b_results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    print(f"[cell={cell}] Wrote {output_path}")
    if hook is not None:
        hook.teardown()
    return 0


def compare(cells: Dict[Tuple[str, int], Path],
            max_model_lens: List[int],
            batch_sizes: List[int],
            report_json: Path,
            report_txt: Path) -> int:
    """Read every per-(cell, max_model_len) JSON, assemble the
    crossover table, write the report, return non-zero if the
    int4 path NEVER wins HBM at any max_model_len.

    cells: dict mapping (cell, max_model_len) -> path to its JSON.
    """
    loaded: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for k, p in cells.items():
        if p.exists():
            loaded[k] = json.loads(p.read_text())

    # Per (max_model_len) HBM comparison: int4 captured vs bf16.
    crossover_rows: List[Dict[str, Any]] = []
    int4_wins_count = 0
    for mml in max_model_lens:
        bf16 = loaded.get((CELL_BF16, mml))
        cap  = loaded.get((CELL_CAPTURED, mml))
        if bf16 is None or cap is None:
            crossover_rows.append({
                "max_model_len":     mml,
                "bf16_hbm_gb":       None,
                "captured_hbm_gb":   None,
                "delta_int4_minus_bf16_gb": None,
                "int4_wins_hbm":     None,
                "note":              "missing cell JSON",
            })
            continue
        bf16_hbm = bf16["hbm_after_init"]["used_gb"]
        cap_hbm  = cap ["hbm_after_init"]["used_gb"]
        delta    = cap_hbm - bf16_hbm  # negative = int4 cheaper
        bf16_conc = bf16["kv_cache_config"].get("max_concurrency")
        cap_conc  = cap ["kv_cache_config"].get("max_concurrency")
        wins = (delta < 0.0)
        if wins:
            int4_wins_count += 1
        crossover_rows.append({
            "max_model_len":            mml,
            "bf16_hbm_gb":              bf16_hbm,
            "captured_hbm_gb":          cap_hbm,
            "delta_int4_minus_bf16_gb": delta,
            "int4_wins_hbm":            wins,
            "bf16_max_concurrency":     bf16_conc,
            "captured_max_concurrency": cap_conc,
            "bf16_num_blocks":          bf16["kv_cache_config"].get("num_gpu_blocks"),
            "captured_num_blocks":      cap ["kv_cache_config"].get("num_gpu_blocks"),
            "bf16_preemption_events":   bf16.get("preemption_events", 0),
            "captured_preemption_events": cap.get("preemption_events", 0),
        })

    # Per (max_model_len, B) throughput comparison + quality.
    perf_rows: List[Dict[str, Any]] = []
    for mml in max_model_lens:
        for B in batch_sizes:
            bf16 = loaded.get((CELL_BF16, mml))
            cap  = loaded.get((CELL_CAPTURED, mml))
            if bf16 is None or cap is None:
                continue
            bb = bf16["per_b"].get(str(B)) or bf16["per_b"].get(B)
            cb = cap ["per_b"].get(str(B)) or cap ["per_b"].get(B)
            if bb is None or cb is None:
                continue
            b_tps = bb.get("agg_tps", 0.0)
            c_tps = cb.get("agg_tps", 0.0)
            ratio = (c_tps / b_tps) if (b_tps > 0 and c_tps > 0) else None
            perf_rows.append({
                "max_model_len":         mml,
                "B":                     B,
                "bf16_agg_tps":          b_tps if b_tps > 0 else None,
                "captured_agg_tps":      c_tps if c_tps > 0 else None,
                "captured_over_bf16_x":  ratio,
                "bf16_quality_pass_rate":     bb.get("quality_passes", 0) / max(1, bb.get("quality_total_runs", 1)),
                "captured_quality_pass_rate": cb.get("quality_passes", 0) / max(1, cb.get("quality_total_runs", 1)),
                "bf16_oom":              bb.get("oom_error") or bb.get("error"),
                "captured_oom":          cb.get("oom_error") or cb.get("error"),
                "bf16_skipped":          bb.get("skipped_reason"),
                "captured_skipped":      cb.get("skipped_reason"),
            })

    # Verdict.
    # Decision tree from the spec:
    #   - int4 wins HBM at long context AND quality intact at that point
    #     -> Phase 6F kernel optimization is JUSTIFIED.
    #   - int4 never wins HBM -> NOT_JUSTIFIED. Skip 6F kernel work.
    #   - int4 wins HBM but stays slow -> NOT_THROUGHPUT_ACCELERATOR
    #     (frame as quality/memory backend, not throughput).
    int4_wins_any = (int4_wins_count > 0)
    # Quality at the first max_model_len where int4 wins HBM:
    quality_intact_at_crossover = True
    crossover_mml: Optional[int] = None
    for row in crossover_rows:
        if row.get("int4_wins_hbm") is True:
            crossover_mml = row["max_model_len"]
            # Look up the captured cell's quality at B=1 (the most
            # forgiving B; if even B=1 fails, quality has degraded).
            cap_at_mml = loaded.get((CELL_CAPTURED, crossover_mml))
            if cap_at_mml is not None:
                cb1 = cap_at_mml["per_b"].get("1") or cap_at_mml["per_b"].get(1)
                if cb1 is not None:
                    passes = cb1.get("quality_passes", 0)
                    total  = cb1.get("quality_total_runs", 1)
                    quality_intact_at_crossover = (
                        total > 0 and passes / total >= 0.5
                    )
            break

    # Throughput at the largest max_model_len where int4 wins HBM:
    # 0.5x of bf16 is the threshold for "stays slow"; below that we
    # frame as memory-backend-only.
    throughput_competitive = True
    if crossover_mml is not None:
        cap_at = loaded.get((CELL_CAPTURED, crossover_mml))
        bf_at  = loaded.get((CELL_BF16,     crossover_mml))
        if cap_at and bf_at:
            cb8 = cap_at["per_b"].get("8") or cap_at["per_b"].get(8)
            bb8 = bf_at ["per_b"].get("8") or bf_at ["per_b"].get(8)
            if cb8 and bb8 and bb8.get("agg_tps", 0) > 0:
                ratio = cb8.get("agg_tps", 0) / bb8["agg_tps"]
                throughput_competitive = (ratio >= 0.5)

    if not int4_wins_any:
        verdict = "NOT_JUSTIFIED"
        verdict_note = (
            "int4_protected captured does NOT beat stock bf16 on HBM at "
            "any tested max_model_len. Do not pursue heavy kernel work "
            "(Phase 6F) yet — the protect-mask design hasn't demonstrated "
            "a memory advantage to motivate the additional engineering cost."
        )
    elif not quality_intact_at_crossover:
        verdict = "QUALITY_DEGRADED"
        verdict_note = (
            f"int4_protected wins HBM at max_model_len={crossover_mml}, "
            f"but the quality sanity check fails at that context length. "
            f"Investigate the quality regression before claiming the memory win."
        )
    elif not throughput_competitive:
        verdict = "NOT_THROUGHPUT_ACCELERATOR"
        verdict_note = (
            f"int4_protected wins HBM starting at max_model_len="
            f"{crossover_mml} with quality intact, but throughput at that "
            f"length is below 0.5x of stock bf16. Frame Phase 6 narrative "
            f"as a long-context QUALITY + MEMORY backend, NOT a throughput "
            f"accelerator. Phase 6F kernel surgery still justifiable to "
            f"close the throughput gap, but the protect-mask story stands "
            f"on its memory advantage alone."
        )
    else:
        verdict = "JUSTIFIED"
        verdict_note = (
            f"int4_protected wins HBM at max_model_len={crossover_mml} "
            f"with quality intact AND throughput within 0.5x of stock bf16. "
            f"Phase 6F kernel optimization is JUSTIFIED — the protect-mask "
            f"design has a clear long-context memory advantage and the "
            f"remaining throughput gap is small enough that kernel work "
            f"could close it."
        )

    report = {
        "verdict":            verdict,
        "verdict_note":       verdict_note,
        "model":              next(iter(loaded.values()))["model"] if loaded else None,
        "max_model_lens":     max_model_lens,
        "batch_sizes":        batch_sizes,
        "n_runs_per_B":       next(iter(loaded.values()))["n_runs_per_B"] if loaded else None,
        "int4_wins_count":    int4_wins_count,
        "crossover_mml":      crossover_mml,
        "crossover_rows":     crossover_rows,
        "perf_rows":          perf_rows,
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, indent=2))

    # Pretty-print.
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("Phase 6 long-context HBM crossover bench")
    lines.append("=" * 80)
    lines.append(f"Model: {report['model']}    "
                 f"max_model_lens={report['max_model_lens']}    "
                 f"B={report['batch_sizes']}    n_runs/B={report['n_runs_per_B']}")
    lines.append("")
    lines.append(f"Verdict: {report['verdict']}")
    lines.append("")
    for line in (report['verdict_note'] or "").splitlines() or [""]:
        lines.append(f"  {line}")
    lines.append("")
    lines.append("HBM crossover (after init, with KV cache allocated):")
    lines.append(f"  {'max_model_len':>13} | {'bf16 (GB)':>10} | {'int4 (GB)':>10} | "
                 f"{'delta':>8} | {'bf16 conc':>10} | {'int4 conc':>10} | int4 wins?")
    lines.append("  " + "-" * 100)
    for row in crossover_rows:
        d = row.get("delta_int4_minus_bf16_gb")
        d_str = f"{d:+.2f} GB" if d is not None else "  n/a"
        bf = row.get("bf16_hbm_gb")
        cp = row.get("captured_hbm_gb")
        bc = row.get("bf16_max_concurrency")
        cc = row.get("captured_max_concurrency")
        bf_str = f"{bf:>10.2f}" if bf is not None else "      n/a "
        cp_str = f"{cp:>10.2f}" if cp is not None else "      n/a "
        bc_str = f"{bc:>10.1f}" if bc is not None else "       n/a"
        cc_str = f"{cc:>10.1f}" if cc is not None else "       n/a"
        wins = row.get("int4_wins_hbm")
        wins_str = ("YES" if wins is True else
                    ("no" if wins is False else "n/a"))
        lines.append(
            f"  {row['max_model_len']:>13} | {bf_str} | {cp_str} | "
            f"{d_str:>8} | {bc_str} | {cc_str} |   {wins_str}"
        )
    lines.append("")
    lines.append("Throughput (median agg_tps; OOM/skip shown as '---'):")
    lines.append(f"  {'mml':>6} | {'B':>3} | {'bf16':>8} | {'captured':>9} | "
                 f"{'cap/bf16':>9} | {'cap quality':>11} | {'bf16 quality':>12} | note")
    lines.append("  " + "-" * 100)
    def _tps(v):
        return f"{v:>8.1f}" if v is not None and v > 0 else "    --- "
    def _x(v):
        return f"{v:>8.2f}x" if v is not None and v > 0 else "    --- "
    def _q(v):
        return f"{v*100:>7.0f}%" if v is not None else "   n/a "
    for r in perf_rows:
        note = (r.get("captured_oom") or r.get("bf16_oom")
                or r.get("captured_skipped") or r.get("bf16_skipped") or "")
        if note and len(note) > 30:
            note = note[:30] + "..."
        lines.append(
            f"  {r['max_model_len']:>6} | {r['B']:>3} | "
            f"{_tps(r.get('bf16_agg_tps'))} | "
            f"{_tps(r.get('captured_agg_tps'))}  | "
            f"{_x(r.get('captured_over_bf16_x'))} | "
            f"{_q(r.get('captured_quality_pass_rate')):>11} | "
            f"{_q(r.get('bf16_quality_pass_rate')):>12} | "
            f"{note}"
        )
    lines.append("")
    # Preemption summary.
    any_preempt = any(
        (r.get("bf16_preemption_events") or 0) > 0
        or (r.get("captured_preemption_events") or 0) > 0
        for r in crossover_rows
    )
    if any_preempt:
        lines.append("Preemption events fired during the sweep:")
        for r in crossover_rows:
            be = r.get("bf16_preemption_events") or 0
            ce = r.get("captured_preemption_events") or 0
            if be > 0 or ce > 0:
                lines.append(
                    f"  max_model_len={r['max_model_len']}: "
                    f"bf16={be} captured={ce}"
                )
    else:
        lines.append("No preemption events fired during the sweep.")
    lines.append("")
    lines.append(f"Verdict: {report['verdict']}")
    report_txt.parent.mkdir(parents=True, exist_ok=True)
    report_txt.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    # Verdict exit code:
    #   JUSTIFIED -> 0 (proceed with 6F)
    #   NOT_JUSTIFIED -> 1 (halt 6F)
    #   QUALITY_DEGRADED / NOT_THROUGHPUT_ACCELERATOR -> 0 but partial
    return 0 if verdict == "JUSTIFIED" else (
        1 if verdict == "NOT_JUSTIFIED" else 0
    )


def main() -> int:
    p = argparse.ArgumentParser()
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--worker", action="store_true",
                     help="Internal: run a single (cell, max_model_len) worker.")
    p.add_argument("--cell", choices=CELLS,
                   help="Worker mode: which cell to run.")
    p.add_argument("--output", type=str,
                   help="Worker mode: JSON output path for this cell+mml.")
    p.add_argument("--output-dir", type=str,
                   default="bench_out/phase6_long_context",
                   help="Driver mode: directory for per-cell JSONs + report.")
    p.add_argument("--cells", default=",".join(CELLS),
                   help="Driver mode: comma-separated cells to run. "
                        "Default 'bf16,captured'.")
    p.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--max-model-lens", default=",".join(str(x) for x in DEFAULT_MAX_MODEL_LENS),
                   help="Comma-separated list, e.g. '8192,16384,32768'.")
    p.add_argument("--max-model-len", type=int, default=None,
                   help="Worker mode: single value of max_model_len for this run.")
    p.add_argument("--batch-sizes", default=",".join(str(x) for x in DEFAULT_BATCH_SIZES),
                   help="Comma-separated, e.g. '1,2,4,8'.")
    p.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    p.add_argument("--gpu-memory-utilization", type=float, default=0.5,
                   help="vLLM's KV cache budget = total HBM * this. "
                        "Default 0.5 matches the throughput bench's "
                        "proven-safe value; 0.85 OOMs during graph "
                        "capture at long max_model_len because the "
                        "int4 read path materializes a large gather "
                        "intermediate at captured shapes.")
    p.add_argument("--max-num-seqs", type=int, default=16,
                   help="Bounds vLLM's captured batch shapes. The "
                        "long-context bench only sweeps B<=8; setting "
                        "max_num_seqs=16 (2x headroom) avoids capturing "
                        "huge shapes whose gather intermediates OOM at "
                        "long max_model_len.")
    p.add_argument("--n-runs", type=int, default=DEFAULT_N_RUNS)
    args = p.parse_args()

    if args.worker:
        if not args.cell or not args.output or args.max_model_len is None:
            print("FAIL: --worker requires --cell, --output, --max-model-len.")
            return 2
        batch_sizes = [int(x) for x in args.batch_sizes.split(",") if x.strip()]
        return run_worker(
            cell=args.cell,
            max_model_len=args.max_model_len,
            output_path=Path(args.output),
            model=args.model,
            max_tokens=args.max_tokens,
            gpu_memory_utilization=args.gpu_memory_utilization,
            n_runs=args.n_runs,
            batch_sizes=batch_sizes,
            max_num_seqs=args.max_num_seqs,
        )

    cells_to_run = [c.strip() for c in args.cells.split(",") if c.strip()]
    for c in cells_to_run:
        if c not in CELLS:
            print(f"FAIL: unknown cell {c!r} in --cells (valid: {CELLS})")
            return 2
    max_model_lens = [int(x) for x in args.max_model_lens.split(",") if x.strip()]
    batch_sizes    = [int(x) for x in args.batch_sizes.split(",") if x.strip()]

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cell_paths: Dict[Tuple[str, int], Path] = {}
    for c in cells_to_run:
        for mml in max_model_lens:
            cell_paths[(c, mml)] = out_dir / f"cell_{c}_mml{mml}.json"

    ok, diag = _check_environment(require_int4=(CELL_CAPTURED in cells_to_run))
    if not ok:
        print(f"FAIL: environment check: {diag}")
        return 2

    common_args = [
        "--worker",
        "--model", args.model,
        "--max-tokens", str(args.max_tokens),
        "--gpu-memory-utilization", str(args.gpu_memory_utilization),
        "--max-num-seqs", str(args.max_num_seqs),
        "--n-runs", str(args.n_runs),
        "--batch-sizes", ",".join(str(x) for x in batch_sizes),
    ]
    # Run in (mml, cell) order rather than (cell, mml) so each cell's
    # results land grouped by max_model_len in the output dir — easier
    # to spot mid-run if int4 is winning or losing HBM at the cheap end.
    for mml in max_model_lens:
        for cell in cells_to_run:
            out_path = cell_paths[(cell, mml)]
            print()
            print(f"=== Driver: cell={cell}  max_model_len={mml} ===")
            cmd = [sys.executable, __file__] + common_args + [
                "--cell", cell,
                "--max-model-len", str(mml),
                "--output", str(out_path),
            ]
            ret = subprocess.run(cmd, check=False)
            if ret.returncode != 0:
                print(f"FAIL: worker cell={cell} mml={mml} exited code {ret.returncode}")
                # Don't bail entirely — write whatever we have so far.
                # Subsequent mml's might still produce useful data.

    return compare(
        cells=cell_paths,
        max_model_lens=max_model_lens,
        batch_sizes=batch_sizes,
        report_json=out_dir / "long_context_report.json",
        report_txt=out_dir / "long_context_report.txt",
    )


if __name__ == "__main__":
    sys.exit(main())
