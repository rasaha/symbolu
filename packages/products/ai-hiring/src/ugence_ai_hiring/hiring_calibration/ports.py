"""Integration port for the calibration plane.

Cohort aggregation and calibration-error metrics are hiring-domain descriptive
computations and are done locally. The only shared capability here is emitting a
finished report/proposal to an external analytics / reconciliation / BI system —
an integration boundary, not a duplicated engine. The port is optional; the plane
runs standalone without it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.base import DomainModel
from .report import HiringCalibrationReport


class CalibrationSinkOutcome(DomainModel):
    accepted: bool
    external_reference: str = ""


@runtime_checkable
class CalibrationSinkPort(Protocol):
    """Emits a finished calibration report to a shared analytics/reconciliation system."""

    def emit(self, report: HiringCalibrationReport) -> CalibrationSinkOutcome: ...
