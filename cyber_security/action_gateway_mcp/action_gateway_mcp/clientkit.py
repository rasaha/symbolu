"""Reference client-session helper.

A real MCP client must attach a fresh request nonce and a monotonically
increasing sequence id to every protocol message (so the server can reject
replays and sequence rollbacks). ``ClientSession`` generates well-formed
``RequestContext`` objects for a correlated session; it also lets a test/demo
inject a *declared* identity that differs from the *authenticated* one to exercise
identity-conflict handling.
"""

from __future__ import annotations

from .context import RequestContext


class ClientSession:
    def __init__(self, *, clock, authenticated_agent_id="agent://sre/1",
                 delegator="user://alice", correlation_id="sess-mcp",
                 agent_runtime="mcp-host/1.0", model="claude-opus-4-8",
                 provider="anthropic", authenticated_tool_server="mcp://prod-infra",
                 connection_id="conn-1", session_id="sess-1",
                 start_seq=0, start_nonce=0):
        self.clock = clock
        self.authenticated_agent_id = authenticated_agent_id
        self.authenticated_tool_server = authenticated_tool_server
        self.delegator = delegator
        self.correlation_id = correlation_id
        self.agent_runtime = agent_runtime
        self.model = model
        self.provider = provider
        self.connection_id = connection_id
        self.session_id = session_id
        self._seq = start_seq
        self._nonce = start_nonce

    def counters(self) -> dict:
        return {"seq": self._seq, "nonce": self._nonce}

    def context(self, *, declared_agent_id=None, declared_tool_server=None,
                sequence_override=None) -> RequestContext:
        self._seq += 1
        self._nonce += 1
        seq = sequence_override if sequence_override is not None else self._seq
        return RequestContext(
            connection_id=self.connection_id, session_id=self.session_id,
            correlation_id=self.correlation_id,
            sequence_id=f"{self.correlation_id}:{seq:04d}",
            request_nonce=f"{self.correlation_id}-n{self._nonce}",
            request_timestamp=self.clock.now(),
            declared_agent_id=declared_agent_id or self.authenticated_agent_id,
            authenticated_agent_id=self.authenticated_agent_id,
            declared_tool_server=declared_tool_server or self.authenticated_tool_server,
            authenticated_tool_server=self.authenticated_tool_server,
            agent_runtime=self.agent_runtime, model=self.model, provider=self.provider,
            delegator=self.delegator)

    def replayed_context(self, ctx: RequestContext) -> RequestContext:
        """A context that reuses a prior request nonce (protocol replay attempt)."""
        self._seq += 1
        return RequestContext(
            connection_id=self.connection_id, session_id=self.session_id,
            correlation_id=self.correlation_id,
            sequence_id=f"{self.correlation_id}:{self._seq:04d}",
            request_nonce=ctx.request_nonce, request_timestamp=self.clock.now(),
            declared_agent_id=self.authenticated_agent_id,
            authenticated_agent_id=self.authenticated_agent_id,
            declared_tool_server=self.authenticated_tool_server,
            authenticated_tool_server=self.authenticated_tool_server,
            agent_runtime=self.agent_runtime, model=self.model, provider=self.provider,
            delegator=self.delegator)
