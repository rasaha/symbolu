"""Ratified TAP-outcome → ControlStatus mapping (RA-5 spec §9).

``ugence-tap-provider`` outcomes are *semantic support categories*; RA control
statuses are *satisfaction states*. The mapping is **fail-closed and
non-compensatory**: only an unambiguous, fully-supported outcome may satisfy a
mandatory control.

    SUPPORTED  ∧ evidence_coverage >= 1.0   → PASS
    SUPPORTED  ∧ coverage < 1.0 / None      → UNKNOWN   (not PASS)
    CONSTRAINED                             → UNKNOWN   (not PASS)
    UNSUPPORTED                             → FAIL
    INDETERMINATE                           → UNKNOWN
    (any other / unmapped)                  → UNKNOWN   (fail closed)

The ``evidence_coverage`` ratio is used **only** as the binary full-support gate
here — it is *never* carried into Risk Authority as a weight or score, and high
coverage on one control can never compensate a failed mandatory control (that is
RA's unchanged non-compensatory gate). The public provider boundary already folds
the native ``UNKNOWN`` non-determination into ``INDETERMINATE``; either way it can
never become ``PASS``.
"""

from __future__ import annotations

from ugence_governance_contracts.contracts.assertion import AssertionCoverage

from risk_authority.domain.enums import ControlStatus

__all__ = ["FULL_COVERAGE", "map_assertion_outcome"]

#: The exact coverage a SUPPORTED outcome must reach to satisfy a control.
FULL_COVERAGE = 1.0


def map_assertion_outcome(
    coverage: AssertionCoverage, evidence_coverage: object
) -> ControlStatus:
    """Map a provider assertion outcome to a fail-closed control status (§9)."""

    if coverage is AssertionCoverage.UNSUPPORTED:
        # Evidence contradicts the assertion — a genuine hard failure.
        return ControlStatus.FAIL

    if coverage is AssertionCoverage.SUPPORTED:
        ratio = _as_ratio(evidence_coverage)
        if ratio is not None and ratio >= FULL_COVERAGE:
            return ControlStatus.PASS
        # Partial or unquantified support is not full satisfaction.
        return ControlStatus.UNKNOWN

    # CONSTRAINED / INDETERMINATE / anything unmapped ⇒ never PASS (fail closed).
    return ControlStatus.UNKNOWN


def _as_ratio(value: object) -> "float | None":
    """Coerce a coverage value to a valid ratio in [0, 1], else ``None``.

    Fail-closed on every malformed value — ``None``, booleans, non-numerics,
    NaN/±inf, and **out-of-range** values (``< 0.0`` or ``> 1.0``). A coverage
    outside the unit interval is not "almost full support" to be clamped up to
    PASS; it is a malformed provider value and must resolve to ``UNKNOWN``
    (RA-5 audit L-2). Only a finite ratio genuinely within ``[0.0, 1.0]`` is
    returned.
    """

    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    ratio = float(value)
    if ratio != ratio or ratio in (float("inf"), float("-inf")):  # NaN / inf
        return None
    if ratio < 0.0 or ratio > 1.0:  # out of range ⇒ malformed, never clamp to PASS
        return None
    return ratio
