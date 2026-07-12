"""Gateway-layer error codes.

Enforcement failures that originate inside the reference harness (token replay,
expiry, action-hash mismatch, scope violation, policy mismatch, …) are raised as
``action_gate_ref.errors.GateError`` subclasses and propagate unchanged — the
gateway never downgrades or masks them. The codes here cover gateway-specific
conditions only (unknown request, illegal runtime transition, missing token,
adapter/broker faults).
"""

from __future__ import annotations

from ._ref import errors as _ref_errors

GateError = _ref_errors.GateError  # re-export the harness base


class GatewayError(Exception):
    """Base gateway error carrying a stable machine-readable code."""

    code = "E_GATEWAY"

    def __init__(self, message: str = ""):
        super().__init__(f"{self.code}: {message}" if message else self.code)


class UnknownRequestError(GatewayError):
    code = "E_UNKNOWN_REQUEST"


class IllegalStateError(GatewayError):
    code = "E_ILLEGAL_STATE"


class NoExecutionTokenError(GatewayError):
    code = "E_NO_EXECUTION_TOKEN"


class NotAdmissibleError(GatewayError):
    code = "E_NOT_ADMISSIBLE"


class CredentialError(GatewayError):
    code = "E_CREDENTIAL"


class AdapterError(GatewayError):
    code = "E_ADAPTER"


class UnknownToolError(GatewayError):
    code = "E_UNKNOWN_TOOL"
