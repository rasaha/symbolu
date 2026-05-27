"""Phase 6B.2 — GPU smoke for the pre-capture seq_id resolution hook.

Confirms the hook-on path produces byte-identical generated tokens
vs the hook-off path on a real Qwen-2.5-7B-Instruct + vLLM 0.7.3 +
forked vllm-flash-attn pod. Mirrors bench_phase6_b_pre5_gpu_smoke.py
exactly; only the bisection primitive differs:

  cell hook-off : PHASE6B2_INSTALL_HOOK=0; the install layer is
                  inert; dispatch fork falls back to 6B.1 self-resolve.
                  Equivalent to 6B.1's refactored behavior.
  cell hook-on  : PHASE6B2_INSTALL_HOOK=1 (default); the install
                  wraps model_runner.execute_model. The dispatch
                  fork reads the stashed slot_idx_t; write_decode_
                  batched runs with pre_synced=True.

Usage on the GPU pod:

  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/bench_phase6_b2_hook_gpu_smoke.py \\
      --output-dir /workspace/symbolu/bench_out/phase6b2_gpu_smoke

  # Manual cell-at-a-time:
  python3 bench_phase6_b2_hook_gpu_smoke.py --worker --cell hook-off  --output cell_hook_off.json
  python3 bench_phase6_b2_hook_gpu_smoke.py --worker --cell hook-on   --output cell_hook_on.json
  python3 bench_phase6_b2_hook_gpu_smoke.py --compare cell_hook_off.json cell_hook_on.json

Cell shape (~$0.05 total):
  * Model: Qwen/Qwen2.5-7B-Instruct
  * max_model_len: 4096; gpu_memory_utilization: 0.5
  * max_tokens: 32 greedy decode (temperature=0)
  * B=2 distinct prompts (Greendell needle + short translation)
  * enforce_eager=True (capture is 6B.3's job)

Acceptance gate (Phase 6B.2 G_HOOK GPU portion):
  1. completion_token_ids byte-equal across both cells for every prompt.
  2. hook-on cell: write_decode_batched_via_hook_calls > 0.
  3. hook-off cell: write_decode_batched_via_hook_calls == 0
     (dispatch fork self-resolved).
  4. write_decode_batched_calls > 0 on both cells (both used the new path).
  5. Zero fallbacks in both cells.

Exit codes:
  0 — GREEN; G_HOOK passes
  1 — RED; at least one check failed
  2 — environment error
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROMPTS = [
    (
        "Below is a paragraph about a small fictional town. After it, "
        "answer the question concisely.\n\n"
        "Greendell is nestled between two rivers and has a population "
        "of just over four thousand. Its main industries are pottery, "
        "honey production, and the seasonal wool trade. The annual "
        "harvest festival in early autumn draws visitors from across "
        "the region. The oldest building in town is a stone library "
        "founded in 1742.\n\n"
        "Question: What year was the oldest building in Greendell "
        "founded?\nAnswer:"
    ),
    (
        "Translate to French and explain briefly:\n"
        "English: The quick brown fox jumps over the lazy dog.\n"
        "French:"
    ),
]


CELL_HOOK_OFF = "hook-off"
CELL_HOOK_ON  = "hook-on"


def _check_environment() -> tuple[bool, str]:
    try:
        import torch
    except ImportError as e:
        return False, f"torch import failed: {e}"
    if not torch.cuda.is_available():
        return False, "torch.cuda.is_available() == False; need GPU pod"
    try:
        from vllm import SamplingParams  # noqa: F401
    except ImportError as e:
        return False, f"vllm import failed: {e}"
    try:
        from kv_policy.int4_protected import Int4ProtectedLLM  # noqa: F401
        from kv_policy.phase6b2_precapture_hook import (  # noqa: F401
            install_int4_protected_precapture_hook,
        )
    except ImportError as e:
        return False, f"kv_policy import failed: {e}"
    return True, "ok"


def _find_inner_model(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
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
    ]
    for fn in candidates:
        try:
            mr = fn(llm)
            if mr is not None and hasattr(mr, "execute_model"):
                return mr
        except (AttributeError, IndexError):
            continue
    return None


def run_worker(cell: str, output_path: Path, *, model: str,
               max_model_len: int, max_tokens: int,
               gpu_memory_utilization: float) -> int:
    if cell not in (CELL_HOOK_OFF, CELL_HOOK_ON):
        print(f"FAIL: unknown cell {cell!r}")
        return 1
    # Env override BEFORE vllm import. The hook reads
    # PHASE6B2_INSTALL_HOOK at install time.
    if cell == CELL_HOOK_OFF:
        os.environ["PHASE6B2_INSTALL_HOOK"] = "0"
    else:
        os.environ["PHASE6B2_INSTALL_HOOK"] = "1"

    ok, diag = _check_environment()
    if not ok:
        print(f"FAIL: {diag}")
        return 2

    import torch
    from vllm import SamplingParams
    import kv_policy.int4_protected
    from kv_policy.int4_protected import Int4ProtectedLLM
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    from kv_policy.phase6b2_precapture_hook import (
        install_int4_protected_precapture_hook,
    )

    print(f"[cell={cell}] Loading {model}...")
    t0 = time.time()
    llm = Int4ProtectedLLM(
        model=model,
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
        enforce_eager=True,
    )
    t_load = time.time() - t0
    print(f"[cell={cell}] Loaded in {t_load:.1f}s.")

    # Warmup once so writers are constructed.
    print(f"[cell={cell}] Warmup...")
    llm.generate(["Hello."], SamplingParams(temperature=0.0, max_tokens=4))

    # Install hook (post-warmup so writers exist). When PHASE6B2_
    # INSTALL_HOOK=0 the install returns inert; hook-off cell stays
    # on 6B.1 self-resolve.
    inner = _find_inner_model(llm)
    model_runner = _find_model_runner(llm)
    if inner is None or model_runner is None:
        print(f"FAIL: cannot locate inner model or model_runner")
        return 2

    # Collect writers from the warmed-up model.
    writers = []
    for _, sub in inner.named_modules():
        impl = getattr(sub, "impl", None)
        if isinstance(impl, Int4ProtectedAttentionImpl):
            w = getattr(impl, "_phase5b_paged_writer", None)
            if w is not None:
                writers.append(w)
    print(f"[cell={cell}] Collected {len(writers)} writers from model.")

    hook = install_int4_protected_precapture_hook(model_runner, writers)
    print(f"[cell={cell}] Hook handle: enabled={hook.enabled}, "
          f"target={hook.hook_target_name}")

    # Reset call stats AFTER warmup + hook install.
    Int4ProtectedAttentionImpl.reset_call_stats()

    print(f"[cell={cell}] Generating B={len(PROMPTS)} prompts, max_tokens={max_tokens}...")
    t0 = time.time()
    outputs = llm.generate(
        PROMPTS,
        SamplingParams(temperature=0.0, max_tokens=max_tokens),
    )
    torch.cuda.synchronize()
    t_gen = time.time() - t0

    call_stats = Int4ProtectedAttentionImpl.get_call_stats()
    print(f"[cell={cell}] Generated in {t_gen:.2f}s.  call_stats={call_stats}")
    print(f"[cell={cell}] Hook stats: stash_call_count={hook.stash_call_count}, "
          f"skipped_step_count={hook.skipped_step_count}")

    per_prompt = []
    for i, out in enumerate(outputs):
        c0 = out.outputs[0]
        per_prompt.append({
            "prompt_idx":      i,
            "prompt_preview":  PROMPTS[i][:60],
            "prompt_token_ids": list(out.prompt_token_ids or []),
            "completion_text": c0.text,
            "completion_token_ids": list(c0.token_ids),
        })

    payload = {
        "cell":                            cell,
        "model":                           model,
        "max_model_len":                   max_model_len,
        "gpu_memory_utilization":          gpu_memory_utilization,
        "max_tokens":                      max_tokens,
        "n_prompts":                       len(PROMPTS),
        "call_stats":                      call_stats,
        "hook_enabled":                    hook.enabled,
        "hook_target_name":                hook.hook_target_name,
        "hook_stash_call_count":           hook.stash_call_count,
        "hook_skipped_step_count":         hook.skipped_step_count,
        "load_seconds":                    t_load,
        "generate_seconds":                t_gen,
        "per_prompt":                      per_prompt,
        "phase6b2_install_hook_env":       os.environ.get("PHASE6B2_INSTALL_HOOK"),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    print(f"[cell={cell}] Wrote {output_path}")

    # Teardown the hook before exit (good hygiene; subprocess will
    # destroy the engine anyway).
    hook.teardown()
    return 0


def compare(hook_off_path: Path, hook_on_path: Path,
            report_json: Path, report_txt: Path) -> int:
    hook_off = json.loads(hook_off_path.read_text())
    hook_on  = json.loads(hook_on_path.read_text())

    checks: list[tuple[str, bool, str]] = []
    # Check 1: completion_token_ids byte-equal across both cells.
    n_prompts = len(hook_off["per_prompt"])
    if n_prompts != len(hook_on["per_prompt"]):
        checks.append(("n_prompts_match", False,
                       f"hook-off={n_prompts}, hook-on={len(hook_on['per_prompt'])}"))
    else:
        any_diverge = False
        diverge_details = []
        for i in range(n_prompts):
            lt = hook_off["per_prompt"][i]["completion_token_ids"]
            rt = hook_on ["per_prompt"][i]["completion_token_ids"]
            if lt == rt:
                continue
            any_diverge = True
            common = 0
            for j in range(min(len(lt), len(rt))):
                if lt[j] != rt[j]:
                    break
                common += 1
            diverge_details.append(
                f"prompt[{i}]: diverges at token {common}/{min(len(lt), len(rt))}; "
                f"off={lt[common:common+5]} on={rt[common:common+5]}"
            )
        checks.append((
            "completion_token_ids_byte_equal",
            not any_diverge,
            "all prompts byte-equal" if not any_diverge else "; ".join(diverge_details),
        ))

    # Check 2: hook-on cell used the hook stash.
    on_via_hook = hook_on["call_stats"].get("write_decode_batched_via_hook_calls", 0)
    checks.append((
        "hook_on_cell_used_hook_path",
        on_via_hook > 0,
        f"write_decode_batched_via_hook_calls={on_via_hook}",
    ))

    # Check 3: hook-off cell self-resolved (zero hook calls).
    off_via_hook = hook_off["call_stats"].get("write_decode_batched_via_hook_calls", 0)
    checks.append((
        "hook_off_cell_self_resolved",
        off_via_hook == 0,
        f"write_decode_batched_via_hook_calls={off_via_hook}",
    ))

    # Check 4: both cells fired write_decode_batched (the new path).
    off_batched = hook_off["call_stats"].get("write_decode_batched_calls", 0)
    on_batched  = hook_on ["call_stats"].get("write_decode_batched_calls", 0)
    checks.append((
        "both_cells_used_write_decode_batched",
        off_batched > 0 and on_batched > 0,
        f"hook-off={off_batched}, hook-on={on_batched}",
    ))

    # Check 5: zero fallbacks both cells.
    for cell_name, stats in (("hook-off", hook_off["call_stats"]),
                              ("hook-on",  hook_on["call_stats"])):
        wfb = stats.get("write_path_fallback", 0)
        dfb = stats.get("decode_calls_fallback", 0)
        checks.append((
            f"{cell_name}_zero_fallbacks",
            wfb == 0 and dfb == 0,
            f"write_path_fallback={wfb}, decode_calls_fallback={dfb}",
        ))

    # Check 6: hook handle reports a non-zero stash_call_count on
    # the hook-on cell (i.e., the wrap actually fired).
    on_stash_calls = hook_on.get("hook_stash_call_count", 0)
    checks.append((
        "hook_on_stash_call_count_positive",
        on_stash_calls > 0,
        f"stash_call_count={on_stash_calls}",
    ))

    overall_ok = all(ok for _, ok, _ in checks)
    report = {
        "verdict":            "GREEN" if overall_ok else "RED",
        "hook_off_cell":      str(hook_off_path),
        "hook_on_cell":       str(hook_on_path),
        "model":              hook_off.get("model"),
        "n_prompts":          hook_off.get("n_prompts"),
        "max_tokens":         hook_off.get("max_tokens"),
        "checks": [
            {"name": name, "passed": ok, "detail": detail}
            for name, ok, detail in checks
        ],
        "hook_off_call_stats": hook_off["call_stats"],
        "hook_on_call_stats":  hook_on["call_stats"],
        "hook_on_handle":      {
            "enabled":            hook_on.get("hook_enabled"),
            "hook_target_name":   hook_on.get("hook_target_name"),
            "stash_call_count":   hook_on.get("hook_stash_call_count"),
            "skipped_step_count": hook_on.get("hook_skipped_step_count"),
        },
        "hook_off_handle":     {
            "enabled":            hook_off.get("hook_enabled"),
            "hook_target_name":   hook_off.get("hook_target_name"),
        },
        "per_prompt_diffs":    [],
    }
    for i in range(min(len(hook_off["per_prompt"]), len(hook_on["per_prompt"]))):
        offp = hook_off["per_prompt"][i]
        onp  = hook_on ["per_prompt"][i]
        report["per_prompt_diffs"].append({
            "prompt_idx":           i,
            "prompt_preview":       offp["prompt_preview"],
            "hook_off_text":        offp["completion_text"],
            "hook_on_text":         onp["completion_text"],
            "tokens_byte_equal":    offp["completion_token_ids"] == onp["completion_token_ids"],
        })

    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, indent=2))

    lines = []
    lines.append("=" * 78)
    lines.append("Phase 6B.2 GPU smoke — hook-on vs hook-off comparison")
    lines.append("=" * 78)
    lines.append(f"Model:      {report['model']}")
    lines.append(f"Prompts:    {report['n_prompts']}    max_tokens: {report['max_tokens']}")
    lines.append(f"Verdict:    {report['verdict']}")
    lines.append("")
    lines.append("Checks:")
    for c in report["checks"]:
        mark = "PASS" if c["passed"] else "FAIL"
        lines.append(f"  [{mark}] {c['name']:<44s} {c['detail']}")
    lines.append("")
    lines.append("Call stats:")
    lines.append(f"  hook-off:  {json.dumps(report['hook_off_call_stats'], sort_keys=True)}")
    lines.append(f"  hook-on:   {json.dumps(report['hook_on_call_stats'],  sort_keys=True)}")
    lines.append("")
    lines.append("Hook handle (hook-on cell):")
    h_on = report["hook_on_handle"]
    lines.append(f"  enabled={h_on['enabled']}, target={h_on['hook_target_name']}, "
                 f"stash_calls={h_on['stash_call_count']}, skipped={h_on['skipped_step_count']}")
    lines.append("")
    lines.append("Per-prompt diffs:")
    for d in report["per_prompt_diffs"]:
        lines.append(f"  prompt[{d['prompt_idx']}] preview: {d['prompt_preview']!r}")
        lines.append(f"    tokens_byte_equal:  {d['tokens_byte_equal']}")
        if not d["tokens_byte_equal"]:
            lines.append(f"    hook_off_text:      {d['hook_off_text']!r}")
            lines.append(f"    hook_on_text:       {d['hook_on_text']!r}")
    lines.append("")
    if overall_ok:
        lines.append("Phase 6B.2 GPU smoke: GREEN")
        lines.append("  Hook-driven slot_idx resolution produces byte-identical")
        lines.append("  generated tokens vs the dispatch-fork's 6B.1 self-resolve")
        lines.append(f"  path on {report['model']} at B={report['n_prompts']}.")
    else:
        lines.append("Phase 6B.2 GPU smoke: RED")
        lines.append("  At least one check failed. See per-check detail above.")
    report_txt.parent.mkdir(parents=True, exist_ok=True)
    report_txt.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if overall_ok else 1


def main() -> int:
    p = argparse.ArgumentParser()
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--worker", action="store_true",
                     help="Run as a single-cell worker (internal).")
    grp.add_argument("--compare", nargs=2, metavar=("HOOK_OFF", "HOOK_ON"),
                     help="Compare two existing cell JSONs and emit a report.")
    p.add_argument("--cell", choices=[CELL_HOOK_OFF, CELL_HOOK_ON],
                   help="Worker mode: which cell to run.")
    p.add_argument("--output", type=str,
                   help="Worker mode: JSON output path for this cell's results.")
    p.add_argument("--output-dir", type=str,
                   default="bench_out/phase6b2_gpu_smoke",
                   help="Driver mode: directory for both cells + report.")
    p.add_argument("--model",          default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--max-model-len",  type=int,   default=4096)
    p.add_argument("--max-tokens",     type=int,   default=32)
    p.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    args = p.parse_args()

    if args.worker:
        if not args.cell or not args.output:
            print("FAIL: --worker requires --cell and --output.")
            return 2
        return run_worker(
            cell=args.cell, output_path=Path(args.output),
            model=args.model, max_model_len=args.max_model_len,
            max_tokens=args.max_tokens,
            gpu_memory_utilization=args.gpu_memory_utilization,
        )

    if args.compare:
        return compare(
            hook_off_path=Path(args.compare[0]),
            hook_on_path=Path(args.compare[1]),
            report_json=Path(args.compare[0]).parent / "smoke_report.json",
            report_txt=Path(args.compare[0]).parent / "smoke_report.txt",
        )

    # Driver mode: spawn two workers as subprocesses.
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    hook_off_json = out_dir / "cell_hook_off.json"
    hook_on_json  = out_dir / "cell_hook_on.json"
    report_json   = out_dir / "smoke_report.json"
    report_txt    = out_dir / "smoke_report.txt"

    ok, diag = _check_environment()
    if not ok:
        print(f"FAIL: environment check: {diag}")
        return 2

    common_args = [
        "--worker",
        "--model", args.model,
        "--max-model-len", str(args.max_model_len),
        "--max-tokens", str(args.max_tokens),
        "--gpu-memory-utilization", str(args.gpu_memory_utilization),
    ]
    for cell, out_path in (
        (CELL_HOOK_OFF, hook_off_json),
        (CELL_HOOK_ON,  hook_on_json),
    ):
        print()
        print(f"=== Driver: spawning worker for cell={cell} ===")
        cmd = [sys.executable, __file__] + common_args + [
            "--cell", cell,
            "--output", str(out_path),
        ]
        ret = subprocess.run(cmd, check=False)
        if ret.returncode != 0:
            print(f"FAIL: worker cell={cell} exited with code {ret.returncode}")
            return ret.returncode

    return compare(hook_off_json, hook_on_json, report_json, report_txt)


if __name__ == "__main__":
    sys.exit(main())
