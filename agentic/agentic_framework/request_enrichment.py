"""
Request-boundary governance enrichment helpers.

This module defines a single reusable seam for converting inference /
CG / sovereign-derived signals into the kwargs that governance-aware
request objects consume. It centralizes the "adapter metadata →
governance inputs" translation so that every request-boundary caller
(``SafeMCPGateway.call_tool_simple``, future ``AuthorizationRequest``
builders, replay harnesses, etc.) uses one shape, one contract, one
import.

What this module does
---------------------
- Accepts narrow, explicit inputs (today: ``cg_metadata`` +
  governance ``tier``).
- Delegates the actual signal derivation to the already-built
  sovereign bridge helpers (``governance_inputs_from_cg_metadata``).
- Returns a plain dict of governance kwargs suitable for being:
    * attached to an ``MCPToolCall`` (via ``setattr`` / field
      assignment, since ``vritti_result`` is duck-typed), or
    * splatted into a future ``AuthorizationRequest(**...)``.

What this module does NOT do
----------------------------
- It does NOT orchestrate, schedule, or dispatch anything.
- It does NOT fabricate ``sovereign_projection_metadata`` —
  CG adapter metadata carries only the 32D state and optional
  ``delta_S``; it does not carry a ``SovereignProjectionResult``.
- It does NOT invent new formal request fields. The returned keys
  (``entropy_result``, ``vritti_result``) already exist on the
  consumers as either formal fields or duck-typed attributes.
- It does NOT mutate any request object in place. Callers own the
  attachment step, preserving their existing attachment contract.

Neutral-when-absent contract
----------------------------
When ``cg_metadata`` is ``None``, this helper returns an empty dict.
Callers can therefore unconditionally splat or ignore the result
without branching twice on the absence case.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def build_governance_enrichment_kwargs(
    *,
    cg_metadata: Optional[Dict[str, Any]] = None,
    tier: str = "consumer",
) -> Dict[str, Any]:
    """
    Build the governance-enrichment kwargs for a request-boundary call.

    This is the canonical request-boundary seam for converting
    CG-adapter metadata (and, in later phases, other inference-time
    signals) into the keyword arguments consumed by governance-aware
    request objects.

    Args:
        cg_metadata: Optional CG-capable LLM adapter metadata
            (e.g. ``MistralCGAdapter.last_cg_metadata``) carrying the
            32D sovereign ``state`` and optional ``delta_S``. When
            provided, it is passed through
            ``governance_inputs_from_cg_metadata`` to derive canonical
            ``EntropyResult`` and ``ChittaVrittiResult`` values. When
            ``None``, this helper is a no-op and returns ``{}``.
        tier: Governance tier selector passed through to the bridge
            helper (``"consumer"`` or ``"enterprise"``). Ignored when
            ``cg_metadata`` is ``None``.

    Returns:
        A plain dict. Empty when ``cg_metadata`` is ``None``. Otherwise
        contains exactly:
            - ``"entropy_result"``: canonical ``EntropyResult``
            - ``"vritti_result"``:  canonical ``ChittaVrittiResult``

        The shape is deliberately identical to the bridge helper's
        return shape — this function's job is seam + neutrality, not
        translation.

    Raises:
        TypeError: if ``cg_metadata`` is provided but is not a mapping.
        ValueError: if ``cg_metadata['state']`` is missing or ``None``.

    Example:
        >>> kwargs = build_governance_enrichment_kwargs(
        ...     cg_metadata=adapter.last_cg_metadata, tier="consumer",
        ... )
        >>> call.entropy_result = kwargs.get("entropy_result")
        >>> if "vritti_result" in kwargs:
        ...     call.vritti_result = kwargs["vritti_result"]
    """
    if cg_metadata is None:
        # Neutral-when-absent: the absence of inference-time signals
        # is the default production path today. Returning {} lets
        # callers splat unconditionally without a second None branch.
        return {}

    # Lazy import: the sovereign bridge transitively reaches
    # torch-adjacent code. Importing only on the enriched path keeps
    # the default call_tool_simple() / AuthorizationRequest hot path
    # free of that cost.
    from agentic.agentic_framework.sovereign_bridge import (
        governance_inputs_from_cg_metadata,
    )
    return governance_inputs_from_cg_metadata(cg_metadata, tier=tier)
