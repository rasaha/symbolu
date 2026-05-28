"""Phase 6E CPU/CUDA verifier — fused decode write byte-equivalence.

Drives a sequence of `write_decode_batched` calls in BOTH modes:
  * PHASE6E_FUSED_WRITER=0 (default): inline op chain
  * PHASE6E_FUSED_WRITER=1: fused entry point. With the
    int4_protected_C extension built AND tensors on CUDA, this routes
    through the custom CUDA kernels; otherwise it routes through the
    byte-identical Python reference.

Asserts every mutated state tensor is byte-equal between the two
modes. This pins down the BEHAVIORAL CONTRACT that any CUDA kernel
implementation must satisfy — when the .cu code lands, this same
verifier catches any divergence by re-running with the env flag set.

State tensors checked (in-place mutations from the captured region):
  kv_cache[0]                            -- packed int4 K
  kv_cache[1]                            -- packed int4 V
  k_scale_ext, k_xmin_ext                -- K sidecars
  v_scale_ext, v_xmin_ext                -- V sidecars
  k_protect_ext                          -- protect-mask K
  _k_stage_pool                          -- K staging buffer
  _k_stage_block_id_pool                 -- K stage block tracker
  _k_stage_count_pool                    -- K stage count tracker
  _seq_pos_pool                          -- per-slot seq position
  (bf16 backing pools only if PHASE6C_BF16_BACKING_SKIP=0)

Covers:
  * B in {1, 2, 4, 8, 16, 32} (CPU sweep; CUDA mode honours the same).
  * Multi-step sequences exercising:
      - block boundary transition (positions 30 → 31 → 32 → 0)
      - inactive mask (some slot_mapping = -1) — though decode rarely
        has this in V0, the captured region handles it for graph safety
      - random K/V tensors with realistic dtype + scale

Usage:
  python verify_phase6e_fused_byte_eq.py                  # CPU only
  python verify_phase6e_fused_byte_eq.py --device cuda    # CUDA, requires built extension

When run with --device cuda and the int4_protected_C extension is
loadable, the fused mode goes through the custom CUDA kernels (the
real production target). Without the extension (or on CPU), it goes
through the Python reference. PHASE6E_FUSED_WRITER_DISABLE_CUDA=1
forces the Python reference even on CUDA, useful for isolating
"kernel vs scaffolding" if a CUDA failure appears.
"""
from __future__ import annotations

import argparse
import copy
import os
import sys
import unittest
from pathlib import Path

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

try:
    import torch
except ImportError:
    print("FAIL: torch import failed; cannot run verifier")
    sys.exit(2)


_FUSED_ENV = "PHASE6E_FUSED_WRITER"

# CLI override populated by main() before unittest.main(). Tests honour
# DEVICE for test_build_writer().
DEVICE = torch.device("cpu")


def _build_writer(seed: int = 0):
    """Construct a fresh PagedKVWriter with a small kv_cache for CPU
    testing. NB=128 gives every B=32 slot its own non-overlapping
    starting block PLUS block 0 as a "safe scatter" destination for
    inactive rows (slot_mapping = -1 safe-clamps to slot 0).

    Bumps PHASE6_MAX_ACTIVE_SLOTS before instantiation so B=16 / B=32
    fit; the writer reads this env at construction time.
    """
    # Bump the slot pool so B=32 fits; needs to happen BEFORE PagedKVWriter
    # is constructed so the writer reads the new value.
    os.environ.setdefault("PHASE6_MAX_ACTIVE_SLOTS", "64")
    # In a long-lived test process the env-var set above is sticky, but
    # if the user overrode it to something small we still need at least 64.
    try:
        if int(os.environ["PHASE6_MAX_ACTIVE_SLOTS"]) < 64:
            os.environ["PHASE6_MAX_ACTIVE_SLOTS"] = "64"
    except ValueError:
        os.environ["PHASE6_MAX_ACTIVE_SLOTS"] = "64"

    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter
    torch.manual_seed(seed)
    w = PagedKVWriter(layer_idx=0)
    NB, BS, H, D = 128, 32, 4, 128
    kv_cache = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8, device=DEVICE)
    w._protect_mask_cpu = torch.zeros((H, D), dtype=torch.int8)
    # 5 protected dims per head — same as Qwen calibration order of magnitude.
    w._protect_mask_cpu[:, :5] = 1
    w._lazy_alloc(kv_cache)
    return w, kv_cache, NB, BS, H, D


