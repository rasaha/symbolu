"""
FrequencySketch conformance tests — PCAM vs CTM+ reference.

This suite locks the behavioral contract between the PCAM simulator's
FrequencySketch port and the canonical implementation at

    CTM_plus/KVPolicy/kv_policy/attention_evictor.py:69-112

per ADR-0001 (docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md).

Scope
-----
Sketch-level parity ONLY. End-to-end KVCachePolicy parity lives in
test_attention_evictor_parity.py. Keeping them separate keeps failures
diagnosable — a mismatch here means the sketch port is wrong, a mismatch
there means the scoring / pinning / fast-path logic is wrong.

PCAM side
---------
The PCAM-side sketch is expected at `simulator.pcam.kv_policy.FrequencySketch`.
Until the PCAM alignment PR lands that module, the tests skip with a
clear pointer. This is intentional: the harness is committed now so that
(a) the contract is visible in the repo and (b) the tests auto-activate
as the implementation lands.

Reference side
--------------
Imported directly from `kv_policy.attention_evictor`. The reference is the
oracle — we never assert against hand-computed hash outputs. We assert
PCAM equals reference on a fixed trace, and we assert structural invariants
(saturation, monotonicity, halving) that must hold on both.

Golden trace
------------
simulator/pcam/tests/fixtures/sketch_golden_trace.json contains input-only
scenarios. The expected outputs are computed at test time by running the
reference, which keeps the fixture human-readable while preserving
exact-equality assertions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

# ---------------------------------------------------------------------------
# Path wiring for the reference package.
#
# CTM_plus/KVPolicy/kv_policy is a standalone setup.py package imported as
# `kv_policy`, not as `CTM_plus.KVPolicy.kv_policy`. We add its parent to
# sys.path so tests run without requiring `pip install -e`.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_KV_POLICY_PARENT = _REPO_ROOT / "CTM_plus" / "KVPolicy"
if str(_KV_POLICY_PARENT) not in sys.path:
    sys.path.insert(0, str(_KV_POLICY_PARENT))

from kv_policy.attention_evictor import FrequencySketch as RefFrequencySketch


# ---------------------------------------------------------------------------
# PCAM-side import with graceful skip.
# ---------------------------------------------------------------------------
_PCAM_SKIP_REASON = (
    "PCAM-side FrequencySketch not found at simulator.pcam.kv_policy. "
    "This module is introduced by the PCAM alignment PR described in "
    "simulator/pcam/docs/PCAM_UPDATE_PR_SCOPE.md. The test suite will "
    "auto-activate once that module exists and exports FrequencySketch."
)


def _load_pcam_sketch_class():
    """Resolve the PCAM-side FrequencySketch class, or skip."""
    try:
        from simulator.pcam.kv_policy import FrequencySketch as PCAMFrequencySketch  # type: ignore
    except ImportError:
        pytest.skip(_PCAM_SKIP_REASON, allow_module_level=False)
    return PCAMFrequencySketch


# ---------------------------------------------------------------------------
# Golden trace fixture loader.
# ---------------------------------------------------------------------------
_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sketch_golden_trace.json"


@pytest.fixture(scope="module")
def golden_trace() -> Dict[str, Any]:
    with _FIXTURE_PATH.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _paired_sketches(capacity: int) -> Tuple[RefFrequencySketch, Any]:
    """Build a reference sketch and a PCAM sketch with identical construction."""
    pcam_cls = _load_pcam_sketch_class()
    return RefFrequencySketch(capacity), pcam_cls(capacity)


def _assert_equal_estimates(
    ref: RefFrequencySketch,
    pcam: Any,
    keys: List[int],
    context: str,
) -> None:
    """Assert that both sketches return bit-identical estimates for every key."""
    for key in keys:
        r = ref.estimate(key)
        p = pcam.estimate(key)
        assert r == p, (
            f"[{context}] estimate divergence on key={key}: "
            f"reference={r}, pcam={p}"
        )


# ===========================================================================
# Structural tests — must hold on both sides independently.
# ===========================================================================


class TestStructuralInvariants:
    """Contract-level checks that don't require parity, just internal consistency."""

    def test_reference_width_floor(self):
        """Reference enforces max(64, capacity) before next_pow2."""
        tiny = RefFrequencySketch(capacity=4)
        assert tiny.width >= 64, "reference must floor width at 64"
        assert (tiny.width & (tiny.width - 1)) == 0, "width must be power of two"

    def test_reference_depth_is_four(self):
        assert RefFrequencySketch(capacity=256).depth == 4

    def test_reference_reset_threshold_is_ten_times_capacity(self):
        assert RefFrequencySketch(capacity=128).reset_threshold == 1280

    def test_reference_saturates_at_fifteen(self):
        """20 increments of one key must land at estimate == 15, not 16 or 20."""
        s = RefFrequencySketch(capacity=4096)  # large, no halving
        for _ in range(20):
            s.increment(42)
        assert s.estimate(42) == 15

    def test_pcam_matches_structural_invariants(self):
        """PCAM port must expose the same width floor, depth, threshold."""
        pcam_cls = _load_pcam_sketch_class()
        tiny = pcam_cls(capacity=4)
        mid = pcam_cls(capacity=128)
        assert tiny.width >= 64
        assert (tiny.width & (tiny.width - 1)) == 0
        assert tiny.depth == 4
        assert mid.reset_threshold == 1280


