"""Opaque, versioned cursor for stable message pagination (Phase 3A).

A cursor encodes only ``(version, conversation_id, after_sequence)``. It is base64url
of a compact JSON object — opaque to clients and self-describing to the server. A
cursor is bound to its conversation: presenting one issued for a different
conversation fails closed (``INVALID_CURSOR`` → 400) rather than leaking rows.
"""

from __future__ import annotations

import base64
import binascii
import json
import uuid

from ..errors import DilChatError, ErrorCode

CURSOR_VERSION = 1
_MAX_CURSOR_BYTES = 512


def encode_cursor(conversation_id: uuid.UUID, after_sequence: int) -> str:
    raw = json.dumps(
        {"v": CURSOR_VERSION, "c": str(conversation_id), "s": int(after_sequence)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str, conversation_id: uuid.UUID) -> int:
    """Return the ``after_sequence`` encoded in ``cursor`` for ``conversation_id``.

    Fails closed with ``INVALID_CURSOR`` (400) on any malformed, oversized, wrong
    version, or cross-conversation cursor.
    """
    if not cursor or len(cursor) > _MAX_CURSOR_BYTES:
        raise DilChatError(ErrorCode.INVALID_CURSOR, "Malformed pagination cursor.")
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        data = json.loads(raw)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise DilChatError(ErrorCode.INVALID_CURSOR, "Malformed pagination cursor.") from exc
    if not isinstance(data, dict) or data.get("v") != CURSOR_VERSION:
        raise DilChatError(ErrorCode.INVALID_CURSOR, "Unsupported cursor version.")
    seq = data.get("s")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
        raise DilChatError(ErrorCode.INVALID_CURSOR, "Malformed pagination cursor.")
    # Bind the cursor to its conversation — a cursor from another conversation is
    # never honoured (anti-enumeration / fail closed).
    if str(data.get("c")) != str(conversation_id):
        raise DilChatError(ErrorCode.INVALID_CURSOR, "Cursor does not belong to this conversation.")
    return seq
