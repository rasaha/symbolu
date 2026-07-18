"""CER reference implementation (public draft).

A self-contained, standard-library-only implementation of CER validation,
canonicalization, the identity projection, and the action digest. It imports no
proprietary ActionGate or ACP internals. This is the clean-room reference used to
demonstrate that CER is independently implementable from its written specification.
"""
from .cer import action_digest, canonical_bytes, normalized_payload, validate
from .errors import CleanRoomError as CERError

__all__ = ["validate", "normalized_payload", "canonical_bytes", "action_digest", "CERError"]
