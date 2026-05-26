"""Phase 6B.1 — CPU tests for PagedKVWriter.write_decode_batched + the
_is_pure_decode_write dispatch helper.

Tests:
  * `_is_pure_decode_write` returns the right verdict on representative
    `attn_metadata` shapes (pure decode, mixed, prefill-only,
    spec-decode-style multi-token-per-seq, empty).
  * `write_decode_batched` is bit-equivalent to the legacy looped
    `writer.write(seq_id=...)` for B in {1, 2, 4, 8} across Modes A/B/C
    (fresh-block partial, near-boundary handoff, mid-block handoff).
  * The new device-side counter pools (`_seq_pos_pool`,
    `_k_stage_count_pool`, `_k_stage_block_id_pool`) end in a state
    consistent with the legacy SeqState ints.

Pure CPU. No GPU, no full vLLM stack. Mirrors the structural
pattern of `verify_phase5b_4c_1_write.py`.

Run via pytest from CTM_plus/Bench:
  PYTHONPATH=../KVPolicy pytest tests/test_paged_writer_decode_batched.py -v
"""
from __future__ import annotations

import os
import sys
import tempfile

import pytest

torch = pytest.importorskip("torch")

_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_kvp_root = os.path.join(_repo_root, "KVPolicy")
if _kvp_root not in sys.path:
    sys.path.insert(0, _kvp_root)


QWEN_NUM_LAYERS = 28
H_KV       = 4
D          = 128
BS         = 32
V_GROUP    = 32
N_PROTECT  = 5
DTYPE_BF   = torch.bfloat16


@pytest.fixture(scope="module")
def protect_mask_path():
    """Build a synthetic protect-mask artifact and point PROTECT_MASK_PATH at it."""
    mask = torch.zeros((H_KV, D), dtype=torch.int8)
    mask[:, :N_PROTECT] = 1
    full = mask.unsqueeze(0).expand(QWEN_NUM_LAYERS, -1, -1).contiguous()
    fd, path = tempfile.mkstemp(suffix=".pt")
    os.close(fd)
    torch.save(full, path)
    prior = os.environ.get("PROTECT_MASK_PATH")
    os.environ["PROTECT_MASK_PATH"] = path
    yield path
    if prior is None:
        os.environ.pop("PROTECT_MASK_PATH", None)
    else:
        os.environ["PROTECT_MASK_PATH"] = prior
    os.unlink(path)


# ---------------------------------------------------------------------- #
# _is_pure_decode_write
# ---------------------------------------------------------------------- #


class _FakeDecodeMeta:
    def __init__(self, B: int, max_q: int = 1):
        self.block_tables = torch.tensor(
            [[i * 4] for i in range(B)], dtype=torch.long,
        )
        self.max_decode_query_len = max_q


class _FakePrefillMeta:
    def __init__(self, n_q: int):
        self.num_prefill_tokens = n_q


class _FakeMeta:
    def __init__(self, decode=None, prefill=None):
        self.decode_metadata = decode
        self.prefill_metadata = prefill


def test_is_pure_decode_pure_decode_B2():
    from kv_policy.phase5b_backend_install import _is_pure_decode_write
    assert _is_pure_decode_write(_FakeMeta(decode=_FakeDecodeMeta(2)), T_total=2)


def test_is_pure_decode_pure_decode_B8():
    from kv_policy.phase5b_backend_install import _is_pure_decode_write
    assert _is_pure_decode_write(_FakeMeta(decode=_FakeDecodeMeta(8)), T_total=8)


def test_is_pure_decode_spec_decode_rejects():
    from kv_policy.phase5b_backend_install import _is_pure_decode_write
    # max_decode_query_len > 1 means spec-decode-style multi-token write.
    assert not _is_pure_decode_write(
        _FakeMeta(decode=_FakeDecodeMeta(2, max_q=3)), T_total=6,
    )


def test_is_pure_decode_mixed_rejects():
    from kv_policy.phase5b_backend_install import _is_pure_decode_write
    meta = _FakeMeta(
        decode=_FakeDecodeMeta(2), prefill=_FakePrefillMeta(100),
    )
    assert not _is_pure_decode_write(meta, T_total=102)


def test_is_pure_decode_pure_prefill_rejects():
    from kv_policy.phase5b_backend_install import _is_pure_decode_write
    assert not _is_pure_decode_write(
        _FakeMeta(prefill=_FakePrefillMeta(100)), T_total=100,
    )


