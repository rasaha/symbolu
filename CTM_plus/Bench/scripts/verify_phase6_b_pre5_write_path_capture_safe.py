"""Phase 6 v2 Option B pre-flight (B-pre-5 / Phase 6B.1) —
write_decode_batched capture-safety verify.

Two independent checks:

  1. **AST static check.** Parses
     `kv_policy/phase5b_4c_paged_writer.py`, locates the
     `write_decode_batched` method, and walks the AST nodes that fall
     between the `# CAPTURED-REGION-START` and `# CAPTURED-REGION-END`
     sentinel comments. Asserts ZERO occurrences of:
       - Method calls `.item()`, `.cpu()`, `.tolist()`
       - Subscript reads on `_seq_states` / `_slot_map` attributes
         (Python dict lookups)
     These are the patterns that crash `torch.cuda.graph()` capture
     (per OPTION_B_PREFLIGHT.md §"Why it's not a one-session change").

  2. **Runtime instrumentation check.** Monkey-patches
     `torch.Tensor.item`, `.cpu`, and `.tolist` to record every call,
     then runs a B=2, 4-step decode workload through
     `write_decode_batched`. Asserts the total host-sync count matches
     the EXEMPT pre-capture / post-capture pattern (the one coalesced
     `.cpu().tolist()` on `slot_idx_t` plus the writeback's three
     `.cpu().tolist()` calls + slot_idx_t.long() ops) and that NO
     additional host-sync call fires from inside the captured region's
     stack frame.

The dispatch helper `_is_pure_decode_write` and the legacy `write()`
path are NOT in scope — they're either before the captured region or
on the prefill-only branch.

CPU-runnable — no GPU, no full vLLM stack. Run from CTM_plus/Bench:
  PYTHONPATH=../KVPolicy python3 \\
      scripts/verify_phase6_b_pre5_write_path_capture_safe.py

Exit 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import ast
import inspect
import os
import sys
import tempfile
import traceback
from pathlib import Path

import torch


_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_kvp_root = os.path.join(_repo_root, "KVPolicy")
if _kvp_root not in sys.path:
    sys.path.insert(0, _kvp_root)


WRITER_PATH = Path(_kvp_root) / "kv_policy" / "phase5b_4c_paged_writer.py"
METHOD_NAME = "write_decode_batched"

# Forbidden method names inside the captured region.
FORBIDDEN_ATTRS = {"item", "cpu", "tolist"}

# Attribute-access names whose subscript would be a Python dict lookup.
DICT_ATTR_NAMES = {"_seq_states", "_slot_map"}


# --------------------------------------------------------------------- #
# Check 1: AST static walk
# --------------------------------------------------------------------- #


def _find_method_node(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise RuntimeError(f"method {name!r} not found in AST")


def _captured_region_line_range(src_text: str) -> tuple[int, int]:
    """Locate the line numbers of the # CAPTURED-REGION-START and
    # CAPTURED-REGION-END sentinel comments. Returns (start_line,
    end_line) 1-indexed, exclusive of the sentinels themselves."""
    start = end = None
    for idx, line in enumerate(src_text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("# CAPTURED-REGION-START") and start is None:
            start = idx
        elif stripped.startswith("# CAPTURED-REGION-END") and end is None:
            end = idx
    if start is None or end is None:
        raise RuntimeError(
            "CAPTURED-REGION-START / CAPTURED-REGION-END sentinels not "
            f"both found in source (start={start}, end={end})"
        )
    return start, end


def _walk_in_range(node: ast.AST, lo: int, hi: int):
    """Yield AST descendants whose `lineno` falls in (lo, hi)."""
    for child in ast.walk(node):
        ln = getattr(child, "lineno", None)
        if ln is not None and lo < ln < hi:
            yield child


def check_ast_static() -> tuple[bool, list[str]]:
    """Returns (ok, violations). violations: list of human-readable
    "file:line: pattern" strings."""
    src_text = WRITER_PATH.read_text()
    tree = ast.parse(src_text)
    lo, hi = _captured_region_line_range(src_text)

    violations: list[str] = []
    for sub in _walk_in_range(tree, lo, hi):
        # Forbidden attribute calls: x.item() / x.cpu() / x.tolist()
        if isinstance(sub, ast.Call):
            f = sub.func
            if (
                isinstance(f, ast.Attribute)
                and f.attr in FORBIDDEN_ATTRS
            ):
                violations.append(
                    f"{WRITER_PATH.name}:{sub.lineno}: forbidden host "
                    f"sync `.{f.attr}()` in captured region"
                )
        # Dict subscripts: x._seq_states[...] / x._slot_map[...]
        if isinstance(sub, ast.Subscript):
            value = sub.value
            if (
                isinstance(value, ast.Attribute)
                and value.attr in DICT_ATTR_NAMES
            ):
                violations.append(
                    f"{WRITER_PATH.name}:{sub.lineno}: forbidden dict "
                    f"lookup on `.{value.attr}` in captured region"
                )

    return (len(violations) == 0, violations)


# --------------------------------------------------------------------- #
# Check 2: runtime instrumentation
# --------------------------------------------------------------------- #


def _build_workload():
    """Build a CPU writer in a state ready for B=2 decode."""
    NUM_LAYERS, H_KV, D, BS, N_PROTECT = 28, 4, 128, 32, 5
    mask = torch.zeros((H_KV, D), dtype=torch.int8)
    mask[:, :N_PROTECT] = 1
    full = mask.unsqueeze(0).expand(NUM_LAYERS, -1, -1).contiguous()
    fd, path = tempfile.mkstemp(suffix=".pt")
    os.close(fd)
    torch.save(full, path)
    os.environ["PROTECT_MASK_PATH"] = path

    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter
    w = PagedKVWriter(layer_idx=0, sidecar_dtype=torch.bfloat16)
    kv = torch.zeros((2, 64, BS, H_KV, D), dtype=torch.uint8)
    # Prefill 32 tokens for two seqs.
    for i, sid in enumerate([200, 201]):
        base_block = (i + 1) * 4
        slots = torch.arange(base_block * BS, base_block * BS + BS, dtype=torch.long)
        k = torch.randn(BS, H_KV, D, dtype=torch.bfloat16) * 0.5
        v = torch.randn(BS, H_KV, D, dtype=torch.bfloat16) * 0.5
        w.write(k, v, kv, slots, seq_id=sid)
    slot_idx_t = torch.tensor(
        [w._slot_map[200], w._slot_map[201]], dtype=torch.long,
    )

    def make_step(step: int):
        k_step = torch.randn(2, H_KV, D, dtype=torch.bfloat16) * 0.5
        v_step = torch.randn(2, H_KV, D, dtype=torch.bfloat16) * 0.5
        slot_mapping = torch.tensor(
            [4 * BS + BS + step, 2 * 4 * BS + BS + step],
            dtype=torch.long,
        )
        return k_step, v_step, slot_mapping

    return w, kv, slot_idx_t, make_step, path


def _frames_above_match_filename(filename_substr: str) -> bool:
    """Walk the call stack and check whether any frame's filename
    contains `filename_substr`. Used to attribute a host-sync call to
    `phase5b_4c_paged_writer.py`."""
    f = inspect.currentframe()
    # Skip self + caller (the patched method itself).
    while f is not None:
        co = f.f_code
        if filename_substr in co.co_filename:
            return True
        f = f.f_back
    return False


def check_runtime() -> tuple[bool, dict]:
    """Returns (ok, stats). stats: dict mapping call-site -> count."""
    # Patch torch.Tensor's three forbidden methods.
    orig_item    = torch.Tensor.item
    orig_cpu     = torch.Tensor.cpu
    orig_tolist  = torch.Tensor.tolist

    # Counters keyed by (method_name, in_writer_frame).
    counts: dict[tuple[str, bool], int] = {}

    def _bump(name, in_writer):
        key = (name, in_writer)
        counts[key] = counts.get(key, 0) + 1

    def _patched_item(self, *a, **kw):
        in_writer = _frames_above_match_filename("phase5b_4c_paged_writer.py")
        _bump("item", in_writer)
        return orig_item(self, *a, **kw)

    def _patched_cpu(self, *a, **kw):
        in_writer = _frames_above_match_filename("phase5b_4c_paged_writer.py")
        _bump("cpu", in_writer)
        return orig_cpu(self, *a, **kw)

    def _patched_tolist(self, *a, **kw):
        in_writer = _frames_above_match_filename("phase5b_4c_paged_writer.py")
        _bump("tolist", in_writer)
        return orig_tolist(self, *a, **kw)

    torch.Tensor.item   = _patched_item
    torch.Tensor.cpu    = _patched_cpu
    torch.Tensor.tolist = _patched_tolist

    try:
        w, kv, slot_idx_t, make_step, tmp_mask_path = _build_workload()
        # Reset counts AFTER setup (prefill uses legacy writer.write which
        # has host syncs; we only care about write_decode_batched).
        counts.clear()
        N_STEPS = 4
        for step in range(N_STEPS):
            k_step, v_step, slot_mapping = make_step(step)
            w.write_decode_batched(
                key=k_step, value=v_step, kv_cache=kv,
                slot_mapping=slot_mapping, slot_idx_t=slot_idx_t,
            )
    finally:
        torch.Tensor.item   = orig_item
        torch.Tensor.cpu    = orig_cpu
        torch.Tensor.tolist = orig_tolist

    # Collate per-call expectations.
    # The exempt pattern per write_decode_batched call:
    #   PRE-CAPTURE:
    #     slot_idx_t.cpu().tolist()           -> 1 .cpu() + 1 .tolist()
    #     overflow guard: per-slot item()     -> B .item() calls
    #     (for B=2: 2 .item() calls per step in the guard)
    #   POST-CAPTURE writeback:
    #     3 .cpu().tolist() calls
    #     (each via .cpu() + .tolist() = 6 calls per step from writer)
    #
    # NO host sync should originate from the captured region itself.
    # We assert that ALL writer-frame host syncs are accounted for by
    # the exempt pattern.
    B = 2
    # Phase 6C made backing-skip the DEFAULT: the bf16-backing overflow
    # guard (B `.item()`s per step) is inside `if not _bf16_backing_
    # skipped:` and never fires in skip mode. The expectation tracks the
    # mode the workload writer actually allocated in, so the verifier
    # stays meaningful in both (set PHASE6C_BF16_BACKING_SKIP=0 for the
    # legacy-pool count).
    overflow_guard_items = 0 if getattr(w, "_bf16_backing_skipped", True) else B
    expected_per_step = {
        # .cpu(): 1 pre-capture + 3 post-capture (slot_idx + 3 pool dumps)
        "cpu":    1 + 3,
        # .tolist(): same 1 + 3
        "tolist": 1 + 3,
        # .item(): B from the overflow guard (legacy backing mode only)
        # + B from the Phase 6B.2 sentinel-gate inside
        # _sync_pool_counters_from_states (checks
        # `_k_stage_block_id_pool[slot]` per slot to decide whether
        # the prefill->decode transition sync should fire). Both are
        # PRE-CAPTURE host syncs; the AST verifier's CAPTURED-REGION
        # span sees zero forbidden calls.
        "item":   overflow_guard_items + B,
    }
    n_steps = 4
    expected_total = {k: v * n_steps for k, v in expected_per_step.items()}

    # Build the actual writer-frame totals from counts.
    actual_total: dict[str, int] = {"cpu": 0, "tolist": 0, "item": 0}
    for (name, in_writer), c in counts.items():
        if in_writer:
            actual_total[name] = actual_total.get(name, 0) + c

    ok = (actual_total == expected_total)
    stats = {
        "expected_per_step":    expected_per_step,
        "expected_total":       expected_total,
        "actual_total":         actual_total,
        "raw_counts":           {f"{n}:in_writer={iw}": c for (n, iw), c in counts.items()},
        "n_steps":              n_steps,
        "B":                    B,
    }
    try:
        os.unlink(tmp_mask_path)
    except OSError:
        pass
    return ok, stats


# --------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------- #


def main() -> int:
    print("=" * 78)
    print("Phase 6 v2 Option B pre-flight (B-pre-5 / Phase 6B.1)")
    print("write_decode_batched capture-safety verify")
    print("=" * 78)
    print(f"device=cpu (verify is CPU-only)  torch={torch.__version__}")
    print()

    overall_ok = True

    # Check 1: AST static.
    print("Check 1: AST static walk of CAPTURED-REGION span...")
    try:
        ast_ok, violations = check_ast_static()
        if ast_ok:
            print("  PASS — no forbidden .item()/.cpu()/.tolist() calls; "
                  "no _seq_states/_slot_map subscripts in captured region.")
        else:
            print(f"  FAIL — {len(violations)} violations:")
            for v in violations:
                print(f"    * {v}")
            overall_ok = False
    except Exception:
        traceback.print_exc()
        overall_ok = False

    # Check 2: runtime instrumentation.
    print()
    print("Check 2: runtime monkeypatch host-sync count...")
    try:
        rt_ok, stats = check_runtime()
        if rt_ok:
            print("  PASS — host-sync calls from phase5b_4c_paged_writer "
                  "frames exactly match the exempt pre/post-capture pattern:")
            print(f"    expected: {stats['expected_total']}")
            print(f"    actual:   {stats['actual_total']}")
        else:
            print("  FAIL — runtime host-sync count diverges from exempt pattern:")
            print(f"    expected: {stats['expected_total']}")
            print(f"    actual:   {stats['actual_total']}")
            print(f"    raw:      {stats['raw_counts']}")
            overall_ok = False
    except Exception:
        traceback.print_exc()
        overall_ok = False

    print()
    if overall_ok:
        print("Phase 6B.1 write-path capture-safety: GREEN")
        print("  write_decode_batched's captured region contains zero")
        print("  forbidden host-sync patterns. The exempt pre-capture and")
        print("  post-capture steps account for ALL observed host syncs in")
        print("  the writer's frame. 6B.2's vLLM hook will hoist these")
        print("  exempt steps out of the captured region entirely.")
        return 0
    print("Phase 6B.1 write-path capture-safety: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
