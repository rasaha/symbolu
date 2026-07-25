"""Provider conformance kit — reusable validation for any provider registry."""
from __future__ import annotations

from .runner import (
    CheckResult,
    ProviderConformanceReport,
    run_provider_conformance,
)

__all__ = ["run_provider_conformance", "ProviderConformanceReport", "CheckResult"]