# ===========================================================================
# Parity tests — PCAM must be observationally equivalent to the reference.
# ===========================================================================


class TestSketchParity:
    """Bit-for-bit estimate equality on fixed input streams."""

    def test_single_key_saturation_parity(self):
        """Repeated same key: both sides must saturate at 15 identically."""
        ref, pcam = _paired_sketches(capacity=1024)
        for step in range(1, 21):
            r_inc = ref.increment(42)
            p_inc = pcam.increment(42)
            assert r_inc == p_inc, (
                f"increment return value diverged at step {step}: "
                f"ref={r_inc}, pcam={p_inc}"
            )
        _assert_equal_estimates(ref, pcam, [42], "post-saturation")
        assert ref.estimate(42) == 15

    def test_distinct_keys_light_load_parity(self):
        """32 distinct keys into a width-1024 sketch — collisions rare but possible."""
        ref, pcam = _paired_sketches(capacity=1024)
        for k in range(32):
            ref.increment(k)
            pcam.increment(k)
        # Check every inserted key plus one never-seen key.
        _assert_equal_estimates(
            ref, pcam, list(range(32)) + [9999], "distinct-keys"
        )
        # Never-inserted key must be 0 on the reference side (no collisions at
        # this load factor). If it ever isn't, the assertion on parity still
        # holds — parity is the real contract.
        assert ref.estimate(9999) == 0

    def test_hash_determinism_parity(self):
        """Two independent instances must map identical keys identically."""
        ref_a, pcam_a = _paired_sketches(capacity=256)
        ref_b, pcam_b = _paired_sketches(capacity=256)
        keys = [0, 1, 42, 128, 255, 1000, 65535, 2147483647]

        # Insert the same keys into all four sketches.
        for k in keys:
            ref_a.increment(k)
            ref_b.increment(k)
            pcam_a.increment(k)
            pcam_b.increment(k)

        # Reference instances must agree with themselves (sanity).
        for k in keys:
            assert ref_a.estimate(k) == ref_b.estimate(k)
        # PCAM instances must agree with themselves.
        for k in keys:
            assert pcam_a.estimate(k) == pcam_b.estimate(k)
        # And PCAM must agree with reference.
        _assert_equal_estimates(ref_a, pcam_a, keys, "hash-determinism")


