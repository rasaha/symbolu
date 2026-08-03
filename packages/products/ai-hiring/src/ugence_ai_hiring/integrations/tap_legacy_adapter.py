"""Compatibility path for the TAP adapter (logic-free facade).

Canonical module: :mod:`ugence_ai_hiring.integrations.tap_adapter`.

This module name is retained as a compatibility import path. It contains **no**
adapter implementation and **no** second copy of the logic: every symbol
re-exports the *same object* from :mod:`ugence_ai_hiring.integrations.tap_adapter`
(object identity preserved), so existing
``from ugence_ai_hiring.integrations.tap_legacy_adapter import ...`` statements
keep working unchanged and resolve to the identical callables. New code should
import the canonical :mod:`~ugence_ai_hiring.integrations.tap_adapter` directly.

The adapter now bridges the **canonical** ``ugence_tap_provider`` distribution
(the legacy ``dgm-tap-provider`` distribution is no longer an AI Hiring
dependency), lazily and with no TAP adjudication of its own — see the canonical
module for the boundary contract.
"""

from __future__ import annotations

from .tap_adapter import (
    build_claim_assertion_evaluator,
    build_tap_provider,
    load_tap_provider_cls,
)

__all__ = [
    "load_tap_provider_cls",
    "build_tap_provider",
    "build_claim_assertion_evaluator",
]