def test_is_pure_decode_T_mismatch_rejects():
    from kv_policy.phase5b_backend_install import _is_pure_decode_write
    # B=2 but T=4: shouldn't claim "pure decode" because the row count
    # doesn't equal the number of decode seqs.
    assert not _is_pure_decode_write(
        _FakeMeta(decode=_FakeDecodeMeta(2)), T_total=4,
    )


def test_is_pure_decode_empty_block_tables_rejects():
    from kv_policy.phase5b_backend_install import _is_pure_decode_write
    class _Empty:
        block_tables = torch.zeros((0, 0), dtype=torch.long)
        max_decode_query_len = 1
    assert not _is_pure_decode_write(_FakeMeta(decode=_Empty()), T_total=0)


def test_is_pure_decode_no_decode_meta_rejects():
    from kv_policy.phase5b_backend_install import _is_pure_decode_write
    assert not _is_pure_decode_write(_FakeMeta(), T_total=0)


def test_is_pure_decode_env_override_forces_legacy():
    """PHASE6B1_USE_DECODE_BATCHED=0 forces the gate to return False,
    routing all writes through the legacy partition + per-seq loop.
    Used by the GPU smoke to capture a pre-refactor reference cell."""
    from kv_policy.phase5b_backend_install import _is_pure_decode_write
    prior = os.environ.get("PHASE6B1_USE_DECODE_BATCHED")
    os.environ["PHASE6B1_USE_DECODE_BATCHED"] = "0"
    try:
        # Even a clean pure-decode shape returns False under override.
        assert not _is_pure_decode_write(
            _FakeMeta(decode=_FakeDecodeMeta(2)), T_total=2,
        )
    finally:
        if prior is None:
            os.environ.pop("PHASE6B1_USE_DECODE_BATCHED", None)
        else:
            os.environ["PHASE6B1_USE_DECODE_BATCHED"] = prior


def test_is_pure_decode_env_default_is_on():
    """Default behavior: when env unset, the gate returns True for a
    clean pure-decode shape. (Regression for the env-var addition.)"""
    from kv_policy.phase5b_backend_install import _is_pure_decode_write
    prior = os.environ.get("PHASE6B1_USE_DECODE_BATCHED")
    os.environ.pop("PHASE6B1_USE_DECODE_BATCHED", None)
    try:
        assert _is_pure_decode_write(
            _FakeMeta(decode=_FakeDecodeMeta(4)), T_total=4,
        )
    finally:
        if prior is not None:
            os.environ["PHASE6B1_USE_DECODE_BATCHED"] = prior


# ---------------------------------------------------------------------- #
# write_decode_batched bit-equivalence vs legacy writer.write loop
# ---------------------------------------------------------------------- #


def _make_writer():
    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter
    return PagedKVWriter(layer_idx=0, sidecar_dtype=DTYPE_BF)


def _make_kv_cache(NB=64):
    return torch.zeros((2, NB, BS, H_KV, D), dtype=torch.uint8)


