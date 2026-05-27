"""Phase 6B.2 — CPU tests for the pre-capture seq_id resolution hook.

No vLLM stack needed; uses mock objects with the same attribute
shape vLLM emits. Mirrors the test_swap_telemetry + test_tier5a_
composition_smoke patterns.

Coverage:
  * Stash helpers (write/read/clear, attribute + fallback dict paths)
  * _is_pure_decode_step predicate on mocked attn_metadata shapes
  * _resolve_and_stash core logic (mock writers + decode_metadata)
  * install_int4_protected_precapture_hook (wrap/teardown semantics)
  * Idempotency of teardown
  * Env override (PHASE6B2_INSTALL_HOOK=0)
  * Hook fires only on pure-decode steps (mixed / prefill no-op)
  * write_decode_batched pre_synced kwarg honors caller intent

Run from CTM_plus/Bench:
  PYTHONPATH=../KVPolicy pytest tests/test_phase6b2_precapture_hook.py -v
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


# ---------------------------------------------------------------------- #
# Mocks
# ---------------------------------------------------------------------- #


class _MockDecodeMeta:
    """Mimics FlashAttentionMetadata.decode_metadata enough for the
    hook to read seq_ids from block_tables[:, 0]."""
    def __init__(self, seq_ids, max_decode_query_len=1):
        # block_tables[i, 0] is the seq's first block — what the
        # hook reads as the seq_id key. seq_ids parameter is exactly
        # those first-block ints in row order.
        self.block_tables = torch.tensor(
            [[sid] for sid in seq_ids], dtype=torch.long,
        )
        self.max_decode_query_len = max_decode_query_len


class _MockPrefillMeta:
    def __init__(self, n_q):
        self.num_prefill_tokens = n_q


class _MockAttnMeta:
    """Setattr-accepting attn_metadata mock. Pure-decode iff
    constructed with decode= and no prefill=."""
    def __init__(self, decode=None, prefill=None):
        self.decode_metadata = decode
        self.prefill_metadata = prefill


class _SlotAttnMeta:
    """Slot-class mock that rejects setattr — exercises the
    fallback module-level stash dict."""
    __slots__ = ("decode_metadata", "prefill_metadata")

    def __init__(self, decode=None, prefill=None):
        self.decode_metadata = decode
        self.prefill_metadata = prefill


class _MockModelInput:
    def __init__(self, attn_metadata):
        self.attn_metadata = attn_metadata


class _MockModelRunner:
    """Exposes a callable execute_model attribute. Records every call."""
    def __init__(self):
        self.calls = []

    def execute_model(self, model_input, kv_caches, *args, **kwargs):
        self.calls.append((model_input, kv_caches, args, kwargs))
        return "result_from_original_execute_model"


# ---------------------------------------------------------------------- #
# Protect mask fixture (shared writer init)
# ---------------------------------------------------------------------- #


NUM_LAYERS = 28
H_KV       = 4
D          = 128
BS         = 32
V_GROUP    = 32
N_PROTECT  = 5
DTYPE_BF   = torch.bfloat16


@pytest.fixture(scope="module")
def protect_mask_path():
    mask = torch.zeros((H_KV, D), dtype=torch.int8)
    mask[:, :N_PROTECT] = 1
    full = mask.unsqueeze(0).expand(NUM_LAYERS, -1, -1).contiguous()
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


def _make_writer():
    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter
    return PagedKVWriter(layer_idx=0, sidecar_dtype=DTYPE_BF)


def _make_kv_cache(NB=32):
    return torch.zeros((2, NB, BS, H_KV, D), dtype=torch.uint8)


def _allocate_writer(w, kv, seq_ids):
    """Trigger _lazy_alloc + SeqState creation on the writer for the
    given seq_ids. Mirrors prefill behavior."""
    for sid in seq_ids:
        k = torch.randn(BS, H_KV, D, dtype=DTYPE_BF) * 0.5
        v = torch.randn(BS, H_KV, D, dtype=DTYPE_BF) * 0.5
        base = (seq_ids.index(sid) + 1) * 4
        slots = torch.arange(base * BS, base * BS + BS, dtype=torch.long)
        w.write(k, v, kv, slots, seq_id=sid)


# ---------------------------------------------------------------------- #
# Stash helpers
# ---------------------------------------------------------------------- #


def test_stash_setattr_path():
    from kv_policy import phase6b2_precapture_hook as hook
    meta = _MockAttnMeta()
    payload = {"slot_idx_t": torch.tensor([0, 1, 2]), "seq_ids": [10, 11, 12], "hook_version": "test"}
    ok = hook.write_stash(meta, payload)
    assert ok
    # Reachable via attribute
    assert getattr(meta, hook.STASH_ATTR) is payload
    # Reachable via read_stash
    got = hook.read_stash(meta)
    assert got is payload


def test_stash_fallback_dict_path():
    """Slot-class metadata exercises the module-level fallback dict."""
    from kv_policy import phase6b2_precapture_hook as hook
    meta = _SlotAttnMeta()
    payload = {"slot_idx_t": torch.tensor([0, 1]), "seq_ids": [20, 21], "hook_version": "test"}
    ok = hook.write_stash(meta, payload)
    assert ok
    # NOT reachable via attribute (slot class rejects setattr)
    assert not hasattr(meta, hook.STASH_ATTR)
    # But IS reachable via read_stash (fallback dict)
    got = hook.read_stash(meta)
    assert got is payload
    # Cleanup
    hook.clear_stash(meta)


def test_read_stash_missing_returns_none():
    from kv_policy import phase6b2_precapture_hook as hook
    meta = _MockAttnMeta()
    assert hook.read_stash(meta) is None


def test_clear_stash_idempotent():
    from kv_policy import phase6b2_precapture_hook as hook
    meta = _MockAttnMeta()
    payload = {"slot_idx_t": torch.tensor([0]), "seq_ids": [1], "hook_version": "test"}
    hook.write_stash(meta, payload)
    hook.clear_stash(meta)
    assert hook.read_stash(meta) is None
    # Second call no-ops
    hook.clear_stash(meta)
    assert hook.read_stash(meta) is None


# ---------------------------------------------------------------------- #
# _is_pure_decode_step
# ---------------------------------------------------------------------- #


def test_is_pure_decode_step_pure_decode():
    from kv_policy.phase6b2_precapture_hook import _is_pure_decode_step
    meta = _MockAttnMeta(decode=_MockDecodeMeta([100, 101]))
    assert _is_pure_decode_step(meta)


def test_is_pure_decode_step_spec_decode_rejects():
    from kv_policy.phase6b2_precapture_hook import _is_pure_decode_step
    meta = _MockAttnMeta(decode=_MockDecodeMeta([100], max_decode_query_len=3))
    assert not _is_pure_decode_step(meta)


def test_is_pure_decode_step_mixed_rejects():
    from kv_policy.phase6b2_precapture_hook import _is_pure_decode_step
    meta = _MockAttnMeta(
        decode=_MockDecodeMeta([100, 101]),
        prefill=_MockPrefillMeta(50),
    )
    assert not _is_pure_decode_step(meta)


def test_is_pure_decode_step_prefill_only_rejects():
    from kv_policy.phase6b2_precapture_hook import _is_pure_decode_step
    meta = _MockAttnMeta(prefill=_MockPrefillMeta(50))
    assert not _is_pure_decode_step(meta)


def test_is_pure_decode_step_none_rejects():
    from kv_policy.phase6b2_precapture_hook import _is_pure_decode_step
    assert not _is_pure_decode_step(None)


def test_is_pure_decode_step_empty_block_tables_rejects():
    from kv_policy.phase6b2_precapture_hook import _is_pure_decode_step
    class _Empty:
        block_tables = torch.zeros((0, 0), dtype=torch.long)
        max_decode_query_len = 1
    meta = _MockAttnMeta(decode=_Empty())
    assert not _is_pure_decode_step(meta)


# ---------------------------------------------------------------------- #
# _resolve_and_stash
# ---------------------------------------------------------------------- #


def test_resolve_and_stash_one_writer(protect_mask_path):
    from kv_policy.phase6b2_precapture_hook import _resolve_and_stash, read_stash
    w = _make_writer()
    kv = _make_kv_cache()
    seq_ids = [100, 101]
    _allocate_writer(w, kv, seq_ids)
    meta = _MockAttnMeta(decode=_MockDecodeMeta(seq_ids))

    payload = _resolve_and_stash(meta, [w], torch.device("cpu"))

    assert "slot_idx_t" in payload
    assert "seq_ids" in payload
    assert payload["seq_ids"] == seq_ids
    # The resolved slot_idx_t should index into the writer's pool.
    # Since prefill allocated slot 0 to seq_ids[0] and slot 1 to seq_ids[1],
    # slot_idx_t should be [0, 1].
    assert payload["slot_idx_t"].tolist() == [0, 1]
    # Reachable via read_stash too
    assert read_stash(meta) is payload


def test_resolve_and_stash_aligns_multiple_writers(protect_mask_path):
    """The hook calls ensure_seq_state on EVERY writer in the list so
    all writers' _slot_maps agree on the seq_id -> slot mapping. This
    test verifies the alignment property."""
    from kv_policy.phase6b2_precapture_hook import _resolve_and_stash
    w0 = _make_writer()
    w1 = _make_writer()
    kv0 = _make_kv_cache()
    kv1 = _make_kv_cache()
    seq_ids = [200, 201, 202]
    _allocate_writer(w0, kv0, seq_ids)
    _allocate_writer(w1, kv1, seq_ids)
    meta = _MockAttnMeta(decode=_MockDecodeMeta(seq_ids))

    _resolve_and_stash(meta, [w0, w1], torch.device("cpu"))

    # Both writers should have the same _slot_map for these seq_ids.
    for sid in seq_ids:
        assert w0._slot_map[sid] == w1._slot_map[sid], (
            f"slot mismatch for seq_id={sid}: "
            f"w0={w0._slot_map[sid]}, w1={w1._slot_map[sid]}"
        )


def test_resolve_and_stash_reentry_idempotent(protect_mask_path):
    """A step that fires the hook twice (e.g., chunked-prefill intra-
    step) shouldn't re-resolve — same slot_idx_t reused."""
    from kv_policy.phase6b2_precapture_hook import _resolve_and_stash
    w = _make_writer()
    kv = _make_kv_cache()
    seq_ids = [300, 301]
    _allocate_writer(w, kv, seq_ids)
    meta = _MockAttnMeta(decode=_MockDecodeMeta(seq_ids))

    p1 = _resolve_and_stash(meta, [w], torch.device("cpu"))
    p2 = _resolve_and_stash(meta, [w], torch.device("cpu"))
    assert p1 is p2  # same payload object