class TestHalvingParity:
    """Halving is the trickiest path — test it isolated."""

    def test_halving_fires_at_reset_threshold(self):
        """
        At capacity=16 the reset threshold is 160. The halve happens INSIDE
        increment() when size >= reset_threshold, BEFORE the current key's
        counters are bumped.

        We verify:
          1. Size crosses the threshold on both sides simultaneously.
          2. Previously-saturated counters are right-shifted.
          3. Post-halve size is exactly half of pre-halve size.
        """
        ref, pcam = _paired_sketches(capacity=16)
        assert ref.reset_threshold == 160
        assert pcam.reset_threshold == 160

        # Saturate key 0 on both sides up front so we can watch it halve.
        for _ in range(15):
            ref.increment(0)
            pcam.increment(0)
        assert ref.estimate(0) == 15
        assert pcam.estimate(0) == 15

        # Drive size up to just under the threshold with filler keys.
        for k in range(1, 145):  # 144 more increments → size = 159
            ref.increment(k)
            pcam.increment(k)
        assert ref.size == 159
        assert pcam.size == 159
        # Key 0 is still saturated on both.
        _assert_equal_estimates(ref, pcam, [0], "pre-halve")
        assert ref.estimate(0) == 15

        # The next increment crosses the threshold and triggers halving.
        ref.increment(9999)
        pcam.increment(9999)

        # Post-halve size must be exactly (160 >> 1) = 80, then +1 for the
        # current increment's row bumps — but size is only bumped once per
        # increment() call, BEFORE the halve runs. So the halve sees size=160
        # and produces size=80. There is no post-halve bump to size itself.
        assert ref.size == 80
        assert pcam.size == 80

        # Key 0 was 15 → right-shift → 7.
        assert ref.estimate(0) == 7
        assert pcam.estimate(0) == 7

    def test_post_halving_ordering_preservation(self):
        """
        Keys with distinct pre-halve counts must retain rough ordering after
        halving. 8 >> 1 = 4, 4 >> 1 = 2, 2 >> 1 = 1, 1 >> 1 = 0.
        """
        ref, pcam = _paired_sketches(capacity=64)

        def bump(sketches, key, times):
            for _ in range(times):
                for s in sketches:
                    s.increment(key)

        sketches = [ref, pcam]
        bump(sketches, 100, 8)
        bump(sketches, 101, 4)
        bump(sketches, 102, 2)
        bump(sketches, 103, 1)

        # Verify pre-halve state.
        assert ref.estimate(100) == 8
        assert ref.estimate(101) == 4
        assert ref.estimate(102) == 2
        assert ref.estimate(103) == 1

        # Push size over threshold = 640 with filler keys.
        for k in range(10000, 10000 + 626):
            ref.increment(k)
            pcam.increment(k)
            if ref.size >= ref.reset_threshold:
                break

        # After at least one halving event, parity must hold...
        _assert_equal_estimates(
            ref, pcam, [100, 101, 102, 103], "post-halve-ordering"
        )
        # ...and the pre-halve ordering must be preserved on the reference
        # side (and therefore on PCAM via parity).
        assert ref.estimate(100) >= ref.estimate(101) >= ref.estimate(
            102
        ) >= ref.estimate(103)


# ===========================================================================
# Golden-trace driven tests — replay the fixture file.
# ===========================================================================


class TestGoldenTraceReplay:
    """Drive both sides from the human-readable fixture."""

    def test_fixture_file_loads_and_has_expected_scenarios(self, golden_trace):
        assert "sketch_traces" in golden_trace
        expected = {
            "single_key_saturation",
            "distinct_keys_light_load",
            "halving_threshold",
            "post_halving_order_preservation",
            "hash_determinism",
        }
        assert expected.issubset(set(golden_trace["sketch_traces"].keys()))

    def test_golden_single_key_saturation(self, golden_trace):
        trace = golden_trace["sketch_traces"]["single_key_saturation"]
        ref, pcam = _paired_sketches(capacity=trace["capacity"])
        observe = trace["observe_key"]
        for _ in trace["increments"]:
            ref.increment(observe)
            pcam.increment(observe)
        assert ref.estimate(observe) == pcam.estimate(observe) == 15

    def test_golden_hash_determinism(self, golden_trace):
        trace = golden_trace["sketch_traces"]["hash_determinism"]
        ref, pcam = _paired_sketches(capacity=trace["capacity"])
        # Insert each probe key once and verify parity.
        for k in trace["keys"]:
            ref.increment(k)
            pcam.increment(k)
        _assert_equal_estimates(ref, pcam, trace["keys"], "golden-hash")


# ===========================================================================
# Randomized differential test — the safety net.
# ===========================================================================


class TestRandomizedParity:
    """
    Drive a long pseudo-random trace through both sketches and assert
    per-step parity. Catches drift that the targeted tests above might miss.
    """

    def test_randomized_parity_500_steps(self):
        import random

        rng = random.Random(0xC0DECAFE)
        ref, pcam = _paired_sketches(capacity=512)

        key_universe = list(range(200))
        for step in range(500):
            key = rng.choice(key_universe)
            r = ref.increment(key)
            p = pcam.increment(key)
            assert r == p, (
                f"increment return diverged at step {step}, key={key}: "
                f"ref={r}, pcam={p}, ref.size={ref.size}, pcam.size={pcam.size}"
            )
            # Spot-check estimates on a few keys every 25 steps.
            if step % 25 == 0:
                probes = rng.sample(key_universe, 8)
                _assert_equal_estimates(ref, pcam, probes, f"step={step}")
