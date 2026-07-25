"""Comparative Governance Benchmark — measure the governance value of DGM + TAP + ActionGate.

A deterministic, application-level benchmark that runs four governance strategies
against the same frozen Phase 5I enterprise scenarios:

    A. No Governance
    B. Action Governance Only   (ActionGate, no TAP)
    C. Assertion Governance Only (TAP, no ActionGate)
    D. Full Governance          (reuses the validated Phase 5I pilot workflow)

It answers: compared with simpler alternatives, what measurable governance benefit
does the full architecture provide, and what additional governance workload does
it introduce? It builds no new governance layer, owns no frozen source, and reuses
the frozen packages through their public APIs only.

Strategy isolation is enforced mechanically: the no-governance strategy imports
neither provider, the action-only strategy never imports TAP, and the
assertion-only strategy never imports ActionGate.
"""
from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
