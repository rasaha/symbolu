"""Phase 6N — CPU tests for prot-int8 (asym-static int8 protected channels).

Pinned acceptance criteria (PHASE6N_PROT_INT8_DESIGN.md):

  1. QUANT MATH IS THE PROBE'S. The writer's quantize/dequant round trip
     must reproduce probe_block_quant_error.policy_errors's
     'prot_int8_static_asym' policy BIT-EXACTLY (that probe run is the
     evidence the variant was locked on — the build must ship the same
     math, not an approximation of it).

  2. FLAG OFF => NO-OP. With $INT4_PROTECTED_PROT_INT8 unset the sidecar
     stays bf16 and the store/view converters are IDENTITY passthroughs
     (same tensor object — the pre-6N op chain byte-for-byte), even when
     calibration min/max are available.

  3. ARTIFACT-MISSING FALLBACK. Flag set + pre-v2 artifact (no
     k_min/k_max) => loud warning, prot-int8 stays off, bf16 behavior.

  4. ALL THREE WRITE SITES AGREE. write() (prefill), the decode inline
     body, and the Phase 6E fused Python ref produce identical uint8
     codes for the same tokens.

  5. READ PATHS DEQUANT. get_packed_view / get_packed_view_batched
     return bf16 'k_protect_bf16' == dequant(stored codes) bit-exact
     (the kernel contract is unchanged).

  6. S1 DUMP CONTRACT. The byte-gate dump records DEQUANTED bf16 protect
     plus a format marker under both modes.

  7. CALIBRATION EMIT. The accumulator tracks signed min/max across
     batches; _widen_minmax pushes each bound outward by
     (margin-1) x range; the v2 artifact loader round-trips and old
     formats return None.

All tests are CPU-only.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
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
        CTM_ROOT = _root
        break
else:  # pragma: no cover
    raise RuntimeError("KVPolicy root not found")

import torch

from kv_policy import phase5b_4c_paged_writer as pw

NB, BS, H, D, N_PROT = 8, 32, 2, 128, 5

_MANAGED_ENVS = (
    pw._PROT_INT8_ENV,
    pw._PROTECT_MASK_ENV,
    pw._DUMP_ENV,
    pw._FUSED_WRITER_ENV,
)


def _load_script_module(name: str):
    """Import a Bench/scripts module by path (they're not a package)."""
    path = CTM_ROOT / "Bench" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mk_mask():
    """(H, D) int8 mask with N_PROT distinct channels per head."""
    mask = torch.zeros((H, D), dtype=torch.int8)
    for h in range(H):
        mask[h, torch.arange(N_PROT) * (7 + h) % D] = 0
    # deterministic, sorted, distinct channel picks per head
    mask.zero_()
    mask[0, [3, 17, 40, 90, 127]] = 1
    mask[1, [0, 5, 64, 100, 126]] = 1
    return mask


def _mk_minmax(seed: int = 1):
    """(k_min, k_max) (H, D) f32 with k_min < k_max everywhere, plus a
    one-sided (strictly positive) region — the case asym-static exists
    for."""
    g = torch.Generator().manual_seed(seed)
    center = torch.randn((H, D), generator=g)
    half = torch.rand((H, D), generator=g) * 4.0 + 0.5
    k_min = center - half
    k_max = center + half
    k_min[:, :8] = 0.5          # one-sided channels
    k_max[:, :8] = 9.0
    return k_min, k_max


def _mk_writer(flag_on_minmax=None, protect_mask=None):
    """Fresh CPU writer + kv_cache, lazily allocated."""
    w = pw.PagedKVWriter(
        layer_idx=0,
        protect_mask=_mk_mask() if protect_mask is None else protect_mask,
        protect_minmax=flag_on_minmax,
    )
    kv_cache = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8)
    w._lazy_alloc(kv_cache)
    return w, kv_cache


def _keys_in_range(T: int, k_min, k_max, seed: int = 2):
    """(T, H, D) bf16 keys uniform inside [k_min, k_max] per channel —
    no clipping, so the roundtrip bound is exactly scale/2."""
    g = torch.Generator().manual_seed(seed)
    u = torch.rand((T, H, D), generator=g)
    x = k_min.unsqueeze(0) + u * (k_max - k_min).unsqueeze(0)
    return x.to(torch.bfloat16)


