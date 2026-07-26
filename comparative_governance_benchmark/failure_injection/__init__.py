"""Deterministic failure-injection application + matrix."""
from __future__ import annotations

from .apply import apply_profile, needs_registry_failure
from .matrix import FailureCell, run_matrix

__all__ = ["apply_profile", "needs_registry_failure", "run_matrix", "FailureCell"]
