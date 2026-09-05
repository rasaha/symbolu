"""G7 / G8 — neutral idempotency and validity contracts: structure & determinism.

These tests prove that the two additive families reject inconsistent
combinations at construction, derive every answer from an explicit instant
(never a clock), canonicalize deterministically, and — the compatibility half —
leave every frozen provider dataclass byte-for-byte untouched.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

import ugence_governance_contracts as g
from ugence_governance_contracts import api
from ugence_governance_contracts.contracts.idempotency import (
    IdempotencyContractError,
    IdempotencyDisposition,
    IdempotencyKey,
    IdempotencyResolution,
    IdempotencyScope,
)
from ugence_governance_contracts.contracts.validity import (
    Validity,
    ValidityContractError,
    ValidityStatus,
)

_T0 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
_IST = timezone(timedelta(hours=5, minutes=30))
_EDT = timezone(timedelta(hours=-4))

# Pinned canonical forms. A change here is a contract change, not a refactor.
_KEY_BYTES = (
    b'{"actor":"agent://a","key":"k-1","partition":"tenant-1",'
    b'"scope":"ACTOR_AND_TARGET","target_resource":"ns/prod"}'
)
_KEY_DIGEST = "3c1b18cf73430677e7f35d38d27fec98e9fb3e31a09c7a150b7b9b3e69dfa037"
_RES_DIGEST = "8400786c3219eca41a0f32b9ff34012d48e63f269a76c5d13613346bec48515d"
_VAL_BYTES = (
    b'{"expires_at":"2026-09-04 11:00:00+00:00","issued_at":"2026-09-04 10:00:00+00:00",'
    b'"stale_after":"2026-09-04 10:30:00+00:00"}'
)
_VAL_DIGEST = "2d949c3d305fe04a325704aebe837b58f07ee0b9b54cf119f6ac5f4d9da854e5"


def _key(**kw) -> IdempotencyKey:
    base = dict(key="k-1", scope=IdempotencyScope.ACTOR_AND_TARGET,
                actor="agent://a", target_resource="ns/prod", partition="tenant-1")
    base.update(kw)
    return IdempotencyKey(**base)


def _validity(**kw) -> Validity:
    base = dict(issued_at=_T0, expires_at=_T0 + timedelta(hours=1),
                stale_after=_T0 + timedelta(minutes=30))
    base.update(kw)
    return Validity(**base)


# --------------------------------------------------------------------------- #
# Public surface
# --------------------------------------------------------------------------- #
def test_families_are_exported_once_and_identically():
    for name in ("IdempotencyScope", "IdempotencyKey", "IdempotencyDisposition",
                 "IdempotencyResolution", "IdempotencyContractError",
                 "ValidityStatus", "Validity", "ValidityContractError"):
        assert name in api.__all__, name
        assert getattr(api, name) is getattr(g, name), name
    assert IdempotencyKey.__module__ == "ugence_governance_contracts.contracts.idempotency"
    assert Validity.__module__ == "ugence_governance_contracts.contracts.validity"


def test_enum_values_serialize_deterministically():
    assert [m.value for m in IdempotencyScope] == [
        "GLOBAL", "ACTOR", "TARGET_RESOURCE", "ACTOR_AND_TARGET"]
    assert [m.value for m in IdempotencyDisposition] == ["FIRST", "DUPLICATE", "UNKNOWN"]
    assert [m.value for m in ValidityStatus] == ["NOT_YET_VALID", "FRESH", "STALE", "EXPIRED"]
    assert json.dumps(IdempotencyDisposition.DUPLICATE) == '"DUPLICATE"'


def test_errors_are_value_errors_and_distinct():
    assert issubclass(IdempotencyContractError, ValueError)
    assert issubclass(ValidityContractError, ValueError)
    assert IdempotencyContractError is not ValidityContractError
    assert not issubclass(IdempotencyContractError, g.EvidenceContractError)
    assert not issubclass(ValidityContractError, g.SystemIdentityContractError)


# --------------------------------------------------------------------------- #
# G7 — IdempotencyKey
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_key_must_be_nonblank_string(bad):
    with pytest.raises(IdempotencyContractError):
        IdempotencyKey(key=bad, scope=IdempotencyScope.GLOBAL)


def test_key_and_coordinates_are_stripped_so_whitespace_never_forks_identity():
    a = IdempotencyKey(key=" k ", scope=IdempotencyScope.ACTOR, actor=" agent://a ", partition=" t ")
    b = IdempotencyKey(key="k", scope=IdempotencyScope.ACTOR, actor="agent://a", partition="t")
    assert a == b
    assert a.canonical_digest() == b.canonical_digest()


def test_scope_must_be_enum_member():
    with pytest.raises(IdempotencyContractError):
        IdempotencyKey(key="k", scope="ACTOR")  # type: ignore[arg-type]


@pytest.mark.parametrize("scope,required", [
    (IdempotencyScope.ACTOR, ("actor",)),
    (IdempotencyScope.TARGET_RESOURCE, ("target_resource",)),
    (IdempotencyScope.ACTOR_AND_TARGET, ("actor", "target_resource")),
])
def test_scope_named_coordinates_are_required(scope, required):
    for name in required:
        kw = {"actor": "a", "target_resource": "r"}
        kw[name] = ""
        with pytest.raises(IdempotencyContractError, match=f"{name} is required"):
            IdempotencyKey(key="k", scope=scope, **{k: v for k, v in kw.items()
                                                    if k in ("actor", "target_resource")
                                                    and (k in required)})


@pytest.mark.parametrize("scope,forbidden", [
    (IdempotencyScope.GLOBAL, ("actor", "target_resource")),
    (IdempotencyScope.ACTOR, ("target_resource",)),
    (IdempotencyScope.TARGET_RESOURCE, ("actor",)),
])
def test_coordinates_the_scope_does_not_name_must_be_empty(scope, forbidden):
    named = {"actor": "a", "target_resource": "r"}
    for name in forbidden:
        kw = {k: v for k, v in named.items() if k not in forbidden}
        kw[name] = "x"
        with pytest.raises(IdempotencyContractError, match="must be empty"):
            IdempotencyKey(key="k", scope=scope, **kw)


def test_every_scope_is_constructible_with_exactly_its_coordinates():
    assert IdempotencyKey(key="k", scope=IdempotencyScope.GLOBAL).identity == ("", "GLOBAL", "", "", "k")
    assert IdempotencyKey(key="k", scope=IdempotencyScope.ACTOR, actor="a").actor == "a"
    assert IdempotencyKey(key="k", scope=IdempotencyScope.TARGET_RESOURCE,
                          target_resource="r").target_resource == "r"
    assert _key().identity == ("tenant-1", "ACTOR_AND_TARGET", "agent://a", "ns/prod", "k-1")


def test_key_canonical_form_is_pinned():
    k = _key()
    assert k.canonical_bytes() == _KEY_BYTES
    assert k.canonical_digest() == _KEY_DIGEST
    assert hashlib.sha256(k.canonical_bytes()).hexdigest() == k.canonical_digest()
    assert _key() == k and _key().canonical_digest() == k.canonical_digest()


@pytest.mark.parametrize("kw", [
    {"key": "k-2"},
    {"actor": "agent://b"},
    {"target_resource": "ns/stage"},
    {"partition": "tenant-2"},
])
def test_any_coordinate_change_changes_the_identity(kw):
    assert _key(**kw).canonical_digest() != _key().canonical_digest()


def test_same_key_under_a_different_scope_is_a_different_identity():
    a = IdempotencyKey(key="k", scope=IdempotencyScope.ACTOR, actor="a")
    b = IdempotencyKey(key="k", scope=IdempotencyScope.GLOBAL)
    assert a.canonical_digest() != b.canonical_digest()


def test_digest_fits_the_frozen_free_string_field_without_changing_it():
    # Adopting the contract means placing the digest in the existing free-string
    # field; the field's type and default are untouched.
    req = g.ExecutionDispatchRequest(action_type="do", idempotency_key=_key().canonical_digest())
    assert len(req.idempotency_key) == 64
    assert g.ExecutionDispatchRequest(action_type="do").idempotency_key == ""


# --------------------------------------------------------------------------- #
# G7 — IdempotencyResolution
# --------------------------------------------------------------------------- #
def test_duplicate_requires_original_and_others_forbid_it():
    with pytest.raises(IdempotencyContractError, match="duplicate_of is required"):
        IdempotencyResolution(key=_key(), disposition=IdempotencyDisposition.DUPLICATE)
    with pytest.raises(IdempotencyContractError, match="duplicate_of is required"):
        IdempotencyResolution(key=_key(), disposition=IdempotencyDisposition.DUPLICATE,
                              duplicate_of="   ")
    for d in (IdempotencyDisposition.FIRST, IdempotencyDisposition.UNKNOWN):
        with pytest.raises(IdempotencyContractError, match="must be empty"):
            IdempotencyResolution(key=_key(), disposition=d, duplicate_of="req-0")


def test_resolution_requires_typed_key_and_disposition():
    with pytest.raises(IdempotencyContractError):
        IdempotencyResolution(key="k", disposition=IdempotencyDisposition.FIRST)  # type: ignore[arg-type]
    with pytest.raises(IdempotencyContractError):
        IdempotencyResolution(key=_key(), disposition="FIRST")  # type: ignore[arg-type]


def test_unknown_is_never_first_and_never_determinate():
    first = IdempotencyResolution(key=_key(), disposition=IdempotencyDisposition.FIRST)
    dup = IdempotencyResolution(key=_key(), disposition=IdempotencyDisposition.DUPLICATE,
                                duplicate_of=" req-0 ")
    unknown = IdempotencyResolution(key=_key(), disposition=IdempotencyDisposition.UNKNOWN)
    assert (first.is_first, first.is_duplicate, first.is_determinate) == (True, False, True)
    assert (dup.is_first, dup.is_duplicate, dup.is_determinate) == (False, True, True)
    assert dup.duplicate_of == "req-0"
    assert (unknown.is_first, unknown.is_duplicate, unknown.is_determinate) == (False, False, False)


def test_resolution_canonical_digest_is_pinned_and_binds_the_original():
    dup = IdempotencyResolution(key=_key(), disposition=IdempotencyDisposition.DUPLICATE,
                                duplicate_of="req-0")
    assert dup.canonical_digest() == _RES_DIGEST
    other = IdempotencyResolution(key=_key(), disposition=IdempotencyDisposition.DUPLICATE,
                                  duplicate_of="req-1")
    assert other.canonical_digest() != dup.canonical_digest()
    payload = json.loads(dup.canonical_bytes())
    assert payload["key"]["scope"] == "ACTOR_AND_TARGET" and payload["disposition"] == "DUPLICATE"


# --------------------------------------------------------------------------- #
# G8 — Validity
# --------------------------------------------------------------------------- #
def test_issued_at_is_required_and_every_instant_must_be_aware():
    with pytest.raises(ValidityContractError, match="must be a datetime"):
        Validity(issued_at="2026-09-04")  # type: ignore[arg-type]
    with pytest.raises(ValidityContractError, match="timezone-aware"):
        Validity(issued_at=datetime(2026, 9, 4, 10, 0))
    with pytest.raises(ValidityContractError, match="timezone-aware"):
        Validity(issued_at=_T0, expires_at=datetime(2026, 9, 4, 11, 0))
    with pytest.raises(ValidityContractError, match="timezone-aware"):
        Validity(issued_at=_T0, stale_after=datetime(2026, 9, 4, 10, 30))


def test_window_is_nonempty_and_soft_bound_lies_inside_it():
    with pytest.raises(ValidityContractError, match="issued_at must precede expires_at"):
        Validity(issued_at=_T0, expires_at=_T0)
    with pytest.raises(ValidityContractError, match="issued_at must precede expires_at"):
        Validity(issued_at=_T0, expires_at=_T0 - timedelta(seconds=1))
    with pytest.raises(ValidityContractError, match="must not precede issued_at"):
        Validity(issued_at=_T0, stale_after=_T0 - timedelta(seconds=1))
    with pytest.raises(ValidityContractError, match="must precede expires_at"):
        Validity(issued_at=_T0, expires_at=_T0 + timedelta(hours=1),
                 stale_after=_T0 + timedelta(hours=1))
    # stale_after == issued_at is admissible: stale from the first instant.
    assert Validity(issued_at=_T0, stale_after=_T0).status_at(_T0) is ValidityStatus.STALE


def test_status_precedence_over_the_whole_window():
    v = _validity()
    assert v.status_at(_T0 - timedelta(microseconds=1)) is ValidityStatus.NOT_YET_VALID
    assert v.status_at(_T0) is ValidityStatus.FRESH
    assert v.status_at(_T0 + timedelta(minutes=30) - timedelta(microseconds=1)) is ValidityStatus.FRESH
    assert v.status_at(_T0 + timedelta(minutes=30)) is ValidityStatus.STALE
    assert v.status_at(_T0 + timedelta(hours=1) - timedelta(microseconds=1)) is ValidityStatus.STALE
    assert v.status_at(_T0 + timedelta(hours=1)) is ValidityStatus.EXPIRED
    assert v.status_at(_T0 + timedelta(days=365)) is ValidityStatus.EXPIRED


def test_predicates_agree_with_status():
    v = _validity()
    cases = {
        _T0 - timedelta(seconds=1): (False, False, False, False),
        _T0: (True, True, False, False),
        _T0 + timedelta(minutes=45): (True, False, True, False),
        _T0 + timedelta(hours=2): (False, False, False, True),
    }
    for as_of, (valid, fresh, stale, expired) in cases.items():
        assert v.is_valid_at(as_of) is valid, as_of
        assert v.is_fresh_at(as_of) is fresh, as_of
        assert v.is_stale_at(as_of) is stale, as_of
        assert v.is_expired_at(as_of) is expired, as_of


def test_open_bounds():
    no_expiry = Validity(issued_at=_T0)
    assert no_expiry.status_at(_T0 + timedelta(days=10_000)) is ValidityStatus.FRESH
    assert no_expiry.is_valid_at(_T0 + timedelta(days=10_000))
    never_stale = Validity(issued_at=_T0, expires_at=_T0 + timedelta(hours=1))
    assert never_stale.status_at(_T0 + timedelta(minutes=59)) is ValidityStatus.FRESH
    assert never_stale.status_at(_T0 + timedelta(hours=1)) is ValidityStatus.EXPIRED


def test_evaluation_instant_must_be_aware_never_defaulted():
    v = _validity()
    with pytest.raises(ValidityContractError, match="as_of must be timezone-aware"):
        v.status_at(datetime(2026, 9, 4, 10, 30))
    with pytest.raises(ValidityContractError, match="as_of must be timezone-aware"):
        v.is_valid_at(datetime(2026, 9, 4, 10, 30))


def test_offsets_evaluate_as_instants():
    v = _validity()
    # 15:30+05:30 and 06:00-04:00 are both 10:00Z — FRESH, not NOT_YET_VALID.
    assert v.status_at(datetime(2026, 9, 4, 15, 30, tzinfo=_IST)) is ValidityStatus.FRESH
    assert v.status_at(datetime(2026, 9, 4, 6, 0, tzinfo=_EDT)) is ValidityStatus.FRESH


def test_validity_canonical_form_is_pinned_and_utc_normalized():
    v = _validity()
    assert v.canonical_bytes() == _VAL_BYTES
    assert v.canonical_digest() == _VAL_DIGEST
    assert hashlib.sha256(v.canonical_bytes()).hexdigest() == v.canonical_digest()
    ist = Validity(issued_at=datetime(2026, 9, 4, 15, 30, tzinfo=_IST),
                   expires_at=datetime(2026, 9, 4, 16, 30, tzinfo=_IST),
                   stale_after=datetime(2026, 9, 4, 16, 0, tzinfo=_IST))
    edt = Validity(issued_at=datetime(2026, 9, 4, 6, 0, tzinfo=_EDT),
                   expires_at=datetime(2026, 9, 4, 7, 0, tzinfo=_EDT),
                   stale_after=datetime(2026, 9, 4, 6, 30, tzinfo=_EDT))
    assert v == ist == edt
    assert v.canonical_bytes() == ist.canonical_bytes() == edt.canonical_bytes()
    assert v.canonical_digest() == ist.canonical_digest() == edt.canonical_digest()
    assert _validity(issued_at=_T0 + timedelta(microseconds=1)).canonical_digest() != v.canonical_digest()
    assert Validity(issued_at=_T0).canonical_digest() != v.canonical_digest()


# --------------------------------------------------------------------------- #
# Compatibility — the frozen provider contracts did not move
# --------------------------------------------------------------------------- #
def test_provider_contracts_gained_no_field_and_kept_their_signatures():
    assert [f.name for f in dataclasses.fields(g.ActionGovernanceRequest)] == [
        "action_type", "requested_parameters", "actor", "authority_context",
        "target_resource", "policy_refs", "risk_context", "evidence_refs",
        "decision_refs", "idempotency_key", "correlation_id", "authorization_expired"]
    assert [f.name for f in dataclasses.fields(g.ActionGovernanceResult)] == [
        "outcome", "constraints", "obligations", "expiry", "authority_basis",
        "reason_codes", "provider_trace_id", "fingerprint"]
    assert [f.name for f in dataclasses.fields(g.ExecutionDispatchRequest)] == [
        "action_type", "parameters", "idempotency_key", "correlation_id"]
    assert [f.name for f in dataclasses.fields(g.ExecutionDispatchResult)] == [
        "accepted", "external_request_id", "acknowledgement", "pending",
        "timed_out", "transport_error", "retryable"]
    # Constructor signatures are exactly the ones the migration baseline froze.
    baseline = json.loads(
        (pathlib.Path(__file__).resolve().parents[1] / "serialization"
         / "frozen_contract_fixtures.json").read_text())["instances"]
    for name in ("ActionGovernanceRequest", "ActionGovernanceResult",
                 "ExecutionDispatchRequest", "ExecutionDispatchResult"):
        assert str(inspect.signature(getattr(g, name))) == baseline[name]["ctor_sig"], name


def test_contract_version_unchanged_package_version_advanced():
    # G4 (0.5.0) is additive in the same way G7 and G8 were in 0.4.0: the
    # PROVIDER contract surface is untouched, so CONTRACT_VERSION does not move.
    assert g.CONTRACT_VERSION == "1.0.0"
    assert g.__version__ == "0.8.0"


def test_neither_family_reads_a_clock():
    import ast
    import pathlib
    from ugence_governance_contracts.contracts import idempotency, validity
    for mod in (idempotency, validity):
        tree = ast.parse(pathlib.Path(mod.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                assert name not in ("now", "utcnow", "today", "time"), (mod.__name__, name)
                if name == "astimezone":
                    assert node.args, f"{mod.__name__}: zero-argument astimezone infers local tz"
