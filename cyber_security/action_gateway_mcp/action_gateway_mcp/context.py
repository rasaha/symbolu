"""Protocol-neutral request context + identity reconciliation.

Captures who is calling and over what session/transport, keeping *declared*
(self-asserted in the payload) identity separate from *authenticated* (established
by the transport, e.g. mTLS / signed session) identity. Per the integrity rules,
self-declared agent/tool-server fields are never trusted when a stronger
transport-authenticated value exists, and a genuine conflict fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RequestContext:
    # transport / session
    connection_id: str
    session_id: str
    correlation_id: str
    sequence_id: str
    request_nonce: str
    request_timestamp: str
    # identity — declared (payload) vs authenticated (transport)
    declared_agent_id: str
    authenticated_agent_id: str | None = None
    declared_tool_server: str | None = None
    authenticated_tool_server: str | None = None
    # descriptive
    agent_runtime: str = "mcp-host/unknown"
    model: str | None = None
    provider: str | None = None
    delegator: str = "user://unknown"
    delegator_type: str = "HUMAN"
    delegation_ref: str | None = None
    agent_key_id: str = "k7"
    client_capabilities: list = field(default_factory=list)

    # ---- identity resolution ----

    def effective_agent_id(self) -> str:
        """Authenticated identity wins over the self-declared one."""
        return self.authenticated_agent_id or self.declared_agent_id

    def effective_tool_server(self) -> str | None:
        return self.authenticated_tool_server or self.declared_tool_server

    def identity_conflicts(self) -> list:
        """Return the set of hard identity conflicts (both present and differing)."""
        conflicts = []
        if (self.authenticated_agent_id is not None
                and self.declared_agent_id is not None
                and self.authenticated_agent_id != self.declared_agent_id):
            conflicts.append({
                "field": "agent_id", "declared": self.declared_agent_id,
                "authenticated": self.authenticated_agent_id})
        if (self.authenticated_tool_server is not None
                and self.declared_tool_server is not None
                and self.authenticated_tool_server != self.declared_tool_server):
            conflicts.append({
                "field": "tool_server", "declared": self.declared_tool_server,
                "authenticated": self.authenticated_tool_server})
        return conflicts

    def identity_record(self) -> dict:
        """Both identities, always recorded so a divergence is auditable."""
        return {
            "declared_agent_id": self.declared_agent_id,
            "authenticated_agent_id": self.authenticated_agent_id,
            "effective_agent_id": self.effective_agent_id(),
            "declared_tool_server": self.declared_tool_server,
            "authenticated_tool_server": self.authenticated_tool_server,
            "conflicts": self.identity_conflicts(),
        }

    def sequence_num(self) -> int:
        """Numeric suffix of ``sequence_id`` (``sess:0007`` -> 7); -1 if absent."""
        tail = self.sequence_id.rsplit(":", 1)[-1]
        try:
            return int(tail)
        except ValueError:
            return -1
