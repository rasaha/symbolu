"""Phase 6J Stage 2 — CPU/static tests for the naive-mask toggle.

Pinned acceptance criteria (per the staged-execution plan):

  1. Default path unchanged: when PHASE6J_NAIVE_FORCE_ZERO is unset
     or 0, _resolve_k_protect_bf16 returns the input tensor's
     contiguous view byte-for-byte equal to the input.

  2. Env flag forces zero protect mask ONLY when set: with
     PHASE6J_NAIVE_FORCE_ZERO=1, the helper returns a zeros tensor
     of the same shape + dtype + device + contiguity as the input.

  3. Calibrated protect mask still loads normally: the flag does
     NOT touch the writer's mask-loading code path
     (load_protect_mask_for_layer + _build_protect_tables). The
     writer's protect_mask attribute reads from PROTECT_MASK_PATH
     regardless of the naive flag.

  4. No unrelated writer/kernel behavior changes: the writer's
     k_protect_ext is still allocated + populated identically; only
     the read-side substitution differs.

All tests are CPU-only. The read-path substitution doesn't depend
on CUDA; we test the helper in isolation + verify the writer
behaviors via direct attribute inspection.
"""
from __future__ import annotations

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
    print("FAIL: torch import failed; cannot run Phase 6J flag tests")
    sys.exit(2)

from kv_policy import phase5b_backend_install as bi


_ENV = bi._PHASE6J_NAIVE_FORCE_ZERO_ENV   # = "PHASE6J_NAIVE_FORCE_ZERO"


