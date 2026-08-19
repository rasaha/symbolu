"""Every digest this package emits is ``sha256:<64 lowercase hex>``. Structurally.

A bare-hex digest would be a second spelling of the same value, and two spellings defeat
the equality checks the whole boundary rests on.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

import ugence_cloud_scaling_authorization_contracts as pkg
from ugence_cloud_scaling_authorization_contracts import is_canonical_digest

SRC = pathlib.Path(pkg.__file__).resolve().parent
SOURCES = sorted(SRC.rglob("*.py"))

_BARE_HEX = re.compile(r"(?<![:0-9a-fA-Fx])\b[0-9a-f]{64}\b")


def _walk(value, path="root"):
    """Yield every ``(path, str)`` leaf in a nested canonical structure."""

    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            yield from _walk(v, f"{path}[{i}]")


def test_no_source_literal_is_a_bare_hex_digest():
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not _BARE_HEX.fullmatch(node.value), (
                    f"{path.name}:{node.lineno} carries a bare-hex digest literal"
                )


def test_every_emitted_digest_field_is_canonical(candidate):
    """Walk the whole canonical form: anything digest-shaped must carry the prefix."""

    for path, value in _walk(candidate.to_canonical_dict()):
        if _BARE_HEX.fullmatch(value):
            pytest.fail(f"{path} emits a bare-hex digest: {value}")
        if path.endswith(("digest", "_digest", "idempotency_key")):
            assert is_canonical_digest(value), f"{path} is not canonical: {value!r}"


def test_all_named_digest_accessors_are_canonical(candidate):
    for obj in (
        candidate,
        candidate.target_scope,
        candidate.policy_binding,
        candidate.producer_attestation,
    ):
        assert is_canonical_digest(obj.digest())


def test_the_validator_rejects_the_near_misses():
    good = "sha256:" + "a" * 64
    assert is_canonical_digest(good)
    for bad in (
        "a" * 64,                      # bare hex
        "sha256:" + "A" * 64,          # uppercase
        "sha256:" + "a" * 63,          # short
        "sha256:" + "a" * 65,          # long
        "sha1:" + "a" * 64,            # wrong algorithm
        "sha256:" + "g" * 64,          # non-hex
        "SHA256:" + "a" * 64,          # uppercase prefix
        "",
        None,
        b"sha256:" + b"a" * 64,
    ):
        assert not is_canonical_digest(bad), f"{bad!r} was accepted"
