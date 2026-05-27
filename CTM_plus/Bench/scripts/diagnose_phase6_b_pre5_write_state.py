"""Phase 6B.1 diagnostic — dump live PagedKVWriter state on the GPU pod.

Designed to diagnose unexpected RED outcomes from
``bench_phase6_b_pre5_gpu_smoke.py`` WITHOUT re-running the full
smoke. Pattern mirrors ``tier5a_v0_engine_inspect.py``.

Two modes:

  ``--inspect-only`` (default; zero GPU spend)
      Imports the kv_policy modules, introspects:
        * the env-var override state (PHASE6B1_USE_DECODE_BATCHED)
        * _is_pure_decode_write's verdict on representative
          synthetic attn_metadata shapes (sanity-check the dispatch
          gate without actually running it)
        * the in-tree int4_protected file SHAs vs the frozen
          G5c baseline (catches drift between branch checkout and
          baseline)
        * forked vllm_flash_attn wheel importability + per-file SHA
          if the wheel is installed (the load-bearing G6b view)
      Useful for verifying "did my checkout land cleanly?" before
      spending any pod GPU time.

  ``--live``
      Additionally loads ``Int4ProtectedLLM(Qwen/Qwen2.5-7B-Instruct)``,
      runs ONE warmup + ONE 2-prompt B=2 generate, and dumps:
        * per-layer PagedKVWriter state (slot_map, free_slots,
          pool tensor shapes/devices/data_ptr, pool counter values)
        * Int4ProtectedAttentionImpl._call_stats snapshot pre and
          post the live generate
        * before/after counter deltas per slot — confirms the
          dispatch fork is alive and the write_decode_batched
          path actually fires for pure-decode steps
      Cost: ~$0.02 (one model load + ~30 generated tokens).

Output:
  * stdout: human-readable summary
  * --output PATH: structured JSON dump for paste-back / archival

Run from CTM_plus/Bench:
  # Cheap pre-flight (zero GPU):
  PYTHONPATH=../KVPolicy python3 \\
      scripts/diagnose_phase6_b_pre5_write_state.py --inspect-only

  # On the GPU pod, with live writer-state dump:
  PYTHONPATH=../KVPolicy /workspace/venv-vllm/bin/python3 \\
      scripts/diagnose_phase6_b_pre5_write_state.py --live \\
      --output /workspace/symbolu/bench_out/phase6b1_diag.json

Exit code 0 always (this is informational, not a gate); a
non-zero exit means the script ITSELF failed to introspect (e.g.,
torch unimportable). Inspect the JSON for the verdicts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Optional


_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_kvp_root = os.path.join(_repo_root, "KVPolicy")
if _kvp_root not in sys.path:
    sys.path.insert(0, _kvp_root)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _sha256_of_path(p: Path) -> Optional[str]:
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _module_file(mod_name: str) -> Optional[str]:
    try:
        mod = __import__(mod_name, fromlist=["_"])
    except Exception:
        return None
    return getattr(mod, "__file__", None)


def _find_inner_model(llm):
    """Same heuristic as audit_phase6_b_pre4_pointer_stability.py."""
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


# ---------------------------------------------------------------------- #
# Inspect-only: env, dispatch, file SHAs, wheel SHA
# ---------------------------------------------------------------------- #


def _check_dispatch_gate() -> dict:
    """Probe _is_pure_decode_write's verdict on canned shapes WITHOUT
    constructing a real attn_metadata. Returns {shape_label: verdict}."""
    from kv_policy.phase5b_backend_install import _is_pure_decode_write

    class _DecMeta:
        def __init__(self, B, max_q=1):
            import torch as _t
            self.block_tables = _t.tensor(
                [[i * 4] for i in range(B)], dtype=_t.long,
            )
            self.max_decode_query_len = max_q

    class _PreMeta:
        def __init__(self, n_q): self.num_prefill_tokens = n_q

    class _Meta:
        def __init__(self, decode=None, prefill=None):
            self.decode_metadata = decode
            self.prefill_metadata = prefill

    cases = [
        ("pure_decode_B2",      _Meta(decode=_DecMeta(2)),     2),
        ("pure_decode_B8",      _Meta(decode=_DecMeta(8)),     8),
        ("spec_decode_rejects", _Meta(decode=_DecMeta(2, max_q=3)), 6),
        ("mixed_rejects",       _Meta(decode=_DecMeta(2), prefill=_PreMeta(100)), 102),
        ("pure_prefill_rejects",_Meta(prefill=_PreMeta(100)),  100),
        ("no_decode_rejects",   _Meta(),                       0),
    ]
    out = {}
    for label, meta, T in cases:
        try:
            out[label] = bool(_is_pure_decode_write(meta, T))
        except Exception as e:  # pragma: no cover
            out[label] = f"ERROR: {type(e).__name__}: {e}"
    return out


def _g5c_drift() -> dict:
    """SHA-diff the pinned int4_protected files vs the frozen baseline."""
    baseline_path = Path(__file__).parent.parent / "ctm_bench" / "scripts" / "int4_protected_files_baseline.json"
    if not baseline_path.is_file():
        return {"ok": False, "reason": f"baseline missing at {baseline_path}"}
    baseline = json.loads(baseline_path.read_text()).get("files", {})
    drifts = []
    matches = []
    ctm_plus_dir = Path(__file__).parent.parent.parent  # CTM_plus/
    for rel, expected_sha in baseline.items():
        p = ctm_plus_dir / rel
        actual = _sha256_of_path(p)
        if actual is None:
            drifts.append({"file": rel, "status": "missing"})
        elif actual != expected_sha:
            drifts.append({
                "file": rel, "status": "modified",
                "expected_sha8": expected_sha[:8],
                "actual_sha8": actual[:8],
            })
        else:
            matches.append(rel)
    return {
        "ok":      len(drifts) == 0,
        "n_match": len(matches),
        "n_drift": len(drifts),
        "drifts":  drifts,
    }


def _wheel_sha_view() -> dict:
    """Inspect the installed forked vllm_flash_attn wheel — the load-
    bearing G6b dependency. Cheap (~0.1s); skip on CPU CI."""
    for mod_name in ("vllm_flash_attn", "vllm.vllm_flash_attn"):
        try:
            mod = __import__(mod_name, fromlist=["_"])
        except Exception:
            continue
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        wheel_dir = Path(f).parent
        if not wheel_dir.is_dir():
            continue
        files = []
        for p in sorted(wheel_dir.rglob("*")):
            if not p.is_file(): continue
            if "__pycache__" in p.parts: continue
            if p.suffix not in (".py", ".so"): continue
            files.append({
                "rel":    str(p.relative_to(wheel_dir).as_posix()),
                "sha8":   (_sha256_of_path(p) or "")[:8],
                "size_b": p.stat().st_size,
            })
        return {
            "module":    mod_name,
            "dir":       str(wheel_dir),
            "n_files":   len(files),
            "files":     files,
        }
    return {
        "module":    None,
        "dir":       None,
        "n_files":   0,
        "reason":    "vllm_flash_attn not importable (expected on CPU CI; "
                     "GPU pod MUST have the forked wheel)",
    }


def _inspect_only_payload() -> dict:
    """Builds the dict for --inspect-only mode. No GPU, no model load."""
    payload: dict = {}
    payload["env"] = {
        "PHASE6B1_USE_DECODE_BATCHED": os.environ.get(
            "PHASE6B1_USE_DECODE_BATCHED", "<unset; defaults to '1' (on)>"
        ),
        "PROTECT_MASK_PATH": os.environ.get(
            "PROTECT_MASK_PATH", "<unset; defaults to qwen2_5_7b_protect_mask_4pct.pt>"
        ),
        "PHASE6_MAX_ACTIVE_SLOTS": os.environ.get(
            "PHASE6_MAX_ACTIVE_SLOTS", "<unset; defaults to 8>"
        ),
        "PHASE5B_4C_BF16_BACKING_MAX_SEQLEN": os.environ.get(
            "PHASE5B_4C_BF16_BACKING_MAX_SEQLEN", "<unset; defaults to 4096>"
        ),
    }
    payload["module_files"] = {
        "phase5b_backend_install": _module_file("kv_policy.phase5b_backend_install"),
        "phase5b_4c_paged_writer": _module_file("kv_policy.phase5b_4c_paged_writer"),
    }
    payload["dispatch_gate_verdicts"] = _check_dispatch_gate()
    payload["g5c_drift"]              = _g5c_drift()
    payload["wheel_g6b_view"]         = _wheel_sha_view()
    return payload


# ---------------------------------------------------------------------- #
# Live: load model, dump per-layer writer state, run 1 decode, dump delta
# ---------------------------------------------------------------------- #


def _snapshot_writer_state(model) -> list:
    """Return list of per-layer writer state dicts."""
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl

    snapshots = []
    for name, sub in model.named_modules():
        impl = getattr(sub, "impl", None)
        if not isinstance(impl, Int4ProtectedAttentionImpl):
            continue
        w = getattr(impl, "_phase5b_paged_writer", None)
        if w is None:
            snapshots.append({
                "layer_name": name,
                "writer":     None,
                "note":       "no writer constructed yet",
            })
            continue
        snap = {
            "layer_name":   name,
            "layer_idx":    getattr(w, "layer_idx", None),
            "allocated":    getattr(w, "_allocated", False),
            "slot_map":     dict(getattr(w, "_slot_map", {})),
            "free_slots":   list(getattr(w, "_free_slots", [])),
            "max_active_slots": getattr(w, "_max_active_slots", None),
            "n_seq_states": len(getattr(w, "_seq_states", {})),
        }
        # Pool tensor metadata (no contents — those are 100s of MB).
        pool_tensors = [
            ("_k_stage_pool",          getattr(w, "_k_stage_pool",          None)),
            ("_bf16_k_backing_pool",   getattr(w, "_bf16_k_backing_pool",   None)),
            ("_bf16_v_backing_pool",   getattr(w, "_bf16_v_backing_pool",   None)),
            ("_seq_pos_pool",          getattr(w, "_seq_pos_pool",          None)),
            ("_k_stage_count_pool",    getattr(w, "_k_stage_count_pool",    None)),
            ("_k_stage_block_id_pool", getattr(w, "_k_stage_block_id_pool", None)),
        ]
        pool_meta = {}
        for pname, t in pool_tensors:
            if t is None:
                pool_meta[pname] = None
                continue
            pool_meta[pname] = {
                "shape":  list(t.shape),
                "dtype":  str(t.dtype),
                "device": str(t.device),
                "data_ptr": t.data_ptr(),
            }
        snap["pool_tensors"] = pool_meta
        # Counter pool VALUES (small; cheap to sync).
        try:
            snap["seq_pos_pool_values"]          = w._seq_pos_pool.cpu().tolist()
            snap["k_stage_count_pool_values"]    = w._k_stage_count_pool.cpu().tolist()
            snap["k_stage_block_id_pool_values"] = w._k_stage_block_id_pool.cpu().tolist()
        except Exception as e:
            snap["counter_dump_error"] = f"{type(e).__name__}: {e}"
        snapshots.append(snap)
    return snapshots


def _live_payload(args) -> dict:
    """Load Qwen-7B, run a small generate, dump writer state before/after."""
    payload: dict = {}
    try:
        import torch  # noqa: F401
        from vllm import SamplingParams
        import kv_policy.int4_protected  # noqa: F401
        from kv_policy.int4_protected import Int4ProtectedLLM
        from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    except Exception as e:
        payload["import_error"] = f"{type(e).__name__}: {e}"
        return payload

    payload["model"] = args.model
    t0 = time.time()
    print(f"Loading {args.model} (max_model_len={args.max_model_len}, gpu_mem_util={args.gpu_memory_utilization})...")
    try:
        llm = Int4ProtectedLLM(
            model=args.model,
            max_model_len=args.max_model_len,
            gpu_memory_utilization=args.gpu_memory_utilization,
            enforce_eager=True,
        )
    except Exception as e:
        payload["load_error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        return payload
    payload["load_seconds"] = time.time() - t0

    inner = _find_inner_model(llm)
    if inner is None:
        payload["inner_model_locate_error"] = "could not locate inner model via known accessors"
        return payload

    # Warmup once so writers are constructed.
    Int4ProtectedAttentionImpl.reset_call_stats()
    llm.generate(["Hello."], SamplingParams(temperature=0.0, max_tokens=4))
    payload["call_stats_post_warmup"] = Int4ProtectedAttentionImpl.get_call_stats()

    payload["writer_state_post_warmup"] = _snapshot_writer_state(inner)

    # Run a small 2-prompt B=2 generate to exercise the dispatch fork.
    Int4ProtectedAttentionImpl.reset_call_stats()
    prompts = [
        "Below is a paragraph about a fictional town. Greendell has a stone "
        "library founded in 1742.\nQuestion: What year was it founded?\nAnswer:",
        "Translate to French: The quick brown fox.\nFrench:",
    ]
    t0 = time.time()
    outs = llm.generate(prompts, SamplingParams(
        temperature=0.0, max_tokens=args.max_tokens,
    ))
    payload["generate_seconds"] = time.time() - t0

    payload["call_stats_post_generate"] = Int4ProtectedAttentionImpl.get_call_stats()
    payload["writer_state_post_generate"] = _snapshot_writer_state(inner)

    payload["per_prompt_outputs"] = []
    for i, o in enumerate(outs):
        c0 = o.outputs[0]
        payload["per_prompt_outputs"].append({
            "prompt_idx":           i,
            "prompt_preview":       prompts[i][:60],
            "completion_text":      c0.text,
            "completion_token_ids": list(c0.token_ids),
        })

    return payload


# ---------------------------------------------------------------------- #
# main
# ---------------------------------------------------------------------- #


def _format_summary(payload: dict, live: bool) -> str:
    lines = []
    lines.append("=" * 78)
    lines.append("Phase 6B.1 write-path diagnostic")
    lines.append("=" * 78)
    lines.append(f"mode: {'LIVE (model loaded)' if live else 'INSPECT-ONLY (no GPU)'}")
    lines.append("")
    lines.append("Env:")
    for k, v in payload.get("inspect", {}).get("env", {}).items():
        lines.append(f"  {k:<40s} = {v}")
    lines.append("")
    lines.append("Module file paths:")
    for k, v in payload.get("inspect", {}).get("module_files", {}).items():
        lines.append(f"  {k:<40s} = {v}")
    lines.append("")
    lines.append("Dispatch gate verdicts (_is_pure_decode_write):")
    for label, verdict in payload.get("inspect", {}).get("dispatch_gate_verdicts", {}).items():
        lines.append(f"  {label:<28s} -> {verdict}")
    lines.append("")
    g5c = payload.get("inspect", {}).get("g5c_drift", {})
    lines.append(f"G5c drift check: ok={g5c.get('ok')}  "
                 f"match={g5c.get('n_match')}  drift={g5c.get('n_drift')}")
    for d in g5c.get("drifts", []):
        lines.append(f"  ! {d}")
    lines.append("")
    wheel = payload.get("inspect", {}).get("wheel_g6b_view", {})
    lines.append(f"G6b wheel view: module={wheel.get('module')}  "
                 f"n_files={wheel.get('n_files')}")
    if wheel.get("reason"):
        lines.append(f"  note: {wheel['reason']}")
    elif wheel.get("files"):
        for f in wheel["files"][:6]:
            lines.append(f"  {f['rel']:<32s} sha8={f['sha8']} size={f['size_b']}")
        if len(wheel["files"]) > 6:
            lines.append(f"  ... ({len(wheel['files']) - 6} more)")

    if live:
        live_p = payload.get("live", {})
        lines.append("")
        lines.append("Live run:")
        if "import_error" in live_p:
            lines.append(f"  IMPORT_ERROR: {live_p['import_error']}")
            return "\n".join(lines)
        if "load_error" in live_p:
            lines.append(f"  LOAD_ERROR:")
            lines.append("    " + live_p["load_error"].splitlines()[0])
            return "\n".join(lines)
        lines.append(f"  load_seconds: {live_p.get('load_seconds'):.2f}")
        lines.append(f"  generate_seconds: {live_p.get('generate_seconds'):.2f}")
        lines.append(f"  call_stats POST WARMUP:  "
                     f"{live_p.get('call_stats_post_warmup')}")
        lines.append(f"  call_stats POST GENERATE: "
                     f"{live_p.get('call_stats_post_generate')}")
        lines.append("")
        ws = live_p.get("writer_state_post_generate", [])
        lines.append(f"  Writer state (post generate): {len(ws)} layers")
        for s in ws[:2]:  # show first 2 layers; rest in JSON
            lines.append(f"    {s.get('layer_name')}: "
                         f"slot_map={s.get('slot_map')} "
                         f"free_slots={s.get('free_slots')}")
            lines.append(f"      seq_pos_pool          = {s.get('seq_pos_pool_values')}")
            lines.append(f"      k_stage_count_pool    = {s.get('k_stage_count_pool_values')}")
            lines.append(f"      k_stage_block_id_pool = {s.get('k_stage_block_id_pool_values')}")
        if len(ws) > 2:
            lines.append(f"    ... ({len(ws) - 2} more layers in JSON)")
        lines.append("")
        lines.append("  Per-prompt outputs:")
        for p in live_p.get("per_prompt_outputs", []):
            lines.append(f"    [{p['prompt_idx']}] {p['prompt_preview']!r}")
            lines.append(f"        -> {p['completion_text']!r}")
            lines.append(f"        token_ids[:6] = {p['completion_token_ids'][:6]}")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--inspect-only", action="store_true", default=True,
                      help="(default) zero-GPU introspection — env, dispatch gate, file SHAs.")
    mode.add_argument("--live", action="store_true",
                      help="Additionally load the model + run a small B=2 generate.")
    p.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--max-model-len", type=int, default=4096)
    p.add_argument("--max-tokens",    type=int, default=8)
    p.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    p.add_argument("--output", type=str, default=None,
                   help="If set, write the full structured payload as JSON to this path.")
    args = p.parse_args()

    payload: dict = {"mode": "live" if args.live else "inspect_only"}
    try:
        payload["inspect"] = _inspect_only_payload()
    except Exception as e:
        payload["inspect_error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    if args.live:
        try:
            payload["live"] = _live_payload(args)
        except Exception as e:
            payload["live_error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    summary = _format_summary(payload, live=args.live)
    print(summary)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(payload, indent=2, default=str))
        print()
        print(f"Wrote structured payload -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