class TestPhase6JNaiveFlagHelper(unittest.TestCase):
    """The helper is the load-bearing surface — production code calls
    bi._resolve_k_protect_bf16(...) from both read paths."""

    def setUp(self):
        # Snapshot + clear the env to start each test clean.
        self._saved_env = os.environ.pop(_ENV, None)
        # Reset the one-shot log announcement so each test sees a
        # fresh "first fire" state.
        bi._phase6j_naive_force_zero_announced = False

    def tearDown(self):
        os.environ.pop(_ENV, None)
        if self._saved_env is not None:
            os.environ[_ENV] = self._saved_env
        bi._phase6j_naive_force_zero_announced = False

    def _make_sample(self, shape=(2, 32, 4, 5), dtype=torch.bfloat16):
        # Non-trivial values so we'd notice if the helper accidentally
        # zeroed the default-OFF case.
        return torch.randn(*shape, dtype=dtype)

    # -- ENV reader -----------------------------------------------------

    def test_env_off_by_default(self):
        os.environ.pop(_ENV, None)
        self.assertFalse(bi._phase6j_naive_force_zero_enabled())

    def test_env_off_when_set_to_zero(self):
        os.environ[_ENV] = "0"
        self.assertFalse(bi._phase6j_naive_force_zero_enabled())

    def test_env_on_when_set_to_one(self):
        os.environ[_ENV] = "1"
        self.assertTrue(bi._phase6j_naive_force_zero_enabled())

    def test_env_on_when_truthy_string(self):
        for v in ("true", "True", "yes"):
            os.environ[_ENV] = v
            self.assertTrue(
                bi._phase6j_naive_force_zero_enabled(),
                f"expected truthy for {v!r}",
            )

    def test_env_off_when_other_string(self):
        os.environ[_ENV] = "no"
        self.assertFalse(bi._phase6j_naive_force_zero_enabled())

    # -- Helper behavior: DEFAULT (env OFF) -----------------------------

    def test_default_returns_input_values(self):
        """ACCEPTANCE 1: default path unchanged. Helper returns the
        same VALUES as the input (contiguous-cast may copy, but content
        is identical)."""
        os.environ.pop(_ENV, None)
        raw = self._make_sample()
        out = bi._resolve_k_protect_bf16(raw)
        self.assertTrue(torch.equal(out, raw),
                        "default path must return input values unchanged")

    def test_default_returns_contiguous(self):
        """The helper must always produce a contiguous tensor (the
        flash_attn API requires it). Even when the input is a
        non-contig view, the output should be contiguous."""
        os.environ.pop(_ENV, None)
        # Create a non-contig view: take every other element along dim=-1.
        raw_strided = self._make_sample(shape=(2, 32, 4, 10))[..., ::2]
        self.assertFalse(raw_strided.is_contiguous())
        out = bi._resolve_k_protect_bf16(raw_strided)
        self.assertTrue(out.is_contiguous(),
                        "helper output must be contiguous")
        # Content must still match.
        self.assertTrue(torch.equal(out, raw_strided.contiguous()))

    def test_default_preserves_dtype_device(self):
        os.environ.pop(_ENV, None)
        raw = self._make_sample(dtype=torch.bfloat16)
        out = bi._resolve_k_protect_bf16(raw)
        self.assertEqual(out.dtype, raw.dtype)
        self.assertEqual(out.device, raw.device)
        self.assertEqual(out.shape, raw.shape)

    # -- Helper behavior: NAIVE (env ON) --------------------------------

    def test_force_zero_returns_zeros(self):
        """ACCEPTANCE 2: env-on substitutes zeros. The helper returns
        a tensor whose every element is exactly zero."""
        os.environ[_ENV] = "1"
        raw = self._make_sample()
        self.assertNotEqual(raw.abs().max().item(), 0.0,
                            "test setup: raw must be non-trivial")
        out = bi._resolve_k_protect_bf16(raw)
        # Compare against a fresh zeros tensor of the same shape.
        expected = torch.zeros_like(raw)
        self.assertTrue(torch.equal(out, expected),
                        "force-zero path must return exact zeros")

    def test_force_zero_preserves_shape_dtype_device(self):
        os.environ[_ENV] = "1"
        for shape in [(1, 32, 4, 1), (2, 32, 4, 5), (8, 64, 8, 3)]:
            raw = self._make_sample(shape=shape, dtype=torch.bfloat16)
            out = bi._resolve_k_protect_bf16(raw)
            self.assertEqual(out.shape, raw.shape)
            self.assertEqual(out.dtype, raw.dtype)
            self.assertEqual(out.device, raw.device)

    def test_force_zero_is_contiguous(self):
        os.environ[_ENV] = "1"
        # Non-contig input; output still contiguous.
        raw_strided = self._make_sample(shape=(2, 32, 4, 10))[..., ::2]
        out = bi._resolve_k_protect_bf16(raw_strided)
        self.assertTrue(out.is_contiguous())
        self.assertTrue(torch.equal(out, torch.zeros_like(out)))

    def test_force_zero_does_not_mutate_input(self):
        """The substitution must NOT touch the writer's k_protect_ext
        view. Confirm the input tensor's content is intact after the
        call (we're returning a fresh zeros, not zeroing the input)."""
        os.environ[_ENV] = "1"
        raw = self._make_sample()
        raw_copy = raw.clone()
        _ = bi._resolve_k_protect_bf16(raw)
        self.assertTrue(torch.equal(raw, raw_copy),
                        "input must not be mutated by the helper")

    # -- Toggle isolation: env ON does NOT touch protect-mask loading --

    def test_calibrated_mask_loading_unaffected_by_naive_flag(self):
        """ACCEPTANCE 3: the calibrated protect-mask still loads
        normally when the naive flag is set. The flag is purely a
        READ-side substitution; mask loading is a WRITE-side
        construction.

        We assert that the two code paths share no state by checking
        that `_build_protect_tables` produces the same output
        regardless of the env flag's setting.
        """
        from kv_policy.phase5b_4c_paged_writer import _build_protect_tables
        # Synthetic non-trivial mask: 3 channels protected per head.
        H, D = 4, 128
        mask = torch.zeros((H, D), dtype=torch.int8)
        mask[:, :3] = 1
        n_protect = int(mask.sum(dim=-1).max().item())

        os.environ.pop(_ENV, None)
        slot_off, pd_off = _build_protect_tables(mask, n_protect)

        os.environ[_ENV] = "1"
        slot_on, pd_on = _build_protect_tables(mask, n_protect)

        self.assertTrue(torch.equal(slot_off, slot_on),
                        "protect_slot table must be identical regardless of naive flag")
        self.assertTrue(torch.equal(pd_off, pd_on),
                        "protected_d_per_head must be identical regardless of naive flag")
        # And: protected_d_per_head[h, 0..n-1] must be the real
        # nonzero indices, not all zeros.
        self.assertEqual(int(pd_off[0, 0]), 0)
        self.assertEqual(int(pd_off[0, 1]), 1)
        self.assertEqual(int(pd_off[0, 2]), 2)

    def test_writer_k_protect_ext_alloc_unaffected_by_naive_flag(self):
        """ACCEPTANCE 4: the writer's k_protect_ext is allocated +
        sized identically regardless of the naive flag. Only the
        read substitution differs. Confirm by inspecting the writer's
        attributes after _lazy_alloc fires under both flag states."""
        from kv_policy.phase5b_4c_paged_writer import PagedKVWriter

        def _build_writer():
            w = PagedKVWriter(layer_idx=0)
            NB, BS, H, D = 8, 32, 4, 128
            kv_cache = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8)
            w._protect_mask_cpu = torch.zeros((H, D), dtype=torch.int8)
            w._protect_mask_cpu[:, :3] = 1   # 3 protected channels per head
            w._lazy_alloc(kv_cache)
            return w

        os.environ.pop(_ENV, None)
        w_off = _build_writer()
        os.environ[_ENV] = "1"
        w_on  = _build_writer()

        # Shapes + dtypes identical:
        self.assertEqual(w_off.k_protect_ext.shape, w_on.k_protect_ext.shape)
        self.assertEqual(w_off.k_protect_ext.dtype, w_on.k_protect_ext.dtype)
        # n_protect identical:
        self.assertEqual(w_off.n_protect, w_on.n_protect)
        # protect_mask itself loaded identically:
        self.assertTrue(torch.equal(w_off.protect_mask, w_on.protect_mask),
                        "protect_mask must be identical regardless of naive flag")
        self.assertTrue(torch.equal(w_off.protected_d_per_head,
                                    w_on.protected_d_per_head))

    # -- Idempotency / one-shot announcement ---------------------------

    def test_announce_fires_only_once(self):
        """The helper logs a single 'naive flag active' message the
        first time it's called with the flag set. Subsequent calls
        are silent. This is a sanity check that the audit-trail log
        line doesn't spam the bench's stdout."""
        os.environ[_ENV] = "1"
        bi._phase6j_naive_force_zero_announced = False
        self.assertFalse(bi._phase6j_naive_force_zero_announced)
        raw = self._make_sample()
        _ = bi._resolve_k_protect_bf16(raw)
        self.assertTrue(bi._phase6j_naive_force_zero_announced)
        # Second call: the flag is still set but the announcement
        # state should remain True (not re-fire).
        _ = bi._resolve_k_protect_bf16(raw)
        self.assertTrue(bi._phase6j_naive_force_zero_announced)

    def test_no_announce_when_flag_off(self):
        """Default-OFF path must not fire the announcement state."""
        os.environ.pop(_ENV, None)
        bi._phase6j_naive_force_zero_announced = False
        raw = self._make_sample()
        _ = bi._resolve_k_protect_bf16(raw)
        self.assertFalse(bi._phase6j_naive_force_zero_announced,
                         "default-OFF must not announce")


if __name__ == "__main__":
    unittest.main(verbosity=2)
