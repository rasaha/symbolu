"""Procurement application — composes the procurement domain and the DGM kernel.

The canonical composition root is :mod:`applications.procurement.platform`. It
wires the unchanged Decision Governance kernel with the procurement domain
adapters into an end-to-end, in-memory platform.

Dependency direction: ``applications.procurement`` → {``domains.procurement``,
``decision_governance``}. The reverse never holds.
"""
from __future__ import annotations

from applications.procurement.configuration import ProcurementConfiguration
from applications.procurement.platform import (
    ProcurementPlatform,
    build_in_memory_platform,
)

__all__ = ["ProcurementPlatform", "build_in_memory_platform", "ProcurementConfiguration"]
