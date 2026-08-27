"""Causal prequential residual bank — the evaluation-layer producer of calibration input.

This is evaluation machinery, not shipped forecasting behaviour: nothing in the production
path constructs or requires it. It exists because the in-window rolling-origin collection is
unusable for a bounded replay — it re-fits at every sample of every window, and it can only
match actuals that fall *inside* the same window, which excludes the very outcomes a
longer-horizon forecast needs.

The bank instead accumulates one residual per preregistered origin and replays them forward:

* one bank per ``(subject, target, horizon, arm)`` — residuals are never shared across arms;
* a residual is eligible at cutoff ``c`` only when its origin precedes ``c`` **and** its
  matched actual was observable at or before ``c``;
* at most ``bank_cap`` residuals are used, keeping the most recent origins and evicting the
  oldest first, with deterministic tie-breaking;
* all state is instance state on an explicitly-constructed provider. There are no module
  globals, no hidden mutable defaults and no callbacks.

The as-of rule is the whole point. A residual whose outcome had not yet happened at ``c``
would let the interval "know" the future, and a future-contaminated bank tends to *narrow*
intervals and *flatter* coverage — the failure mode that looks like success.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..canonical.identity import CapacitySubject
from ..canonical.serialization import content_digest
from .calibration import (
    CalibrationProvider,
    CalibrationResiduals,
)
from .series import _as_utc
from .targets import ForecastTarget
from .uncertainty import UncertaintyConfig, UncertaintyError
from .window import ForecastHorizon

#: 7 days x 96 quarter-hour origins per day (run manifest §7.2).
DEFAULT_BANK_CAP = 672

#: Seconds between preregistered calibration origins (UTC quarter-hours).
CALIBRATION_ORIGIN_STRIDE_SECONDS = 900.0


@dataclass(frozen=True)
class ResidualEntry:
    """One residual with the two times that decide when it may be used."""

    origin: datetime
    actual_event_time: datetime
    value: float

    def __post_init__(self) -> None:
        for name in ("origin", "actual_event_time"):
            if not isinstance(getattr(self, name), datetime):
                raise UncertaintyError(f"residual {name} must be a datetime")
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise UncertaintyError("residual value must be a real number")
        if not math.isfinite(float(self.value)):
            raise UncertaintyError("residual value must be finite")
        if _as_utc(self.actual_event_time) <= _as_utc(self.origin):
            raise UncertaintyError("a residual's actual must be strictly after its origin")

    def sort_key(self) -> Tuple[float, float, float]:
        """Deterministic total order: origin, then actual time, then value.

        Origins collide only when a caller feeds the same instant twice; the extra keys make
        the eviction order total rather than dependent on insertion order.
        """
        return (
            _as_utc(self.origin).timestamp(),
            _as_utc(self.actual_event_time).timestamp(),
            float(self.value),
        )


def is_calibration_origin(t: datetime) -> bool:
    """True for a UTC quarter-hour instant (minute in {0,15,30,45}, second 0)."""
    u = _as_utc(t)
    return u.minute % 15 == 0 and u.second == 0 and u.microsecond == 0


class PrequentialResidualBank:
    """Ordered residual store for a single ``(subject, target, horizon, arm)`` binding."""

    def __init__(self, *, bank_cap: int = DEFAULT_BANK_CAP):
        if isinstance(bank_cap, bool) or not isinstance(bank_cap, int) or bank_cap < 1:
            raise UncertaintyError("bank_cap must be an int >= 1")
        self._cap = bank_cap
        self._entries: List[ResidualEntry] = []

    @property
    def bank_cap(self) -> int:
        return self._cap

    @property
    def size(self) -> int:
        return len(self._entries)

    def admit(self, entry: ResidualEntry) -> None:
        """Record a residual. Eligibility at read time still decides whether it is used."""
        if not isinstance(entry, ResidualEntry):
            raise UncertaintyError("bank entries must be ResidualEntry")
        self._entries.append(entry)

    def eligible_at(self, cutoff: datetime) -> Tuple[ResidualEntry, ...]:
        """The causally admissible, capped, deterministically ordered entries at ``cutoff``."""
        c = _as_utc(cutoff)
        eligible = [
            e
            for e in self._entries
            if _as_utc(e.origin) < c and _as_utc(e.actual_event_time) <= c
        ]
        eligible.sort(key=ResidualEntry.sort_key)
        if len(eligible) > self._cap:
            # Oldest-origin-first eviction: keep the most recent `cap` entries.
            eligible = eligible[-self._cap :]
        return tuple(eligible)


def _subject_key(subject: CapacitySubject) -> str:
    """Stable subject identity for bank keying (CapacitySubject exposes no digest())."""
    return content_digest(
        "forecast_calibration_subject_key",
        "capacity-forecast-calibration-subject-1",
        subject.to_canonical_dict(),
    )


def _binding_key(
    subject: CapacitySubject, target: ForecastTarget, horizon_seconds: float, arm_model_id: str
) -> Tuple[str, str, float, str]:
    return (_subject_key(subject), target.value, float(horizon_seconds), arm_model_id)


class ReplayCalibrationProvider(CalibrationProvider):
    """A :class:`~.calibration.CalibrationProvider` backed by per-binding causal banks.

    Construct one per replay run and pass it to ``run_replay_evaluation``. It is explicit,
    owned by the caller, and holds no state that outlives the object.
    """

    def __init__(
        self,
        *,
        config: UncertaintyConfig,
        cutoff_sequence_digest: str,
        bank_cap: int = DEFAULT_BANK_CAP,
        require_calibration_origin: bool = True,
    ):
        if not isinstance(config, UncertaintyConfig):
            raise UncertaintyError("config must be an UncertaintyConfig")
        if not isinstance(cutoff_sequence_digest, str) or cutoff_sequence_digest == "":
            raise UncertaintyError("cutoff_sequence_digest must be a non-empty string")
        if isinstance(bank_cap, bool) or not isinstance(bank_cap, int) or bank_cap < 1:
            raise UncertaintyError("bank_cap must be an int >= 1")
        self._config = config
        self._config_digest = config.digest()
        self._cutoff_sequence_digest = cutoff_sequence_digest
        self._bank_cap = bank_cap
        self._require_origin = require_calibration_origin
        self._banks: Dict[Tuple[str, str, float, str], PrequentialResidualBank] = {}

    # -- accounting ---------------------------------------------------------------------
    @property
    def bank_cap(self) -> int:
        return self._bank_cap

    def bank_sizes(self) -> Dict[Tuple[str, str, float, str], int]:
        """Per-binding residual counts, for calibration accounting kept apart from gating."""
        return {k: b.size for k, b in sorted(self._banks.items())}

    # -- feeding ------------------------------------------------------------------------
    def observe(
        self,
        *,
        subject: CapacitySubject,
        target: ForecastTarget,
        horizon: ForecastHorizon,
        arm_model_id: str,
        origin: datetime,
        actual_event_time: datetime,
        residual: float,
    ) -> bool:
        """Admit one residual. Returns ``False`` when the origin is off-schedule.

        Off-schedule origins are declined rather than raising: a replay may legitimately visit
        cutoffs that are not calibration origins, and silently admitting them would change the
        preregistered calibration schedule.
        """
        if self._require_origin and not is_calibration_origin(origin):
            return False
        key = _binding_key(subject, target, horizon.seconds, arm_model_id)
        bank = self._banks.get(key)
        if bank is None:
            bank = PrequentialResidualBank(bank_cap=self._bank_cap)
            self._banks[key] = bank
        bank.admit(
            ResidualEntry(origin=origin, actual_event_time=actual_event_time, value=float(residual))
        )
        return True

    # -- reading ------------------------------------------------------------------------
    def calibration_for(
        self,
        subject: CapacitySubject,
        target: ForecastTarget,
        horizon: ForecastHorizon,
        arm_model_id: str,
        cutoff: datetime,
    ) -> Optional[CalibrationResiduals]:
        bank = self._banks.get(_binding_key(subject, target, horizon.seconds, arm_model_id))
        if bank is None:
            return None
        entries = bank.eligible_at(cutoff)
        if not entries:
            return None
        return CalibrationResiduals(
            subject=subject,
            target=target,
            horizon_seconds=float(horizon.seconds),
            arm_model_id=arm_model_id,
            evaluation_cutoff=cutoff,
            values=tuple(e.value for e in entries),
            earliest_origin=entries[0].origin,
            latest_origin=entries[-1].origin,
            bank_cap=bank.bank_cap,
            config_digest=self._config_digest,
            cutoff_sequence_digest=self._cutoff_sequence_digest,
        )


def cutoff_sequence_digest(cutoffs) -> str:
    """Deterministic identity of an ordered cutoff sequence (preregistration binding)."""
    return content_digest(
        "forecast_cutoff_sequence",
        "capacity-forecast-cutoff-sequence-1",
        [_as_utc(c).isoformat() for c in cutoffs],
    )


__all__ = [
    "DEFAULT_BANK_CAP",
    "CALIBRATION_ORIGIN_STRIDE_SECONDS",
    "ResidualEntry",
    "PrequentialResidualBank",
    "ReplayCalibrationProvider",
    "is_calibration_origin",
    "cutoff_sequence_digest",
]