def _snapshot_writer_state(writer, kv_cache):
    """Capture every mutable tensor the captured region writes to.

    Returns a dict {name: tensor.clone()} suitable for byte-eq
    comparison via torch.equal.
    """
    snap = {
        "kv_cache_k":              kv_cache[0].clone(),
        "kv_cache_v":              kv_cache[1].clone(),
        "k_scale_ext":             writer.k_scale_ext.clone(),
        "k_xmin_ext":              writer.k_xmin_ext.clone(),
        "v_scale_ext":             writer.v_scale_ext.clone(),
        "v_xmin_ext":              writer.v_xmin_ext.clone(),
        "k_protect_ext":           writer.k_protect_ext.clone(),
        "_k_stage_pool":           writer._k_stage_pool.clone(),
        "_k_stage_block_id_pool":  writer._k_stage_block_id_pool.clone(),
        "_k_stage_count_pool":     writer._k_stage_count_pool.clone(),
        "_seq_pos_pool":           writer._seq_pos_pool.clone(),
    }
    if writer._bf16_k_backing_pool is not None:
        snap["_bf16_k_backing_pool"] = writer._bf16_k_backing_pool.clone()
        snap["_bf16_v_backing_pool"] = writer._bf16_v_backing_pool.clone()
    return snap


def _diff_snapshots(snap_a: dict, snap_b: dict) -> list:
    """Return list of (name, max_abs_diff_or_None) for tensors that differ."""
    diffs = []
    keys = sorted(set(snap_a.keys()) | set(snap_b.keys()))
    for k in keys:
        a = snap_a.get(k)
        b = snap_b.get(k)
        if a is None or b is None:
            diffs.append((k, None))
            continue
        if not torch.equal(a, b):
            try:
                ad = a.to(torch.float64)
                bd = b.to(torch.float64)
                max_diff = float((ad - bd).abs().max().item())
            except Exception:
                max_diff = None
            diffs.append((k, max_diff))
    return diffs


def _drive_write_sequence(
    writer,
    kv_cache,
    B: int,
    n_steps: int,
    seed: int,
    inactive_pattern: str = "none",
    non_contiguous: bool = False,
):
    """Drive `n_steps` simulated decode writes. Each step:
       - chooses a unique slot per batch position
       - increments per-slot positions by 1 (so we walk through blocks)
       - generates fresh random K and V
       - calls write_decode_batched directly with pre_synced=True
         (skip the post-capture writeback that would touch seq_state
         python ints — we're testing the captured region in isolation)

    inactive_pattern:
       "none"     -- all rows active (slot_mapping >= 0)
       "first"    -- slot_mapping[0] = -1 every step (single inactive row)
       "rotating" -- one row inactive per step, rotating through (step % B)

    IMPORTANT: this test mirrors vLLM's actual production allocation,
    where each active sequence lives in non-overlapping cache blocks.
    Specifically, base[s] = (s + 1) * BS so active block_ids[s] are
    distinct across the batch AND distinct from the "safe-clamp"
    destination block 0 that inactive rows scatter to.

    Why we constrain inactive_pattern to at most ONE inactive row per
    step: inactive rows safe-clamp to (block_id=0, position=0). Multiple
    inactive rows in the same step would all scatter to the same
    (block 0, pos 0) destination in v_packed / k_protect_ext. PyTorch's
    duplicate-index scatter is documented as UNDEFINED — two runs of
    the same code can produce different outputs, making byte-equality
    inherently unstable. Production vLLM rarely has more than one
    padding row, and at CUDA graph replay the captured ops execute
    deterministically regardless.

    Why active block_ids must stay distinct: same argument for the
    active row scatter. base[s] = (s + 1) * BS guarantees row s lives
    in block (s + 1) at step 0, walking into (s + 1) + 1 only at step
    BS, so collisions never happen within the tested step ranges.
    """
    torch.manual_seed(seed)
    # Allocate B slots; the writer pops them from the free pool.
    slot_ids = list(range(B))
    for s in slot_ids:
        writer.ensure_seq_state(seq_id=s, device=torch.device("cpu"))

    BS = writer.BS
    H = writer.H
    D = writer.D

    slot_idx_t = torch.tensor(
        [writer._slot_map[s] for s in slot_ids], dtype=torch.long, device=DEVICE,
    )

    # Active rows start at block (s+1) so block 0 stays reserved as the
    # safe-clamp destination for inactive rows. See docstring above.
    base_positions = torch.tensor(
        [(s + 1) * BS for s in range(B)], dtype=torch.long, device=DEVICE,
    )

    for step in range(n_steps):
        # absolute position = base + step;  block_id = abs // BS;  pos = abs % BS
        # vLLM-style slot_mapping packs block × BS + pos.
        abs_pos = base_positions + step
        slot_mapping = abs_pos.clone()

        if inactive_pattern == "first" and B >= 1:
            slot_mapping[0] = -1
        elif inactive_pattern == "rotating" and B >= 1:
            slot_mapping[step % B] = -1

        if non_contiguous:
            # Production vLLM's QKV split hands the writer non-contiguous
            # (B, H, D) views. Reproduce that here: allocate a (B, 2*H, D)
            # tensor and slice the first H heads; the resulting view has
            # stride (2*H*D, D, 1), which fails the kernel's contig check
            # unless the dispatch wrapper calls .contiguous(). Without
            # this case the verifier silently misses regressions on the
            # production path.
            big_k = torch.randn((B, 2 * H, D), dtype=torch.bfloat16, device=DEVICE)
            big_v = torch.randn((B, 2 * H, D), dtype=torch.bfloat16, device=DEVICE)
            key   = big_k[:, :H, :]
            value = big_v[:, :H, :]
            assert not key.is_contiguous() and not value.is_contiguous()
        else:
            key   = torch.randn((B, H, D), dtype=torch.bfloat16, device=DEVICE)
            value = torch.randn((B, H, D), dtype=torch.bfloat16, device=DEVICE)
        writer.write_decode_batched(
            key=key,
            value=value,
            kv_cache=kv_cache,
            slot_mapping=slot_mapping,
            slot_idx_t=slot_idx_t,
            pre_synced=True,
        )


