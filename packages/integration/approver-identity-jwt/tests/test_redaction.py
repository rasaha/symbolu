"""The token never leaves the ``authenticate`` call: not in an answer, a reason, an
exception message, a repr, a log record or any attribute reachable from the adapter
afterwards. Held for every path the adapter has, refused and accepted alike."""

from __future__ import annotations

import gc
import logging

import pytest

from ugence_governed_review_service import IdentityUnavailable

from ugence_approver_identity_jwt import JwtApproverIdentityAdapter, Refusal

from conftest import STUDIO_AUDIENCE, base_claims, config_for


def _walk(obj, seen=None, depth=0):
    seen = seen if seen is not None else set()
    if id(obj) in seen or depth > 6:
        return
    seen.add(id(obj))
    if isinstance(obj, (str, bytes)):
        yield obj if isinstance(obj, str) else obj.decode("latin-1")
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(k, seen, depth + 1)
            yield from _walk(v, seen, depth + 1)
        return
    if isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            yield from _walk(v, seen, depth + 1)
        return
    if hasattr(obj, "__dict__"):
        for v in vars(obj).values():
            yield from _walk(v, seen, depth + 1)


def _segments(token: str) -> list[str]:
    """Any piece of the token long enough to identify it: header, payload, signature."""

    return [s for s in token.split(".") if len(s) >= 8]


def _every_path(issuer, clock):
    """(label, token, expected) for each outcome the adapter can reach."""

    ok = issuer.mint(base_claims(issuer), kid="rsa-1")
    return [
        ("accepted", ok, None),
        ("alg", issuer.mint_hmac(base_claims(issuer), kid="rsa-1"), Refusal.ALG_NOT_PERMITTED),
        ("typ", issuer.mint(base_claims(issuer), kid="rsa-1", typ="JWT"), Refusal.TYP_NOT_ACCESS_TOKEN),
        ("kid", issuer.mint(base_claims(issuer), kid="rsa-1", headers={"kid": "ghost"}), Refusal.KEY_UNKNOWN),
        ("sig", issuer.mint(base_claims(issuer), kid="rsa-1", pem=issuer.foreign_pem()), Refusal.SIGNATURE_INVALID),
        ("iss", issuer.mint(base_claims(issuer, iss="https://x.test"), kid="rsa-1"), Refusal.ISSUER_MISMATCH),
        ("aud", issuer.mint(base_claims(issuer, aud=STUDIO_AUDIENCE), kid="rsa-1"), Refusal.AUDIENCE_MISMATCH),
        ("missing", issuer.mint(base_claims(issuer, exp=None), kid="rsa-1"), Refusal.CLAIM_MISSING),
        ("malformed", issuer.mint(base_claims(issuer, amr="pwd"), kid="rsa-1"), Refusal.CLAIM_MALFORMED),
        ("untyped", "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4In0.bm90LWEtc2ln", Refusal.TYP_NOT_ACCESS_TOKEN),
        ("garbage", "eyJ%%notbase64.eyJzdWIiOiJ4In0.bm90LWEtc2ln", Refusal.MALFORMED),
        ("large", "x" * 20000, Refusal.PROOF_TOO_LARGE),
    ]


def test_no_token_fragment_appears_in_any_answer_repr_log_or_attribute(issuer, clock, caplog):
    caplog.set_level(logging.DEBUG)
    adapter = JwtApproverIdentityAdapter(config_for(issuer), clock=clock.datetime)
    for label, token, expected in _every_path(issuer, clock):
        answer = adapter.authenticate(token)
        if expected is None:
            assert answer.authenticated, label
        else:
            assert answer.refusal == expected.value, label
        rendered = " ".join([repr(answer), str(answer), repr(adapter), repr(adapter.config),
                             repr(adapter.keys), answer.refusal, str(answer.claims)])
        for fragment in _segments(token) + [token[:32]]:
            assert fragment not in rendered, (label, "answer or repr")
            assert fragment not in caplog.text, (label, "log")
        gc.collect()
        for text in _walk(adapter):
            for fragment in _segments(token) + [token[:32]]:
                assert fragment not in text, (label, "attribute reachable from the adapter")
    assert caplog.records == [], "the adapter emits no log record at all"


def test_an_outage_message_names_the_failure_kind_and_nothing_from_the_wire(issuer, clock):
    adapter = JwtApproverIdentityAdapter(config_for(issuer), clock=clock.datetime)
    token = issuer.mint(base_claims(issuer), kid="rsa-1")
    issuer.fail_next = 1
    with pytest.raises(IdentityUnavailable) as excinfo:
        adapter.authenticate(token)
    message = str(excinfo.value)
    assert message == "JWKS could not be fetched: HTTPError"
    for fragment in _segments(token):
        assert fragment not in message
    issuer.serve_malformed = True
    with pytest.raises(IdentityUnavailable) as excinfo:
        adapter.authenticate(token)
    assert "not JSON" in str(excinfo.value) and "html" not in str(excinfo.value)


def test_the_refusal_vocabulary_is_closed_and_carries_no_free_text():
    for member in Refusal:
        assert member.value == member.name and member.value.isupper()
    assert len(Refusal) == 14
