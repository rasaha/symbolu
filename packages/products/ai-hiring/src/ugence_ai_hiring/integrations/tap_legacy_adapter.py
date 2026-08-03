"""Legacy TAP compatibility adapter (optional, isolated).

Bridges the current ``tap_provider`` distribution (``TAPProvider``, an
:class:`AssertionGovernanceProvider`) onto the AI Hiring core's neutral assertion
boundary (:class:`ClaimAssertionEvaluator`).

Boundary discipline:

* This module imports ``tap_provider`` **lazily** — only when a loader is called —
  so importing it (or the AI Hiring core) never requires the legacy distribution
  to be installed.
* It implements **no** TAP adjudication. Assertion evaluation stays inside the
  injected ``TAPProvider``; the core only wires it through the neutral
  ``AssertionGovernanceProvider`` protocol (via the framework's
  ``AssertionAssessmentIntegration``).

Install with ``pip install "ugence-ai-hiring[tap]"``. Classification:
``LEGACY_COMPATIBILITY_DEPENDENCY`` (temporary; migrates to ``ugence-tap-provider``
in a later dependency-only PR).
"""

from __future__ import annotations

from typing import Any

from ugence_governance_provider_framework.api import AssertionAssessmentIntegration

from ..recommendations.tap_integration import ClaimAssertionEvaluator
from . import LegacyProviderUnavailable

__all__ = [
    "load_tap_provider_cls",
    "build_tap_provider",
    "build_claim_assertion_evaluator",
]

_DIST_HINT = 'pip install "ugence-ai-hiring[tap]"  (legacy: dgm-tap-provider)'


def load_tap_provider_cls():
    """Return the legacy ``TAPProvider`` class (lazy import).

    Raises :class:`LegacyProviderUnavailable` if ``tap_provider`` is not installed.
    """
    try:
        from tap_provider.provider import TAPProvider
    except ImportError as exc:  # pragma: no cover - exercised in the no-legacy env
        raise LegacyProviderUnavailable(
            "the TAP legacy provider ('tap_provider') is not installed; "
            f"{_DIST_HINT}"
        ) from exc
    return TAPProvider


def build_tap_provider(client: Any, **kwargs: Any):
    """Construct a legacy ``TAPProvider`` from a caller-supplied client.

    The ``client`` (a ``TapClient``) and any keyword options pass straight through
    to the legacy provider; this adapter adds no policy of its own. Returns an
    object satisfying the neutral ``AssertionGovernanceProvider`` protocol.
    """
    provider_cls = load_tap_provider_cls()
    return provider_cls(client, **kwargs)


def build_claim_assertion_evaluator(
    client: Any, *, provider_id: str = "", **kwargs: Any
) -> ClaimAssertionEvaluator:
    """Wire a legacy TAP provider into the core's neutral claim-assertion evaluator.

    The legacy provider is wrapped by the framework's neutral
    ``AssertionAssessmentIntegration`` and handed to the core evaluator. AI Hiring
    performs no assertion adjudication of its own.
    """
    provider = build_tap_provider(client, **kwargs)
    integration = AssertionAssessmentIntegration(provider)
    return ClaimAssertionEvaluator(integration, provider_id=provider_id)
