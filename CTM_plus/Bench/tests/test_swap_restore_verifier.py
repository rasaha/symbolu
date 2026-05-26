"""Phase TIER5A.1 CPU tests for the swap-restore verifier.

Covers the G1 verdict-logic surface exposed by
``ctm_bench.swap_restore_verifier``:

* compute_g1_verdict returns GREEN on bit-identical outputs with
  pressure-cell swap_out_blocks > 0.
* RED when outputs differ.
* NO_PRESSURE when outputs are identical but swap path was not
  exercised.
* INVALID when either cell didn't complete or both outputs are
  empty.
* Divergence index + common prefix tokens reported in all
  divergent / partial cases.
* Workload spec validation rejects malformed inputs.
* ``make_default_verifier_prompt`` is deterministic byte-for-byte
  across runs.

No torch, no vllm. CPU-only.
"""

from __future__ import annotations

import pytest

from ctm_bench.swap_restore_verifier import (
    G1Result,
    G1Verdict,
    VerifierCellRecord,
    VerifierWorkloadSpec,
    _common_prefix_length,
    _first_divergence,
    compute_g1_verdict,
    make_default_verifier_prompt,
)


# ---------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------- #


def _record(
    *,
    name: str,
    outputs: tuple,
    swap_out: int = 0,
    swap_in: int = 0,
    preempt: int = 0,
    completed: bool = True,
    cpu_peak: int = 0,
) -> VerifierCellRecord:
    return VerifierCellRecord(
        cell_name=name,
        prompt_token_ids=(101, 102, 103),
        output_token_ids=outputs,
        n_decode_tokens=len(outputs),
        swap_out_blocks_total=swap_out,
        swap_in_blocks_total=swap_in,
        preemption_events_total=preempt,
        cpu_swap_pool_peak_used_blocks=cpu_peak,
        completed=completed,
    )


# ---------------------------------------------------------------- #
# common_prefix_length + first_divergence
# ---------------------------------------------------------------- #


def test_common_prefix_length_full_match():
    a = (1, 2, 3, 4)
    b = (1, 2, 3, 4)
    assert _common_prefix_length(a, b) == 4


def test_common_prefix_length_partial_match():
    a = (1, 2, 3, 4)
    b = (1, 2, 9, 4)
    assert _common_prefix_length(a, b) == 2


def test_common_prefix_length_disjoint():
    a = (1, 2)
    b = (5, 6)
    assert _common_prefix_length(a, b) == 0


def test_common_prefix_length_different_lengths_with_full_overlap():
    a = (1, 2, 3)
    b = (1, 2, 3, 4)
    assert _common_prefix_length(a, b) == 3


def test_first_divergence_identical_returns_none():
    assert _first_divergence((1, 2, 3), (1, 2, 3)) is None


def test_first_divergence_at_specific_index():
    assert _first_divergence((1, 2, 9, 4), (1, 2, 3, 4)) == 2


def test_first_divergence_length_mismatch_with_identical_prefix():
    """Equal prefix but different lengths: divergence at the
    shorter length."""
    assert _first_divergence((1, 2, 3), (1, 2, 3, 4)) == 3


# ---------------------------------------------------------------- #
# G1 verdict — GREEN
# ---------------------------------------------------------------- #


def test_g1_green_on_bit_identical_with_swap_evidence():
    base = _record(name="A", outputs=(50, 51, 52, 53))
    press = _record(
        name="B", outputs=(50, 51, 52, 53),
        swap_out=128, swap_in=64, preempt=4, cpu_peak=200,
    )
    r = compute_g1_verdict(baseline=base, pressure=press)
    assert isinstance(r, G1Result)
    assert r.verdict == G1Verdict.GREEN
    assert r.passed is True
    assert r.bit_identical is True
    assert r.common_prefix_tokens == 4
    assert r.divergence_index is None
    assert "bit-identical" in r.reason
    assert "swap_out_blocks=128" in r.reason


# ---------------------------------------------------------------- #
# G1 verdict — NO_PRESSURE
# ---------------------------------------------------------------- #


def test_g1_no_pressure_when_swap_out_zero():
    base = _record(name="A", outputs=(50, 51, 52, 53))
    press = _record(
        name="B", outputs=(50, 51, 52, 53),
        swap_out=0,   # the swap path never fired
    )
    r = compute_g1_verdict(baseline=base, pressure=press)
    assert r.verdict == G1Verdict.NO_PRESSURE
    assert r.passed is False
    assert r.bit_identical is True
    assert "not exercised" in r.reason


# ---------------------------------------------------------------- #
# G1 verdict — RED
# ---------------------------------------------------------------- #


def test_g1_red_when_outputs_diverge_mid_decode():
    base = _record(name="A", outputs=(50, 51, 52, 53))
    press = _record(
        name="B", outputs=(50, 51, 99, 53),
        swap_out=8,
    )
    r = compute_g1_verdict(baseline=base, pressure=press)
    assert r.verdict == G1Verdict.RED
    assert r.passed is False
    assert r.bit_identical is False
    assert r.common_prefix_tokens == 2
    assert r.divergence_index == 2
    assert "diverged at index 2" in r.reason


