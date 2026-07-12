"""MCP-layer error codes (transport/registry/identity concerns).

Enforcement failures raised by the runtime gateway or the frozen harness
(``GateError`` subclasses: token replay, expiry, action-hash mismatch, scope
violation, policy mismatch, stale state, credential errors) propagate unchanged.
"""

from __future__ import annotations

from ._core import ref_errors

GateError = ref_errors.GateError


class McpError(Exception):
    code = "E_MCP"

    def __init__(self, message: str = ""):
        super().__init__(f"{self.code}: {message}" if message else self.code)


class ProtocolError(McpError):
    code = "E_MCP_PROTOCOL"


class UnknownToolError(McpError):
    code = "E_MCP_UNKNOWN_TOOL"


class ArgumentError(McpError):
    code = "E_MCP_BAD_ARGUMENTS"


class IdentityMismatchError(McpError):
    code = "E_MCP_IDENTITY_MISMATCH"


class ReplayedRequestError(McpError):
    code = "E_MCP_REPLAYED_REQUEST"


class SequenceRollbackError(McpError):
    code = "E_MCP_SEQUENCE_ROLLBACK"


class PhaseError(McpError):
    code = "E_MCP_PHASE"
