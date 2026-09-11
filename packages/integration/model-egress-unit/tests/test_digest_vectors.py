"""Frozen digest vectors — the pin owner condition 2 requires.

The owner ratified the composed construction on 2026-09-11 on four conditions,
the second of which is that "the canonical encoding, ordering rules, hash
algorithm and relevant schema/version are pinned".

Every other digest test in this suite is a *relative* comparison: it asserts
that changing a field moves the digest. Relative tests cannot see a change to
the encoder itself. Alter ``separators``, drop ``sort_keys``, rename a framing
key, change a domain string or the timestamp format, and every digest in the
exchange moves together — while every relative assertion still holds, because
both sides moved. The suite would stay green while the contract silently became
a different contract.

These vectors are the fixed point. They are literal bytes, computed once and
reviewed, from inputs with no clock, no ``uuid4`` and no fixture indirection, so
a reader can recompute them by hand. **No test regenerates them.** A vector that
moves is either an unratified change to canonicalization v1 — which the module's
own rule is to forbid without a new version string — or a deliberate, ratified
version bump that must change ``MEU_CANONICALIZATION_VERSION`` with it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ugence_model_egress_unit import (
    EXCHANGE_SCHEMA_VERSION,
    MEU_CANONICALIZATION_VERSION,
    AuthorizationBinding,
    EgressRequest,
    MinimizedUnit,
    content_digest,
    minimized_context_digest,
    payload_digest,
)

# --- a fixture with no entropy in it -----------------------------------------
#
# Fixed UUIDs and a fixed instant. Nothing here is drawn from a clock or a
# random source, so the vectors below are reproducible on any machine.

TENANT = uuid.UUID("00000000-0000-4000-8000-000000000001")
REQUEST_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
CORRELATION_ID = uuid.UUID("00000000-0000-4000-8000-000000000003")

SUBMITTED_AT = datetime(2026, 9, 11, 12, 0, 0, 500000, tzinfo=timezone.utc)
NOT_VALID_AFTER = datetime(2026, 9, 11, 13, 0, 0, 500000, tzinfo=timezone.utc)

BINDING = AuthorizationBinding(
    clearance_ref="cer-vector-0001",
    clearance_digest="c" * 64,
    tenant_id=TENANT,
    authorized_vendor="reference-vendor",
    authorized_model="reference-model",
    policy_id="pol-vector-0001",
    reservation_id="rsv-vector-0001",
)

UNITS = (
    MinimizedUnit("unit-1", "the first admitted unit", 5),
    MinimizedUnit("unit-2", "the second admitted unit", 5),
)


def _request(**over) -> EgressRequest:
    return EgressRequest.create(
        request_id=over.get("request_id", REQUEST_ID),
        tenant_id=TENANT,
        correlation_id=CORRELATION_ID,
        submitted_at=SUBMITTED_AT,
        not_valid_after=NOT_VALID_AFTER,
        authorization=BINDING,
        minimized_context=over.get("units", UNITS),
        parameters=over.get("parameters", {"max_output_tokens": 256}),
    )


# --- the vectors themselves --------------------------------------------------

VECTOR_MINIMIZED_CONTEXT = (
    "71e4f5c839b02af3fb802c553026c3aec3a558cafd081cb3f6e4573e467d04a0")
VECTOR_CONTENT = (
    "0f4ede86bde428cd181addfc70ae93a1f153f8a321d98f3d7b91adbb1ea5e980")
VECTOR_REQUEST = (
    "967ae97a9a1d2b35f0ce49c597d1fa2243d063e69e20c91a47ddb0ac1a7c0a90")


def test_the_minimized_context_vector_is_unchanged():
    """Ordered ``[unit_id, exact_text]`` pairs, framed and SHA-256'd."""

    assert minimized_context_digest(UNITS) == VECTOR_MINIMIZED_CONTEXT


def test_the_content_vector_is_unchanged():
    assert content_digest("the first admitted unit") == VECTOR_CONTENT


def test_the_request_digest_vector_is_unchanged():
    """The outer digest, over the fixed body including the context digest."""

    assert _request().digest() == VECTOR_REQUEST


def test_a_payload_digest_shares_the_content_primitive():
    """Recorded rather than assumed: ``payload_digest`` *is* ``content_digest``.

    The separation that matters is between a content digest and the *context*
    digest, which carries its own type in the preimage — see the domain tests in
    ``test_canonical.py``. A response body and a prompt body hashed as bare
    content share one primitive, and that is the pinned behaviour.
    """

    assert payload_digest("the first admitted unit") == VECTOR_CONTENT


def test_the_pinned_version_strings_are_part_of_the_contract():
    """If either string moves, the vectors above must move with it — that is what
    makes the version a version rather than a label."""

    assert MEU_CANONICALIZATION_VERSION == (
        "ugence.model-egress-unit/canonicalization/v1")
    assert EXCHANGE_SCHEMA_VERSION == "ugence.model-egress-unit/exchange/v1"


def test_ordering_moves_the_pinned_vector():
    """The positive control for the vector itself.

    Without this, a ``minimized_context_digest`` that ignored its input entirely
    and returned a constant would satisfy the vector test above.
    """

    assert minimized_context_digest(tuple(reversed(UNITS))) != (
        VECTOR_MINIMIZED_CONTEXT)


def test_substituted_text_under_the_same_identifiers_moves_the_vector():
    """Owner condition 4: identifiers alone can never satisfy the contract.

    Same ``unit_id`` values, same order, same token counts — only the text
    differs, and the pinned digest must not survive it.
    """

    substituted = (
        MinimizedUnit("unit-1", "a substituted first unit", 5),
        MinimizedUnit("unit-2", "a substituted second unit", 5),
    )
    assert minimized_context_digest(substituted) != VECTOR_MINIMIZED_CONTEXT
    assert _request(units=substituted).digest() != VECTOR_REQUEST
