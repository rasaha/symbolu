"""Shared infrastructure for the data-independent experiments track.

Modules:
  stats      — RNG, ridge OOF R^2, numerical rank, random orthogonal families,
               shuffle, percentile/permutation gates, bootstrap CI, BH-FDR.
  repro      — git hash / versions / seed / runtime / output hashes.
  report     — ReportBuilder (markdown reports from execution).
  config     — versioned dataclass configs (JSON-backed).
  experiment — Experiment base class (prepare/run/validate/summarize/report).

Structural / synthetic calibration infrastructure only — no semantics, no real
data, no A′ execution.
"""
from __future__ import annotations

from . import config, experiment, report, repro, stats  # noqa: F401
