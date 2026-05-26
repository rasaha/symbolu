"""Phase TIER5A — Bit-identity verifier across forced preemption.

Acceptance gate **G1**: int4_protected output must be bit-identical
before vs after a forced ``preemption_mode='swap'`` swap-out +
swap-in cycle.

The verifier compares two greedy-decode runs of the same prompt:

* **Baseline cell** (cell A in the TIER5A bench): low memory
  pressure, no preemption expected. Records the reference
  output token IDs.
* **Pressure cell** (cell B in the TIER5A bench): engineered
  pressure that forces vLLM to swap the verifier prompt's KV
  blocks out to CPU and back. Records the output token IDs +
  swap-event evidence.

G1 verdict logic:

* ``GREEN`` — bit-identical AND the pressure cell observed
  ``swap_out_blocks > 0`` (so the run actually exercised the
  swap path; otherwise the comparison is meaningless).
* ``NO_PRESSURE`` — outputs are bit-identical but
  ``swap_out_blocks == 0``. The pressure cell didn't actually
  trigger the swap path; the comparison doesn't prove anything
  about int4_protected's behaviour under swap. Operator must
  re-engineer pressure (lower ``gpu_memory_utilization``, more
  concurrent requests, etc.).
* ``RED`` — outputs differ. The packed KV layout did not survive
  the swap path. Phase TIER5A finding is negative; cold tier
  (Phase TIER5B) cannot be folded in for free.
* ``INVALID`` — at least one of the two cells failed to produce
  any output for the verifier prompt. Test failure, not an
  int4_protected verdict.

## Orthogonality contract (durable)

This module does NOT touch and MUST NOT import:

* ``Int4ProtectedAttentionImpl`` (orthogonal)
* The forked vllm-flash-attn kernel (orthogonal)
* The protected-channel splice, sink mechanism, or paged writer

The verifier observes outputs (token IDs) and engine telemetry
only. The TIER5A G5 + G6 gates enforce this contract.

CPU-only design: all comparison logic is unit-testable with
synthetic token lists. The GPU-touching part (driving an
AsyncLLMEngine) is wired in ``bench_tier5a_swap_restore.py``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


class G1Verdict(str, enum.Enum):
    """Acceptance verdict for the G1 gate."""

    GREEN = "green"
    NO_PRESSURE = "no_pressure"
    RED = "red"
    INVALID = "invalid"


@dataclass(frozen=True)
class VerifierCellRecord:
    """Single-cell outcome for the verifier prompt.

    Captures the data that G1 needs to compare across cells.
    Frozen so cells can be aggregated / passed across boundaries
    safely.
    """

    cell_name: str
    prompt_token_ids: Tuple[int, ...]
    output_token_ids: Tuple[int, ...]
    n_decode_tokens: int
    swap_out_blocks_total: int
    swap_in_blocks_total: int
    preemption_events_total: int
    cpu_swap_pool_peak_used_blocks: int = 0
    cpu_swap_pool_total_blocks: int = 0
    request_id: Optional[str] = None
    completed: bool = True
    notes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class G1Result:
    """Aggregate G1 verdict + the supporting evidence."""

    verdict: G1Verdict
    baseline: VerifierCellRecord
    pressure: VerifierCellRecord
    bit_identical: bool
    common_prefix_tokens: int
    divergence_index: Optional[int]
    reason: str

    @property
    def passed(self) -> bool:
        """True iff verdict is GREEN."""
        return self.verdict == G1Verdict.GREEN


def _common_prefix_length(
    a: Sequence[int], b: Sequence[int],
) -> int:
    """Number of leading tokens that match between ``a`` and ``b``."""
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n


def _first_divergence(
    a: Sequence[int], b: Sequence[int],
) -> Optional[int]:
    """Index of the first differing position. ``None`` iff the
    sequences are equal AND the same length.

    Length mismatch with identical prefix returns ``min(len(a),
    len(b))`` — the index where the shorter sequence ends.
    """
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    if len(a) != len(b):
        return n
    return None


def compute_g1_verdict(
    *,
    baseline: VerifierCellRecord,
    pressure: VerifierCellRecord,
) -> G1Result:
    """Apply the G1 verdict rule to two cell records.

    The verdict is documented in the module docstring. This
    function is pure: same inputs → same verdict. CPU-only.
    No vLLM, no torch.
    """
    if not baseline.completed or not pressure.completed:
        return G1Result(
            verdict=G1Verdict.INVALID,
            baseline=baseline,
            pressure=pressure,
            bit_identical=False,
            common_prefix_tokens=0,
            divergence_index=0 if (
                baseline.output_token_ids or pressure.output_token_ids
            ) else None,
            reason=(
                "at least one cell did not complete the verifier "
                "prompt — comparison is invalid"
            ),
        )

    if not baseline.output_token_ids and not pressure.output_token_ids:
        return G1Result(
            verdict=G1Verdict.INVALID,
            baseline=baseline,
            pressure=pressure,
            bit_identical=False,
            common_prefix_tokens=0,
            divergence_index=None,
            reason=(
                "both cells produced empty output — verifier prompt "
                "did not decode in either cell"
            ),
        )

    if not baseline.output_token_ids or not pressure.output_token_ids:
        empty_cell = (
            "baseline" if not baseline.output_token_ids else "pressure"
        )
        return G1Result(
            verdict=G1Verdict.INVALID,
            baseline=baseline,
            pressure=pressure,
            bit_identical=False,
            common_prefix_tokens=0,
            divergence_index=0,
            reason=(
                f"{empty_cell} cell produced empty output for the "
                "verifier prompt"
            ),
        )

    base_ids = list(baseline.output_token_ids)
    press_ids = list(pressure.output_token_ids)
    bit_identical = base_ids == press_ids
    common_prefix = _common_prefix_length(base_ids, press_ids)
    div_idx = _first_divergence(base_ids, press_ids)

    if not bit_identical:
        return G1Result(
            verdict=G1Verdict.RED,
            baseline=baseline,
            pressure=pressure,
            bit_identical=False,
            common_prefix_tokens=common_prefix,
            divergence_index=div_idx,
            reason=(
                f"outputs diverged at index {div_idx} "
                f"(common prefix {common_prefix} tokens, baseline len "
                f"{len(base_ids)}, pressure len {len(press_ids)})"
            ),
        )

    # Outputs are bit-identical. Did the pressure cell actually
    # exercise the swap path?
    if pressure.swap_out_blocks_total <= 0:
        return G1Result(
            verdict=G1Verdict.NO_PRESSURE,
            baseline=baseline,
            pressure=pressure,
            bit_identical=True,
            common_prefix_tokens=common_prefix,
            divergence_index=None,
            reason=(
                "outputs are bit-identical but pressure cell "
                f"swap_out_blocks={pressure.swap_out_blocks_total}; "
                "the swap path was not exercised, so G1 is "
                "inconclusive. Re-run with tighter "
                "gpu_memory_utilization or more concurrent "
                "pressure requests."
            ),
        )

    return G1Result(
        verdict=G1Verdict.GREEN,
        baseline=baseline,
        pressure=pressure,
        bit_identical=True,
        common_prefix_tokens=common_prefix,
        divergence_index=None,
        reason=(
            f"bit-identical (n={len(base_ids)} tokens); "
            f"pressure cell swap_out_blocks="
            f"{pressure.swap_out_blocks_total}, "
            f"preemption_events={pressure.preemption_events_total}, "
            f"cpu_swap_pool_peak_used_blocks="
            f"{pressure.cpu_swap_pool_peak_used_blocks}"
        ),
    )


# ---------------------------------------------------------------- #
# Mini-batch synthesis for the pressure cell.
#
# The verifier prompt is submitted FIRST, with greedy decode,
# inside a cell that also submits a swarm of pressure prompts.
# We want vLLM's preemption decision to fall on the verifier.
# Generating distinct-content pressure prompts (so they don't
# share prefixes with the verifier) maximizes the chance that
# the verifier gets selected for swap when memory pressure peaks.
# ---------------------------------------------------------------- #


@dataclass(frozen=True)
class VerifierWorkloadSpec:
    """Spec for the two-cell bench workload.

    * ``verifier_prompt_token_ids`` — the single prompt whose
      output we G1-compare across cells.
    * ``verifier_max_decode_tokens`` — greedy decode length for
      the verifier. Should be modest (32-128) so the comparison
      is fast.
    * ``n_pressure_requests`` — number of pressure prompts to
      submit alongside the verifier in cell B. ``0`` for cell A
      (no pressure).
    * ``pressure_prompt_lengths`` — per-pressure-request prompt
      length distribution. Sampled with replacement.
    * ``pressure_max_decode_tokens`` — per-pressure-request decode
      length. Longer = more KV pressure per pressure request.
    * ``pareto_arrival_rate`` — pareto base rate; the bench will
      use this directly via ``ParetoArrivalConfig``.
    * ``pareto_alpha`` — Pareto burstiness shape. Lower = more
      bursty.
    """

    verifier_prompt_token_ids: Tuple[int, ...]
    verifier_max_decode_tokens: int
    n_pressure_requests: int
    pressure_prompt_lengths: Tuple[int, ...]
    pressure_max_decode_tokens: int
    pareto_arrival_rate: float
    pareto_alpha: float

    def __post_init__(self) -> None:  # type: ignore[override]
        if self.verifier_max_decode_tokens <= 0:
            raise ValueError(
                "verifier_max_decode_tokens must be > 0; got "
                f"{self.verifier_max_decode_tokens}"
            )
        if self.n_pressure_requests < 0:
            raise ValueError(
                "n_pressure_requests must be >= 0; got "
                f"{self.n_pressure_requests}"
            )
        if self.pressure_max_decode_tokens < 0:
            raise ValueError(
                "pressure_max_decode_tokens must be >= 0; got "
                f"{self.pressure_max_decode_tokens}"
            )
        if self.n_pressure_requests > 0:
            if not self.pressure_prompt_lengths:
                raise ValueError(
                    "pressure_prompt_lengths must be non-empty when "
                    "n_pressure_requests > 0"
                )
            for L in self.pressure_prompt_lengths:
                if L <= 0:
                    raise ValueError(
                        "all pressure_prompt_lengths must be > 0; "
                        f"got {L}"
                    )
        if self.pareto_arrival_rate <= 0:
            raise ValueError(
                "pareto_arrival_rate must be > 0; got "
                f"{self.pareto_arrival_rate}"
            )
        if self.pareto_alpha <= 0:
            raise ValueError(
                "pareto_alpha must be > 0; got "
                f"{self.pareto_alpha}"
            )


def make_default_verifier_prompt(*, length_tokens: int = 96) -> Tuple[int, ...]:
    """A deterministic synthetic prompt for the verifier.

    Uses token IDs in [1, 9999] (a safe range for most tokenizers
    in v0.7.3-supported models). The pattern is deterministic so
    repeated TIER5A runs use the same prompt and can compare
    outputs across runs (not just cells within one run).

    Token IDs are deliberately distinct from
    ``SharedPrefixPromptBuilder``'s tail range [6000, 9999] so
    the verifier doesn't accidentally collide with any cohort
    prefix used elsewhere in the bench harness.
    """
    if length_tokens <= 0:
        raise ValueError(f"length_tokens must be > 0; got {length_tokens}")
    # Linear-congruential-ish generator in pure Python so the
    # prompt is reproducible byte-for-byte without numpy.
    seed = 0x5A_5A5A
    out: List[int] = []
    for i in range(length_tokens):
        seed = (seed * 1103515245 + 12345 + i * 7) & 0x7fffffff
        out.append(1 + (seed % 5999))   # [1, 5999]
    return tuple(out)