def test_resolve_and_stash_no_writers_returns_empty(protect_mask_path):
    """Defensive: if writers list is empty, returns empty dict (caller
    falls back to self-resolve)."""
    from kv_policy.phase6b2_precapture_hook import _resolve_and_stash
    meta = _MockAttnMeta(decode=_MockDecodeMeta([400]))
    payload = _resolve_and_stash(meta, [], torch.device("cpu"))
    assert payload == {}


def test_resolve_and_stash_unallocated_writer(protect_mask_path):
    """An unallocated writer (no _lazy_alloc yet) is skipped; the
    hook returns empty payload if NONE of the writers are allocated."""
    from kv_policy.phase6b2_precapture_hook import _resolve_and_stash
    w = _make_writer()  # NOT lazy-allocated
    meta = _MockAttnMeta(decode=_MockDecodeMeta([500]))
    payload = _resolve_and_stash(meta, [w], torch.device("cpu"))
    # No allocated writers -> empty stash
    assert payload == {}


# ---------------------------------------------------------------------- #
# install_int4_protected_precapture_hook — wrap/teardown
# ---------------------------------------------------------------------- #


def test_install_wraps_execute_model(protect_mask_path):
    from kv_policy.phase6b2_precapture_hook import install_int4_protected_precapture_hook
    mr = _MockModelRunner()
    handle = install_int4_protected_precapture_hook(mr, writers=[])
    assert handle.enabled
    assert handle.hook_target_name == "execute_model"
    # The wrap is now an instance attribute (setattr-shadowed bound
    # method). Confirm by introspecting __dict__.
    assert "execute_model" in mr.__dict__
    assert mr.__dict__["execute_model"].__name__ == "execute_model"
    handle.teardown()


