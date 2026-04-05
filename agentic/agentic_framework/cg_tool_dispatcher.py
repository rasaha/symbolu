"""
CG Tool Dispatcher: the owner component that holds a CG-capable LLM
adapter together with a SafeMCPGateway.

Motivation
----------
The Phase 1 + Phase 2 enrichment wiring (see
``agentic/AGENTIC_ARCHITECTURE.md`` § "Inference CG Metadata ↔ MCP
Gateway") lets a tool call carry sovereign signals from a CG-capable
adapter (``MistralCGAdapter.last_cg_metadata``) into governance. But
that seam has no obvious owner in production code: the adapter lives
in an ``AgenticLLMWrapper``, the gateway lives in its own path, and
nothing today simultaneously holds both.

``CGToolDispatcher`` is that missing piece — the smallest honest
owner component that composes:

    adapter.last_cg_metadata  →  gateway.call_tool_simple(cg_metadata=...)

It does no generation itself and adds no policy. It just routes a
tool call through the gateway using the most recent sovereign state
the adapter produced. That is the entire contract.

Non-goals
---------
- Not a reflective agent (no reasoning loop).
- Not a policy surface (no confidence thresholds, tiers are
  pass-through).
- Not a fallback: if the adapter has not generated yet, the dispatcher
  calls the gateway without ``cg_metadata`` (preserving the exact
  no-CG path).

See also
--------
- ``examples/cg_tool_demo.py`` — end-to-end demo of the enrichment
  path. The dispatcher formalizes the ad-hoc composition that demo
  performs inline.
- ``agentic/agentic_framework/request_enrichment.py`` — the
  request-boundary helper this dispatcher relies on transitively
  via ``SafeMCPGateway.call_tool_simple``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class _CGCapableAdapter(Protocol):
    """Structural type describing the adapter contract this dispatcher needs.

    Any object exposing a ``last_cg_metadata`` dict (possibly empty)
    satisfies the contract. ``MistralCGAdapter`` is the canonical
    implementation; the demo ``DemoCGAdapter`` satisfies it too.
    """

    last_cg_metadata: Dict[str, Any]


class CGToolDispatcher:
    """
    Owner component: holds a CG-capable adapter + a SafeMCPGateway and
    dispatches tool calls enriched with the adapter's most recent
    sovereign state.

    Example
    -------
    >>> from agentic.agentic_framework.mcp_gateway import (
    ...     create_mock_mcp_gateway,
    ... )
    >>> # adapter here is any object with a .last_cg_metadata dict
    >>> dispatcher = CGToolDispatcher(adapter, create_mock_mcp_gateway())
    >>> # after `adapter.generate(prompt)` populates last_cg_metadata:
    >>> result = await dispatcher.dispatch(
    ...     tool_name="file_read",
    ...     parameters={"path": "/tmp/x"},
    ... )
    """

    def __init__(
        self,
        adapter: _CGCapableAdapter,
        gateway: Any,
        *,
        tier: str = "consumer",
    ) -> None:
        """
        Args:
            adapter: Any object exposing ``last_cg_metadata: dict``.
                In production this is typically a ``MistralCGAdapter``.
            gateway: A ``SafeMCPGateway`` (or a compatible gateway with
                an awaitable ``call_tool_simple(...)`` method).
            tier: Governance tier to pass through to the gateway
                (``"consumer"`` or ``"enterprise"``). Only used when
                the adapter has produced CG metadata.
        """
        self.adapter = adapter
        self.gateway = gateway
        self.tier = tier

    def _current_cg_metadata(self) -> Optional[Dict[str, Any]]:
        """Return the adapter's most recent CG metadata, or None if
        the adapter has not generated yet (empty dict)."""
        md = getattr(self.adapter, "last_cg_metadata", None)
        if not md:
            return None
        return md

    async def dispatch(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        *,
        quality_score: float = 0.8,
        coherence_score: float = 0.8,
    ) -> Any:
        """
        Dispatch a tool call through the gateway, enriched with the
        adapter's most recent CG metadata when available.

        When ``self.adapter.last_cg_metadata`` is non-empty, it is
        passed through to ``gateway.call_tool_simple(cg_metadata=...)``
        and the sovereign bridge derives canonical ``EntropyResult`` +
        ``ChittaVrittiResult`` for governance. When it is empty (no
        generation yet), the call goes through without ``cg_metadata``
        — preserving the exact no-CG code path.

        Args:
            tool_name: Name of the tool to invoke.
            parameters: Tool parameters.
            quality_score: Quality score forwarded to the gateway.
            coherence_score: Coherence score forwarded to the gateway.

        Returns:
            The gateway's ``MCPToolResult``.
        """
        cg_metadata = self._current_cg_metadata()
        return await self.gateway.call_tool_simple(
            tool_name=tool_name,
            parameters=parameters,
            quality_score=quality_score,
            coherence_score=coherence_score,
            cg_metadata=cg_metadata,
            tier=self.tier,
        )


#: Default mapping from ``ActionItem.action_type`` strings (as produced
#: by ``goal_decomposition``) to MCP tool names registered on the
#: ``create_mock_mcp_gateway()`` gateway. This is the minimal honest
#: wiring the ChatGPT checklist calls for: one concrete MCP endpoint
#: per action type the agent can already emit.
#:
#: The mapping is deliberately small — "generate" and "execute" have
#: no honest default tool, so callers must supply their own entries
#: for those types. ``AgenticLLMWrapper`` routes only action types
#: present in whatever mapping it is given; unmapped types fall
#: through to the existing placeholder execution path.
DEFAULT_ACTION_TYPE_TO_TOOL: Dict[str, str] = {
    "search": "search",
    "compute": "compute",
    "validate": "validate",
}


__all__ = ["CGToolDispatcher", "DEFAULT_ACTION_TYPE_TO_TOOL"]