def test_g1_red_when_length_differs():
    base = _record(name="A", outputs=(50, 51, 52))
    press = _record(
        name="B", outputs=(50, 51, 52, 53),
        swap_out=8,
    )
    r = compute_g1_verdict(baseline=base, pressure=press)
    assert r.verdict == G1Verdict.RED
    assert r.bit_identical is False
    assert r.common_prefix_tokens == 3
    assert r.divergence_index == 3


# ---------------------------------------------------------------- #
# G1 verdict — INVALID
# ---------------------------------------------------------------- #


def test_g1_invalid_when_cell_did_not_complete():
    base = _record(name="A", outputs=(50, 51, 52), completed=False)
    press = _record(name="B", outputs=(50, 51, 52), swap_out=8)
    r = compute_g1_verdict(baseline=base, pressure=press)
    assert r.verdict == G1Verdict.INVALID
    assert r.passed is False
    assert "did not complete" in r.reason


def test_g1_invalid_when_both_outputs_empty():
    base = _record(name="A", outputs=())
    press = _record(name="B", outputs=(), swap_out=8)
    r = compute_g1_verdict(baseline=base, pressure=press)
    assert r.verdict == G1Verdict.INVALID
    assert "both cells produced empty output" in r.reason


def test_g1_invalid_when_one_output_empty():
    base = _record(name="A", outputs=(1, 2, 3))
    press = _record(name="B", outputs=(), swap_out=8)
    r = compute_g1_verdict(baseline=base, pressure=press)
    assert r.verdict == G1Verdict.INVALID
    assert "pressure cell produced empty output" in r.reason


# ---------------------------------------------------------------- #
# VerifierWorkloadSpec validation
# ---------------------------------------------------------------- #


def test_workload_spec_valid_minimal():
    spec = VerifierWorkloadSpec(
        verifier_prompt_token_ids=(1, 2, 3),
        verifier_max_decode_tokens=32,
        n_pressure_requests=0,
        pressure_prompt_lengths=(),
        pressure_max_decode_tokens=0,
        pareto_arrival_rate=4.0,
        pareto_alpha=1.5,
    )
    assert spec.verifier_max_decode_tokens == 32


def test_workload_spec_rejects_zero_verifier_decode():
    with pytest.raises(ValueError):
        VerifierWorkloadSpec(
            verifier_prompt_token_ids=(1,),
            verifier_max_decode_tokens=0,
            n_pressure_requests=0,
            pressure_prompt_lengths=(),
            pressure_max_decode_tokens=0,
            pareto_arrival_rate=4.0,
            pareto_alpha=1.5,
        )


def test_workload_spec_rejects_negative_n_pressure():
    with pytest.raises(ValueError):
        VerifierWorkloadSpec(
            verifier_prompt_token_ids=(1,),
            verifier_max_decode_tokens=32,
            n_pressure_requests=-1,
            pressure_prompt_lengths=(256,),
            pressure_max_decode_tokens=64,
            pareto_arrival_rate=4.0,
            pareto_alpha=1.5,
        )


def test_workload_spec_rejects_pressure_without_lengths():
    with pytest.raises(ValueError):
        VerifierWorkloadSpec(
            verifier_prompt_token_ids=(1,),
            verifier_max_decode_tokens=32,
            n_pressure_requests=10,
            pressure_prompt_lengths=(),     # empty when n_pressure>0
            pressure_max_decode_tokens=64,
            pareto_arrival_rate=4.0,
            pareto_alpha=1.5,
        )


def test_workload_spec_rejects_zero_pressure_length():
    with pytest.raises(ValueError):
        VerifierWorkloadSpec(
            verifier_prompt_token_ids=(1,),
            verifier_max_decode_tokens=32,
            n_pressure_requests=4,
            pressure_prompt_lengths=(0, 64),
            pressure_max_decode_tokens=32,
            pareto_arrival_rate=4.0,
            pareto_alpha=1.5,
        )


def test_workload_spec_rejects_nonpositive_arrival_rate():
    with pytest.raises(ValueError):
        VerifierWorkloadSpec(
            verifier_prompt_token_ids=(1,),
            verifier_max_decode_tokens=32,
            n_pressure_requests=0,
            pressure_prompt_lengths=(),
            pressure_max_decode_tokens=0,
            pareto_arrival_rate=0.0,
            pareto_alpha=1.5,
        )


# ---------------------------------------------------------------- #
# make_default_verifier_prompt — deterministic + bounded
# ---------------------------------------------------------------- #


def test_default_prompt_is_deterministic():
    a = make_default_verifier_prompt(length_tokens=96)
    b = make_default_verifier_prompt(length_tokens=96)
    assert a == b


def test_default_prompt_length_matches_request():
    p = make_default_verifier_prompt(length_tokens=64)
    assert len(p) == 64


def test_default_prompt_token_ids_in_expected_range():
    p = make_default_verifier_prompt(length_tokens=256)
    for tok in p:
        assert 1 <= tok <= 5999


def test_default_prompt_rejects_nonpositive_length():
    with pytest.raises(ValueError):
        make_default_verifier_prompt(length_tokens=0)
    with pytest.raises(ValueError):
        make_default_verifier_prompt(length_tokens=-5)
