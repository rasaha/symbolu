# cython: language_level=3, boundscheck=False, wraparound=False, initializedcheck=False
"""Cython implementation of ``CTMEvictorModern``.

Semantically a drop-in replacement for the pure-Python class in
``vllm_evictor.py``. Same constructor signature, same public methods,
same diagnostic counters, same behavioural contract — pinned by the
parametrized CPU fixture in ``Bench/tests/test_vllm_protocol_fixture.py``.

The motivation (see ``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §11): the
v8 py-spy profile attributed ~20% of wall-clock to the per-call dispatch
overhead vLLM's scheduler and torch's nn.Module dispatcher pay when the
patched evictor's protocol methods (``__contains__``/``add``/``update``/
``remove``/``evict``) are Python rather than C. The CTM+ algorithm
itself is 1.1% of wall. Closing the gap is a code-shape problem.

This module is the code-shape fix:

* ``cdef class`` -> instance state lives in C slots, not ``__dict__``.
* Magic-method slots (``__contains__``) dispatch through the
  ``tp_contains`` slot directly from CPython's ``PySequence_Contains``.
* Hot locals in ``add``/``update``/``remove``/``evict`` are typed,
  removing the bytecode interpretation overhead the profile flagged.
* The Phase-4-specific helpers (``set_block_pre_rope_keys``,
  ``trig_score_block``, ``window_pruning_pass``) keep calling into the
  existing Python ``triattention`` helpers — the trig math is 0.2% of
  wall per the profile, so a C port of that would optimise a non-issue.

Build:
    cd CTM_plus/KVPolicy && python3 setup.py build_ext --inplace

When the compiled ``.so`` is absent (e.g. fresh checkout without a C
toolchain), ``kv_policy.vllm_evictor`` falls back to aliasing
``CTMEvictorModernC = CTMEvictorModern``. CI without the build artifact
still passes the protocol-fixture suite — only the C-variant
parametrisation skips.
"""

import time as _py_time

from .attention_evictor import KVCachePolicy
from .triattention import (
    WindowPruningState,
    aggregate_block_trig_score,
    window_pruning_decision,
)
from .vllm_adapter import CTMvLLMConfig


