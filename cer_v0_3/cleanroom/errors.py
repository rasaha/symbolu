"""Clean-room error taxonomy.

Independent of the frozen ActionGate ``errors`` module. Each error carries a
stable ``category`` string so the differential runner can compare *error classes*
across the two implementations without depending on either's exception types.

Written from the published specification (ACTION_CANONICALIZATION_AND_HASHING_SPEC
and CER V0.2 spec/schema), not from the reference source.
"""
from __future__ import annotations


class CleanRoomError(Exception):
    """Base class. ``category`` is the portable comparison key."""
    category = "error"

    def __init__(self, message: str, *, path: str = ""):
        super().__init__(message)
        self.path = path


# --- canonicalization / Action-Profile violations ---
class BareNumberError(CleanRoomError):
    category = "E_BARE_NUMBER"


class NonFiniteNumberError(CleanRoomError):
    category = "E_NAN_INF"


class DuplicateKeyError(CleanRoomError):
    category = "E_DUPLICATE_KEY"


class NonNFCError(CleanRoomError):
    category = "E_NON_NFC"


class UnsupportedTypeError(CleanRoomError):
    category = "E_UNSUPPORTED_TYPE"


class DuplicateSetElementError(CleanRoomError):
    category = "E_DUPLICATE_SET_ELEMENT"


# --- CER structural / profile validation ---
class CERSchemaError(CleanRoomError):
    category = "E_CER_SCHEMA"


class UnknownProfileError(CleanRoomError):
    category = "E_UNKNOWN_PROFILE"


class UnknownFieldError(CleanRoomError):
    category = "E_UNKNOWN_FIELD"


class MissingFieldError(CleanRoomError):
    category = "E_MISSING_FIELD"


class ProhibitedFieldError(CleanRoomError):
    category = "E_PROHIBITED_FIELD"


class UnsupportedExtensionError(CleanRoomError):
    category = "E_UNSUPPORTED_EXTENSION"


class OperationMismatchError(CleanRoomError):
    category = "E_OPERATION_MISMATCH"


class SecretMaterialError(CleanRoomError):
    category = "E_SECRET_MATERIAL"


class ValueFormatError(CleanRoomError):
    category = "E_VALUE_FORMAT"
