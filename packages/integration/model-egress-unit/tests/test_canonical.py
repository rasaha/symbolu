"""The digests: total, deterministic, domain-separated, and closed to surprises.

No database here — these are properties of the encoder alone.
"""

from __future__ import annotations

import json
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from _fixtures import MODEL, binding, request as _make_request
from ugence_model_egress_unit import (
    MinimizedUnit,
    ResultOutcome,
    EGRESS_REQUEST_DIGEST_DOMAIN,
    EGRESS_RESULT_DIGEST_DOMAIN,
    EXCHANGE_CONTENT_DIGEST_DOMAIN,
    CanonicalizationError,
    EgressRequest,
    EgressResult,
    RefusalReason,
    canonical_bytes,
    canonical_digest,
    content_digest,
)

NOW = datetime(2026, 3, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
RID = uuid.UUID("11111111-1111-1111-1111-111111111111")
TID = uuid.UUID("22222222-2222-2222-2222-222222222222")
CID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def _request(**over):
    """A fully pinned request: every identifier fixed unless the caller varies it.

    ``_fixtures.request`` mints a fresh ``request_id`` and ``correlation_id`` per
    call, which is right for the exchange suites and wrong here — a digest test
    must vary exactly one field at a time or it proves nothing about which field
    moved the value.
    """

    over.setdefault("request_id", RID)
    over.setdefault("correlation_id", CID)
    over.setdefault("submitted_at", NOW)
    tenant = over.pop("tenant_id", TID)
    over.setdefault("authorization", binding(tenant))
    return _make_request(tenant, **over)


# --- determinism and totality ------------------------------------------------

def test_the_same_request_always_digests_the_same():
    assert _request().digest() == _request().digest()


def test_every_field_moves_the_request_digest():
    """Totality, field by field. Without this a field could quietly drop out of
    the encoding and the digest would still look like it covered the request."""

    base = _request().digest()
    assert _request(request_id=uuid.uuid4()).digest() != base
    assert _request(tenant_id=uuid.uuid4()).digest() != base
    assert _request(submitted_at=NOW + timedelta(microseconds=1)).digest() != base
    assert _request(authorization=binding(TID, model="other")).digest() != base
    assert _request(context=(MinimizedUnit("u", "different", 1),)).digest() != base
    assert _request(parameters={"temperature": 1}).digest() != base


def test_every_field_moves_the_result_digest():
    def result(**over):
        kwargs = dict(request_id=RID, tenant_id=TID, correlation_id=CID,
                      recorded_at=NOW, adapter_id="p", payload="an answer",
                      model_ref=MODEL)
        kwargs.update(over)
        return EgressResult.answered(**kwargs)

    base = result().digest()
    assert result(request_id=uuid.uuid4()).digest() != base
    assert result(tenant_id=uuid.uuid4()).digest() != base
    assert result(recorded_at=NOW + timedelta(microseconds=1)).digest() != base
    assert result(adapter_id="q").digest() != base
    assert result(payload="a different answer").digest() != base

    refused = EgressResult.refused(
        request_id=RID, tenant_id=TID, correlation_id=CID, recorded_at=NOW,
        adapter_id="p", reason=RefusalReason.MODEL_NOT_AVAILABLE)
    other = EgressResult.refused(
        request_id=RID, tenant_id=TID, correlation_id=CID, recorded_at=NOW,
        adapter_id="p", reason=RefusalReason.TARGET_NOT_AUTHORIZED)
    assert refused.digest() != other.digest() != base


def test_microseconds_survive_and_offsets_normalize():
    """Two spellings of one instant digest identically; one microsecond apart
    does not. A format that dropped microseconds would merge them."""

    other_zone = timezone(timedelta(hours=5, minutes=30))
    assert (_request(submitted_at=NOW).digest()
            == _request(submitted_at=NOW.astimezone(other_zone)).digest())
    assert (_request(submitted_at=NOW).digest()
            != _request(submitted_at=NOW + timedelta(microseconds=1)).digest())


def test_none_and_empty_string_are_different_digests():
    assert content_digest("") != canonical_digest(
        EXCHANGE_CONTENT_DIGEST_DOMAIN, "x", {"content": None})


# --- domain separation -------------------------------------------------------

def test_the_three_domains_never_collide():
    body = {"a": 1}
    digests = {
        canonical_digest(EGRESS_REQUEST_DIGEST_DOMAIN, "T", body),
        canonical_digest(EGRESS_RESULT_DIGEST_DOMAIN, "T", body),
        canonical_digest(EXCHANGE_CONTENT_DIGEST_DOMAIN, "T", body),
    }
    assert len(digests) == 3, "one body under three domains must give three digests"


def test_the_type_name_is_bound_into_the_digest():
    body = {"a": 1}
    assert (canonical_digest(EGRESS_REQUEST_DIGEST_DOMAIN, "One", body)
            != canonical_digest(EGRESS_REQUEST_DIGEST_DOMAIN, "Two", body))


def test_a_content_digest_is_not_a_request_digest():
    """A value from one domain must never validate as a value from another."""

    assert content_digest("x") != canonical_digest(
        EGRESS_REQUEST_DIGEST_DOMAIN, "EgressRequest", {"content": "x"})


# --- the encoder fails closed ------------------------------------------------

def test_a_naive_datetime_is_rejected():
    with pytest.raises(CanonicalizationError, match="naive datetime"):
        canonical_digest(EGRESS_REQUEST_DIGEST_DOMAIN, "T", {"t": datetime(2026, 1, 1)})


def test_a_float_is_rejected():
    with pytest.raises(CanonicalizationError, match="float is rejected"):
        canonical_digest(EGRESS_REQUEST_DIGEST_DOMAIN, "T", {"x": 1.5})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_floats_are_rejected_too(value):
    with pytest.raises(CanonicalizationError):
        canonical_digest(EGRESS_REQUEST_DIGEST_DOMAIN, "T", {"x": value})


def test_an_unknown_type_is_rejected_rather_than_stringified():
    """No ``default=`` hook and no ``str()`` fallback. A permissive encoder would
    make the digest a function of an object's ``repr`` — including its ``id()``
    for any default one, which is not stable across processes at all."""

    class Opaque:
        pass

    with pytest.raises(CanonicalizationError, match="has no canonical form"):
        canonical_digest(EGRESS_REQUEST_DIGEST_DOMAIN, "T", {"x": Opaque()})


def test_a_non_nfc_string_is_rejected_not_normalized():
    """Silent normalization would map two structurally different payloads onto
    one digest. Rejecting keeps one payload to one digest in both directions."""

    nfd = unicodedata.normalize("NFD", "café")
    assert nfd != "café"
    with pytest.raises(CanonicalizationError, match="not Unicode NFC"):
        content_digest(nfd)


def test_bool_is_not_encoded_as_an_integer():
    """``bool`` subclasses ``int``; dispatched the other way round, ``True`` and
    ``1`` would share a digest."""

    assert (canonical_digest(EGRESS_REQUEST_DIGEST_DOMAIN, "T", {"x": True})
            != canonical_digest(EGRESS_REQUEST_DIGEST_DOMAIN, "T", {"x": 1}))
    assert b'"x":true' in canonical_bytes(EGRESS_REQUEST_DIGEST_DOMAIN, "T", {"x": True})


# --- the framing -------------------------------------------------------------

def test_the_bytes_are_sorted_and_tight():
    raw = canonical_bytes(EGRESS_REQUEST_DIGEST_DOMAIN, "T", {"b": 1, "a": 2})
    assert b", " not in raw and b": " not in raw, "no insignificant whitespace"
    framed = json.loads(raw)
    assert list(framed) == sorted(framed)
    assert list(framed["body"]) == ["a", "b"]


def test_the_canonicalization_version_is_bound_into_every_digest():
    framed = json.loads(canonical_bytes(EGRESS_REQUEST_DIGEST_DOMAIN, "T", {}))
    assert framed["canonicalization"] == "ugence.model-egress-unit/canonicalization/v1"
    assert framed["domain"] == EGRESS_REQUEST_DIGEST_DOMAIN


# --- the record invariants ---------------------------------------------------

def test_a_refusal_must_name_a_reason():
    with pytest.raises(ValueError, match="must name its reason"):
        EgressResult(
            request_id=RID, tenant_id=TID, correlation_id=CID, recorded_at=NOW,
            outcome=ResultOutcome.REFUSED, adapter_id="p",
            provenance={"kind": "RESPONSE", "genuine_call": False},
            payload=None, content_digest=None, refusal_reason=None)


def test_only_an_answer_carries_a_payload():
    with pytest.raises(ValueError, match="no payload to carry"):
        EgressResult(
            request_id=RID, tenant_id=TID, correlation_id=CID, recorded_at=NOW,
            outcome=ResultOutcome.OUTCOME_UNKNOWN, adapter_id="p",
            provenance={"kind": "DISPATCH_ATTEMPT", "genuine_call": False},
            payload="smuggled", content_digest=None)


def test_no_result_may_claim_a_genuine_call():
    """The provenance check, in the record rather than only in the database."""

    with pytest.raises(ValueError, match="no genuine provider call"):
        EgressResult(
            request_id=RID, tenant_id=TID, correlation_id=CID, recorded_at=NOW,
            outcome=ResultOutcome.FAILED, adapter_id="p",
            provenance={"kind": "RESPONSE", "genuine_call": True},
            payload=None, content_digest=None)


def test_trust_is_not_a_field_a_caller_may_raise():
    with pytest.raises(ValueError, match="constant"):
        EgressResult(
            request_id=RID, tenant_id=TID, correlation_id=CID, recorded_at=NOW,
            outcome=ResultOutcome.FAILED, adapter_id="p",
            provenance={"kind": "RESPONSE", "genuine_call": False},
            payload=None, content_digest=None, trust="TRUSTED")
