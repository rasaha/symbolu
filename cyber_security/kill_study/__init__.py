"""BCVF-Bio adversarial synthetic kill study.

A self-contained, deterministic falsification study asking whether the BCVF
second-order detector adds measurable value beyond a tuned local-linear-trend
Kalman + CUSUM baseline once all non-detector protections are equalized.

Scope: synthetic only. No human data, no biometric-validity claim, no
production-security claim, no FSCS. See PREREGISTRATION.md.
"""

from __future__ import annotations

from .config import StudyConfig

__all__ = ["StudyConfig"]
