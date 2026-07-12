"""Machine-readable, fail-closed error codes.

Every code mirrors ACTION_CANONICALIZATION_AND_HASHING_SPEC.md §18 (plus a few
schema/gate codes). A canonicalization or validation error is always a hard
failure — never a best-effort result.
"""

from __future__ import annotations


class GateError(Exception):
    """Base class carrying a stable machine-readable code."""

    code = "E_GATE"

    def __init__(self, message: str = "", *, field: str | None = None):
        self.field = field
        super().__init__(f"{self.code}: {message}" + (f" (field={field})" if field else ""))


# --- Canonicalization / hashing errors (spec §18) ---
class DuplicateKeyError(GateError):
    code = "E_DUP_KEY"


class InvalidUTF8Error(GateError):
    code = "E_INVALID_UTF8"


class BareNumberError(GateError):
    code = "E_BARE_NUMBER"


class NanInfError(GateError):
    code = "E_NAN_INF"


class BadTimestampError(GateError):
    code = "E_BAD_TIMESTAMP"


class AmbiguousIdError(GateError):
    code = "E_AMBIGUOUS_ID"


class UnknownSchemaError(GateError):
    code = "E_UNKNOWN_SCHEMA"


class InvalidEnumError(GateError):
    code = "E_INVALID_ENUM"


class InvalidSignatureError(GateError):
    code = "E_INVALID_SIGNATURE"


class MissingCanonRuleError(GateError):
    code = "E_MISSING_CANON_RULE"


class NonNFCError(GateError):
    code = "E_NON_NFC"


class RequiredMissingError(GateError):
    code = "E_REQUIRED_MISSING"


# --- Binding / replay errors (approval, token, audit) ---
class ActionHashMismatchError(GateError):
    code = "E_ACTION_HASH_MISMATCH"


class PolicyMismatchError(GateError):
    code = "E_POLICY_MISMATCH"


class ExpiredError(GateError):
    code = "E_EXPIRED"


class NonceReplayError(GateError):
    code = "E_NONCE_REPLAY"


class ScopeViolationError(GateError):
    code = "E_SCOPE_VIOLATION"


class TargetMismatchError(GateError):
    code = "E_TARGET_MISMATCH"


class ConstraintsChangedError(GateError):
    code = "E_CONSTRAINTS_CHANGED"


class EvidenceBindingError(GateError):
    code = "E_EVIDENCE_BINDING"


class StaleStateError(GateError):
    code = "E_STALE_STATE"


class AuditChainError(GateError):
    code = "E_AUDIT_CHAIN"


ALL_CODES = sorted(
    cls.code
    for cls in list(globals().values())
    if isinstance(cls, type) and issubclass(cls, GateError) and cls is not GateError
)