def _run_equivalence(
    B: int, prefill_len: int, n_decode_steps: int, seed: int,
):
    """Run the same workload through:
      (a) legacy writer.write(seq_id=...) called B times per decode step
      (b) writer.write_decode_batched called once per decode step
    Returns dict mapping check_name -> bool (True iff bit-identical).
    """
    torch.manual_seed(seed)

    w_legacy = _make_writer()
    w_new    = _make_writer()
    kv_legacy = _make_kv_cache()
    kv_new    = kv_legacy.clone()

    seq_ids = [100 + i for i in range(B)]
    seq_base_blocks = [(i + 1) * 4 for i in range(B)]

    # Prefill — legacy single-seq path on BOTH writers (deterministic).
    for i, sid in enumerate(seq_ids):
        base_block = seq_base_blocks[i]
        slots = torch.arange(
            base_block * BS, base_block * BS + prefill_len, dtype=torch.long,
        )
        k = torch.randn(prefill_len, H_KV, D, dtype=DTYPE_BF) * 0.5
        v = torch.randn(prefill_len, H_KV, D, dtype=DTYPE_BF) * 0.5
        for w, kv in ((w_legacy, kv_legacy), (w_new, kv_new)):
            w.write(k, v, kv, slots, seq_id=sid)

    assert w_legacy._slot_map == w_new._slot_map, (
        "slot maps diverged during prefill — test setup bug"
    )
    slot_idx_t = torch.tensor(
        [w_new._slot_map[s] for s in seq_ids], dtype=torch.long,
    )

    # Decode loop — legacy and new paths.
    for step in range(n_decode_steps):
        k_step = torch.randn(B, H_KV, D, dtype=DTYPE_BF) * 0.5
        v_step = torch.randn(B, H_KV, D, dtype=DTYPE_BF) * 0.5
        slot_mapping = torch.tensor(
            [seq_base_blocks[i] * BS + prefill_len + step for i in range(B)],
            dtype=torch.long,
        )
        for i, sid in enumerate(seq_ids):
            w_legacy.write(
                k_step[i:i+1], v_step[i:i+1], kv_legacy,
                slot_mapping[i:i+1], seq_id=sid,
            )
        w_new.write_decode_batched(
            key=k_step, value=v_step, kv_cache=kv_new,
            slot_mapping=slot_mapping, slot_idx_t=slot_idx_t,
        )

    return {
        "kv_cache":         torch.equal(kv_legacy, kv_new),
        "k_scale_ext":      torch.equal(w_legacy.k_scale_ext, w_new.k_scale_ext),
        "k_xmin_ext":       torch.equal(w_legacy.k_xmin_ext, w_new.k_xmin_ext),
        "k_protect_ext":    torch.equal(w_legacy.k_protect_ext, w_new.k_protect_ext),
        "v_scale_ext":      torch.equal(w_legacy.v_scale_ext, w_new.v_scale_ext),
        "v_xmin_ext":       torch.equal(w_legacy.v_xmin_ext, w_new.v_xmin_ext),
        "bf16_k_backing":   torch.equal(w_legacy._bf16_k_backing_pool, w_new._bf16_k_backing_pool),
        "bf16_v_backing":   torch.equal(w_legacy._bf16_v_backing_pool, w_new._bf16_v_backing_pool),
        "k_stage_pool":     torch.equal(w_legacy._k_stage_pool, w_new._k_stage_pool),
    }


# Mode A: aligned prefill (prefill_len % BS == 0); decode starts on a
# fresh block boundary.
@pytest.mark.parametrize("B", [1, 2, 4, 8])
@pytest.mark.parametrize("decode_steps", [8, 32, 64])
def test_mode_A_equivalence(protect_mask_path, B, decode_steps):
    results = _run_equivalence(
        B=B, prefill_len=BS, n_decode_steps=decode_steps,
        seed=0xA000 + B * 100 + decode_steps,
    )
    failed = [name for name, ok in results.items() if not ok]
    assert not failed, f"Mode A bit-equivalence failed: {failed}"


# Mode B: prefill ends at near-block-boundary (prefill_len = BS - 1);
# the first decode token completes the prefill's partial block.
@pytest.mark.parametrize("B", [1, 2, 4, 8])
@pytest.mark.parametrize("decode_steps", [1, 32, 64])
def test_mode_B_equivalence(protect_mask_path, B, decode_steps):
    results = _run_equivalence(
        B=B, prefill_len=BS - 1, n_decode_steps=decode_steps,
        seed=0xB000 + B * 100 + decode_steps,
    )
    failed = [name for name, ok in results.items() if not ok]
    assert not failed, f"Mode B bit-equivalence failed: {failed}"


# Mode C: prefill ends mid-block (prefill_len = BS // 2); decode
# continues filling the same partial block before a block boundary
# fires.
@pytest.mark.parametrize("B", [1, 2, 4, 8])
@pytest.mark.parametrize("decode_steps", [1, 32, 64])
def test_mode_C_equivalence(protect_mask_path, B, decode_steps):
    results = _run_equivalence(
        B=B, prefill_len=BS // 2, n_decode_steps=decode_steps,
        seed=0xC000 + B * 100 + decode_steps,
    )
    failed = [name for name, ok in results.items() if not ok]
    assert not failed, f"Mode C bit-equivalence failed: {failed}"


# ---------------------------------------------------------------------- #
# Pool counter state checks
# ---------------------------------------------------------------------- #


