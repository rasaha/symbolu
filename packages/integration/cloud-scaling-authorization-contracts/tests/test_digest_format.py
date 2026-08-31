"""Every digest this package emits carries the shape of the namespace it belongs to.

Phase 5A's own digests are ``sha256:<64 lowercase hex>``, structurally. A bare-hex spelling
of one of those would be a second spelling of the same value, and two spellings defeat the
equality checks the whole boundary rests on.

Since 5B-1 the candidate also **carries** two digests that are not Phase 5A's: the Policy
Authority's ``policy_content_digest`` and ``policy_body_digest``, which are bare lowercase
64-hex in the authority's own namespace. They are bare because that is the exact string the
issuance signature covers; re-encoding them with a ``sha256:`` prefix would mint a digest
nobody signed, over a frame nobody hashed (D-5B1-4). So the rule this module enforces is
per-namespace, and the two namespaces are asserted to be mutually exclusive rather than
merely different.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

import ugence_cloud_scaling_authorization_contracts as pkg
from ugence_cloud_scaling_authorization_contracts import (
    is_canonical_digest,
    is_policy_authority_digest,
)

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


#: The only paths in a candidate's canonical form that carry a Policy Authority digest.
#: Exhaustive and pinned: a new bare-hex field anywhere else fails the walk below, which is
#: what stops the authority's namespace leaking into Phase 5A's by accident.
POLICY_AUTHORITY_DIGEST_PATHS = frozenset(
    {
        "root.policy_coordinate_binding.policy_content_digest",
        "root.policy_coordinate_binding.policy_body_digest",
    }
)


def test_every_emitted_digest_field_is_canonical(candidate):
    """Walk the whole canonical form: every digest carries its own namespace's shape."""

    seen_policy_authority = set()
    for path, value in _walk(candidate.to_canonical_dict()):
        if path in POLICY_AUTHORITY_DIGEST_PATHS:
            assert is_policy_authority_digest(value), f"{path} is not bare 64-hex: {value!r}"
            assert not is_canonical_digest(value), (
                f"{path} carries a Phase 5A prefix on a Policy Authority digest: {value!r}"
            )
            seen_policy_authority.add(path)
            continue
        if _BARE_HEX.fullmatch(value):
            pytest.fail(f"{path} emits a bare-hex digest: {value}")
        if path.endswith(("digest", "_digest", "idempotency_key")):
            assert is_canonical_digest(value), f"{path} is not canonical: {value!r}"
    assert seen_policy_authority == POLICY_AUTHORITY_DIGEST_PATHS, (
        "a pinned Policy Authority digest path is no longer emitted: "
        f"{sorted(POLICY_AUTHORITY_DIGEST_PATHS - seen_policy_authority)}"
    )


def test_the_two_digest_namespaces_are_mutually_exclusive():
    """Neither predicate accepts anything the other does, and nothing converts between them."""

    prefixed = "sha256:" + "a" * 64
    bare = "a" * 64
    assert is_canonical_digest(prefixed) and not is_policy_authority_digest(prefixed)
    assert is_policy_authority_digest(bare) and not is_canonical_digest(bare)
    assert not any(
        "prefix" in name or "strip" in name or "convert" in name
        for name in dir(pkg)
        if "digest" in name
    )


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
