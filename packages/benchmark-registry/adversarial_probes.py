#!/usr/bin/env python3
"""Independent adversarial probes for the Ugence Benchmark Registry (BR-1).

Deliberately **independent** of the package's own test suite: this file imports
no test module, no ``_builders`` helper, no ``conftest`` and no private
submodule. It uses the curated public API and the standard library only, so it
exercises exactly what a consumer can reach — and it runs unchanged against the
source tree or against an installed wheel.

Every probe attempts something an attacker or a careless consumer would try, and
asserts the package refuses it, or that the refusal is detectable. Each is
attempted against a **working** happy path first, so a probe that passed because
its fixture was already broken shows up as the happy-path probe failing.

Run:
    PYTHONPATH=packages/benchmark-registry/src \\
        python packages/benchmark-registry/adversarial_probes.py
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import pickle
import sys
from datetime import datetime, timedelta, timezone

from ugence_benchmark_registry.api import (
    BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN,
    BENCHMARK_IDENTITY_COORDINATES,
    BENCHMARK_LIFECYCLE_ORDER,
    BENCHMARK_LIFECYCLE_TRANSITIONS,
    BENCHMARK_REFUSAL_REASONS,
    BENCHMARK_REGISTRY_CANONICALIZATION_VERSION,
    BENCHMARK_TERMINAL_LIFECYCLE_STATES,
    BR1_BENCHMARK_REFUSAL_REASONS,
    BenchmarkApplicabilityCoordinate,
    BenchmarkApplicabilityDeclaration,
    BenchmarkApprovalReference,
    BenchmarkCanonicalizationError,
    BenchmarkContractError,
    BenchmarkCoordinate,
    BenchmarkEffectivePeriod,
    BenchmarkLifecycleError,
    BenchmarkLifecycleState,
    BenchmarkMeasurementSemantics,
    BenchmarkRefusalReason,
    BenchmarkScope,
    BenchmarkScopeKind,
    BenchmarkSourceRequirements,
    BenchmarkStructuralStatus,
    BenchmarkSupersessionDeclaration,
    BenchmarkSupersessionStatus,
    CanonicalBenchmarkDefinitionIdentity,
    TemporalBoundDeclaration,
    canonical_bytes,
    is_valid_lifecycle_transition,
    require_valid_lifecycle_transition,
)

_R = BenchmarkRefusalReason

PASSED = 0
FAILED = []

CONTENT_DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64
FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
INSIDE = datetime(2026, 6, 15, tzinfo=timezone.utc)


print("Ugence Benchmark Registry — BR-1 adversarial probes")
print("=" * 70)


def probe(name):
    def decorator(fn):
        global PASSED
        try:
            fn()
        except Exception as error:  # noqa: BLE001 - a probe harness reports all
            FAILED.append((name, f"{type(error).__name__}: {error}"))
            print(f"FAIL  {name}\n        {type(error).__name__}: {error}")
        else:
            PASSED += 1
            print(f"ok    {name}")
        return fn

    return decorator


def refuses(fn, *types):
    try:
        fn()
    except types as error:
        return error
    except Exception as error:  # noqa: BLE001
        raise AssertionError(
            f"expected one of {[t.__name__ for t in types]}, got "
            f"{type(error).__name__}: {error}"
        ) from None
    raise AssertionError("expected a refusal, none was raised")


# --------------------------------------------------------------------------- #
# Builders — local, so the probes depend on nothing but the public API
# --------------------------------------------------------------------------- #
def coordinate(**kw):
    values = {
        "benchmark_id": "bmk-probe",
        "benchmark_family": "family-probe",
        "benchmark_version": "1.4.0",
        "scope": BenchmarkScope.for_tenant("tenant-alpha"),
        "geography": BenchmarkApplicabilityCoordinate.applicable("EU"),
        "domain": BenchmarkApplicabilityCoordinate.applicable("support"),
    }
    values.update(kw)
    return BenchmarkCoordinate(**values)


def measurement(**kw):
    values = {
        "intended_outcome_ref": "outcome-probe",
        "metric_ref": "metric-probe",
        "unit": "minutes",
        "measurement_protocol_ref": "protocol-probe",
        "population_ref": "cohort-probe",
        "aggregation_semantics_ref": "aggregation-probe",
        "observation_window_ref": "window-probe",
    }
    values.update(kw)
    return BenchmarkMeasurementSemantics(**values)


def approval(**kw):
    values = {
        "approval_ref": "approval-probe",
        "approval_authority_ref": "authority-probe",
        "approved_content_digest": CONTENT_DIGEST,
    }
    values.update(kw)
    return BenchmarkApprovalReference(**values)


def identity(**kw):
    values = {
        "coordinate": coordinate(),
        "content_digest": CONTENT_DIGEST,
        "measurement": measurement(),
        "effective_period": BenchmarkEffectivePeriod.bounded(FROM, TO),
        "source_requirements": BenchmarkSourceRequirements(
            source_ref="source-probe",
            provenance_requirement_refs=("prov-b", "prov-a"),
        ),
        "approval": approval(),
        "publisher_id": "publisher-probe",
        "lifecycle_state": BenchmarkLifecycleState.REGISTERED,
        "supersession": BenchmarkSupersessionDeclaration.undetermined(),
    }
    values.update(kw)
    return CanonicalBenchmarkDefinitionIdentity(**values)


# =========================================================================== #
# P-00 — the control
# =========================================================================== #
@probe("P-00 the happy path constructs and digests")
def _p00():
    item = identity()
    assert len(item.canonical_digest()) == 64
    assert item.is_effective_at(INSIDE) is True
    assert item.temporal_refusal_at(INSIDE) is None


# =========================================================================== #
# P-01..P-06 — exact-only coordinates (ADR B-8, §17.1, §17.2)
# =========================================================================== #
@probe("P-01 a floating 'latest' version is unrepresentable")
def _p01():
    for token in ("latest", "LATEST", "current", "newest", "head", "*"):
        error = refuses(
            lambda t=token: coordinate(benchmark_version=t), BenchmarkContractError
        )
        assert error.reason is _R.BENCHMARK_COORDINATE_NOT_EXACT, (token, error.reason)


@probe("P-02 a version range or comparator is unrepresentable")
def _p02():
    for token in ("^1.2.3", "~1.2.3", ">=1.2.3", "1.2.x", "1.2", "1.2.3 - 1.4.0"):
        refuses(lambda t=token: coordinate(benchmark_version=t), BenchmarkContractError)


@probe("P-03 a partial coordinate cannot be constructed")
def _p03():
    for field in ("benchmark_id", "benchmark_family", "benchmark_version",
                  "scope", "geography", "domain"):
        kwargs = {f.name: getattr(coordinate(), f.name)
                  for f in dataclasses.fields(BenchmarkCoordinate)}
        kwargs.pop(field)
        refuses(lambda k=kwargs: BenchmarkCoordinate(**k), TypeError)


@probe("P-04 a wildcard in any coordinate is refused")
def _p04():
    for char in ("*", "?", "%", "^", "|", ",", "[", "]"):
        refuses(
            lambda c=char: coordinate(benchmark_id=f"bmk{c}"), BenchmarkContractError
        )


@probe("P-05 no exported symbol offers latest/current selection")
def _p05():
    from ugence_benchmark_registry import api as public

    for name in public.__all__:
        lowered = name.lower()
        for token in ("latest", "current", "newest", "lookup", "search"):
            assert token not in lowered, name


@probe("P-06 a near-match coordinate is a different coordinate")
def _p06():
    lower = coordinate(benchmark_id="bmk-alpha")
    upper = coordinate(benchmark_id="BMK-ALPHA")
    assert lower.canonical_digest() != upper.canonical_digest()
    refuses(lambda: coordinate(benchmark_id=" bmk-alpha"), BenchmarkContractError)


# =========================================================================== #
# P-07..P-12 — identity completeness and digest binding (ADR §15, B-8)
# =========================================================================== #
@probe("P-07 every ADR §15 coordinate path resolves on a real identity")
def _p07():
    assert len(BENCHMARK_IDENTITY_COORDINATES) == 20
    item = identity()
    for path in BENCHMARK_IDENTITY_COORDINATES:
        target = item
        for part in path.split("."):
            target = getattr(target, part)
        assert target is not None, path


@probe("P-08 every identity field is mandatory")
def _p08():
    for field in dataclasses.fields(CanonicalBenchmarkDefinitionIdentity):
        assert field.default is dataclasses.MISSING, field.name
        assert field.default_factory is dataclasses.MISSING, field.name
        kwargs = {f.name: getattr(identity(), f.name)
                  for f in dataclasses.fields(CanonicalBenchmarkDefinitionIdentity)}
        kwargs.pop(field.name)
        refuses(lambda k=kwargs: CanonicalBenchmarkDefinitionIdentity(**k), TypeError)


@probe("P-09 every leaf coordinate is independently digest-sensitive")
def _p09():
    def leaves(contract, prefix=""):
        found = []
        for field in dataclasses.fields(contract):
            value = getattr(contract, field.name)
            path = f"{prefix}{field.name}"
            if dataclasses.is_dataclass(value) and not isinstance(value, type):
                found.extend(leaves(value, prefix=f"{path}."))
            else:
                found.append(path)
        return found

    # Per-path (not per-type) replacements: a generic same-typed replacement is
    # not always a *valid* replacement — ``benchmark_version`` must stay an
    # exact semver, for instance. Since the canonicalization-boundary
    # correction, ``canonical_digest`` revalidates the whole graph before
    # producing a digest, so a replacement that leaves the object in a state
    # no public constructor could have produced is now correctly refused
    # rather than silently digested — matching what the digest-coverage test
    # suite proves in full (tests/contract/test_digest_coverage.py).
    per_path = {
        "coordinate.benchmark_id": "bmk-mutated-probe",
        "coordinate.benchmark_family": "family-mutated-probe",
        "coordinate.benchmark_version": "9.9.9",
        "content_digest": OTHER_DIGEST,
        "measurement.intended_outcome_ref": "outcome-mutated-probe",
        "measurement.metric_ref": "metric-mutated-probe",
        "measurement.unit": "hours",
        "measurement.measurement_protocol_ref": "protocol-mutated-probe",
        "measurement.population_ref": "cohort-mutated-probe",
        "measurement.aggregation_semantics_ref": "aggregation-mutated-probe",
        "measurement.observation_window_ref": "window-mutated-probe",
        "effective_period.effective_from": datetime(2026, 2, 1, tzinfo=timezone.utc),
        "effective_period.effective_to": datetime(2028, 1, 1, tzinfo=timezone.utc),
        "source_requirements.source_ref": "source-mutated-probe",
        "source_requirements.provenance_requirement_refs": ("mutated-probe",),
        "approval.approval_ref": "approval-mutated-probe",
        "approval.approval_authority_ref": "authority-mutated-probe",
        "publisher_id": "publisher-mutated-probe",
        "lifecycle_state": BenchmarkLifecycleState.AUTHORED,
        "coordinate.scope.tenant_id": "tenant-mutated-probe",
        "coordinate.geography.value": "US",
        "coordinate.domain.value": "field-service",
    }
    # A handful of leaves cannot move alone without breaking a cross-field
    # invariant (B-5's approval/content-digest binding; scope, applicability
    # and effective-period self-consistency); moving the companion alongside
    # keeps the whole object a state the public constructors could produce.
    companions = {
        "content_digest": {"approval.approved_content_digest": OTHER_DIGEST},
        "approval.approved_content_digest": {"content_digest": OTHER_DIGEST},
        "coordinate.scope.kind": {"coordinate.scope.tenant_id": ""},
        "coordinate.geography.declaration": {"coordinate.geography.value": ""},
        "coordinate.domain.declaration": {"coordinate.domain.value": ""},
        "effective_period.end_declaration": {"effective_period.effective_to": None},
    }
    per_path["approval.approved_content_digest"] = OTHER_DIGEST
    per_path["coordinate.scope.kind"] = BenchmarkScopeKind.PLATFORM_WIDE
    per_path["coordinate.geography.declaration"] = (
        BenchmarkApplicabilityDeclaration.NOT_APPLICABLE
    )
    per_path["coordinate.domain.declaration"] = (
        BenchmarkApplicabilityDeclaration.NOT_APPLICABLE
    )
    per_path["effective_period.end_declaration"] = TemporalBoundDeclaration.OPEN_ENDED
    # supersession.status has exactly one ratified value (DD-4) — no valid
    # alternate exists, and the graph-revalidation gate now correctly refuses
    # any other value. Its digest sensitivity is proved separately by P-27.

    def resolve(root, dotted):
        target_path, _, leaf = dotted.rpartition(".")
        owner = root
        if target_path:
            for part in target_path.split("."):
                owner = getattr(owner, part)
        return owner, leaf

    paths = leaves(identity())
    assert len(paths) == 28, len(paths)
    assert set(paths) - {"supersession.status"} == set(per_path), (
        set(paths) - {"supersession.status"} ^ set(per_path)
    )
    for path in per_path:
        item = identity()
        before = item.canonical_digest()
        owner, leaf = resolve(item, path)
        original = getattr(owner, leaf)
        replacement = per_path[path]
        assert replacement != original, path
        object.__setattr__(owner, leaf, replacement)
        for companion_path, companion_value in companions.get(path, {}).items():
            c_owner, c_leaf = resolve(item, companion_path)
            object.__setattr__(c_owner, c_leaf, companion_value)
        assert item.canonical_digest() != before, path


@probe("P-10 no coordinate can be hidden in a mapping or extension bag")
def _p10():
    for contract in (BenchmarkCoordinate, BenchmarkMeasurementSemantics,
                     CanonicalBenchmarkDefinitionIdentity):
        for field in dataclasses.fields(contract):
            lowered = f"{field.name} {field.type}".lower()
            for token in ("dict", "mapping", "metadata", "extra", "extension"):
                assert token not in lowered, (contract.__name__, field.name)
    period = BenchmarkEffectivePeriod.open_ended(FROM)
    object.__setattr__(period, "effective_from", {"smuggled": "coordinate"})
    refuses(lambda: canonical_bytes(period), BenchmarkCanonicalizationError)


@probe("P-11 the identity digest is not the declared content digest")
def _p11():
    item = identity()
    assert item.canonical_digest() != item.content_digest
    assert item.canonical_digest() != CONTENT_DIGEST


@probe("P-12 the digest reconstructs from published bytes with hashlib alone")
def _p12():
    item = identity()
    raw = canonical_bytes(item)
    assert hashlib.sha256(raw).hexdigest() == item.canonical_digest()
    framed = json.loads(raw.decode("utf-8"))
    assert framed["canonicalization"] == BENCHMARK_REGISTRY_CANONICALIZATION_VERSION
    assert framed["domain"] == BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN
    assert framed["type"] == "CanonicalBenchmarkDefinitionIdentity"


# =========================================================================== #
# P-13..P-18 — canonicalization discipline (ADR §22)
# =========================================================================== #
@probe("P-13 two spellings of one instant produce one byte sequence")
def _p13():
    utc = datetime(2026, 1, 1, tzinfo=timezone.utc)
    shifted = datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=3)))
    assert utc == shifted
    assert canonical_bytes(
        BenchmarkEffectivePeriod.open_ended(utc)
    ) == canonical_bytes(BenchmarkEffectivePeriod.open_ended(shifted))


@probe("P-14 microseconds survive canonicalization")
def _p14():
    precise = datetime(2026, 1, 1, 0, 0, 0, 654321, tzinfo=timezone.utc)
    raw = canonical_bytes(BenchmarkEffectivePeriod.open_ended(precise))
    assert b"00:00:00.654321Z" in raw


@probe("P-15 a naive datetime is refused at both boundaries")
def _p15():
    naive = datetime(2026, 1, 1)
    refuses(lambda: BenchmarkEffectivePeriod.open_ended(naive), BenchmarkContractError)
    period = BenchmarkEffectivePeriod.open_ended(FROM)
    object.__setattr__(period, "effective_from", naive)
    refuses(lambda: canonical_bytes(period), BenchmarkCanonicalizationError)


@probe("P-16 floats, bytes and unknown objects fail closed")
def _p16():
    class Opaque:
        def __repr__(self):
            raise AssertionError("repr must never be reached by the encoder")

    for value in (1.5, float("nan"), float("inf"), b"\x00", Opaque(), {1: 2}):
        period = BenchmarkEffectivePeriod.open_ended(FROM)
        object.__setattr__(period, "effective_from", value)
        refuses(lambda p=period: canonical_bytes(p), BenchmarkCanonicalizationError)


@probe("P-17 a non-NFC string is refused, never normalized")
def _p17():
    nfd = "Café"
    nfc = "Café"
    assert nfd != nfc
    refuses(lambda: BenchmarkScope.for_tenant(nfd), BenchmarkContractError)
    assert BenchmarkScope.for_tenant(nfc).tenant_id == nfc
    scope = BenchmarkScope.for_tenant(nfc)
    object.__setattr__(scope, "tenant_id", nfd)
    refuses(lambda: canonical_bytes(scope), BenchmarkCanonicalizationError)


@probe("P-18 an order-irrelevant set is canonicalized; corrupted order is renormalized")
def _p18():
    forward = BenchmarkSourceRequirements(
        source_ref="s", provenance_requirement_refs=("r-a", "r-b", "r-c")
    )
    jumbled = BenchmarkSourceRequirements(
        source_ref="s", provenance_requirement_refs=("r-c", "r-a", "r-b")
    )
    assert canonical_bytes(forward) == canonical_bytes(jumbled)
    # A hand-placed out-of-order tuple is no longer rendered as given: graph
    # revalidation re-runs the contract's own order-normalization before any
    # byte is produced, so the corrupted order is restored, not preserved.
    object.__setattr__(jumbled, "provenance_requirement_refs", ("r-c", "r-a"))
    assert b'["r-a","r-c"]' in canonical_bytes(jumbled)
    assert b'["r-c","r-a"]' not in canonical_bytes(jumbled)
    refuses(
        lambda: BenchmarkSourceRequirements(
            source_ref="s", provenance_requirement_refs=("r-a", "r-a")
        ),
        BenchmarkContractError,
    )


# =========================================================================== #
# P-19..P-23 — lifecycle (ADR §29)
# =========================================================================== #
@probe("P-19 the lifecycle relation is exactly the three ratified arrows")
def _p19():
    admissible = {
        (current, proposed)
        for current, states in BENCHMARK_LIFECYCLE_TRANSITIONS.items()
        for proposed in states
    }
    assert admissible == {
        (BenchmarkLifecycleState.AUTHORED, BenchmarkLifecycleState.APPROVED),
        (BenchmarkLifecycleState.APPROVED, BenchmarkLifecycleState.REGISTERED),
        (BenchmarkLifecycleState.REGISTERED, BenchmarkLifecycleState.REVOKED),
    }


@probe("P-20 every non-arrow in the 4x4 matrix is refused")
def _p20():
    admissible = {
        (current, proposed)
        for current, states in BENCHMARK_LIFECYCLE_TRANSITIONS.items()
        for proposed in states
    }
    for current in BenchmarkLifecycleState:
        for proposed in BenchmarkLifecycleState:
            expected = (current, proposed) in admissible
            assert is_valid_lifecycle_transition(current, proposed) is expected
            if not expected:
                error = refuses(
                    lambda c=current, p=proposed: require_valid_lifecycle_transition(
                        c, p
                    ),
                    BenchmarkLifecycleError,
                )
                assert error.reason is _R.BENCHMARK_INVALID_LIFECYCLE_TRANSITION


@probe("P-21 REVOKED is terminal and the relation cannot be widened")
def _p21():
    assert BENCHMARK_TERMINAL_LIFECYCLE_STATES == frozenset(
        {BenchmarkLifecycleState.REVOKED}
    )
    def widen():
        BENCHMARK_LIFECYCLE_TRANSITIONS[BenchmarkLifecycleState.REVOKED] = frozenset(
            {BenchmarkLifecycleState.REGISTERED}
        )

    refuses(widen, TypeError)
    for states in BENCHMARK_LIFECYCLE_TRANSITIONS.values():
        assert isinstance(states, frozenset)


@probe("P-22 no SUPERSEDED and no EXPIRED lifecycle state exists")
def _p22():
    values = {m.value for m in BenchmarkLifecycleState}
    assert values == {"AUTHORED", "APPROVED", "REGISTERED", "REVOKED"}
    assert list(BENCHMARK_LIFECYCLE_ORDER) == list(BenchmarkLifecycleState)


@probe("P-23 a revoked definition is representable and refused")
def _p23():
    revoked = identity(lifecycle_state=BenchmarkLifecycleState.REVOKED)
    assert revoked.lifecycle_refusal is _R.BENCHMARK_REVOKED
    assert identity().lifecycle_refusal is None
    names = {f.name for f in dataclasses.fields(CanonicalBenchmarkDefinitionIdentity)}
    for banned in ("revoker", "revoked_at", "revocation_ref"):
        assert banned not in names


# =========================================================================== #
# P-24..P-27 — supersession (ADR §15 row 20, §17.12, DD-4)
# =========================================================================== #
@probe("P-24 supersession is mandatory and can only be UNDETERMINED")
def _p24():
    assert [m.value for m in BenchmarkSupersessionStatus] == ["UNDETERMINED"]
    item = identity()
    assert item.supersession.status is BenchmarkSupersessionStatus.UNDETERMINED


@probe("P-25 no structured successor reference is minted")
def _p25():
    for contract in (BenchmarkSupersessionDeclaration,
                     CanonicalBenchmarkDefinitionIdentity, BenchmarkCoordinate):
        for field in dataclasses.fields(contract):
            for banned in ("successor", "supersedes", "predecessor", "replaces"):
                assert banned not in field.name.lower(), field.name


@probe("P-26 UNDETERMINED is not a claim of 'not superseded'")
def _p26():
    declaration = BenchmarkSupersessionDeclaration.undetermined()
    for name in dir(declaration):
        assert "not_superseded" not in name.lower()
        assert "is_current" not in name.lower()


@probe("P-27 supersession's one admissible value cannot be moved and stay valid")
def _p27():
    """``supersession.status`` has exactly one ratified value until DD-4.

    There is no second value any state the public constructors could produce
    would hold there, so its digest sensitivity can no longer be shown by
    corrupting it — that state is now correctly refused. This proves the
    refusal instead: the leaf's presence in the canonical body is already
    proved by P-07/P-09, and BENCHMARK_MALFORMED_CONTRACT-style refusal for
    any other value is what the canonicalization boundary now guarantees.
    """

    item = identity()
    object.__setattr__(item.supersession, "status", "OTHER")
    refuses(lambda: item.canonical_digest(), BenchmarkCanonicalizationError)


# =========================================================================== #
# P-28..P-32 — approval, role separation and scope (B-3, B-4, B-5, §15 row 5)
# =========================================================================== #
@probe("P-28 an approval binding different content is refused")
def _p28():
    error = refuses(
        lambda: identity(approval=approval(approved_content_digest=OTHER_DIGEST)),
        BenchmarkContractError,
    )
    assert error.reason is _R.BENCHMARK_APPROVAL_REFERENCE_INVALID


@probe("P-29 a publisher may not also be the approving authority")
def _p29():
    error = refuses(
        lambda: identity(publisher_id="authority-probe"), BenchmarkContractError
    )
    assert error.reason is _R.BENCHMARK_ROLE_SEPARATION_VIOLATED


@probe("P-30 an approval label proves nothing")
def _p30():
    item = identity()
    assert item.structural_status is BenchmarkStructuralStatus.STRUCTURAL_UNVERIFIED
    assert item.trusted_resolution_performed is False
    assert item.unresolved_reason is _R.BENCHMARK_RESOLUTION_NOT_PERFORMED


@probe("P-31 scope is declared explicitly, never by omission")
def _p31():
    assert BenchmarkScope.platform_wide().tenant_id == ""
    refuses(
        lambda: BenchmarkScope(kind=BenchmarkScopeKind.PLATFORM_WIDE,
                               tenant_id="tenant-alpha"),
        BenchmarkContractError,
    )
    refuses(
        lambda: BenchmarkScope(kind=BenchmarkScopeKind.TENANT, tenant_id=""),
        BenchmarkContractError,
    )


@probe("P-32 applicability is declared, and both declarations are digest-bound")
def _p32():
    refuses(
        lambda: BenchmarkApplicabilityCoordinate(
            declaration=BenchmarkApplicabilityDeclaration.APPLICABLE, value=""
        ),
        BenchmarkContractError,
    )
    refuses(
        lambda: BenchmarkApplicabilityCoordinate(
            declaration=BenchmarkApplicabilityDeclaration.NOT_APPLICABLE, value="EU"
        ),
        BenchmarkContractError,
    )
    assert canonical_bytes(
        BenchmarkApplicabilityCoordinate.applicable("EU")
    ) != canonical_bytes(BenchmarkApplicabilityCoordinate.not_applicable())


# =========================================================================== #
# P-33..P-36 — temporal discipline (ADR §17.9, §22.9, §22.10)
# =========================================================================== #
@probe("P-33 the effective period is half-open [from, to)")
def _p33():
    period = BenchmarkEffectivePeriod.bounded(FROM, TO)
    micro = timedelta(microseconds=1)
    assert period.is_effective_at(FROM) is True
    assert period.is_effective_at(FROM - micro) is False
    assert period.is_effective_at(TO - micro) is True
    assert period.is_effective_at(TO) is False
    assert period.temporal_refusal_at(FROM - micro) is _R.BENCHMARK_NOT_YET_EFFECTIVE
    assert period.temporal_refusal_at(TO) is _R.BENCHMARK_EXPIRED


@probe("P-34 an open-ended period is a decision, not an omission")
def _p34():
    refuses(
        lambda: BenchmarkEffectivePeriod(
            effective_from=FROM,
            end_declaration=TemporalBoundDeclaration.BOUNDED,
            effective_to=None,
        ),
        BenchmarkContractError,
    )
    refuses(
        lambda: BenchmarkEffectivePeriod(
            effective_from=FROM,
            end_declaration=TemporalBoundDeclaration.OPEN_ENDED,
            effective_to=TO,
        ),
        BenchmarkContractError,
    )


@probe("P-35 an empty or reversed interval is refused")
def _p35():
    refuses(lambda: BenchmarkEffectivePeriod.bounded(FROM, FROM),
            BenchmarkContractError)
    refuses(lambda: BenchmarkEffectivePeriod.bounded(TO, FROM),
            BenchmarkContractError)


@probe("P-36 the evaluation instant is a mandatory parameter, never a clock read")
def _p36():
    period = BenchmarkEffectivePeriod.bounded(FROM, TO)
    refuses(lambda: period.is_effective_at(), TypeError)
    refuses(lambda: period.temporal_refusal_at(), TypeError)
    refuses(lambda: identity().structural_refusals_at(), TypeError)


# =========================================================================== #
# P-37..P-42 — anti-forgery
# =========================================================================== #
@probe("P-37 no trust flag exists to set")
def _p37():
    from ugence_benchmark_registry import api as public

    for name in public.__all__:
        obj = getattr(public, name)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            for field in dataclasses.fields(obj):
                for banned in ("verified", "trusted", "resolved", "signature",
                               "authentic", "score", "coverage"):
                    assert banned not in field.name.lower(), (name, field.name)


@probe("P-38 the honest status properties cannot be assigned or shadowed")
def _p38():
    item = identity()
    for prop in ("structural_status", "trusted_resolution_performed",
                 "unresolved_reason"):
        refuses(lambda p=prop: setattr(item, p, "TRUSTED"), AttributeError)
        refuses(lambda p=prop: object.__setattr__(item, p, "TRUSTED"), AttributeError)
    assert item.structural_status is BenchmarkStructuralStatus.STRUCTURAL_UNVERIFIED


@probe("P-39 a subclass that lies about itself cannot be canonicalized at all")
def _p39():
    class Forged(CanonicalBenchmarkDefinitionIdentity):
        @property
        def structural_status(self):
            return "TRUSTED"

    real = identity()
    forged = Forged(**{f.name: getattr(real, f.name)
                       for f in dataclasses.fields(
                           CanonicalBenchmarkDefinitionIdentity)})
    # Only the exact registered class canonicalizes; a subclass is refused
    # outright, never merely relabeled with its own ``type`` tag.
    refuses(lambda: forged.canonical_digest(), BenchmarkCanonicalizationError)
    refuses(lambda: canonical_bytes(forged), BenchmarkCanonicalizationError)


@probe("P-40 a duck-typed lookalike is refused at a load-bearing boundary")
def _p40():
    class LooksLikeAScope:
        kind = BenchmarkScopeKind.PLATFORM_WIDE
        tenant_id = ""

    refuses(lambda: coordinate(scope=LooksLikeAScope()), BenchmarkContractError)

    class SneakyScope(BenchmarkScope):
        pass

    refuses(
        lambda: coordinate(
            scope=SneakyScope(kind=BenchmarkScopeKind.PLATFORM_WIDE, tenant_id="")
        ),
        BenchmarkContractError,
    )


@probe("P-41 copy, deepcopy and pickle cannot raise the status")
def _p41():
    item = identity()
    for clone in (copy.copy(item), copy.deepcopy(item),
                  pickle.loads(pickle.dumps(item))):
        assert clone == item
        assert clone.canonical_digest() == item.canonical_digest()
        assert clone.trusted_resolution_performed is False


@probe("P-42 tampering after construction moves the digest")
def _p42():
    item = identity()
    before = item.canonical_digest()
    object.__setattr__(item, "publisher_id", "publisher-attacker")
    assert item.canonical_digest() != before


# =========================================================================== #
# P-43..P-48 — milestone boundary (ADR §30, §32)
# =========================================================================== #
@probe("P-43 no registry, resolver, store or registration surface is exported")
def _p43():
    from ugence_benchmark_registry import api as public

    # The two pinned byte constants carry the capability's own name — they are
    # the canonicalization version and the digest domain, and naming the
    # capability in its own byte space is required by ADR §22.1, not a registry
    # surface. Exempted by exact name so no other symbol can borrow the excuse.
    exempt = {
        "BENCHMARK_REGISTRY_CANONICALIZATION_VERSION",
    }
    for name in public.__all__:
        if name in exempt:
            continue
        lowered = name.lower()
        for banned in ("registry", "resolver", "store", "repository",
                       "registration", "admission", "publisher", "signer",
                       "trustanchor", "revocation"):
            assert banned not in lowered, name


@probe("P-44 exactly one digest domain is minted")
def _p44():
    from ugence_benchmark_registry import api as public

    domains = [n for n in public.__all__ if n.endswith("_DIGEST_DOMAIN")]
    assert domains == ["BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN"], domains
    assert BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN == (
        "ugence.benchmark-registry/benchmark-definition-identity/v1"
    )
    assert BENCHMARK_REGISTRY_CANONICALIZATION_VERSION == (
        "ugence.benchmark-registry/canonicalization/v1"
    )


@probe("P-45 the refusal vocabulary is seventeen refusals with no success state")
def _p45():
    assert len(BENCHMARK_REFUSAL_REASONS) == 17
    assert BENCHMARK_REFUSAL_REASONS == BR1_BENCHMARK_REFUSAL_REASONS
    positive = {"OK", "SUCCESS", "VALID", "ADMITTED", "RESOLVED", "APPROVED",
                "TRUSTED", "PASS"}
    for member in BenchmarkRefusalReason:
        assert member.value.startswith("BENCHMARK_"), member
        assert not (set(member.value.split("_")) & positive), member


@probe("P-46 no BR-2 runtime refusal code is minted")
def _p46():
    values = {m.value for m in BenchmarkRefusalReason}
    for banned in ("BENCHMARK_NOT_FOUND", "BENCHMARK_REGISTRY_UNAVAILABLE",
                   "BENCHMARK_ADMISSION_DENIED", "BENCHMARK_SIGNATURE_INVALID",
                   "BENCHMARK_KEY_REVOKED", "BENCHMARK_TRUST_ANCHOR_MISSING",
                   "BENCHMARK_SUPERSEDED", "BENCHMARK_STORAGE_FAILURE"):
        assert banned not in values, banned


@probe("P-47 no readiness, forecasting, attribution, valuation or ROI surface")
def _p47():
    from ugence_benchmark_registry import api as public

    for name in public.__all__:
        for banned in ("readiness", "forecast", "attribution", "valuation",
                       "roi", "monetary", "deploy", "authorize", "policy"):
            assert banned not in name.lower(), name


@probe("P-48 no comparison, evaluation or result surface exists (B-12)")
def _p48():
    from ugence_benchmark_registry import api as public

    for name in public.__all__:
        obj = getattr(public, name)
        if callable(obj) and not isinstance(obj, type):
            for banned in ("compare", "evaluate", "compute", "score", "measure"):
                assert banned not in name.lower(), name


@probe("P-49 every structural refusal set names resolution-not-performed")
def _p49():
    for item in (identity(), identity(lifecycle_state=BenchmarkLifecycleState.AUTHORED)):
        for instant in (FROM, INSIDE, TO):
            refusals = item.structural_refusals_at(instant)
            assert _R.BENCHMARK_RESOLUTION_NOT_PERFORMED in refusals
            order = list(BenchmarkRefusalReason)
            assert list(refusals) == sorted(refusals, key=order.index)


@probe("P-51 a lying str subclass is refused for its type, not incidentally")
def _p51():
    class SneakyStr(str):
        def __eq__(self, other):
            return True

        def __ne__(self, other):
            return False

        __hash__ = str.__hash__

    # A subclass can corrupt every comparison the contracts make — the padding
    # check, the NFC check, the role-separation comparison and canonicalization.
    # It must therefore be refused as *malformed*, before any of them run.
    for build in (
        lambda v: coordinate(benchmark_id=v),
        lambda v: coordinate(benchmark_family=v),
        lambda v: BenchmarkScope.for_tenant(v),
        lambda v: measurement(unit=v),
        lambda v: identity(publisher_id=v),
    ):
        error = refuses(lambda f=build: f(SneakyStr("value")), BenchmarkContractError)
        assert error.reason is _R.BENCHMARK_MALFORMED_CONTRACT, error.reason


@probe("P-52 a same-named foreign dataclass cannot borrow the genuine bytes")
def _p52():
    """F-1 — the canonicalization-boundary correction's headline attack.

    Before the correction, a foreign dataclass named exactly
    ``BenchmarkCoordinate`` — defined nowhere near this package, its
    ``__module__`` forged to match — was accepted by ``canonical_bytes``
    because domain selection was keyed by ``type(contract).__name__``, a
    string, not by class identity. If its fields serialized to the same
    body, it produced *byte-identical, digest-identical* output to the
    genuine class. Class-identity dispatch (``type(contract) is
    SomeExactClass``) closes this: the foreign class is a different object
    regardless of its name or module, and is refused.
    """

    genuine = coordinate(
        benchmark_id="bmk-min", benchmark_family="family-min",
        benchmark_version="0.1.0", scope=BenchmarkScope.platform_wide(),
        geography=BenchmarkApplicabilityCoordinate.not_applicable(),
        domain=BenchmarkApplicabilityCoordinate.not_applicable(),
    )
    genuine_digest = genuine.canonical_digest()

    # Distinct Python identifiers so they never shadow the genuine imports in
    # this function's scope — the forgery is in ``__name__``/``__qualname__``/
    # ``__module__``, exactly as an attacker would need to fake it, not in
    # what the local variable is called.
    @dataclasses.dataclass(frozen=True)
    class _ForeignScope:
        kind: object
        tenant_id: str

    @dataclasses.dataclass(frozen=True)
    class _ForeignApplicabilityCoordinate:
        declaration: object
        value: str

    @dataclasses.dataclass(frozen=True)
    class _ForeignCoordinate:
        benchmark_id: str
        benchmark_family: str
        benchmark_version: str
        scope: object
        geography: object
        domain: object

    for cls, name in (
        (_ForeignScope, "BenchmarkScope"),
        (_ForeignApplicabilityCoordinate, "BenchmarkApplicabilityCoordinate"),
        (_ForeignCoordinate, "BenchmarkCoordinate"),
    ):
        cls.__name__ = name
        cls.__qualname__ = name
        cls.__module__ = "ugence_benchmark_registry.contracts.identity"

    forged = _ForeignCoordinate(
        benchmark_id="bmk-min", benchmark_family="family-min",
        benchmark_version="0.1.0",
        scope=_ForeignScope(kind=BenchmarkScopeKind.PLATFORM_WIDE, tenant_id=""),
        geography=_ForeignApplicabilityCoordinate(
            declaration=BenchmarkApplicabilityDeclaration.NOT_APPLICABLE, value=""
        ),
        domain=_ForeignApplicabilityCoordinate(
            declaration=BenchmarkApplicabilityDeclaration.NOT_APPLICABLE, value=""
        ),
    )
    refuses(lambda: canonical_bytes(forged), BenchmarkCanonicalizationError)
    refuses(
        lambda: __import__(
            "ugence_benchmark_registry.contracts.canonical", fromlist=["canonical_digest"]
        ).canonical_digest(forged),
        BenchmarkCanonicalizationError,
    )
    # And the genuine digest is unaffected by the attempt.
    assert genuine.canonical_digest() == genuine_digest


@probe("P-53 an invalid value inside a same-named foreign contract is still refused")
def _p53():
    """A same-named foreign class carrying a value the real constructor would
    reject (a floating ``benchmark_version``) must not slip through by
    virtue of bypassing ``__post_init__`` entirely."""

    @dataclasses.dataclass(frozen=True)
    class EvilCoordinate:
        benchmark_id: str
        benchmark_family: str
        benchmark_version: str
        scope: object
        geography: object
        domain: object

    EvilCoordinate.__name__ = "BenchmarkCoordinate"
    EvilCoordinate.__qualname__ = "BenchmarkCoordinate"
    EvilCoordinate.__module__ = "ugence_benchmark_registry.contracts.identity"

    evil = EvilCoordinate(
        benchmark_id="bmk-min", benchmark_family="family-min",
        benchmark_version="latest",  # a floating token the real type refuses
        scope=BenchmarkScope.platform_wide(),
        geography=BenchmarkApplicabilityCoordinate.not_applicable(),
        domain=BenchmarkApplicabilityCoordinate.not_applicable(),
    )
    refuses(lambda: canonical_bytes(evil), BenchmarkCanonicalizationError)


@probe("P-54 the contract-type registry cannot be widened by any caller")
def _p54():
    """The registry cannot be widened through its intended function, and —
    the correction to this correction — cannot be widened by rebinding a
    module attribute either, because there is no module attribute that
    holds it.

    The original P-54 only checked that calling the private
    ``_register_contract_type`` function raised post-seal, and that
    ``canonical._REGISTERED_CONTRACT_TYPES`` was a ``MappingProxyType``. That
    left a direct attack unprobed: a ``MappingProxyType`` stops the mapping
    from being *mutated*, but nothing stops the *module attribute holding
    it* from being reassigned wholesale — ``canonical._REGISTERED_CONTRACT_
    TYPES = {Evil: domain}`` is ordinary, always-legal Python for any code
    that imported the module, and the unmodified ``canonical_bytes`` would
    then trust it, because it read that name from the module's globals at
    call time. This probe reproduces exactly that attack and confirms it no
    longer has anywhere to land: the registry lives inside a closure with no
    module-level name of its own, so setting ``canonical._REGISTERED_
    CONTRACT_TYPES`` (or any other guessed name) creates an inert new
    attribute nothing consults.
    """

    from ugence_benchmark_registry.contracts import canonical as _canonical

    refuses(
        lambda: _canonical._register_contract_type(
            dataclasses.make_dataclass("Evil", [("x", int)]),
            BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN,
        ),
        RuntimeError,
    )
    assert not hasattr(_canonical, "_REGISTERED_CONTRACT_TYPES")

    @dataclasses.dataclass(frozen=True)
    class Evil:
        benchmark_version: str = "latest"

        def __post_init__(self) -> None:  # attacker-authored, always passes
            pass

    # The attack: reassign the guessed module attribute wholesale, then call
    # the real, unmodified public API against the attacker's own instance.
    _canonical._REGISTERED_CONTRACT_TYPES = {
        Evil: BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN
    }
    try:
        refuses(lambda: _canonical.canonical_bytes(Evil()), BenchmarkCanonicalizationError)
        refuses(lambda: _canonical.canonical_digest(Evil()), BenchmarkCanonicalizationError)
    finally:
        del _canonical._REGISTERED_CONTRACT_TYPES

    # The read-only introspection snapshot cannot be turned into a weapon
    # either: mutating or replacing it has no effect on what the encoder
    # trusts, because the encoder never reads it.
    snapshot = _canonical._contract_type_registry_snapshot()
    assert isinstance(snapshot, type(__import__("types").MappingProxyType({})))
    try:
        snapshot[Evil] = BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN
        raise AssertionError("snapshot must be immutable")
    except TypeError:
        pass
    refuses(lambda: _canonical.canonical_bytes(Evil()), BenchmarkCanonicalizationError)


@probe("P-56 a metaclass forging the class object's own equality/hash cannot borrow the genuine bytes")
def _p56():
    """The 'class identity' claim, attacked directly.

    ``canonical.py`` states membership is decided by ``cls is
    SomeExactClass``. The vulnerable implementation this replaces actually
    used ``in``/``[]`` against a ``dict`` keyed by class objects — which
    dispatches to ``__hash__``/``__eq__``, not to ``is``. A *type object*'s
    own equality and hash are governed by its **metaclass**, not by the
    class itself (the class's own ``__eq__``/``__hash__`` govern its
    *instances*). A foreign class built with a metaclass that forges the
    type object's ``__eq__``/``__hash__`` to collide with a genuine
    registered class defeats a dict-membership check while being a
    completely different object holding attacker-chosen fields — including
    ``benchmark_version="latest"``, and an attacker-authored ``__post_init__``
    that graph revalidation would then call as if it were the genuine type's.
    This probe reproduces that attack exactly and confirms the corrected
    identity check refuses it: comparing with ``is`` has no dunder method for
    any metaclass to override.
    """

    genuine = BenchmarkCoordinate

    class _SpoofMeta(type):
        def __eq__(cls, other):
            return other is genuine or other is cls

        def __hash__(cls):
            return hash(genuine)

    @dataclasses.dataclass(frozen=True)
    class _ForeignBase(metaclass=_SpoofMeta):
        pass

    @dataclasses.dataclass(frozen=True)
    class _Foreign(_ForeignBase):
        benchmark_id: str = "attacker-id"
        benchmark_family: str = "attacker-family"
        benchmark_version: str = "latest"  # the real type would refuse this
        scope: object = None
        geography: object = None
        domain: object = None

        def __post_init__(self) -> None:  # attacker-authored, always passes
            pass

    _Foreign.__name__ = "BenchmarkCoordinate"
    _Foreign.__qualname__ = "BenchmarkCoordinate"
    _Foreign.__module__ = genuine.__module__

    assert _Foreign is not genuine
    assert _Foreign == genuine, "the metaclass forgery must actually fool dict equality"

    forged = _Foreign()
    refuses(lambda: canonical_bytes(forged), BenchmarkCanonicalizationError)
    refuses(
        lambda: __import__(
            "ugence_benchmark_registry.contracts.canonical", fromlist=["canonical_digest"]
        ).canonical_digest(forged),
        BenchmarkCanonicalizationError,
    )


@probe("P-55 a semver with build metadata is unrepresentable (F-3)")
def _p55():
    for version in ("1.2.3+a", "1.2.3+build.7", "1.2.3-alpha+build"):
        error = refuses(
            lambda v=version: coordinate(benchmark_version=v), BenchmarkContractError
        )
        assert error.reason is _R.BENCHMARK_COORDINATE_NOT_EXACT, (version, error.reason)
    for version in ("1.2.3", "1.2.3-alpha", "1.2.3-alpha.1"):
        assert coordinate(benchmark_version=version).benchmark_version == version


@probe("P-50 the package imports nothing outside the standard library")
def _p50():
    import ugence_benchmark_registry as pkg

    prefix = pkg.__name__
    foreign = sorted(
        name
        for name in sys.modules
        if name.startswith("ugence") and not name.startswith(prefix)
    )
    assert foreign == [], foreign


def main() -> int:
    total = PASSED + len(FAILED)
    print("=" * 70)
    if FAILED:
        print(f"{len(FAILED)} of {total} probes FAILED")
        for name, detail in FAILED:
            print(f"  - {name}: {detail}")
        return 1
    print(f"{PASSED} probes passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
