"""
Phase 5 tests for active-mode vLLM integration.

Scope:

- ``benchmarks.vllm_active_bridge`` importability without vllm
- ``VLLMVersionSupportError`` and ``check_vllm_active_mode_supported``
  fail-clean behavior against the current environment
- ``install_pcam_active_evictor`` wiring verified against a mock
  FreeKVCacheBlockQueue / BlockPool (no real vllm needed)
- ``uninstall_pcam_active_evictor`` restores the originals
- Bridge gracefully handles PCAM fallback (empty victim list)
- ``benchmarks.pcam_vllm_perf`` CLI argument parsing and fail-clean
  exit codes
- ``_find_block_pool`` path-walking logic against a mock engine

These tests are deterministic, CPU-only, and do not require torch,
transformers, vllm, or any model weights. The mock harness for the
active-mode bridge replicates just enough of ``FreeKVCacheBlockQueue``'s
interface (``popleft_n``, ``append``, ``append_n``, ``remove``,
``get_all_free_blocks``, ``num_free_blocks``) to exercise the
monkey-patch logic against a Python stand-in.
"""

from __future__ import annotations

import importlib
import json
import types
from pathlib import Path
from typing import Any, List

import pytest

from simulator.pcam import PCAMConfig

from benchmarks.vllm_active_bridge import (
    ActiveModeInstallation,
    VLLMVersionSupportError,
    check_vllm_active_mode_supported,
    install_pcam_active_evictor,
    uninstall_pcam_active_evictor,
)
from benchmarks.pcam_vllm_perf import (
    _find_block_pool,
    _load_prompts,
    _percentile,
    build_argparser,
    render_report,
    run as perf_run,
    PolicyRunResult,
)


# ===========================================================================
# Version detection — environment-aware
# ===========================================================================


def _vllm_v1_core_available() -> bool:
    """
    Return True iff the current env has vllm installed AND exposes
    the v1 core architecture. Mirrors the feature-detection path used
    by ``check_vllm_active_mode_supported``.
    """
    try:
        from vllm.v1.core.block_pool import BlockPool  # noqa: F401
        from vllm.v1.core.kv_cache_utils import (  # noqa: F401
            FreeKVCacheBlockQueue,
            KVCacheBlock,
        )
        return True
    except ImportError:
        return False


class TestVersionSupport:
    def test_bridge_module_imports_without_vllm(self):
        """
        The bridge module must import cleanly even when vllm is not
        present. Version detection happens inside the function, not
        at module load.
        """
        import benchmarks.vllm_active_bridge as bridge
        assert bridge.VLLMVersionSupportError is VLLMVersionSupportError
        assert bridge.check_vllm_active_mode_supported is check_vllm_active_mode_supported

    @pytest.mark.skipif(
        _vllm_v1_core_available(),
        reason="vllm v1 core is installed in this env; fail-clean "
               "path is only reachable when it isn't.",
    )
    def test_check_fails_clean_without_vllm_v1_core(self):
        with pytest.raises(VLLMVersionSupportError) as excinfo:
            check_vllm_active_mode_supported()
        msg = str(excinfo.value)
        # Message must name either vllm or v1.core.block_pool so the
        # user knows exactly what's missing.
        assert "vllm" in msg.lower()


# ===========================================================================
# Mock FreeKVCacheBlockQueue for wiring tests
# ===========================================================================


class _MockBlock:
    """
    Minimal KVCacheBlock-shaped stand-in. Only carries a block_id and
    the prev/next pointers the real FreeKVCacheBlockQueue uses.
    """

    def __init__(self, block_id: int) -> None:
        self.block_id = block_id
        self.prev_free_block: Any = None
        self.next_free_block: Any = None

    def __repr__(self) -> str:
        return f"_MockBlock({self.block_id})"