class _EnvHygiene(unittest.TestCase):
    def setUp(self):
        self._saved = {e: os.environ.pop(e, None) for e in _MANAGED_ENVS}
        # The S1 dump arms itself to the first finalizing writer via a
        # module global — reset so each test sees fresh dump state.
        pw._DUMP_STATE["writer"] = None
        pw._DUMP_STATE["events"] = []

    def tearDown(self):
        for e, v in self._saved.items():
            if v is None:
                os.environ.pop(e, None)
            else:
                os.environ[e] = v
        pw._DUMP_STATE["writer"] = None
        pw._DUMP_STATE["events"] = []


class TestQuantMathMatchesProbe(_EnvHygiene):
    """Acceptance 1: the shipped math == the probe policy the decision
    was made on (probe_block_quant_error.policy_errors,
    'prot_int8_static_asym')."""

    def test_roundtrip_error_bitexact_vs_probe_policy(self):
        probe = _load_script_module("probe_block_quant_error")
        torch.manual_seed(0)
        S = 64
        k = torch.randn(S, H, D).to(torch.bfloat16).float()
        k[:, :, 3] *= 25.0                       # planted outliers
        k[:, :, 17] = k[:, :, 17].abs() + 5.0    # one-sided channel
        mask = _mk_mask().bool()
        mn, mx = k.amin(dim=0), k.amax(dim=0)

        errs = probe.policy_errors(k, mask, static_minmax=(mn, mx))
        self.assertIn("prot_int8_static_asym", errs)

        qmin, qscale = pw.prot_int8_constants(mn, mx)
        codes = pw.prot_int8_quantize(k, qmin, qscale)
        deq = pw.prot_int8_dequantize(codes, qmin, qscale, torch.float32)
        err_mine = (k - deq).abs()

        self.assertTrue(torch.equal(
            err_mine[:, mask], errs["prot_int8_static_asym"][:, mask]))

    def test_scale_derivation_matches_probe(self):
        mn, mx = _mk_minmax()
        _, qscale = pw.prot_int8_constants(mn, mx)
        probe_scale = ((mx.float() - mn.float()) / 255.0).clamp(min=1e-8)
        self.assertTrue(torch.equal(qscale, probe_scale))

    def test_codes_are_uint8_full_range(self):
        mn, mx = _mk_minmax()
        qmin, qscale = pw.prot_int8_constants(mn, mx)
        codes_lo = pw.prot_int8_quantize(mn, qmin, qscale)
        codes_hi = pw.prot_int8_quantize(mx, qmin, qscale)
        self.assertEqual(codes_lo.dtype, torch.uint8)
        self.assertTrue(bool((codes_lo == 0).all()))
        self.assertTrue(bool((codes_hi == 255).all()))
        # Out-of-range values clamp instead of wrapping.
        codes_over = pw.prot_int8_quantize(mx + 100.0, qmin, qscale)
        codes_under = pw.prot_int8_quantize(mn - 100.0, qmin, qscale)
        self.assertTrue(bool((codes_over == 255).all()))
        self.assertTrue(bool((codes_under == 0).all()))

    def test_degenerate_channel_scale_clamped(self):
        mn = torch.zeros((H, D))
        mx = torch.zeros((H, D))                 # constant channels
        qmin, qscale = pw.prot_int8_constants(mn, mx)
        self.assertTrue(bool((qscale == 1e-8).all()))
        deq = pw.prot_int8_dequantize(
            pw.prot_int8_quantize(torch.zeros(4, H, D), qmin, qscale),
            qmin, qscale, torch.float32)
        self.assertTrue(bool(torch.isfinite(deq).all()))


class TestFlagOffNoop(_EnvHygiene):
    """Acceptance 2: flag unset => bf16 sidecar + identity converters,
    even when min/max are available."""

    def test_flag_off_bf16_sidecar_and_identity(self):
        w, kv_cache = _mk_writer(flag_on_minmax=_mk_minmax())
        self.assertFalse(w._prot_int8_active)
        self.assertEqual(w.k_protect_ext.dtype, torch.bfloat16)
        self.assertIsNone(w._prot_qmin)
        t = torch.randn(3, H, N_PROT, dtype=torch.bfloat16)
        self.assertIs(w._protect_store(t), t)     # SAME object — no-op
        self.assertIs(w._protect_view_bf16(t), t)

    def test_flag_off_zero_means_off(self):
        os.environ[pw._PROT_INT8_ENV] = "0"
        w, _ = _mk_writer(flag_on_minmax=_mk_minmax())
        self.assertFalse(w._prot_int8_active)
        self.assertEqual(w.k_protect_ext.dtype, torch.bfloat16)

    def test_flag_off_read_returns_stored_values(self):
        w, kv_cache = _mk_writer()
        k_min, k_max = _mk_minmax()
        key = _keys_in_range(BS, k_min, k_max)
        val = torch.randn(BS, H, D, dtype=torch.bfloat16)
        w.write(key, val, kv_cache, torch.arange(BS))
        gathered = torch.gather(
            key, -1, w.protected_d_per_head.unsqueeze(0).expand(BS, -1, -1))
        view = w.get_packed_view(torch.tensor([0]), kv_cache)
        self.assertEqual(view["k_protect_bf16"].dtype, torch.bfloat16)
        self.assertTrue(torch.equal(
            view["k_protect_bf16"][0], gathered))   # exact bf16 protect