def _run_pair(B: int, n_steps: int, seed: int, inactive_pattern: str = "none",
              non_contiguous: bool = False):
    """Run the same write sequence twice — once with fused OFF, once
    ON — and return both end-state snapshots."""
    # ---- INLINE PATH (PHASE6E_FUSED_WRITER=0) ----
    os.environ[_FUSED_ENV] = "0"
    w_inline, kv_inline, *_ = _build_writer(seed=seed)
    _drive_write_sequence(
        w_inline, kv_inline, B, n_steps, seed=seed,
        inactive_pattern=inactive_pattern, non_contiguous=non_contiguous,
    )
    snap_inline = _snapshot_writer_state(w_inline, kv_inline)

    # ---- FUSED PATH (PHASE6E_FUSED_WRITER=1) ----
    os.environ[_FUSED_ENV] = "1"
    w_fused, kv_fused, *_ = _build_writer(seed=seed)
    _drive_write_sequence(
        w_fused, kv_fused, B, n_steps, seed=seed,
        inactive_pattern=inactive_pattern, non_contiguous=non_contiguous,
    )
    snap_fused = _snapshot_writer_state(w_fused, kv_fused)
    return snap_inline, snap_fused


class Phase6EFusedWriterByteEq(unittest.TestCase):
    def _check(self, B: int, n_steps: int, seed: int = 0,
               inactive_pattern: str = "none",
               non_contiguous: bool = False):
        snap_inline, snap_fused = _run_pair(
            B, n_steps, seed, inactive_pattern, non_contiguous,
        )
        diffs = _diff_snapshots(snap_inline, snap_fused)
        if diffs:
            msg = (f"B={B} n_steps={n_steps} seed={seed} "
                   f"inactive={inactive_pattern} non_contig={non_contiguous} "
                   f"device={DEVICE}: state diverged on:\n"
                   + "\n".join(f"    {k}: max_abs_diff={d}" for k, d in diffs))
            self.fail(msg)

    def test_B1_short(self):
        self._check(B=1, n_steps=3, seed=11)

    def test_B2_short(self):
        self._check(B=2, n_steps=3, seed=22)

    def test_B4_short(self):
        self._check(B=4, n_steps=3, seed=33)

    def test_B8_short(self):
        self._check(B=8, n_steps=3, seed=44)

    def test_B16_short(self):
        self._check(B=16, n_steps=3, seed=144)

    def test_B32_short(self):
        self._check(B=32, n_steps=3, seed=244)

    def test_B8_block_boundary(self):
        # 35 steps drives most slots across a BS=32 block boundary; this
        # exercises the K stage finalize + kv_cache writeback path on
        # at least some slots.
        self._check(B=8, n_steps=35, seed=55)

    def test_B16_block_boundary(self):
        self._check(B=16, n_steps=35, seed=155)

    def test_B2_long_multi_block(self):
        # Drive several block boundaries to verify the K stage
        # accumulation + finalize cycle repeats correctly.
        self._check(B=2, n_steps=70, seed=66)

    def test_B8_inactive_first(self):
        """First batch row inactive every step. Exercises the
        safe-clamp path (slot_mapping[0] = -1 -> safe_slot 0) and
        verifies the K stage is still rolled correctly for the
        remaining active rows."""
        self._check(B=8, n_steps=35, seed=77, inactive_pattern="first")

    def test_B8_inactive_rotating(self):
        """One inactive row per step, rotating through the batch.
        Verifies the active-mask gating doesn't accumulate drift
        across many steps and varies which row is masked."""
        self._check(B=8, n_steps=35, seed=88, inactive_pattern="rotating")

    def test_B8_noncontig_key_value(self):
        """Production vLLM passes the writer (B, H, D) views sliced from
        a wider tensor (the QKV projection output), which are NOT
        contiguous. The CUDA kernels require contig inputs; the dispatch
        wrapper in phase5b_4c_paged_writer.py calls .contiguous() before
        the kernel launch. If that .contiguous() is removed, the kernel
        TORCH_CHECK fires at the very first decode step — the original
        verifier missed this because it always allocates contig tensors."""
        if DEVICE.type != "cuda":
            self.skipTest("Non-contig regression matters only on CUDA path.")
        self._check(B=8, n_steps=3, seed=99, non_contiguous=True)

    def test_default_env_is_off(self):
        """The Phase 6E default is OFF — fused writer is opt-in until
        the CUDA kernel is GPU-verified."""
        os.environ.pop(_FUSED_ENV, None)
        from kv_policy.phase5b_4c_paged_writer import _fused_writer_enabled
        self.assertFalse(_fused_writer_enabled(),
                         "Default should be OFF; ship after CUDA kernel verified.")

    def test_env_on_routes_through_fused(self):
        """PHASE6E_FUSED_WRITER=1 enables the fused path. Sanity check
        the env-flag wiring, not the output (covered by other tests)."""
        os.environ[_FUSED_ENV] = "1"
        from kv_policy.phase5b_4c_paged_writer import _fused_writer_enabled
        self.assertTrue(_fused_writer_enabled())

    def test_cpu_does_not_dispatch_to_cuda(self):
        """On CPU tensors the fused path must NOT call the CUDA
        extension — even when it happens to be importable. The
        eligibility gate in _phase6e_fused_decode_write_python_ref
        checks tensor.is_cuda; CPU runs fall through to the Python op
        chain. Without this guard a stray cuda call on CPU tensors
        would raise.
        """
        if DEVICE.type != "cpu":
            self.skipTest("Only meaningful on CPU runs.")
        os.environ[_FUSED_ENV] = "1"
        w_fused, kv_fused, *_ = _build_writer(seed=0)
        # No exception means dispatch correctly skipped the CUDA path.
        _drive_write_sequence(w_fused, kv_fused, B=2, n_steps=2, seed=0)


