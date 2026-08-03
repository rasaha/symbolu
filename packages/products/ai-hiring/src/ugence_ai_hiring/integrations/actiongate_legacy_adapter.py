"""Compatibility path for the ActionGate adapter (logic-free facade).

Canonical module: :mod:`ugence_ai_hiring.integrations.actiongate_adapter`.

This module name is retained as a compatibility import path. It contains **no**
adapter implementation and **no** second copy of the logic: every symbol
re-exports the *same object* from
:mod:`ugence_ai_hiring.integrations.actiongate_adapter` (object identity
preserved), so existing
``from ugence_ai_hiring.integrations.actiongate_legacy_adapter import ...``
statements keep working unchanged and resolve to the identical callables. New code
should import the canonical
:mod:`~ugence_ai_hiring.integrations.actiongate_adapter` directly.

The adapter now bridges the **canonical** ``ugence_actiongate_provider``
distribution (the legacy ``dgm-actiongate-provider`` distribution is no longer an
AI Hiring dependency), lazily and with no ActionGate authorization logic of its
own; authorization is prepared, never executed — see the canonical module for the
boundary contract.
"""

from __future__ import annotations

from .actiongate_adapter import (
    build_action_authorization_integration,
    build_actiongate_provider,
    load_actiongate_provider_cls,
)

__all__ = [
    "load_actiongate_provider_cls",
    "build_actiongate_provider",
    "build_action_authorization_integration",
]
