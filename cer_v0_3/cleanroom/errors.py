"""Clean-room error taxonomy.

Independent of the frozen ActionGate ``errors`` module. Each error carries a
stable ``category`` string so the differential runner can compare *error classes*
across the two implementations without depending on either's exception types.

Written from the published specification (ACTION_CANONICALIZATION_AND_HASHING_SPEC
and CER V0.2 spec/schema), not from the reference source.
"""
from __future__ import annotations


from ugence_jcs.errors import (
    BareNumberError,
    DuplicateSetElementError,
    JcsError,
    NonFiniteNumberError,
    NonNFCError,
    UnsupportedTypeError,
)

#: The canonicalization error taxonomy moved to the extracted ``ugence-jcs`` leaf
#: (``packages/jcs``) together with the canonicalizer. ``CleanRoomError`` remains the
#: clean-room base class and is that same class, so ``except CleanRoomError`` still
#: catches every canonicalization fault and every CER structural fault below, and each
#: ``category`` key is unchanged.
CleanRoomError = JcsError


# --- canonicalization / Action-Profile violations ---
# BareNumberError, NonFiniteNumberError, NonNFCError, UnsupportedTypeError and
# DuplicateSetElementError are re-exported from ugence_jcs.errors above.
class DuplicateKeyError(CleanRoomError):
    category = "E_DUPLICATE_KEY"


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