def main():
    global DEVICE
    parser = argparse.ArgumentParser(
        description="Phase 6E fused decode-write byte-equivalence verifier.",
    )
    parser.add_argument(
        "--device", choices=("cpu", "cuda"), default="cpu",
        help="Device to run tests on. cuda requires int4_protected_C built.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose unittest output.",
    )
    args, remaining = parser.parse_known_args()

    if args.device == "cuda":
        if not torch.cuda.is_available():
            print("FAIL: --device cuda but torch.cuda.is_available() is False")
            return 2
        DEVICE = torch.device("cuda")
        print(f"Running on CUDA device: {torch.cuda.get_device_name(0)}")
        # Probe for the extension and report status. The fused path
        # itself silently falls back to the Python reference if the
        # extension is missing — so callers know what was actually
        # exercised.
        try:
            import int4_protected_C  # noqa: F401
            print("int4_protected_C extension loaded; fused path will hit the CUDA kernels.")
        except Exception as exc:
            print(
                f"int4_protected_C NOT loaded ({type(exc).__name__}: {exc}); "
                "fused path will fall back to the Python reference. "
                "Build the extension to exercise the CUDA kernels here."
            )
    else:
        DEVICE = torch.device("cpu")

    # Re-invoke unittest with remaining args.
    sys.argv[1:] = remaining + (["-v"] if args.verbose else [])
    unittest.main(verbosity=2 if args.verbose else 1, exit=True)


if __name__ == "__main__":
    # Make sure tests run deterministically — torch will pick up
    # CPU-only and the seeds we set in each test.
    main()
