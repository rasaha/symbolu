"""
Agent Builder — High-Level Factory for Governed Agents

Reduces the boilerplate for assembling a governed agent with custom
tools from ~25 lines to ~10 lines.

Before (manual composition)::

    client = MockMCPClient()
    client.register_tool("search", handler, ToolRiskLevel.READ_ONLY)
    gateway = create_safe_mcp_gateway(mcp_client=client)
    gateway.register_tool(MCPToolDefinition(name="search", ...))
    dispatcher = CGToolDispatcher(adapter, gateway)
    agent = AgenticLLMWrapper(
        llm_client=adapter,
        dispatcher=dispatcher,
        action_type_to_tool={"search": "search"},
    )

After (``build_agent``)::

    agent = build_agent(
        adapter=my_adapter,
        tools={"search": ToolSpec(handler=search_fn, ...)},
    )
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def build_agent(
    *,
    adapter: Any,
    tools: Optional[Dict[str, Any]] = None,
    action_type_to_tool: Optional[Dict[str, str]] = None,
    tier: str = "consumer",
    allow_stub: bool = False,
    gateway: Optional[Any] = None,
    **agent_kwargs: Any,
) -> Any:
    """Build a governed agent with custom tools in one call.

    Composes: adapter → MockMCPClient → SafeMCPGateway →
    CGToolDispatcher → AgenticLLMWrapper.

    Args:
        adapter: LLM adapter implementing ``call(prompt) -> str``.
            For CG-enriched governance, use an adapter that also
            exposes ``last_cg_metadata: dict`` (e.g.
            ``MistralCGAdapter``, ``StubCGLLMAdapter``).
        tools: Dict mapping tool names to ``ToolSpec`` instances.
            Each spec bundles a handler callable with governance
            metadata (risk level, capabilities, etc.).  When provided,
            a fresh ``MockMCPClient`` + ``SafeMCPGateway`` is built
            and every spec is registered via
            ``register_tool_with_handler``.  Ignored when *gateway*
            is provided.
        action_type_to_tool: Maps goal-decomposition action types
            (``"search"``, ``"compute"``, etc.) to tool names.  When
            omitted, defaults to identity mapping from *tools* keys
            (i.e. ``{"search": "search", ...}``).  When *tools* is
            also omitted, falls back to
            ``DEFAULT_ACTION_TYPE_TO_TOOL``.
        tier: Governance tier passed to ``CGToolDispatcher``
            (``"consumer"`` or ``"enterprise"``).
        allow_stub: Silence the warning when *adapter* is a stub.
        gateway: Optional pre-built ``SafeMCPGateway``.  When
            provided, *tools* is ignored and the gateway is used
            as-is.
        **agent_kwargs: Forwarded to ``AgenticLLMWrapper`` (e.g.
            ``max_revisions``, ``quality_threshold``,
            ``use_llm_for_decomposition``).

    Returns:
        A fully wired ``AgenticLLMWrapper`` ready for
        ``agent.run()``, ``agent.run_stream()``, etc.

    See also:
        ``build_cg_mcp_agent()`` in ``cg_tool_dispatcher.py`` — a
        similar factory for CG-capable adapters that expose
        ``last_cg_metadata``.  Use ``build_agent()`` as the default;
        use ``build_cg_mcp_agent()`` only when you need model-internal
        CG signals for governance.

    Example::

        from agentic.agentic_framework.agent_builder import build_agent
        from agentic.agentic_framework.mcp_gateway import ToolSpec, ToolRiskLevel
        from agentic.agentic_framework.llm_adapters import MockLLMAdapter

        agent = build_agent(
            adapter=MockLLMAdapter(default_response="Hello"),
            tools={
                "search": ToolSpec(
                    handler=lambda p: [f"Result for {p.get('query')}"],
                    description="Search the web",
                    risk_level=ToolRiskLevel.READ_ONLY,
                ),
            },
        )
        agent.new_session()
        result = agent.run("Search for Python tutorials")
    """
    # Deferred imports to keep this module cheap.
    from agentic.agentic_framework.agent import AgenticLLMWrapper
    from agentic.agentic_framework.cg_tool_dispatcher import (
        CGToolDispatcher,
        DEFAULT_ACTION_TYPE_TO_TOOL,
    )

    # Stub guardrail
    if getattr(adapter, "IS_STUB", False) and not allow_stub:
        logger.warning(
            "build_agent: wiring a STUB adapter (%s).  Pass "
            "allow_stub=True to acknowledge.",
            type(adapter).__name__,
        )

    # Build or reuse gateway
    if gateway is None and tools:
        from agentic.agentic_framework.mcp_gateway import (
            MockMCPClient,
            create_safe_mcp_gateway,
        )

        client = MockMCPClient()
        gw = create_safe_mcp_gateway(mcp_client=client, audit_enabled=True)

        for tool_name, spec in tools.items():
            gw.register_tool_with_handler(tool_name, spec)

        gateway = gw

    elif gateway is None:
        from agentic.agentic_framework.mcp_gateway import create_mock_mcp_gateway
        gateway = create_mock_mcp_gateway()

    # Build dispatcher (works for both CG and non-CG adapters)
    dispatcher = CGToolDispatcher(adapter, gateway, tier=tier)

    # Derive action_type_to_tool mapping
    if action_type_to_tool is not None:
        mapping = dict(action_type_to_tool)
    elif tools:
        # Identity mapping: each tool name is also an action type
        mapping = {name: name for name in tools}
    else:
        mapping = dict(DEFAULT_ACTION_TYPE_TO_TOOL)

    return AgenticLLMWrapper(
        llm_client=adapter,
        dispatcher=dispatcher,
        action_type_to_tool=mapping,
        **agent_kwargs,
    )


__all__ = ["build_agent"]