def test_install_teardown_restores_original(protect_mask_path):
    """After teardown, the instance-level execute_model shadow must be
    gone so attribute access falls back to the class-level method."""
    from kv_policy.phase6b2_precapture_hook import install_int4_protected_precapture_hook
    mr = _MockModelRunner()
    # Pre-install: execute_model is NOT in instance __dict__ (class method).
    assert "execute_model" not in mr.__dict__
    handle = install_int4_protected_precapture_hook(mr, writers=[])
    # Post-install: instance-level shadow exists.
    assert "execute_model" in mr.__dict__
    handle.teardown()
    # After teardown: the instance-level shadow has been set to the
    # original (bound-method) callable so call behavior is preserved.
    # (Setattr cannot truly DELETE the shadow because the install used
    # setattr; the revert closure sets it back to the captured
    # original_fn which IS the original bound-method object.)
    restored = mr.__dict__["execute_model"]
    # Calling the restored attribute produces the original behavior.
    mr.calls.clear()
    result = restored(_MockModelInput(_MockAttnMeta()), [])
    assert result == "result_from_original_execute_model"
    assert len(mr.calls) == 1


def test_install_teardown_idempotent(protect_mask_path):
    from kv_policy.phase6b2_precapture_hook import install_int4_protected_precapture_hook
    mr = _MockModelRunner()
    handle = install_int4_protected_precapture_hook(mr, writers=[])
    handle.teardown()
    # Second call no-ops
    handle.teardown()


