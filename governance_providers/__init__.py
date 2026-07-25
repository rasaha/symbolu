"""Governance Provider Framework — pluggable governance capabilities for DGM.

An application-layer framework that lets specialized governance capabilities plug
into DGM as interchangeable peer providers, without any dependency from the
kernel to a vendor implementation. Three distinct, non-interchangeable families:
assertion governance (future TAP), action governance (future ActionGate), and
external execution.

Dependency direction: applications → governance_providers → decision_governance.api.
The kernel never imports this framework. Import the public surface from
``governance_providers.api``.
"""
from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