class _MockQueue:
    """
    Minimal FreeKVCacheBlockQueue stand-in. Implements just enough of
    the interface for the active-mode bridge's install/uninstall path
    to exercise: popleft_n, append, append_n, remove,
    get_all_free_blocks, num_free_blocks.

    Order is preserved as an explicit list for test determinism;
    the real implementation is a doubly-linked list but the bridge
    only depends on the public methods above.
    """

    def __init__(self, block_ids: List[int]) -> None:
        self._blocks: List[_MockBlock] = [_MockBlock(bid) for bid in block_ids]
        self._relink()

    def _relink(self) -> None:
        # Set up next/prev pointers so the mock's behavior matches the
        # real linked-list invariant: every block in the queue has
        # non-None prev / next pointers (even sentinels).
        sentinel = _MockBlock(-1)
        for i, blk in enumerate(self._blocks):
            blk.prev_free_block = self._blocks[i - 1] if i > 0 else sentinel
            blk.next_free_block = self._blocks[i + 1] if i + 1 < len(self._blocks) else sentinel

    @property
    def num_free_blocks(self) -> int:
        return len(self._blocks)

    def popleft_n(self, n: int) -> List[_MockBlock]:
        if n == 0:
            return []
        assert self.num_free_blocks >= n
        ret = self._blocks[:n]
        self._blocks = self._blocks[n:]
        self._relink()
        return ret

    def append(self, block: _MockBlock) -> None:
        self._blocks.append(block)
        self._relink()

    def append_n(self, blocks: List[_MockBlock]) -> None:
        self._blocks.extend(blocks)
        self._relink()

    def remove(self, block: _MockBlock) -> None:
        self._blocks = [b for b in self._blocks if b.block_id != block.block_id]
        block.prev_free_block = None
        block.next_free_block = None
        self._relink()

    def get_all_free_blocks(self) -> List[_MockBlock]:
        return list(self._blocks)


class _MockBlockPool:
    def __init__(self, block_ids: List[int]) -> None:
        self.free_block_queue = _MockQueue(block_ids)


# ===========================================================================
# Install / uninstall wiring
# ===========================================================================