class TestFlagOnWriterPaths(_EnvHygiene):
    """Acceptance 4 + 5: uint8 sidecar; all write sites agree; reads
    dequant bit-exactly; the prize (half the protect bytes) is real."""

    def setUp(self):
        super().setUp()
        os.environ[pw._PROT_INT8_ENV] = "1"
        self.k_min, self.k_max = _mk_minmax()

    def test_alloc_uint8_and_constants(self):
        w, _ = _mk_writer(flag_on_minmax=(self.k_min, self.k_max))
        self.assertTrue(w._prot_int8_active)
        self.assertEqual(w.k_protect_ext.dtype, torch.uint8)
        self.assertEqual(w._prot_qmin.shape, (H, N_PROT))
        self.assertEqual(w._prot_qscale.shape, (H, N_PROT))
        self.assertTrue(bool((w._prot_qscale > 0).all()))
        # Constants are the protected channels' minmax in slot order.
        pd = w.protected_d_per_head
        self.assertTrue(torch.equal(
            w._prot_qmin, torch.gather(self.k_min.float(), 1, pd)))
        self.assertEqual(w.get_state()["prot_int8_active"], True)

    def test_sidecar_bytes_halved(self):
        os.environ.pop(pw._PROT_INT8_ENV)
        w_off, _ = _mk_writer()
        os.environ[pw._PROT_INT8_ENV] = "1"
        w_on, _ = _mk_writer(flag_on_minmax=(self.k_min, self.k_max))
        self.assertEqual(w_off.k_protect_ext.shape, w_on.k_protect_ext.shape)
        self.assertEqual(w_on.k_protect_ext.nbytes * 2,
                         w_off.k_protect_ext.nbytes)
        # The dequant constants are the only addition: 2 x (H, N_PROT) f32.
        const_bytes = w_on._prot_qmin.nbytes + w_on._prot_qscale.nbytes
        self.assertEqual(const_bytes, 2 * H * N_PROT * 4)

    def test_prefill_write_quantizes_and_read_dequants(self):
        w, kv_cache = _mk_writer(flag_on_minmax=(self.k_min, self.k_max))
        key = _keys_in_range(BS, self.k_min, self.k_max)
        val = torch.randn(BS, H, D, dtype=torch.bfloat16)
        w.write(key, val, kv_cache, torch.arange(BS))

        gathered = torch.gather(
            key, -1, w.protected_d_per_head.unsqueeze(0).expand(BS, -1, -1))
        expected_codes = pw.prot_int8_quantize(
            gathered, w._prot_qmin, w._prot_qscale)
        self.assertTrue(torch.equal(w.k_protect_ext[0], expected_codes))

        expected_bf16 = pw.prot_int8_dequantize(
            expected_codes, w._prot_qmin, w._prot_qscale, torch.bfloat16)
        view = w.get_packed_view(torch.tensor([0]), kv_cache)
        self.assertEqual(view["k_protect_bf16"].dtype, torch.bfloat16)
        self.assertTrue(torch.equal(view["k_protect_bf16"][0], expected_bf16))

        viewb = w.get_packed_view_batched(torch.tensor([[0]]), kv_cache)
        self.assertEqual(viewb["k_protect_bf16"].dtype, torch.bfloat16)
        self.assertTrue(torch.equal(viewb["k_protect_bf16"][0], expected_bf16))

        # Roundtrip bound: in-range inputs => |err| <= scale/2 (+ bf16
        # cast slack of the dequant output).
        err = (expected_bf16.float() - gathered.float()).abs()
        bound = (w._prot_qscale * 0.5).unsqueeze(0) \
            + 0.01 * gathered.float().abs() + 1e-3
        self.assertTrue(bool((err <= bound).all()))

    def test_decode_batched_matches_prefill_codes(self):
        w_a, kv_a = _mk_writer(flag_on_minmax=(self.k_min, self.k_max))
        w_b, kv_b = _mk_writer(flag_on_minmax=(self.k_min, self.k_max))
        key = _keys_in_range(BS, self.k_min, self.k_max)
        val = torch.randn(BS, H, D, dtype=torch.bfloat16)

        w_a.write(key, val, kv_a, torch.arange(BS))

        w_b.ensure_seq_state(seq_id=0, device=torch.device("cpu"))
        slot_idx_t = torch.tensor([w_b._slot_map[0]], dtype=torch.long)
        for t in range(BS):
            w_b.write_decode_batched(
                key=key[t:t + 1], value=val[t:t + 1], kv_cache=kv_b,
                slot_mapping=torch.tensor([t]), slot_idx_t=slot_idx_t,
                pre_synced=True,
            )
        self.assertTrue(torch.equal(w_a.k_protect_ext, w_b.k_protect_ext))
        self.assertTrue(torch.equal(kv_a[0], kv_b[0]))
        self.assertTrue(torch.equal(w_a.k_scale_ext, w_b.k_scale_ext))

    def test_fused_python_ref_matches_inline(self):
        w_a, kv_a = _mk_writer(flag_on_minmax=(self.k_min, self.k_max))
        os.environ[pw._FUSED_WRITER_ENV] = "1"
        w_b, kv_b = _mk_writer(flag_on_minmax=(self.k_min, self.k_max))
        key = _keys_in_range(BS, self.k_min, self.k_max)
        val = torch.randn(BS, H, D, dtype=torch.bfloat16)
        for w, kv, fused in ((w_a, kv_a, "0"), (w_b, kv_b, "1")):
            os.environ[pw._FUSED_WRITER_ENV] = fused
            w.ensure_seq_state(seq_id=0, device=torch.device("cpu"))
            slot_idx_t = torch.tensor([w._slot_map[0]], dtype=torch.long)
            for t in range(BS):
                w.write_decode_batched(
                    key=key[t:t + 1], value=val[t:t + 1], kv_cache=kv,
                    slot_mapping=torch.tensor([t]), slot_idx_t=slot_idx_t,
                    pre_synced=True,
                )
        self.assertEqual(w_b.k_protect_ext.dtype, torch.uint8)
        self.assertTrue(torch.equal(w_a.k_protect_ext, w_b.k_protect_ext))
        self.assertTrue(torch.equal(kv_a[0], kv_b[0]))

    def test_dump_block_records_dequanted_bf16_with_marker(self):
        with tempfile.TemporaryDirectory() as td:
            dump = os.path.join(td, "s1.pt")
            os.environ[pw._DUMP_ENV] = dump
            w, kv_cache = _mk_writer(flag_on_minmax=(self.k_min, self.k_max))
            key = _keys_in_range(BS, self.k_min, self.k_max)
            val = torch.randn(BS, H, D, dtype=torch.bfloat16)
            w.write(key, val, kv_cache, torch.arange(BS))
            ev = torch.load(dump, weights_only=True)
            self.assertGreaterEqual(len(ev), 1)
            e0 = ev[0]
            self.assertEqual(e0["k_protect_format"], pw._PROT_INT8_FORMAT)
            self.assertEqual(e0["k_protect"].dtype, torch.bfloat16)
            expect = pw.prot_int8_dequantize(
                w.k_protect_ext[0], w._prot_qmin, w._prot_qscale,
                torch.bfloat16)
            self.assertTrue(torch.equal(e0["k_protect"], expect))

    def test_dump_block_flag_off_marker(self):
        os.environ.pop(pw._PROT_INT8_ENV)
        with tempfile.TemporaryDirectory() as td:
            dump = os.path.join(td, "s1.pt")
            os.environ[pw._DUMP_ENV] = dump
            w, kv_cache = _mk_writer()
            key = torch.randn(BS, H, D, dtype=torch.bfloat16)
            val = torch.randn(BS, H, D, dtype=torch.bfloat16)
            w.write(key, val, kv_cache, torch.arange(BS))
            ev = torch.load(dump, weights_only=True)
            self.assertEqual(ev[0]["k_protect_format"], pw._PROT_BF16_FORMAT)
            self.assertTrue(torch.equal(ev[0]["k_protect"],
                                        w.k_protect_ext[0]))