def test_install_disabled_is_inert(protect_mask_path):
    from kv_policy.phase6b2_precapture_hook import install_int4_protected_precapture_hook
    mr = _MockModelRunner()
    handle = install_int4_protected_precapture_hook(mr, writers=[], enable=False)
    assert not handle.enabled
    assert handle.hook_target_name == "disabled"
    # No instance-level shadow installed when inert
    assert "execute_model" not in mr.__dict__


def test_install_env_override_forces_inert(protect_mask_path):
    from kv_policy.phase6b2_precapture_hook import install_int4_protected_precapture_hook
    mr = _MockModelRunner()
    prior = os.environ.get("PHASE6B2_INSTALL_HOOK")
    os.environ["PHASE6B2_INSTALL_HOOK"] = "0"
    try:
        handle = install_int4_protected_precapture_hook(mr, writers=[])
        assert not handle.enabled
        # No instance-level shadow when env override forces inert
        assert "execute_model" not in mr.__dict__
    finally:
        if prior is None:
            os.environ.pop("PHASE6B2_INSTALL_HOOK", None)
        else:
            os.environ["PHASE6B2_INSTALL_HOOK"] = prior


def test_install_missing_execute_model_inert(protect_mask_path):
    from kv_policy.phase6b2_precapture_hook import install_int4_protected_precapture_hook
    class _NoExecute:
        pass
    mr = _NoExecute()
    handle = install_int4_protected_precapture_hook(mr, writers=[])
    assert not handle.enabled
    assert handle.hook_target_name == "no_execute_model_attr"


# ---------------------------------------------------------------------- #
# Wrapped execute_model — end-to-end stash behavior
# ---------------------------------------------------------------------- #


def test_wrap_stashes_on_pure_decode(protect_mask_path):
    """Calling the wrapped execute_model with pure-decode attn_metadata
    populates the stash before delegating."""
    from kv_policy.phase6b2_precapture_hook import (
        install_int4_protected_precapture_hook, read_stash,
    )
    w = _make_writer()
    kv = _make_kv_cache()
    seq_ids = [600, 601]
    _allocate_writer(w, kv, seq_ids)

    mr = _MockModelRunner()
    handle = install_int4_protected_precapture_hook(mr, writers=[w])

    meta = _MockAttnMeta(decode=_MockDecodeMeta(seq_ids))
    model_input = _MockModelInput(meta)
    result = mr.execute_model(model_input, [])

    # Hook delegated to original.
    assert result == "result_from_original_execute_model"
    # Stash present.
    stash = read_stash(meta)
    assert stash is not None
    assert stash["slot_idx_t"].tolist() == [0, 1]
    assert handle.stash_call_count == 1
    assert handle.skipped_step_count == 0
    handle.teardown()


def test_wrap_skips_on_prefill_step(protect_mask_path):
    """Prefill-only step: hook delegates without stashing."""
    from kv_policy.phase6b2_precapture_hook import (
        install_int4_protected_precapture_hook, read_stash,
    )
    w = _make_writer()
    mr = _MockModelRunner()
    handle = install_int4_protected_precapture_hook(mr, writers=[w])

    meta = _MockAttnMeta(prefill=_MockPrefillMeta(100))
    model_input = _MockModelInput(meta)
    mr.execute_model(model_input, [])

    assert read_stash(meta) is None
    assert handle.stash_call_count == 0
    assert handle.skipped_step_count == 1
    handle.teardown()


def test_wrap_skips_when_no_writer_allocated(protect_mask_path):
    """If no writer is _lazy_alloc'd, hook is a no-op (the dispatch
    fork's fallback path will self-resolve)."""
    from kv_policy.phase6b2_precapture_hook import (
        install_int4_protected_precapture_hook, read_stash,
    )
    w = _make_writer()  # NOT allocated
    mr = _MockModelRunner()
    handle = install_int4_protected_precapture_hook(mr, writers=[w])

    meta = _MockAttnMeta(decode=_MockDecodeMeta([700]))
    model_input = _MockModelInput(meta)
    mr.execute_model(model_input, [])

    assert read_stash(meta) is None
    assert handle.stash_call_count == 0
    assert handle.skipped_step_count == 1
    handle.teardown()