class TestActiveModeInstallation:
    @pytest.mark.skipif(
        not _vllm_v1_core_available() and False,  # mock-driven, no vllm needed
        reason="uses mock queue, not a real vllm import",
    )
    def test_install_admits_all_free_blocks(self):
        """
        After install_pcam_active_evictor, the PCAM policy must know
        about every block that was in the free queue at install time.
        """
        pool = _MockBlockPool(block_ids=[1, 2, 3, 4, 5])
        # Bypass the vllm feature-detection probe by monkey-patching
        # the check function for this test. The wiring logic we're
        # testing is identical whether vllm is present or not.
        import benchmarks.vllm_active_bridge as bridge
        original_check = bridge.check_vllm_active_mode_supported
        bridge.check_vllm_active_mode_supported = lambda: None
        try:
            installation = install_pcam_active_evictor(
                block_pool=pool,
                config=PCAMConfig(max_blocks=64, sink_tokens=1),
            )
        finally:
            bridge.check_vllm_active_mode_supported = original_check

        try:
            tracked = installation.policy.blocks
            assert set(tracked.keys()) == {1, 2, 3, 4, 5}
        finally:
            uninstall_pcam_active_evictor(installation)

    def test_uninstall_restores_originals(self):
        """
        After uninstall, the queue's patched methods must have been
        removed from the instance ``__dict__`` so attribute lookup
        resolves to the class methods again. We check via
        ``queue.__dict__`` to get an unambiguous signal (bound-method
        ``is`` comparisons across set / del are unreliable because
        Python re-creates bound method wrappers on each attribute
        access).
        """
        pool = _MockBlockPool(block_ids=[1, 2, 3])
        queue = pool.free_block_queue
        # The mock queue methods live on the class; they are NOT
        # instance attributes before install.
        assert "popleft_n" not in queue.__dict__
        assert "append" not in queue.__dict__
        assert "append_n" not in queue.__dict__

        import benchmarks.vllm_active_bridge as bridge
        bridge.check_vllm_active_mode_supported = lambda: None
        installation = install_pcam_active_evictor(
            block_pool=pool,
            config=PCAMConfig(max_blocks=64),
        )
        # After install: the bridge set instance overrides.
        assert "popleft_n" in queue.__dict__
        assert "append" in queue.__dict__
        assert "append_n" in queue.__dict__

        uninstall_pcam_active_evictor(installation)

        # After uninstall: instance overrides gone, class methods
        # resolve again.
        assert "popleft_n" not in queue.__dict__
        assert "append" not in queue.__dict__
        assert "append_n" not in queue.__dict__
        assert installation.installed is False

        # Behavioral check: popleft_n still works post-uninstall and
        # returns blocks from the front of the queue (original LRU
        # behavior, not PCAM-routed).
        remaining = pool.free_block_queue.get_all_free_blocks()
        assert len(remaining) == 3
        popped = queue.popleft_n(1)
        assert len(popped) == 1

    def test_uninstall_is_idempotent(self):
        pool = _MockBlockPool(block_ids=[1, 2])
        import benchmarks.vllm_active_bridge as bridge
        bridge.check_vllm_active_mode_supported = lambda: None
        installation = install_pcam_active_evictor(
            block_pool=pool, config=PCAMConfig(max_blocks=64),
        )
        uninstall_pcam_active_evictor(installation)
        # Second call must be a no-op, not a double-restore.
        uninstall_pcam_active_evictor(installation)
        assert installation.installed is False

    def test_popleft_n_returns_pcam_chosen_blocks(self):
        """
        With active-mode installed, popleft_n(n) should return the
        blocks PCAM chose (bounded by n) and should have removed them
        from the free queue.
        """
        pool = _MockBlockPool(block_ids=[10, 11, 12, 13, 14])
        import benchmarks.vllm_active_bridge as bridge
        bridge.check_vllm_active_mode_supported = lambda: None
        installation = install_pcam_active_evictor(
            block_pool=pool,
            config=PCAMConfig(max_blocks=64, sink_tokens=1),
        )
        try:
            popped = pool.free_block_queue.popleft_n(2)
            assert len(popped) == 2
            # The popped blocks must have been removed from the queue.
            remaining_ids = {b.block_id for b in pool.free_block_queue.get_all_free_blocks()}
            popped_ids = {b.block_id for b in popped}
            assert popped_ids.isdisjoint(remaining_ids)
            assert len(remaining_ids) == 3

            # Bridge stats incremented
            stats = installation.stats
            assert stats["popleft_n_calls"] == 1
            assert stats["blocks_evicted"] == 2
        finally:
            uninstall_pcam_active_evictor(installation)

    def test_popleft_n_falls_back_on_empty_pcam_selection(self):
        """
        If PCAM returns fewer victims than requested (e.g. because it
        ran out of tracked blocks), the bridge must fall back to LRU
        order for the remainder. The whole operation must still
        return exactly n blocks.
        """
        pool = _MockBlockPool(block_ids=[1, 2, 3])
        import benchmarks.vllm_active_bridge as bridge
        bridge.check_vllm_active_mode_supported = lambda: None
        installation = install_pcam_active_evictor(
            block_pool=pool, config=PCAMConfig(max_blocks=64, sink_tokens=1),
        )
        try:
            # Force PCAM to return empty by monkey-patching its
            # select_victims to return []. The bridge must still
            # return 3 blocks via the LRU fallback.
            installation.policy.select_victims = lambda count: []
            popped = pool.free_block_queue.popleft_n(3)
            assert len(popped) == 3
            assert pool.free_block_queue.num_free_blocks == 0
            assert installation.stats["lru_fallback_blocks"] == 3
            assert installation.stats["pcam_chosen_blocks"] == 0
        finally:
            uninstall_pcam_active_evictor(installation)

    def test_append_tracks_new_blocks_in_pcam(self):
        pool = _MockBlockPool(block_ids=[1, 2])
        import benchmarks.vllm_active_bridge as bridge
        bridge.check_vllm_active_mode_supported = lambda: None
        installation = install_pcam_active_evictor(
            block_pool=pool, config=PCAMConfig(max_blocks=64),
        )
        try:
            new_block = _MockBlock(block_id=99)
            pool.free_block_queue.append(new_block)
            # PCAM must now track block 99
            assert 99 in installation.policy.blocks
            # Stats incremented
            assert installation.stats["append_events"] == 1
        finally:
            uninstall_pcam_active_evictor(installation)

    def test_append_n_tracks_batch(self):
        pool = _MockBlockPool(block_ids=[])
        import benchmarks.vllm_active_bridge as bridge
        bridge.check_vllm_active_mode_supported = lambda: None
        installation = install_pcam_active_evictor(
            block_pool=pool, config=PCAMConfig(max_blocks=64),
        )
        try:
            new_blocks = [_MockBlock(block_id=bid) for bid in (50, 51, 52)]
            pool.free_block_queue.append_n(new_blocks)
            for bid in (50, 51, 52):
                assert bid in installation.policy.blocks
            assert installation.stats["append_events"] == 3
        finally:
            uninstall_pcam_active_evictor(installation)


# ===========================================================================
# pcam_vllm_perf — CLI, prompts, report generation
# ===========================================================================