cdef class CTMEvictorModernC:
    """Cython port of ``CTMEvictorModern``. Public surface and
    diagnostic-counter shape are pinned by the protocol fixture; do not
    rename or drop any ``cdef public`` attribute without updating the
    fixture's parametrisation hook in lockstep.
    """

    # ---- State exposed to Python (tests + the streaming runner) ----
    cdef public object _policy
    cdef public int _block_size
    cdef public dict _content_hash
    cdef public dict _num_hashed_tokens
    cdef public dict _last_accessed
    cdef public set _tracked
    cdef public bint _enable_logging
    cdef public list _evict_timings

    cdef public object _trig_scorer
    cdef public double _trig_score_weight
    cdef public double _trig_blend_weight
    cdef public int _trig_blend_candidate_count
    cdef public dict _block_pre_rope_keys
    cdef public dict _block_layer_head
    cdef public dict _block_trig_score
    cdef public object _window_state

    # Diagnostic counters — tests assert on them and the streaming
    # runner reports them in ``stats``. Keep every name in lockstep
    # with the Python class.
    cdef public Py_ssize_t _phase4_set_pre_rope_keys_calls
    cdef public Py_ssize_t _phase4_set_pre_rope_keys_speculative
    cdef public Py_ssize_t _phase4_trig_score_computes
    cdef public Py_ssize_t _phase4_trig_score_compute_exceptions
    cdef public Py_ssize_t _phase4_trig_score_lookups
    cdef public Py_ssize_t _phase4_trig_score_cache_misses
    cdef public Py_ssize_t _phase4_trig_blend_evict_calls
    cdef public Py_ssize_t _phase4_trig_blend_picks
    cdef public Py_ssize_t _phase4_trig_blend_skips
    cdef public Py_ssize_t _phase4_trig_changed_pick

    # Set externally by ``triattention.install_attn_metadata_side_channel``'s
    # pre-hook; declared here so the cdef class allows attribute set.
    cdef public object _phase4_pending_slot_mapping
    cdef public object _phase4_pending_num_decode_tokens

    # Set externally by ``triattention.install_pre_rope_capture`` /
    # ``install_attn_metadata_side_channel``. The Phase 4 hook code
    # writes counters and a hook-handle list directly onto the evictor
    # object via getattr/setattr patterns; for the cdef class to
    # tolerate those writes every name must be declared as a slot here.
    # All counters use Py_ssize_t; ``_phase4_handles`` is a list-or-None.
    # See ``Bench/tests/test_vllm_protocol_fixture.py`` —
    # ``test_phase4_external_attr_writes_succeed_on_cdef_class`` —
    # for the regression test that pins this surface.
    cdef public object _phase4_handles
    cdef public Py_ssize_t _phase4_rotary_pre_hook_calls
    cdef public Py_ssize_t _phase4_capture_subsample_skips
    cdef public Py_ssize_t _phase4_capture_exceptions
    cdef public Py_ssize_t _phase4_capture_attempts
    cdef public Py_ssize_t _phase4_capture_aborts_no_slot_mapping
    cdef public Py_ssize_t _phase4_capture_aborts_no_decode_tokens
    cdef public Py_ssize_t _phase4_side_channel_pre_hook_calls
    cdef public Py_ssize_t _phase4_side_channel_metadata_missing
    cdef public Py_ssize_t _phase4_side_channel_metadata_found

    def __cinit__(self):
        # Initialise all counters to 0 so getattr() default-zero paths
        # the Python class relies on are unnecessary in C.
        self._phase4_set_pre_rope_keys_calls = 0
        self._phase4_set_pre_rope_keys_speculative = 0
        self._phase4_trig_score_computes = 0
        self._phase4_trig_score_compute_exceptions = 0
        self._phase4_trig_score_lookups = 0
        self._phase4_trig_score_cache_misses = 0
        self._phase4_trig_blend_evict_calls = 0
        self._phase4_trig_blend_picks = 0
        self._phase4_trig_blend_skips = 0
        self._phase4_trig_changed_pick = 0
        self._phase4_pending_slot_mapping = None
        self._phase4_pending_num_decode_tokens = None
        # Hook-install + capture counters written by triattention's
        # install_* hooks. Match the implicit zero-default the Python
        # class gets from ``getattr(self, "...", 0)``.
        self._phase4_handles = None
        self._phase4_rotary_pre_hook_calls = 0
        self._phase4_capture_subsample_skips = 0
        self._phase4_capture_exceptions = 0
        self._phase4_capture_attempts = 0
        self._phase4_capture_aborts_no_slot_mapping = 0
        self._phase4_capture_aborts_no_decode_tokens = 0
        self._phase4_side_channel_pre_hook_calls = 0
        self._phase4_side_channel_metadata_missing = 0
        self._phase4_side_channel_metadata_found = 0

    def __init__(
        self,
        num_blocks_capacity,
        block_size=16,
        ctm_config=None,
        enable_logging=False,
        trig_scorer=None,
        trig_score_weight=0.30,
        window_pruning_interval=128,
        trig_blend_candidate_count=4,
    ):
        # Same construction pattern as the Python class. The defaults
        # match the Round 4 production weights — see the Python class
        # for the audit history.
        if ctm_config is None:
            self._policy = KVCachePolicy(
                max_blocks=num_blocks_capacity,
                block_size=block_size,
            )
        else:
            self._policy = KVCachePolicy(
                max_blocks=num_blocks_capacity,
                block_size=block_size,
                sink_tokens=ctm_config.sink_tokens,
                recent_window=ctm_config.recent_window,
                attention_ema_alpha=ctm_config.attention_ema_alpha,
            )
        self._policy.register_sequence(0)
        self._block_size = int(block_size)
        self._content_hash = {}
        self._num_hashed_tokens = {}
        self._last_accessed = {}
        self._tracked = set()
        self._enable_logging = bool(enable_logging)
        self._evict_timings = []

        self._trig_scorer = trig_scorer
        self._trig_score_weight = float(trig_score_weight)
        self._trig_blend_weight = float(trig_score_weight)
        if trig_blend_candidate_count < 1:
            raise ValueError(
                f"trig_blend_candidate_count must be >= 1; got "
                f"{trig_blend_candidate_count}"
            )
        self._trig_blend_candidate_count = int(trig_blend_candidate_count)
        self._block_pre_rope_keys = {}
        self._block_layer_head = {}
        self._block_trig_score = {}
        self._window_state = WindowPruningState(
            interval_tokens=int(window_pruning_interval)
        )

    # ---- vLLM 0.7 Evictor ABC ----

    def __contains__(self, block_id):
        return block_id in self._tracked

    def add(
        self,
        block_id,
        content_hash,
        num_hashed_tokens,
        last_accessed,
    ):
        cdef int bid = int(block_id)
        self._tracked.add(bid)
        self._content_hash[bid] = content_hash
        self._num_hashed_tokens[bid] = num_hashed_tokens
        self._last_accessed[bid] = last_accessed
        # See the Python class for the sink-offset rationale. The
        # ``ensure_block`` early-return + manual ``gpu_blocks.add`` pair
        # is the fix for the May-2026 GPU run's bug #3.
        cdef int sink_offset = self._policy.sink_tokens
        positions = list(range(sink_offset, sink_offset + self._block_size))
        self._policy.ensure_block(
            block_id=bid, sequence_id=0,
            positions=positions,
        )
        self._policy.gpu_blocks.add(bid)

    def update(self, block_id, last_accessed):
        cdef int bid = int(block_id)
        if bid not in self._tracked:
            return
        self._last_accessed[bid] = last_accessed
        self._policy.on_block_attention(
            block_id=bid, attention_sum=0.0,
            sequence_id=0,
            seq_len=self._num_hashed_tokens.get(bid, self._block_size),
        )

    def forward_block_attention(
        self,
        block_id,
        attention_sum,
        seq_len=None,
    ):
        cdef int bid = int(block_id)
        if bid not in self._tracked:
            return
        if seq_len is None:
            seq_len = self._num_hashed_tokens.get(bid, self._block_size)
        self._policy.on_block_attention(
            block_id=bid,
            attention_sum=float(attention_sum),
            sequence_id=0,
            seq_len=seq_len,
        )

    def remove(self, block_id):
        cdef int bid = int(block_id)
        if bid not in self._tracked:
            return
        self._tracked.discard(bid)
        self._content_hash.pop(bid, None)
        self._num_hashed_tokens.pop(bid, None)
        self._last_accessed.pop(bid, None)
        self._block_pre_rope_keys.pop(bid, None)
        self._block_layer_head.pop(bid, None)
        self._block_trig_score.pop(bid, None)
        self._policy.evict_block(bid)

    def evict(self):
        """Pick a victim using CTM+ scoring. See the Python class for
        the full design rationale; semantics here are
        bit-for-bit-identical and verified by the parametrized
        protocol fixture.
        """
        cdef double _t0 = _py_time.perf_counter()
        cdef bint trig_active
        cdef int candidate_count
        cdef int retry_i
        cdef object victim_id = None
        cdef list victims
        cdef list tracked_candidates
        cdef list stale
        cdef object bid
        cdef bint have_any_trig
        cdef object content_hash
        cdef double base
        cdef object trig
        cdef double final_score
        cdef list blended
        cdef object base_only_winner
        cdef dict base_scores
        try:
            trig_active = (
                self._trig_scorer is not None
                and self._trig_blend_weight > 0.0
            )
            candidate_count = (
                self._trig_blend_candidate_count if trig_active else 1
            )

            for retry_i in range(8):
                victims = list(self._policy.select_victims(count=candidate_count))
                if not victims:
                    raise ValueError(
                        "CTMEvictorModernC.evict() called with no tracked "
                        "blocks. vLLM should not call evict on an empty "
                        "cache; this is either a vLLM bug or a "
                        "tracking-state divergence."
                    )
                tracked_candidates = [b for b in victims if b in self._tracked]
                stale = [b for b in victims if b not in self._tracked]
                for b in stale:
                    self._policy.evict_block(b)
                if not tracked_candidates:
                    continue

                if trig_active and len(tracked_candidates) > 1:
                    # I5: short-circuit when no candidate has captured K.
                    have_any_trig = False
                    for b in tracked_candidates:
                        if b in self._block_trig_score:
                            have_any_trig = True
                            break
                    if not have_any_trig:
                        self._phase4_trig_blend_skips += 1
                        victim_id = tracked_candidates[0]
                        break

                    self._phase4_trig_blend_evict_calls += 1
                    base_scores = {
                        b: self._policy.score_block(b)
                        for b in tracked_candidates
                    }
                    blended = []
                    for b in tracked_candidates:
                        base = float(base_scores[b])
                        trig = self.trig_score_block(b)
                        if trig is None:
                            final_score = base
                        else:
                            final_score = base + (
                                self._trig_blend_weight * float(trig)
                            )
                        blended.append((final_score, b))
                    blended.sort(key=_first)
                    victim_id = blended[0][1]
                    self._phase4_trig_blend_picks += 1
                    base_only_winner = min(
                        tracked_candidates, key=base_scores.get,
                    )
                    if base_only_winner != victim_id:
                        self._phase4_trig_changed_pick += 1
                else:
                    victim_id = tracked_candidates[0]
                break
            else:
                raise ValueError(
                    "CTMEvictorModernC.evict(): exhausted retries trying "
                    "to find a victim that is tracked. policy gpu_blocks "
                    "and self._tracked have diverged."
                )
            assert victim_id is not None
            content_hash = self._content_hash.pop(victim_id)
            self._num_hashed_tokens.pop(victim_id, None)
            self._last_accessed.pop(victim_id, None)
            self._tracked.discard(victim_id)
            self._block_pre_rope_keys.pop(victim_id, None)
            self._block_layer_head.pop(victim_id, None)
            self._block_trig_score.pop(victim_id, None)
            self._policy.evict_block(victim_id)
            return (victim_id, content_hash)
        finally:
            self._evict_timings.append(_py_time.perf_counter() - _t0)

    def evict_timings_seconds(self):
        return list(self._evict_timings)

    def reset_evict_timings(self):
        self._evict_timings.clear()

    @property
    def num_blocks(self):
        return len(self._tracked)

    def get_stats(self):
        return self._policy.stats

    # ---- Phase 4 API ----

    def set_block_pre_rope_keys(
        self,
        block_id,
        keys,
        layer=0,
        head=0,
    ):
        cdef int bid = int(block_id)
        self._phase4_set_pre_rope_keys_calls += 1
        if bid not in self._tracked:
            self._phase4_set_pre_rope_keys_speculative += 1
        keys_list = list(keys)
        self._block_pre_rope_keys[bid] = keys_list
        self._block_layer_head[bid] = (int(layer), int(head))
        if self._trig_scorer is not None:
            self._phase4_trig_score_computes += 1
            try:
                self._block_trig_score[bid] = (
                    aggregate_block_trig_score(
                        scorer=self._trig_scorer,
                        layer=int(layer), head=int(head),
                        block_keys=keys_list,
                    )
                )
            except Exception:
                self._phase4_trig_score_compute_exceptions += 1

    def trig_score_block(self, block_id):
        cdef int bid = int(block_id)
        if self._trig_scorer is None:
            return None
        self._phase4_trig_score_lookups += 1
        cached = self._block_trig_score.get(bid)
        if cached is not None:
            return cached
        self._phase4_trig_score_cache_misses += 1
        block_keys = self._block_pre_rope_keys.get(bid)
        if not block_keys:
            return None
        layer_head = self._block_layer_head.get(bid, (0, 0))
        return aggregate_block_trig_score(
            scorer=self._trig_scorer,
            layer=layer_head[0], head=layer_head[1],
            block_keys=block_keys,
        )

    def window_pruning_passed(self, decode_tokens_emitted):
        return window_pruning_decision(
            self._window_state, decode_tokens_emitted,
        )

    def window_pruning_pass(self, target_blocks):
        cdef int target = int(target_blocks)
        cdef int n_to_evict
        cdef int evicted = 0
        if self._trig_scorer is None or len(self._tracked) <= target:
            return 0

        scored = []
        for bid in list(self._tracked):
            score = self.trig_score_block(bid)
            if score is None:
                continue
            scored.append((score, bid))

        if not scored:
            return 0

        scored.sort(key=_first)
        n_to_evict = max(0, len(self._tracked) - target)
        for _, bid in scored[:n_to_evict]:
            try:
                self.remove(bid)
                self._block_pre_rope_keys.pop(bid, None)
                self._block_layer_head.pop(bid, None)
                self._block_trig_score.pop(bid, None)
                evicted += 1
            except Exception:
                continue
        return evicted

    @property
    def window_pruning_invocations(self):
        return self._window_state.n_prune_invocations


def _first(t):
    """Module-level key function for ``list.sort(key=...)``. Cython
    handles a module-level ``def`` better than a lambda in a hot path.
    """
    return t[0]