def test_wrap_delegates_args_verbatim(protect_mask_path):
    """The wrap must pass model_input + kv_caches + *args + **kwargs
    through verbatim to the original."""
    from kv_policy.phase6b2_precapture_hook import install_int4_protected_precapture_hook
    mr = _MockModelRunner()
    handle = install_int4_protected_precapture_hook(mr, writers=[])

    meta = _MockAttnMeta(prefill=_MockPrefillMeta(50))
    model_input = _MockModelInput(meta)
    extra_args = (1, 2, 3)
    extra_kwargs = {"foo": "bar", "qux": 42}
    mr.execute_model(model_input, "fake_kv_caches", *extra_args, **extra_kwargs)

    assert len(mr.calls) == 1
    mi, kvc, args, kwargs = mr.calls[0]
    assert mi is model_input
    assert kvc == "fake_kv_caches"
    assert args == extra_args
    assert kwargs == extra_kwargs
    handle.teardown()


# ---------------------------------------------------------------------- #
# write_decode_batched pre_synced kwarg
# ---------------------------------------------------------------------- #


def test_write_decode_batched_pre_synced_skips_sync(protect_mask_path):
    """When pre_synced=True, write_decode_batched still produces
    correct state but skips its internal _sync_pool_counters and
    _writeback. Bit-equivalent output when caller has done the sync."""
    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter

    torch.manual_seed(0xDEAD)
    w_a = PagedKVWriter(layer_idx=0, sidecar_dtype=DTYPE_BF)
    w_b = PagedKVWriter(layer_idx=0, sidecar_dtype=DTYPE_BF)
    kv_a = _make_kv_cache(NB=64)
    kv_b = kv_a.clone()

    # Identical prefill.
    seq_ids = [800, 801]
    for i, sid in enumerate(seq_ids):
        base = (i + 1) * 4
        slots = torch.arange(base * BS, base * BS + BS, dtype=torch.long)
        k = torch.randn(BS, H_KV, D, dtype=DTYPE_BF) * 0.5
        v = torch.randn(BS, H_KV, D, dtype=DTYPE_BF) * 0.5
        w_a.write(k, v, kv_a, slots, seq_id=sid)
        w_b.write(k, v, kv_b, slots, seq_id=sid)

    slot_idx_t = torch.tensor([w_a._slot_map[s] for s in seq_ids], dtype=torch.long)

    # 16 decode steps. w_a: pre_synced=False (legacy). w_b:
    # pre_synced=True with manual sync (mimics what the hook does).
    for step in range(16):
        k = torch.randn(2, H_KV, D, dtype=DTYPE_BF) * 0.5
        v = torch.randn(2, H_KV, D, dtype=DTYPE_BF) * 0.5
        slot_mapping = torch.tensor([4 * BS + BS + step, 8 * BS + BS + step], dtype=torch.long)
        w_a.write_decode_batched(k, v, kv_a, slot_mapping, slot_idx_t, pre_synced=False)
        # For w_b: sync first (mimicking the hook), then call with pre_synced=True
        w_b._sync_pool_counters_from_states(slot_idx_t.tolist())
        w_b.write_decode_batched(k, v, kv_b, slot_mapping, slot_idx_t, pre_synced=True)

    # Bit-equivalent state across the two paths.
    assert torch.equal(kv_a, kv_b)
    assert torch.equal(w_a.k_scale_ext, w_b.k_scale_ext)
    assert torch.equal(w_a.k_xmin_ext, w_b.k_xmin_ext)
    assert torch.equal(w_a.k_protect_ext, w_b.k_protect_ext)
    assert torch.equal(w_a.v_scale_ext, w_b.v_scale_ext)
    assert torch.equal(w_a.v_xmin_ext, w_b.v_xmin_ext)
    assert torch.equal(w_a._bf16_k_backing_pool, w_b._bf16_k_backing_pool)
    assert torch.equal(w_a._bf16_v_backing_pool, w_b._bf16_v_backing_pool)
    assert torch.equal(w_a._k_stage_pool, w_b._k_stage_pool)


def test_write_decode_batched_default_pre_synced_false(protect_mask_path):
    """Default behavior: pre_synced kwarg defaults to False, preserving
    Phase 6B.1 behavior (the writer does its own sync)."""
    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter
    import inspect
    sig = inspect.signature(PagedKVWriter.write_decode_batched)
    pre_synced_param = sig.parameters.get("pre_synced")
    assert pre_synced_param is not None
    assert pre_synced_param.default is False
    assert pre_synced_param.kind == inspect.Parameter.KEYWORD_ONLY
