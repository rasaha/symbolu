"""Phase 6K.18 — CPU tests for chunked prefill (int4_protected).

What is provable on CPU (and therefore pinned here), per
PHASE6K18_CHUNKED_PREFILL_DESIGN.md:

  1. MACHINERY BYTE-GATE (the CPU analog of pod gate G2): the same
     tokens written monolithically vs split across chunk-shaped write()
     calls produce BYTE-IDENTICAL finalized blocks (packed K nibbles +
     scale + xmin + protect), byte-identical per-token V sidecars, and a
     byte-identical staged K tail. K quant is block-local (group ==
     block == 32), so chunk boundaries must be invisible in storage.
     Verified raw-bf16 AND prot-int8 (6N).

  2. D1 TAIL SPLICE on the REAL writer: chunk 2's context rebuild takes
     the staged leg (exact bf16) while the boundary block is mid-stage,
     and the finalized leg (bounded quant residual) after a later chunk
     completes it; never-finalized + unstaged refuses loudly.

  3. D2 IDENTITY CONTRACT: run_prefix_prefill resolves SeqStates via the
     6B.2 prefill rid stash and REFUSES loudly when the stash (or the
     SeqState) is missing; the write-partition + decode-resolve refusals
     extend C-ID to chunked_active; the default (un-armed) path keeps
     the 6K.16 alignment rail verbatim.

  4. MIXED-STEP partitioning (decode rows + chunk segments in one batch,
     a shape only the chunked scheduler builds): prefill segments map to
     [0, npt), decode rows to npt+i; pure-decode/pure-prefill shapes are
     byte-identical to pre-6K.18 (with_ctx defaults off).

  5. GC exemption: a mid-chunked-prefill SeqState (prefill_open) is not
     evicted by pure-decode GC under chunked_active; cleared on first
     decode appearance; non-chunked GC behavior unchanged.

  6. Hook stash split: mixed steps split rids at num_prefills
     (prefills-first batch order); pure steps unchanged.

What is NOT provable here and stays a pod gate: end-to-end chunked
output vs monolithic (G3), needle at util 0.85 (G4), mixed-batch TTFT
(G5), APC+chunked + prot-int8 cells (G6). See the design doc's gate
checklist — the factory keeps a construction-time warning until those
are green.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT_CANDIDATES = [
    Path("/workspace/symbolu/CTM_plus"),
    Path("/home/user/symbolu/CTM_plus"),
    Path(__file__).resolve().parent.parent,
]
for _root in ROOT_CANDIDATES:
    kvp = _root / "KVPolicy"
    candidate = kvp if kvp.is_dir() else _root
    if (candidate / "kv_policy").is_dir():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        break

import torch  # noqa: E402

from kv_policy import phase5b_4c_paged_writer as pw  # noqa: E402
from kv_policy import phase6k16_prefix_prefill as pp  # noqa: E402
from kv_policy import phase6b2_precapture_hook as hook  # noqa: E402

NB, BS, H, D, N_PROT, G = 12, 32, 2, 128, 5, 32

_MANAGED_ENVS = (
    pw._PROT_INT8_ENV,
    "INT4_PROTECTED_ALLOW_CHUNKED_PREFILL",
    "PHASE6K14_EVICT_ON_DECODE",
    "PHASE6K9_RESET_ON_PREFILL",
)


def _mk_mask():
    mask = torch.zeros((H, D), dtype=torch.int8)
    mask[0, [3, 17, 40, 90, 127]] = 1
    mask[1, [0, 5, 64, 100, 126]] = 1
    return mask


def _mk_minmax(seed: int = 1):
    g = torch.Generator().manual_seed(seed)
    center = torch.randn((H, D), generator=g)
    half = torch.rand((H, D), generator=g) * 4.0 + 0.5
    return center - half, center + half


def _mk_writer(prot_minmax=None):
    w = pw.PagedKVWriter(
        layer_idx=0,
        protect_mask=_mk_mask(),
        protect_minmax=prot_minmax,
    )
    kv_cache = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8)
    w._lazy_alloc(kv_cache)
    return w, kv_cache


def _mk_kv(T: int, seed: int = 2):
    g = torch.Generator().manual_seed(seed)
    k = (torch.randn((T, H, D), generator=g) * 3).to(torch.bfloat16)
    v = torch.randn((T, H, D), generator=g).to(torch.bfloat16)
    return k, v


def _write_chunks(w, kv_cache, key, value, boundaries, seq_id=5,
                  first_slot=0):
    """Write key/value via chunk-shaped write() calls. ``boundaries``
    are the chunk end offsets, e.g. [44, 80] = chunks [0:44), [44:80).
    Same seq_id every chunk — the 6K.16c rid contract chunking rides on.
    """
    start = 0
    for end in boundaries:
        sl = torch.arange(first_slot + start, first_slot + end,
                          dtype=torch.long)
        w.write(key=key[start:end], value=value[start:end],
                kv_cache=kv_cache, slot_mapping=sl, seq_id=seq_id)
        start = end


class _Hygiene(unittest.TestCase):
    def setUp(self):
        self._saved = {e: os.environ.pop(e, None) for e in _MANAGED_ENVS}
        pw.set_chunked_active(False)
        pw.set_apc_active(False)

    def tearDown(self):
        for e, v in self._saved.items():
            if v is None:
                os.environ.pop(e, None)
            else:
                os.environ[e] = v
        pw.set_chunked_active(False)
        pw.set_apc_active(False)


# --------------------------------------------------------------------- #
# 1. Machinery byte-gate (CPU analog of pod gate G2).
# --------------------------------------------------------------------- #

class TestChunkedWriteByteExact(_Hygiene):
    """Same 32 tokens => identical bytes, regardless of chunk boundaries.
    This is the design's S1-class invariant: K quant is block-local, the
    staging buffer spans write() calls, V/protect are per-token."""

    T = 80          # blocks 0,1 full; block 2 partial (16 rows)

    def _assert_storage_equal(self, wa, kva, wb, kvb, *, tail_rows=16):
        # Finalized K blocks: packed nibbles + scale + xmin byte-equal.
        self.assertTrue(bool((kva[0, :2] == kvb[0, :2]).all()),
                        "packed K nibbles differ across chunking")
        for name in ("k_scale_ext", "k_xmin_ext"):
            a, b = getattr(wa, name)[:2], getattr(wb, name)[:2]
            self.assertTrue(bool((a == b).all()), f"{name} differs")
        # Per-token sidecars: cover the partial block's written rows too.
        self.assertTrue(bool(
            (wa.k_protect_ext[:2] == wb.k_protect_ext[:2]).all()
            and (wa.k_protect_ext[2, :tail_rows]
                 == wb.k_protect_ext[2, :tail_rows]).all()),
            "k_protect differs")
        for name in ("v_scale_ext", "v_xmin_ext"):
            a, b = getattr(wa, name), getattr(wb, name)
            self.assertTrue(bool(
                (a[:2] == b[:2]).all()
                and (a[2, :tail_rows] == b[2, :tail_rows]).all()),
                f"{name} differs")
        self.assertTrue(bool(
            (kva[1, :2] == kvb[1, :2]).all()
            and (kva[1, 2, :tail_rows] == kvb[1, 2, :tail_rows]).all()),
            "packed V differs")
        # Staged tail state: identical buffer rows + counters.
        sa, sb = wa.get_seq_state(5), wb.get_seq_state(5)
        self.assertEqual(sa.k_stage_block_id, sb.k_stage_block_id)
        self.assertEqual(sa.k_stage_count, sb.k_stage_count)
        self.assertTrue(bool(
            (sa.k_stage[:tail_rows] == sb.k_stage[:tail_rows]).all()),
            "staged K tail differs")

    def test_two_chunk_split_mid_block(self):
        key, val = _mk_kv(self.T)
        wa, kva = _mk_writer()
        _write_chunks(wa, kva, key, val, [self.T])           # monolithic
        wb, kvb = _mk_writer()
        _write_chunks(wb, kvb, key, val, [44, self.T])       # 44 = mid-block
        self._assert_storage_equal(wa, kva, wb, kvb)

    def test_three_chunk_odd_boundaries(self):
        key, val = _mk_kv(self.T, seed=3)
        wa, kva = _mk_writer()
        _write_chunks(wa, kva, key, val, [self.T])
        wb, kvb = _mk_writer()
        _write_chunks(wb, kvb, key, val, [7, 39, self.T])    # 2 mid-block cuts
        self._assert_storage_equal(wa, kva, wb, kvb)

    def test_chunk1_leaves_boundary_block_unfinalized(self):
        # The premise of the staged leg: after chunk 1, the boundary
        # block's K is ONLY in staging (cache scale still zero-init).
        key, val = _mk_kv(self.T)
        w, kv = _mk_writer()
        _write_chunks(w, kv, key, val, [44])
        self.assertFalse(bool((w.k_scale_ext[1].float() != 0).any()),
                         "boundary block unexpectedly finalized by chunk 1")
        st = w.get_seq_state(5)
        self.assertEqual(st.k_stage_block_id, 1)
        self.assertEqual(st.k_stage_count, 12)
        self.assertTrue(bool((st.k_stage[:12] == key[32:44]).all()),
                        "staged rows are not the exact bf16 inputs")

    def test_prot_int8_byte_exact_across_chunks(self):
        # 6N interaction at the storage level (pod gate G6's CPU analog).
        os.environ[pw._PROT_INT8_ENV] = "1"
        key, val = _mk_kv(self.T, seed=4)
        wa, kva = _mk_writer(prot_minmax=_mk_minmax())
        _write_chunks(wa, kva, key, val, [self.T])
        wb, kvb = _mk_writer(prot_minmax=_mk_minmax())
        _write_chunks(wb, kvb, key, val, [44, self.T])
        self.assertTrue(wa._prot_int8_active and wb._prot_int8_active,
                        "prot-int8 did not activate (env+minmax both set)")
        self.assertEqual(wa.k_protect_ext.dtype, torch.uint8)
        self._assert_storage_equal(wa, kva, wb, kvb)


# --------------------------------------------------------------------- #
# 2. D1 tail splice on the real writer.
# --------------------------------------------------------------------- #

class TestGatherContextTailRealWriter(_Hygiene):

    def test_staged_leg_exact_after_chunk1(self):
        key, val = _mk_kv(80)
        w, kv = _mk_writer()
        _write_chunks(w, kv, key, val, [44])
        bt = torch.arange(NB, dtype=torch.int32)
        k_ctx, v_ctx = pp.gather_context_kv(
            kv, w, bt, 44, torch.bfloat16,
            state=w.get_seq_state(5), allow_tail=True)
        self.assertEqual(tuple(k_ctx.shape), (44, H, D))
        # Tail rows: bit-equal to the original bf16 keys (the staged leg).
        self.assertTrue(bool((k_ctx[32:] == key[32:44]).all()))
        # Full block 0 protect channels: exact (raw-bf16 sidecar).
        idx = w.protected_d_per_head
        got = torch.gather(k_ctx[:32], -1,
                           idx.view(1, H, N_PROT).expand(32, -1, -1))
        want = torch.gather(key[:32], -1,
                            idx.view(1, H, N_PROT).expand(32, -1, -1))
        self.assertTrue(bool((got == want).all()))

    def test_finalized_leg_after_chunk2(self):
        key, val = _mk_kv(80)
        w, kv = _mk_writer()
        _write_chunks(w, kv, key, val, [44, 80])
        # Chunk 2 completed block 1 (finalized) and staged block 2;
        # ctx=44 now takes the finalized leg for the 12 tail rows.
        st = w.get_seq_state(5)
        self.assertEqual(st.k_stage_block_id, 2)
        bt = torch.arange(NB, dtype=torch.int32)
        k_ctx, _ = pp.gather_context_kv(
            kv, w, bt, 44, torch.bfloat16, state=st, allow_tail=True)
        expect = pp.dequant_k_blocks(
            kv[0, 1:2, :, :, :D // 2],
            w.k_scale_ext[1:2], w.k_xmin_ext[1:2],
            w.k_protect_ext[1:2], w.protected_d_per_head,
        )[0, :12].to(torch.bfloat16)
        self.assertTrue(bool((k_ctx[32:] == expect).all()),
                        "finalized leg != boundary-block dequant")
        # Bounded residual vs the true keys (not bit-exact — quantized).
        scale = w.k_scale_ext[1].float()
        err = (k_ctx[32:].float() - key[32:44].float()).abs()
        tol = (0.55 * scale + 1e-2).unsqueeze(0) \
            + 0.02 * key[32:44].float().abs()
        self.assertTrue(bool((err <= tol).all()),
                        f"residual above quant bound: max={err.max():.4f}")

    def test_never_finalized_unstaged_refused(self):
        w, kv = _mk_writer()
        key, val = _mk_kv(44)
        _write_chunks(w, kv, key, val, [44])
        # Lie about the block table: point the tail at an unwritten block.
        bt = torch.tensor([0, 9, 0, 0], dtype=torch.int32)
        with self.assertRaises(RuntimeError) as cm:
            pp.gather_context_kv(kv, w, bt, 44, torch.bfloat16,
                                 state=None, allow_tail=True)
        self.assertIn("never finalized", str(cm.exception))

    def test_unarmed_callers_keep_the_apc_rail(self):
        w, kv = _mk_writer()
        key, val = _mk_kv(44)
        _write_chunks(w, kv, key, val, [44])
        bt = torch.arange(NB, dtype=torch.int32)
        with self.assertRaises(RuntimeError) as cm:
            pp.gather_context_kv(kv, w, bt, 44, torch.bfloat16,
                                 state=w.get_seq_state(5))
        self.assertIn("not a multiple of", str(cm.exception))


# --------------------------------------------------------------------- #
# 3. run_prefix_prefill rid plumbing + refusals (D2).
# --------------------------------------------------------------------- #

class _VarlenCapture:
    def __init__(self):
        self.calls = []

    def __call__(self, **kw):
        self.calls.append(kw)
        # out= is pre-allocated by the caller; leave it zeros.


def _mk_prefill_meta(ctx_list, q_lens, bt_rows):
    qsl = [0]
    for q in q_lens:
        qsl.append(qsl[-1] + q)
    return SimpleNamespace(
        context_lens_tensor=torch.tensor(ctx_list, dtype=torch.int32),
        block_tables=torch.tensor(bt_rows, dtype=torch.int32),
        query_start_loc=torch.tensor(qsl, dtype=torch.int32),
        max_query_len=max(q_lens),
    )


class TestRunPrefixPrefillPlumbing(_Hygiene):

    def _run(self, w, kv, pm, am, q_total):
        cap = _VarlenCapture()
        q = torch.zeros((q_total, H, D), dtype=torch.bfloat16)
        nk, nv = _mk_kv(q_total, seed=9)
        pp.run_prefix_prefill(
            query=q, new_key=nk, new_value=nv, kv_cache=kv, writer=w,
            prefill_meta=pm, flash_attn_varlen_func=cap,
            softmax_scale=1.0, window_size=(-1, -1), alibi_slopes=None,
            logits_soft_cap=None, out=torch.zeros_like(q), fa_version=2,
            attn_metadata=am,
        )
        return cap, nk

    def test_tail_spliced_into_varlen_k(self):
        pw.set_chunked_active(True)
        key, val = _mk_kv(80)
        w, kv = _mk_writer()
        _write_chunks(w, kv, key, val, [44])      # chunk 1 written
        pm = _mk_prefill_meta([44], [36], [list(range(NB))])
        am = SimpleNamespace()
        setattr(am, pw._REAL_SEQ_IDS_PREFILL_ATTR, [5])
        cap, nk = self._run(w, kv, pm, am, 36)
        self.assertEqual(len(cap.calls), 1)
        k_full = cap.calls[0]["k"]
        cu_k = cap.calls[0]["cu_seqlens_k"]
        self.assertEqual(cu_k.tolist(), [0, 44 + 36])
        self.assertTrue(bool((k_full[32:44] == key[32:44]).all()),
                        "staged tail rows not spliced exactly")
        self.assertTrue(bool((k_full[44:] == nk).all()),
                        "new (in-batch) K rows misplaced")

    def test_refuses_without_stash(self):
        pw.set_chunked_active(True)
        key, val = _mk_kv(44)
        w, kv = _mk_writer()
        _write_chunks(w, kv, key, val, [44])
        pm = _mk_prefill_meta([44], [8], [list(range(NB))])
        with self.assertRaises(RuntimeError) as cm:
            self._run(w, kv, pm, SimpleNamespace(), 8)
        self.assertIn("real-seq-id stash unavailable", str(cm.exception))

    def test_refuses_unknown_rid(self):
        pw.set_chunked_active(True)
        key, val = _mk_kv(44)
        w, kv = _mk_writer()
        _write_chunks(w, kv, key, val, [44])
        pm = _mk_prefill_meta([44], [8], [list(range(NB))])
        am = SimpleNamespace()
        setattr(am, pw._REAL_SEQ_IDS_PREFILL_ATTR, [999])  # never wrote
        with self.assertRaises(RuntimeError) as cm:
            self._run(w, kv, pm, am, 8)
        self.assertIn("no SeqState", str(cm.exception))

    def test_unarmed_tail_hits_original_rail(self):
        # chunked_active False + no env: the 6K.16 alignment refusal.
        key, val = _mk_kv(44)
        w, kv = _mk_writer()
        _write_chunks(w, kv, key, val, [44])
        pm = _mk_prefill_meta([44], [8], [list(range(NB))])
        am = SimpleNamespace()
        setattr(am, pw._REAL_SEQ_IDS_PREFILL_ATTR, [5])
        with self.assertRaises(RuntimeError) as cm:
            self._run(w, kv, pm, am, 8)
        self.assertIn("not a multiple of", str(cm.exception))

    def test_aligned_ctx_never_touches_stash(self):
        # Pure APC shape (aligned ctx): no stash, no chunked flag — must
        # run exactly as before 6K.18 (zero new requirements).
        key, val = _mk_kv(64)
        w, kv = _mk_writer()
        _write_chunks(w, kv, key, val, [64])      # 2 full blocks
        pm = _mk_prefill_meta([64], [8], [list(range(NB))])
        cap, nk = self._run(w, kv, pm, SimpleNamespace(), 8)
        self.assertEqual(cap.calls[0]["cu_seqlens_k"].tolist(), [0, 72])


# --------------------------------------------------------------------- #
# 4. GC exemption for mid-chunked-prefill sequences.
# --------------------------------------------------------------------- #

class TestGcChunkedExemption(_Hygiene):

    def _writer_with_states(self):
        w, kv = _mk_writer()
        dev = kv.device
        w.ensure_seq_state(1, dev)
        w.ensure_seq_state(2, dev)
        return w

    def test_prefill_open_exempt_under_chunked(self):
        os.environ["PHASE6K14_EVICT_ON_DECODE"] = "1"
        pw.set_chunked_active(True)
        w = self._writer_with_states()
        w.mark_prefill_open(1)
        freed = w.gc_completed_slots([2])
        self.assertEqual(freed, 0)
        self.assertIn(1, w._seq_states)

    def test_cleared_on_first_decode_appearance(self):
        os.environ["PHASE6K14_EVICT_ON_DECODE"] = "1"
        pw.set_chunked_active(True)
        w = self._writer_with_states()
        w.mark_prefill_open(1)
        w.gc_completed_slots([1, 2])     # seq 1 decoding now -> closed
        self.assertFalse(w.get_seq_state(1).prefill_open)
        freed = w.gc_completed_slots([2])
        self.assertEqual(freed, 1)
        self.assertNotIn(1, w._seq_states)

    def test_non_chunked_gc_unchanged(self):
        os.environ["PHASE6K14_EVICT_ON_DECODE"] = "1"
        # chunked_active False: prefill_open gives no exemption.
        w = self._writer_with_states()
        w.mark_prefill_open(1)
        freed = w.gc_completed_slots([2])
        self.assertEqual(freed, 1)
        self.assertNotIn(1, w._seq_states)


# --------------------------------------------------------------------- #
# 5. Hook stash split (mixed chunked steps).
# --------------------------------------------------------------------- #

class TestHookStashSplit(_Hygiene):

    def test_mixed_step_splits_at_num_prefills(self):
        am = SimpleNamespace(num_prefills=2)
        hook.stash_real_seq_ids_split(am, [10, 11, 20, 21, 22], False)
        self.assertEqual(getattr(am, pw._REAL_SEQ_IDS_PREFILL_ATTR),
                         [10, 11])
        self.assertEqual(getattr(am, pw._REAL_SEQ_IDS_ATTR), [20, 21, 22])

    def test_pure_prefill_unsplit(self):
        am = SimpleNamespace(num_prefills=2)
        hook.stash_real_seq_ids_split(am, [10, 11], False)
        self.assertEqual(getattr(am, pw._REAL_SEQ_IDS_PREFILL_ATTR),
                         [10, 11])
        self.assertFalse(hasattr(am, pw._REAL_SEQ_IDS_ATTR))

    def test_pure_decode_unsplit(self):
        am = SimpleNamespace(num_prefills=0)
        hook.stash_real_seq_ids_split(am, [20, 21], True)
        self.assertEqual(getattr(am, pw._REAL_SEQ_IDS_ATTR), [20, 21])
        self.assertFalse(hasattr(am, pw._REAL_SEQ_IDS_PREFILL_ATTR))

    def test_none_ids_no_attrs(self):
        am = SimpleNamespace(num_prefills=1)
        hook.stash_real_seq_ids_split(am, None, False)
        self.assertFalse(hasattr(am, pw._REAL_SEQ_IDS_ATTR))
        self.assertFalse(hasattr(am, pw._REAL_SEQ_IDS_PREFILL_ATTR))


# --------------------------------------------------------------------- #
# 6. Mixed-step write partitioning.
# --------------------------------------------------------------------- #

def _mk_mixed_metadata(q_lens, ctx_list, n_dec, pre_ids, dec_ids):
    qsl = [0]
    for q in q_lens:
        qsl.append(qsl[-1] + q)
    pre = SimpleNamespace(
        query_start_loc=torch.tensor(qsl, dtype=torch.int32),
        context_lens_tensor=torch.tensor(ctx_list, dtype=torch.int32),
    )
    dec = SimpleNamespace(
        block_tables=torch.zeros((n_dec, 4), dtype=torch.int32),
        seq_lens_tensor=torch.tensor([40] * n_dec, dtype=torch.int32),
    ) if n_dec else None
    am = SimpleNamespace(prefill_metadata=pre, decode_metadata=dec)
    if pre_ids is not None:
        setattr(am, pw._REAL_SEQ_IDS_PREFILL_ATTR, pre_ids)
    if dec_ids is not None:
        setattr(am, pw._REAL_SEQ_IDS_ATTR, dec_ids)
    return am


class TestDeriveWritePartitionsMixed(_Hygiene):

    def _derive(self, am, n_tokens, **kw):
        from kv_policy.phase5b_backend_install import (
            _derive_write_partitions,
        )
        sm = torch.arange(n_tokens, dtype=torch.long)
        return _derive_write_partitions(am, sm, BS, **kw)

    def test_mixed_step_partitions(self):
        am = _mk_mixed_metadata([5, 4], [44, 0], 3,
                                [101, 102], [201, 202, 203])
        parts = self._derive(am, 12, with_ctx=True)
        self.assertEqual(parts, [
            (101, slice(0, 5), 44),
            (102, slice(5, 9), 0),
            (201, slice(9, 10), -1),
            (202, slice(10, 11), -1),
            (203, slice(11, 12), -1),
        ])

    def test_mixed_single_prefill_segment(self):
        # qsl has only 2 entries -> the single-seg path must still cap
        # the prefill partition at npt (not the whole flat batch).
        am = _mk_mixed_metadata([9], [44], 2, [101], [201, 202])
        parts = self._derive(am, 11, with_ctx=True)
        self.assertEqual(parts, [
            (101, slice(0, 9), 44),
            (201, slice(9, 10), -1),
            (202, slice(10, 11), -1),
        ])

    def test_default_return_shape_is_two_tuples(self):
        am = _mk_mixed_metadata([5, 4], [44, 0], 0, [101, 102], None)
        am.decode_metadata = None
        parts = self._derive(am, 9)
        self.assertEqual(parts, [(101, slice(0, 5)), (102, slice(5, 9))])

    def test_pure_decode_unchanged(self):
        am = _mk_mixed_metadata([1], [0], 3, None, [201, 202, 203])
        am.prefill_metadata = None
        parts = self._derive(am, 3)
        self.assertEqual(parts, [(201, slice(0, 1)), (202, slice(1, 2)),
                                 (203, slice(2, 3))])

    def test_mixed_token_row_mismatch_refused(self):
        am = _mk_mixed_metadata([5], [44], 3, [101], [201, 202, 203])
        with self.assertRaises(RuntimeError) as cm:
            self._derive(am, 5 + 2)      # 2 decode tokens, 3 rows
        self.assertIn("mixed-step", str(cm.exception))

    def test_chunked_refuses_block_local_fallback(self):
        pw.set_chunked_active(True)
        am = _mk_mixed_metadata([5, 4], [44, 0], 0, None, None)
        am.decode_metadata = None
        with self.assertRaises(RuntimeError) as cm:
            self._derive(am, 9)
        self.assertIn("chunked prefill", str(cm.exception))

    def test_decode_resolve_refuses_under_chunked(self):
        pw.set_chunked_active(True)
        bt = torch.zeros((2, 4), dtype=torch.int32)
        with self.assertRaises(RuntimeError) as cm:
            pw.resolve_decode_seq_ids(SimpleNamespace(), bt,
                                      torch.tensor([40, 50]), BS,
                                      block_local=True)
        self.assertIn("chunked prefill", str(cm.exception))


# --------------------------------------------------------------------- #
# 7. Static wiring (vllm-free source checks, 6K.17-test style).
# --------------------------------------------------------------------- #

class TestBackendWiringStatics(_Hygiene):

    def _src(self):
        import kv_policy.phase5b_backend_install as bi
        return Path(bi.__file__).read_text()

    def test_arming_check_accepts_chunked(self):
        src = self._src()
        i = src.index("prefix-aware prefill reached")
        window = src[i - 2000:i]
        self.assertIn("chunked_active as _chunked_armed", window)
        self.assertIn("_allow_chunked_prefill_override()", window)

    def test_run_prefix_prefill_receives_attn_metadata(self):
        src = self._src()
        i = src.index("run_prefix_prefill(\n")
        self.assertIn("attn_metadata=attn_metadata",
                      src[i:i + 1200])

    def test_6k9_reset_gated_off_under_chunked(self):
        src = self._src()
        self.assertIn("if not _chunked_on and os.environ.get(", src)
        # And the per-segment chunked rule exists.
        self.assertIn("if _ctx == 0:", src)
        self.assertIn("mark_prefill_open", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