class TestPerfHarnessCLI:
    def test_percentile_helper(self):
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        assert _percentile(values, 0.5) == 0.3
        assert _percentile(values, 0.95) == 0.5
        assert _percentile([], 0.5) == 0.0

    def test_load_prompts_from_cli_args(self):
        prompts = _load_prompts(["hello", "world"], None)
        assert prompts == ["hello", "world"]

    def test_load_prompts_from_file(self, tmp_path: Path):
        p = tmp_path / "prompts.json"
        p.write_text(json.dumps(["alpha", "beta", "gamma"]))
        prompts = _load_prompts(None, p)
        assert prompts == ["alpha", "beta", "gamma"]

    def test_load_prompts_file_rejects_non_list(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"not": "a list"}))
        with pytest.raises(TypeError, match="list"):
            _load_prompts(None, p)

    def test_load_prompts_defaults_when_nothing_given(self):
        prompts = _load_prompts(None, None)
        assert len(prompts) >= 1
        assert all(isinstance(p, str) for p in prompts)

    def test_argparser_policy_choices(self):
        parser = build_argparser()
        args = parser.parse_args(["--policy", "pcam"])
        assert args.policy == "pcam"
        args = parser.parse_args(["--policy", "both"])
        assert args.policy == "both"
        args = parser.parse_args(["--policy", "default"])
        assert args.policy == "default"

    @pytest.mark.skipif(
        _vllm_v1_core_available(),
        reason="vllm v1 core is installed; fail-clean is only "
               "reachable when it isn't.",
    )
    def test_run_pcam_policy_fails_clean_without_vllm(self, capsys):
        rc = perf_run(["--policy", "pcam", "--prompt", "hi", "--quiet"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "ERROR:" in err
        assert "vllm" in err.lower()

    @pytest.mark.skipif(
        _vllm_v1_core_available(),
        reason="vllm v1 core is installed; fail-clean is only "
               "reachable when it isn't.",
    )
    def test_run_default_policy_also_fails_clean_without_vllm(self, capsys):
        rc = perf_run(["--policy", "default", "--prompt", "hi", "--quiet"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "ERROR:" in err

    def test_render_report_empty_results(self):
        """Render-report sanity on an empty list — no crash."""
        out = render_report([])
        assert "REAL SERVING METRICS" in out
        assert "PCAM vLLM Perf" in out

    def test_render_report_one_policy(self):
        result = PolicyRunResult(
            policy="default",
            model="facebook/opt-125m",
            num_prompts=2,
            total_prompt_tokens=20,
            total_completion_tokens=50,
            wall_time_seconds=1.5,
            tokens_per_second=33.33,
            per_prompt_latency_seconds=[0.7, 0.8],
        )
        out = render_report([result])
        assert "default" in out
        assert "facebook/opt-125m" in out or "default" in out
        assert "REAL SERVING METRICS" in out

    def test_render_report_both_policies_shows_delta(self):
        default = PolicyRunResult(
            policy="default", model="m", num_prompts=1,
            total_prompt_tokens=10, total_completion_tokens=10,
            wall_time_seconds=1.0, tokens_per_second=10.0,
            per_prompt_latency_seconds=[1.0],
        )
        pcam = PolicyRunResult(
            policy="pcam", model="m", num_prompts=1,
            total_prompt_tokens=10, total_completion_tokens=10,
            wall_time_seconds=0.8, tokens_per_second=12.5,
            per_prompt_latency_seconds=[0.8],
        )
        out = render_report([default, pcam])
        assert "PCAM throughput delta vs default LRU:" in out
        assert "%" in out


# ===========================================================================
# _find_block_pool path walking
# ===========================================================================


class TestFindBlockPool:
    def test_walks_typical_v1_core_path(self):
        """
        The canonical path is llm.llm_engine.kv_cache_manager.block_pool.
        _find_block_pool must locate it on a mock LLM.
        """
        mock_pool = object()
        mock_mgr = types.SimpleNamespace(block_pool=mock_pool)
        mock_engine = types.SimpleNamespace(kv_cache_manager=mock_mgr)
        mock_llm = types.SimpleNamespace(llm_engine=mock_engine)

        assert _find_block_pool(mock_llm) is mock_pool

    def test_walks_alternate_scheduler_path(self):
        mock_pool = object()
        mock_mgr = types.SimpleNamespace(block_pool=mock_pool)
        mock_sched = types.SimpleNamespace(kv_cache_manager=mock_mgr)
        mock_engine = types.SimpleNamespace(scheduler=mock_sched)
        mock_llm = types.SimpleNamespace(llm_engine=mock_engine)

        assert _find_block_pool(mock_llm) is mock_pool

    def test_raises_on_completely_unknown_engine(self):
        mock_llm = types.SimpleNamespace(completely_unrelated=42)
        with pytest.raises(VLLMVersionSupportError, match="BlockPool"):
            _find_block_pool(mock_llm)