def test_seq_pos_pool_advances_with_active_mask(protect_mask_path):
    """Active sequences advance seq_pos_pool by 1 per write_decode_batched
    call; inactive (slot_mapping < 0) do not."""
    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter

    torch.manual_seed(0xACE)
    w = PagedKVWriter(layer_idx=0, sidecar_dtype=DTYPE_BF)
    kv = _make_kv_cache()
    B = 4
    seq_ids = list(range(200, 200 + B))
    # Prefill all seqs by BS tokens each so they share state shape.
    for i, sid in enumerate(seq_ids):
        base = (i + 1) * 4
        slots = torch.arange(base * BS, base * BS + BS, dtype=torch.long)
        k = torch.randn(BS, H_KV, D, dtype=DTYPE_BF) * 0.5
        v = torch.randn(BS, H_KV, D, dtype=DTYPE_BF) * 0.5
        w.write(k, v, kv, slots, seq_id=sid)
    slot_idx_t = torch.tensor(
        [w._slot_map[s] for s in seq_ids], dtype=torch.long,
    )
    # One decode call with seq 2 marked INACTIVE (slot_mapping = -1).
    k_step = torch.randn(B, H_KV, D, dtype=DTYPE_BF) * 0.5
    v_step = torch.randn(B, H_KV, D, dtype=DTYPE_BF) * 0.5
    slot_mapping = torch.tensor(
        [(i + 1) * 4 * BS + BS + 0 if i != 2 else -1 for i in range(B)],
        dtype=torch.long,
    )
    w.write_decode_batched(
        key=k_step, value=v_step, kv_cache=kv,
        slot_mapping=slot_mapping, slot_idx_t=slot_idx_t,
    )
    seq_pos = w._seq_pos_pool[slot_idx_t].tolist()
    # Active seqs (i in {0, 1, 3}) advanced from BS -> BS+1.
    # Inactive (i == 2) stays at BS.
    expected = [BS + 1, BS + 1, BS, BS + 1]
    assert seq_pos == expected, (seq_pos, expected)


def test_k_stage_block_id_pool_transitions_on_boundary(protect_mask_path):
    """When a decode step moves from block N to block N+1, the
    k_stage_block_id_pool entry for that slot reflects the new block."""
    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter

    torch.manual_seed(0xDEAF)
    w = PagedKVWriter(layer_idx=0, sidecar_dtype=DTYPE_BF)
    kv = _make_kv_cache()
    # Prefill exactly BS tokens at block 4 -> block 4 is FULL, block_id 4.
    base_block = 4
    slots = torch.arange(base_block * BS, base_block * BS + BS, dtype=torch.long)
    k = torch.randn(BS, H_KV, D, dtype=DTYPE_BF) * 0.5
    v = torch.randn(BS, H_KV, D, dtype=DTYPE_BF) * 0.5
    w.write(k, v, kv, slots, seq_id=42)
    slot_idx_t = torch.tensor([w._slot_map[42]], dtype=torch.long)
    # First decode: token at first slot of block 5 (a NEW block).
    k_step = torch.randn(1, H_KV, D, dtype=DTYPE_BF) * 0.5
    v_step = torch.randn(1, H_KV, D, dtype=DTYPE_BF) * 0.5
    slot_mapping = torch.tensor([5 * BS], dtype=torch.long)
    w.write_decode_batched(
        key=k_step, value=v_step, kv_cache=kv,
        slot_mapping=slot_mapping, slot_idx_t=slot_idx_t,
    )
    assert int(w._k_stage_block_id_pool[slot_idx_t].item()) == 5


def test_pool_counters_reset_on_evict(protect_mask_path):
    """evict_sequence returns slot to free pool AND zeros device counters
    so a reused slot starts fresh."""
    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter

    w = PagedKVWriter(layer_idx=0, sidecar_dtype=DTYPE_BF)
    kv = _make_kv_cache()
    # Allocate a slot via legacy write.
    k = torch.randn(BS, H_KV, D, dtype=DTYPE_BF) * 0.5
    v = torch.randn(BS, H_KV, D, dtype=DTYPE_BF) * 0.5
    slots = torch.arange(4 * BS, 4 * BS + BS, dtype=torch.long)
    w.write(k, v, kv, slots, seq_id=42)
    slot_idx = w._slot_map[42]
    # Sync via a decode step so pool counters update.
    slot_idx_t = torch.tensor([slot_idx], dtype=torch.long)
    w.write_decode_batched(
        key=k[:1], value=v[:1], kv_cache=kv,
        slot_mapping=torch.tensor([5 * BS], dtype=torch.long),
        slot_idx_t=slot_idx_t,
    )
    # Confirm counters advanced.
    assert int(w._seq_pos_pool[slot_idx].item()) > 0
    assert int(w._k_stage_block_id_pool[slot_idx].item()) == 5
    # Evict and confirm counter reset.
    w.evict_sequence(42)
    assert int(w._seq_pos_pool[slot_idx].item()) == 0
    assert int(w._k_stage_count_pool[slot_idx].item()) == 0
    assert int(w._k_stage_block_id_pool[slot_idx].item()) == -1