class TestArtifactLoaderAndFallback(_EnvHygiene):
    """Acceptance 3 + 7 (loader half): v2 round-trips; v1/bare/missing
    return None; flag-on with a v1 artifact falls back loudly to bf16."""

    def _save_artifact(self, td, payload):
        path = os.path.join(td, "mask.pt")
        torch.save(payload, path)
        os.environ[pw._PROTECT_MASK_ENV] = path
        return path

    def _mask3d(self, L=2):
        return torch.stack([_mk_mask() for _ in range(L)])

    def test_v2_artifact_roundtrip(self):
        k_min, k_max = _mk_minmax()
        with tempfile.TemporaryDirectory() as td:
            self._save_artifact(td, {
                "mask": self._mask3d(),
                "artifact_version": 2,
                "k_min": torch.stack([k_min, k_min + 1]).to(torch.float16),
                "k_max": torch.stack([k_max, k_max + 1]).to(torch.float16),
                "minmax_margin": 1.1,
            })
            got = pw.load_protect_minmax_for_layer(1)
            self.assertIsNotNone(got)
            lo, hi = got
            self.assertEqual(lo.dtype, torch.float32)
            self.assertEqual(lo.shape, (H, D))
            self.assertTrue(torch.equal(
                lo, (k_min + 1).to(torch.float16).float()))
            self.assertTrue(torch.equal(
                hi, (k_max + 1).to(torch.float16).float()))

    def test_v1_artifact_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            self._save_artifact(td, {"mask": self._mask3d()})
            self.assertIsNone(pw.load_protect_minmax_for_layer(0))

    def test_bare_tensor_artifact_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            self._save_artifact(td, self._mask3d())
            self.assertIsNone(pw.load_protect_minmax_for_layer(0))

    def test_missing_file_returns_none(self):
        os.environ[pw._PROTECT_MASK_ENV] = "/nonexistent/no_artifact.pt"
        self.assertIsNone(pw.load_protect_minmax_for_layer(0))

    def test_malformed_v2_raises(self):
        with tempfile.TemporaryDirectory() as td:
            self._save_artifact(td, {
                "mask": self._mask3d(),
                "k_min": torch.zeros(H, D),       # 2D: missing layer dim
                "k_max": torch.ones(H, D),
            })
            with self.assertRaises(ValueError):
                pw.load_protect_minmax_for_layer(0)
            self._save_artifact(td, {
                "mask": self._mask3d(),
                "k_min": "not a tensor",
                "k_max": torch.ones(2, H, D),
            })
            with self.assertRaises(TypeError):
                pw.load_protect_minmax_for_layer(0)
            k_min, k_max = _mk_minmax()
            self._save_artifact(td, {
                "mask": self._mask3d(),
                "k_min": torch.stack([k_min, k_min]),
                "k_max": torch.stack([k_max, k_max]),
            })
            with self.assertRaises(IndexError):
                pw.load_protect_minmax_for_layer(5)

    def test_flag_on_v1_artifact_warns_and_stays_bf16(self):
        os.environ[pw._PROT_INT8_ENV] = "1"
        with tempfile.TemporaryDirectory() as td:
            self._save_artifact(td, {"mask": self._mask3d()})
            w = pw.PagedKVWriter(layer_idx=0)     # mask + minmax from artifact
            kv_cache = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8)
            with self.assertLogs(pw.logger, level="WARNING") as cm:
                w._lazy_alloc(kv_cache)
            self.assertTrue(any("k_min/k_max" in m for m in cm.output))
            self.assertFalse(w._prot_int8_active)
            self.assertEqual(w.k_protect_ext.dtype, torch.bfloat16)

    def test_flag_on_v2_artifact_activates(self):
        os.environ[pw._PROT_INT8_ENV] = "1"
        k_min, k_max = _mk_minmax()
        with tempfile.TemporaryDirectory() as td:
            self._save_artifact(td, {
                "mask": self._mask3d(),
                "artifact_version": 2,
                "k_min": torch.stack([k_min, k_min]).to(torch.float16),
                "k_max": torch.stack([k_max, k_max]).to(torch.float16),
                "minmax_margin": 1.1,
            })
            w = pw.PagedKVWriter(layer_idx=0)
            kv_cache = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8)
            w._lazy_alloc(kv_cache)
            self.assertTrue(w._prot_int8_active)
            self.assertEqual(w.k_protect_ext.dtype, torch.uint8)
            pd = w.protected_d_per_head
            expect_qmin = torch.gather(
                k_min.to(torch.float16).float(), 1, pd)
            self.assertTrue(torch.equal(w._prot_qmin, expect_qmin))


