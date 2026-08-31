"""Unit tests for the opaque, versioned pagination cursor (Phase 3A)."""

from __future__ import annotations

import base64
import uuid

import pytest

from ugence_dilchat.errors import DilChatError, ErrorCode
from ugence_dilchat.services.chat_cursor import decode_cursor, encode_cursor


def test_roundtrip():
    conv = uuid.uuid4()
    token = encode_cursor(conv, 42)
    assert decode_cursor(token, conv) == 42


def test_cursor_is_opaque_base64():
    conv = uuid.uuid4()
    token = encode_cursor(conv, 7)
    # Opaque token: no raw sequence/uuid leaks in the surface form, but it decodes.
    assert "42" not in token
    base64.urlsafe_b64decode(token.encode())  # valid base64url


@pytest.mark.parametrize("bad", ["", "!!!!", "not-base64!", "a" * 1000])
def test_malformed_cursor_is_invalid(bad):
    with pytest.raises(DilChatError) as exc:
        decode_cursor(bad, uuid.uuid4())
    assert exc.value.code is ErrorCode.INVALID_CURSOR
    assert exc.value.status == 400


def test_cross_conversation_cursor_fails_closed():
    conv_a = uuid.uuid4()
    conv_b = uuid.uuid4()
    token = encode_cursor(conv_a, 5)
    with pytest.raises(DilChatError) as exc:
        decode_cursor(token, conv_b)
    assert exc.value.code is ErrorCode.INVALID_CURSOR


def test_wrong_version_rejected():
    conv = uuid.uuid4()
    forged = base64.urlsafe_b64encode(
        b'{"v":99,"c":"' + str(conv).encode() + b'","s":1}'
    ).decode()
    with pytest.raises(DilChatError) as exc:
        decode_cursor(forged, conv)
    assert exc.value.code is ErrorCode.INVALID_CURSOR


def test_negative_and_nonint_sequence_rejected():
    conv = uuid.uuid4()
    neg = base64.urlsafe_b64encode(
        b'{"v":1,"c":"' + str(conv).encode() + b'","s":-1}'
    ).decode()
    with pytest.raises(DilChatError):
        decode_cursor(neg, conv)