class TestCalibrationEmit(_EnvHygiene):
    """Acceptance 7 (emit half): accumulator min/max + widen semantics +
    artifact stacking, without a GPU or vllm."""

    def test_accumulator_tracks_signed_minmax(self):
        cal = _load_script_module("calibrate_phase5b_protect_mask")
        acc = cal.CalibrationAccumulator()
        b1 = torch.tensor([[[1.0, -2.0]], [[3.0, 0.5]]])    # (T=2, H=1, D=2)
        b2 = torch.tensor([[[-5.0, 4.0]], [[2.0, -1.0]]])
        acc.update("layer0", b1)
        acc.update("layer0", b2)
        self.assertTrue(torch.equal(
            acc.layer_min["layer0"], torch.tensor([[-5.0, -2.0]])))
        self.assertTrue(torch.equal(
            acc.layer_max["layer0"], torch.tensor([[3.0, 4.0]])))
        self.assertTrue(torch.equal(
            acc.layer_maxabs["layer0"], torch.tensor([[5.0, 4.0]])))

    def test_widen_minmax_semantics(self):
        cal = _load_script_module("calibrate_phase5b_protect_mask")
        k_min = torch.tensor([[-1.0, 2.0]])
        k_max = torch.tensor([[3.0, 2.0]])      # ranges: 4.0, 0.0
        lo, hi = cal._widen_minmax(k_min, k_max, 1.1)
        self.assertTrue(torch.allclose(lo, torch.tensor([[-1.4, 2.0]])))
        self.assertTrue(torch.allclose(hi, torch.tensor([[3.4, 2.0]])))
        lo1, hi1 = cal._widen_minmax(k_min, k_max, 1.0)
        self.assertTrue(torch.equal(lo1, k_min) and torch.equal(hi1, k_max))
        with self.assertRaises(ValueError):
            cal._widen_minmax(k_min, k_max, 0.9)

    def test_build_minmax_from_accumulator(self):
        cal = _load_script_module("calibrate_phase5b_protect_mask")
        acc = cal.CalibrationAccumulator()
        acc.update("a", torch.randn(4, H, D))
        acc.update("b", torch.randn(4, H, D) * 2)
        k_min, k_max = cal._build_minmax_from_accumulator(acc, 1.1)
        self.assertEqual(k_min.shape, (2, H, D))
        self.assertEqual(k_min.dtype, torch.float16)
        self.assertTrue(bool((k_max.float() >= k_min.float()).all()))
        # Widened bounds sit strictly outside the observed ones where
        # the range is non-degenerate.
        raw_min = acc.layer_min["a"]
        self.assertTrue(bool((k_min[0].float() <= raw_min + 1e-3).all()))

    def test_end_to_end_artifact_feeds_writer(self):
        """Calibration-shaped artifact (stacked widened minmax + mask)
        -> writer activates and quantizes with the gathered constants."""
        cal = _load_script_module("calibrate_phase5b_protect_mask")
        acc = cal.CalibrationAccumulator()
        torch.manual_seed(3)
        for _ in range(3):
            acc.update("l0", torch.randn(16, H, D) * 3)
        k_min, k_max = cal._build_minmax_from_accumulator(acc, 1.1)
        os.environ[pw._PROT_INT8_ENV] = "1"
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "mask.pt")
            torch.save({
                "mask": torch.stack([_mk_mask()]),
                "artifact_version": 2,
                "k_min": k_min, "k_max": k_max, "minmax_margin": 1.1,
            }, path)
            os.environ[pw._PROTECT_MASK_ENV] = path
            w = pw.PagedKVWriter(layer_idx=0)
            kv_cache = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8)
            w._lazy_alloc(kv_cache)
            self.assertTrue(w._prot_int8_active)
            # Calibration-corpus values (inside the widened range)
            # roundtrip within scale/2.
            key = _keys_in_range(
                BS, acc.layer_min["l0"], acc.layer_max["l0"], seed=4)
            val = torch.randn(BS, H, D, dtype=torch.bfloat16)
            w.write(key, val, kv_cache, torch.arange(BS))
            view = w.get_packed_view(torch.tensor([0]), kv_cache)
            gathered = torch.gather(
                key, -1,
                w.protected_d_per_head.unsqueeze(0).expand(BS, -1, -1))
            err = (view["k_protect_bf16"][0].float() - gathered.float()).abs()
            bound = (w._prot_qscale * 0.5).unsqueeze(0) \
                + 0.01 * gathered.float().abs() + 1e-3
            self.assertTrue(bool((err <= bound).all()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
