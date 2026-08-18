#!/usr/bin/env python3
"""Reproducible proof that the Benchmark Registry contracts install and operate
from a built wheel, with **no** dependency at all and no monorepo source on the
path.

Builds ``ugence-benchmark-registry`` into a temporary local directory and
installs it into a fresh virtualenv with **no system site packages, no
``PYTHONPATH``, no monorepo path and no index** (``--no-index``,
``PIP_NO_INDEX=1``). BR-1 declares **zero** runtime dependencies, so no
wheelhouse preparation is needed and none is done: the install has nothing to
resolve but the package itself, and it fails if anything else appears.

Proved inside that env:

  * ``ugence_benchmark_registry`` imports from site-packages;
  * ``PYTHONPATH`` is unset and no monorepo path is on ``sys.path``, so nothing
    below could be satisfied by source rather than by the installed wheel;
  * the installed distribution list contains the package and nothing else;
  * the declared runtime metadata names **no** dependency;
  * the curated public API resolves and ships ``py.typed``;
  * the installed surface equals the committed ``public_api.json`` exactly —
    every symbol, kind, enum member **and order**, dataclass field **and
    order**, and pinned constant value;
  * the pinned canonical bytes and digests reproduce **byte-for-byte**, and the
    verifier reconstructs them from its own hand-written literals with
    ``hashlib`` alone rather than trusting any package fixture;
  * all twenty ADR §15 coordinates are present and each is independently
    digest-sensitive from the installed wheel;
  * the structural invariants fire (floating/wildcard/range coordinate, blank
    and padded identifier, malformed digest, naive datetime, reversed and empty
    interval, duplicate provenance requirement, applicability XOR, scope XOR,
    approval-digest binding, publisher/approver role separation, closed
    lifecycle relation);
  * no caller can reach a resolved or trusted state (frozen assignment,
    property override, subclass, duck-typed lookalike, cross-tenant replay);
  * there is no registry, resolver, store, registration, signing, revocation or
    successor surface — BR-2 is not started;
  * the independent ``adversarial_probes.py`` harness passes against the
    installed wheel, importing only the curated API;
  * **no** Ugence package, capability, product, console, platform tool or
    third-party package is importable.

Run:  python packages/benchmark-registry/verify_benchmark_registry_distribution.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parents[1]  # packages/benchmark-registry -> packages -> repo root
NAMESPACE = "ugence_benchmark_registry"
DISTRIBUTION = "ugence-benchmark-registry"

_CHECK = r'''
import dataclasses, enum, hashlib, json, pathlib, sys
from datetime import datetime, timedelta, timezone

import importlib.metadata as _md
import os as _os

# ---------------------------------------------------------------------- #
# Isolation, proved before anything is imported from the package
# ---------------------------------------------------------------------- #
assert not _os.environ.get("PYTHONPATH", ""), (
    "PYTHONPATH is set inside the isolated env: " + repr(_os.environ.get("PYTHONPATH"))
)
assert not any("/symbolu" in p for p in sys.path), sys.path
assert not any(p in ("", ".") for p in sys.path[1:]), sys.path

import ugence_benchmark_registry as u
assert u.__version__ == "0.1.0", u.__version__
assert "site-packages" in u.__file__, u.__file__
assert (pathlib.Path(u.__file__).resolve().parent / "py.typed").is_file(), (
    "py.typed not installed"
)
assert not hasattr(u, "CONTRACT_VERSION"), "no CONTRACT_VERSION is minted"

# ---------------------------------------------------------------------- #
# Zero declared runtime dependencies
# ---------------------------------------------------------------------- #
requires = _md.requires("ugence-benchmark-registry") or []
runtime = [r for r in requires if "extra ==" not in r]
assert runtime == [], "the distribution declares a runtime dependency: %r" % runtime

# ---------------------------------------------------------------------- #
# No foreign package is importable
# ---------------------------------------------------------------------- #
import importlib.util as _iu
for foreign in (
    "ugence_governance_contracts", "ugence_uvi_policy_contracts",
    "ugence_policy_authority", "risk_authority", "ugence_risk_authority",
    "ugence_agent_value_readiness", "governed_value", "ugence_tap_provider",
    "ugence_actiongate_provider", "ugence_governance_provider_framework",
    "agent_runtime", "cloud_scaling_operations", "platform_freeze",
    "truth_assurance_pipeline", "pydantic", "numpy", "cryptography", "nacl",
):
    assert _iu.find_spec(foreign) is None, "unexpectedly importable: " + foreign

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
    canonical_digest,
    is_valid_lifecycle_transition,
    require_valid_lifecycle_transition,
)

_R = BenchmarkRefusalReason
CONTENT = "a" * 64
OTHER = "b" * 64
FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
TO = datetime(2027, 1, 1, tzinfo=timezone.utc)


def refuses(fn, *types):
    try:
        fn()
    except types as error:
        return error
    except Exception as error:
        raise AssertionError(
            "expected %r, got %s: %s" % ([t.__name__ for t in types],
                                         type(error).__name__, error)
        ) from None
    raise AssertionError("expected a refusal, none was raised")


# ---------------------------------------------------------------------- #
# Builders — local to this proof
# ---------------------------------------------------------------------- #
def coordinate(**kw):
    values = dict(
        benchmark_id="bmk-support-resolution-time",
        benchmark_family="operational-efficiency",
        benchmark_version="1.4.0",
        scope=BenchmarkScope.for_tenant("tenant-alpha"),
        geography=BenchmarkApplicabilityCoordinate.applicable("EU"),
        domain=BenchmarkApplicabilityCoordinate.applicable("customer-support"),
    )
    values.update(kw)
    return BenchmarkCoordinate(**values)


def measurement(**kw):
    values = dict(
        intended_outcome_ref="outcome-faster-resolution",
        metric_ref="metric-median-resolution-minutes",
        unit="minutes",
        measurement_protocol_ref="protocol-ticket-timestamp-v2",
        population_ref="cohort-tier1-inbound",
        aggregation_semantics_ref="aggregation-median-per-week",
        observation_window_ref="window-trailing-90d",
    )
    values.update(kw)
    return BenchmarkMeasurementSemantics(**values)


def approval(**kw):
    values = dict(
        approval_ref="approval-bmk-2026-0142",
        approval_authority_ref="authority-benchmark-governance-board",
        approved_content_digest=CONTENT,
    )
    values.update(kw)
    return BenchmarkApprovalReference(**values)


def identity(**kw):
    values = dict(
        coordinate=coordinate(),
        content_digest=CONTENT,
        measurement=measurement(),
        effective_period=BenchmarkEffectivePeriod.bounded(FROM, TO),
        source_requirements=BenchmarkSourceRequirements(
            source_ref="source-industry-panel-2026",
            provenance_requirement_refs=(
                "provenance-independent-audit",
                "provenance-attributable-producer",
            ),
        ),
        approval=approval(),
        publisher_id="publisher-benchmark-authoring-office",
        lifecycle_state=BenchmarkLifecycleState.REGISTERED,
        supersession=BenchmarkSupersessionDeclaration.undetermined(),
    )
    values.update(kw)
    return CanonicalBenchmarkDefinitionIdentity(**values)


def minimal_identity():
    return CanonicalBenchmarkDefinitionIdentity(
        coordinate=BenchmarkCoordinate(
            benchmark_id="bmk-min",
            benchmark_family="family-min",
            benchmark_version="0.1.0",
            scope=BenchmarkScope.platform_wide(),
            geography=BenchmarkApplicabilityCoordinate.not_applicable(),
            domain=BenchmarkApplicabilityCoordinate.not_applicable(),
        ),
        content_digest=CONTENT,
        measurement=BenchmarkMeasurementSemantics(
            intended_outcome_ref="o", metric_ref="m", unit="u",
            measurement_protocol_ref="p", population_ref="c",
            aggregation_semantics_ref="a", observation_window_ref="w",
        ),
        effective_period=BenchmarkEffectivePeriod.open_ended(FROM),
        source_requirements=BenchmarkSourceRequirements(
            source_ref="s", provenance_requirement_refs=("r",)
        ),
        approval=BenchmarkApprovalReference(
            approval_ref="ap", approval_authority_ref="auth",
            approved_content_digest=CONTENT,
        ),
        publisher_id="pub",
        lifecycle_state=BenchmarkLifecycleState.AUTHORED,
        supersession=BenchmarkSupersessionDeclaration.undetermined(),
    )


# ---------------------------------------------------------------------- #
# Pinned canonical bytes — written out here, hashed here
# ---------------------------------------------------------------------- #
# The verifier does not read a digest back from the package and compare it to
# itself. It writes the byte sequence it expects, hashes it with hashlib, and
# only then asks the installed wheel to produce the same bytes.
MINIMAL_BYTES = (
    b'{"body":{"approval":{"approval_authority_ref":"auth","approval_ref":"ap",'
    b'"approved_content_digest":"' + b"a" * 64 + b'"},"content_digest":"'
    + b"a" * 64 +
    b'","coordinate":{"benchmark_family":"family-min","benchmark_id":"bmk-min",'
    b'"benchmark_version":"0.1.0","domain":{"declaration":"NOT_APPLICABLE",'
    b'"value":""},"geography":{"declaration":"NOT_APPLICABLE","value":""},'
    b'"scope":{"kind":"PLATFORM_WIDE","tenant_id":""}},"effective_period":'
    b'{"effective_from":"2026-01-01T00:00:00.000000Z","effective_to":null,'
    b'"end_declaration":"OPEN_ENDED"},"lifecycle_state":"AUTHORED","measurement":'
    b'{"aggregation_semantics_ref":"a","intended_outcome_ref":"o","measurement_'
    b'protocol_ref":"p","metric_ref":"m","observation_window_ref":"w",'
    b'"population_ref":"c","unit":"u"},"publisher_id":"pub","source_requirements":'
    b'{"provenance_requirement_refs":["r"],"source_ref":"s"},"supersession":'
    b'{"status":"UNDETERMINED"}},"canonicalization":'
    b'"ugence.benchmark-registry/canonicalization/v1","domain":'
    b'"ugence.benchmark-registry/benchmark-definition-identity/v1","type":'
    b'"CanonicalBenchmarkDefinitionIdentity"}'
)
MINIMAL_DIGEST = "9162ba434cff5b64678bf58f2dd8d9019ea8fafecc30817bf5953a62e7264a69"
FULL_DIGEST = "f27044eafb0519399d71cac460d8820d5c0748aa8de9083346b394f434d93fd9"
COORDINATE_DIGEST = (
    "4c4395db71a09426bb52097f6029b808388ccba22df66ca79f77726b388d26ce"
)

assert hashlib.sha256(MINIMAL_BYTES).hexdigest() == MINIMAL_DIGEST, (
    "the verifier's own literal bytes do not hash to its own pinned digest"
)
assert canonical_bytes(minimal_identity()) == MINIMAL_BYTES, (
    "the installed wheel produced different canonical bytes"
)
assert minimal_identity().canonical_digest() == MINIMAL_DIGEST
assert identity().canonical_digest() == FULL_DIGEST
assert hashlib.sha256(canonical_bytes(identity())).hexdigest() == FULL_DIGEST
assert coordinate().canonical_digest() == COORDINATE_DIGEST
assert identity().canonical_digest() != identity().content_digest

# Framing, version and the single domain.
framed = json.loads(canonical_bytes(identity()).decode("utf-8"))
assert set(framed) == {"body", "canonicalization", "domain", "type"}
assert framed["canonicalization"] == "ugence.benchmark-registry/canonicalization/v1"
assert framed["domain"] == (
    "ugence.benchmark-registry/benchmark-definition-identity/v1"
)
assert framed["type"] == "CanonicalBenchmarkDefinitionIdentity"

# ---------------------------------------------------------------------- #
# Coordinate coverage: all twenty, each independently digest-sensitive
# ---------------------------------------------------------------------- #
assert len(BENCHMARK_IDENTITY_COORDINATES) == 20
for path in BENCHMARK_IDENTITY_COORDINATES:
    target = identity()
    for part in path.split("."):
        target = getattr(target, part)
    assert target is not None, path


def leaves(contract, prefix=""):
    found = []
    for field in dataclasses.fields(contract):
        value = getattr(contract, field.name)
        name = prefix + field.name
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            found.extend(leaves(value, prefix=name + "."))
        else:
            found.append(name)
    return found


# Per-path (not per-type) replacements: a generic same-typed replacement is
# not always *valid* — ``benchmark_version`` must stay an exact semver, for
# instance. ``canonical_digest`` now revalidates the whole graph before
# producing a digest, so a replacement that leaves the object in a state no
# public constructor could have produced is refused rather than silently
# digested — matching packages/benchmark-registry/tests/contract/
# test_digest_coverage.py.
PER_PATH_MUTATIONS = {
    "coordinate.benchmark_id": "bmk-mutated-by-the-verifier",
    "coordinate.benchmark_family": "family-mutated-by-the-verifier",
    "coordinate.benchmark_version": "9.9.9",
    "content_digest": OTHER,
    "measurement.intended_outcome_ref": "outcome-mutated-by-the-verifier",
    "measurement.metric_ref": "metric-mutated-by-the-verifier",
    "measurement.unit": "hours",
    "measurement.measurement_protocol_ref": "protocol-mutated-by-the-verifier",
    "measurement.population_ref": "cohort-mutated-by-the-verifier",
    "measurement.aggregation_semantics_ref": "aggregation-mutated-by-the-verifier",
    "measurement.observation_window_ref": "window-mutated-by-the-verifier",
    "effective_period.effective_from": datetime(2026, 2, 1, tzinfo=timezone.utc),
    "effective_period.effective_to": datetime(2028, 1, 1, tzinfo=timezone.utc),
    "source_requirements.source_ref": "source-mutated-by-the-verifier",
    "source_requirements.provenance_requirement_refs": ("mutated-by-the-verifier",),
    "approval.approval_ref": "approval-mutated-by-the-verifier",
    "approval.approval_authority_ref": "authority-mutated-by-the-verifier",
    "approval.approved_content_digest": OTHER,
    "publisher_id": "publisher-mutated-by-the-verifier",
    "lifecycle_state": BenchmarkLifecycleState.AUTHORED,
    "coordinate.scope.tenant_id": "tenant-mutated-by-the-verifier",
    "coordinate.scope.kind": BenchmarkScopeKind.PLATFORM_WIDE,
    "coordinate.geography.value": "US",
    "coordinate.geography.declaration": BenchmarkApplicabilityDeclaration.NOT_APPLICABLE,
    "coordinate.domain.value": "field-service",
    "coordinate.domain.declaration": BenchmarkApplicabilityDeclaration.NOT_APPLICABLE,
    "effective_period.end_declaration": TemporalBoundDeclaration.OPEN_ENDED,
    # supersession.status has exactly one ratified value (DD-4); no valid
    # alternate exists, so its digest sensitivity is proved separately below.
}
# A handful of leaves cannot move alone without leaving a cross-field
# invariant violated (B-5's approval/content-digest binding; scope,
# applicability and effective-period self-consistency). The companion is
# moved alongside so the whole object stays one the public constructors
# could have produced.
COMPANION_FIXUPS = {
    "content_digest": {"approval.approved_content_digest": OTHER},
    "approval.approved_content_digest": {"content_digest": OTHER},
    "coordinate.scope.kind": {"coordinate.scope.tenant_id": ""},
    "coordinate.geography.declaration": {"coordinate.geography.value": ""},
    "coordinate.domain.declaration": {"coordinate.domain.value": ""},
    "effective_period.end_declaration": {"effective_period.effective_to": None},
}
paths = leaves(identity())
assert len(paths) == 28, len(paths)
assert set(paths) - {"supersession.status"} == set(PER_PATH_MUTATIONS), (
    set(paths) - {"supersession.status"} ^ set(PER_PATH_MUTATIONS)
)


def _resolve(root, dotted):
    target_path, _, leaf = dotted.rpartition(".")
    owner = root
    if target_path:
        for part in target_path.split("."):
            owner = getattr(owner, part)
    return owner, leaf


for path in PER_PATH_MUTATIONS:
    item = identity()
    before = item.canonical_digest()
    owner, leaf = _resolve(item, path)
    current = getattr(owner, leaf)
    replacement = PER_PATH_MUTATIONS[path]
    assert replacement != current, path
    object.__setattr__(owner, leaf, replacement)
    for companion_path, companion_value in COMPANION_FIXUPS.get(path, {}).items():
        c_owner, c_leaf = _resolve(item, companion_path)
        object.__setattr__(c_owner, c_leaf, companion_value)
    assert item.canonical_digest() != before, path

# supersession.status: no valid alternate exists, so corruption is refused,
# never silently canonicalized.
item = identity()
object.__setattr__(item.supersession, "status", "MUTATED-STATUS")
refuses(lambda: item.canonical_digest(), BenchmarkCanonicalizationError)

# ---------------------------------------------------------------------- #
# Exact-only coordinates
# ---------------------------------------------------------------------- #
for token in ("latest", "LATEST", "current", "newest", "head", "*", "any"):
    error = refuses(lambda t=token: coordinate(benchmark_version=t),
                    BenchmarkContractError)
    assert error.reason is _R.BENCHMARK_COORDINATE_NOT_EXACT, token
for token in ("^1.2.3", "~1.2.3", ">=1.2.3", "1.2.x", "1.2", "1.2.3.4", "v1.2.3",
              "1.02.0"):
    refuses(lambda t=token: coordinate(benchmark_version=t), BenchmarkContractError)

# F-3: build metadata is refused, not merely ignored (precedence-equivalent
# versions must not occupy separate append-only coordinates).
for token in ("1.2.3+a", "1.2.3+build.7", "1.2.3-alpha+build"):
    error = refuses(lambda t=token: coordinate(benchmark_version=t),
                    BenchmarkContractError)
    assert error.reason is _R.BENCHMARK_COORDINATE_NOT_EXACT, token
for token in ("1.2.3", "1.2.3-alpha", "1.2.3-alpha.1"):
    assert coordinate(benchmark_version=token).benchmark_version == token
for field in [f.name for f in dataclasses.fields(BenchmarkCoordinate)]:
    kwargs = {f.name: getattr(coordinate(), f.name)
              for f in dataclasses.fields(BenchmarkCoordinate)}
    kwargs.pop(field)
    refuses(lambda k=kwargs: BenchmarkCoordinate(**k), TypeError)

# ---------------------------------------------------------------------- #
# Structural invariants
# ---------------------------------------------------------------------- #
refuses(lambda: coordinate(benchmark_id=""), BenchmarkContractError)
refuses(lambda: coordinate(benchmark_id=" padded"), BenchmarkContractError)
refuses(lambda: identity(content_digest="A" * 64), BenchmarkContractError)
refuses(lambda: BenchmarkEffectivePeriod.open_ended(datetime(2026, 1, 1)),
        BenchmarkContractError)
refuses(lambda: BenchmarkEffectivePeriod.bounded(TO, FROM), BenchmarkContractError)
refuses(lambda: BenchmarkEffectivePeriod.bounded(FROM, FROM), BenchmarkContractError)
refuses(
    lambda: BenchmarkSourceRequirements(source_ref="s",
                                        provenance_requirement_refs=("r", "r")),
    BenchmarkContractError,
)
refuses(
    lambda: BenchmarkSourceRequirements(source_ref="s",
                                        provenance_requirement_refs=()),
    BenchmarkContractError,
)
refuses(lambda: measurement(unit=""), BenchmarkContractError)
refuses(
    lambda: BenchmarkApplicabilityCoordinate(
        declaration=BenchmarkApplicabilityDeclaration.APPLICABLE, value=""),
    BenchmarkContractError,
)
refuses(
    lambda: BenchmarkApplicabilityCoordinate(
        declaration=BenchmarkApplicabilityDeclaration.NOT_APPLICABLE, value="EU"),
    BenchmarkContractError,
)
refuses(lambda: BenchmarkScope(kind=BenchmarkScopeKind.TENANT, tenant_id=""),
        BenchmarkContractError)
refuses(lambda: BenchmarkScope(kind=BenchmarkScopeKind.PLATFORM_WIDE,
                               tenant_id="t"), BenchmarkContractError)
error = refuses(lambda: identity(approval=approval(approved_content_digest=OTHER)),
                BenchmarkContractError)
assert error.reason is _R.BENCHMARK_APPROVAL_REFERENCE_INVALID
error = refuses(lambda: identity(publisher_id="authority-benchmark-governance-board"),
                BenchmarkContractError)
assert error.reason is _R.BENCHMARK_ROLE_SEPARATION_VIOLATED

# Non-NFC and encoder rejections.
nfd, nfc = "Café", "Café"
assert nfd != nfc
refuses(lambda: BenchmarkScope.for_tenant(nfd), BenchmarkContractError)
scope = BenchmarkScope.for_tenant(nfc)
object.__setattr__(scope, "tenant_id", nfd)
refuses(lambda: canonical_bytes(scope), BenchmarkCanonicalizationError)
for value in (1.5, float("nan"), float("inf"), b"\x00", {"a": 1}, object()):
    period = BenchmarkEffectivePeriod.open_ended(FROM)
    object.__setattr__(period, "effective_from", value)
    refuses(lambda p=period: canonical_bytes(p), BenchmarkCanonicalizationError)

# Half-open boundaries.
period = BenchmarkEffectivePeriod.bounded(FROM, TO)
micro = timedelta(microseconds=1)
assert period.is_effective_at(FROM) is True
assert period.is_effective_at(FROM - micro) is False
assert period.is_effective_at(TO - micro) is True
assert period.is_effective_at(TO) is False
assert period.temporal_refusal_at(FROM - micro) is _R.BENCHMARK_NOT_YET_EFFECTIVE
assert period.temporal_refusal_at(TO) is _R.BENCHMARK_EXPIRED
refuses(lambda: period.is_effective_at(), TypeError)

# UTC normalization and microsecond preservation.
shifted = datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=3)))
assert canonical_bytes(BenchmarkEffectivePeriod.open_ended(FROM)) == canonical_bytes(
    BenchmarkEffectivePeriod.open_ended(shifted)
)
precise = datetime(2026, 1, 1, 0, 0, 0, 654321, tzinfo=timezone.utc)
assert b"00:00:00.654321Z" in canonical_bytes(
    BenchmarkEffectivePeriod.open_ended(precise)
)

# Order-irrelevant normalization; the encoder itself stays order-faithful.
a = BenchmarkSourceRequirements(source_ref="s",
                                provenance_requirement_refs=("r-a", "r-b"))
c = BenchmarkSourceRequirements(source_ref="s",
                                provenance_requirement_refs=("r-b", "r-a"))
assert canonical_bytes(a) == canonical_bytes(c)
# Graph revalidation re-runs the contract's own order-normalization before
# any byte is produced, so a hand-placed out-of-order tuple is restored to
# its canonical sorted order rather than encoded as given.
object.__setattr__(c, "provenance_requirement_refs", ("r-b", "r-a"))
assert b'["r-a","r-b"]' in canonical_bytes(c)
assert b'["r-b","r-a"]' not in canonical_bytes(c)

# ---------------------------------------------------------------------- #
# Lifecycle relation
# ---------------------------------------------------------------------- #
admissible = {
    (BenchmarkLifecycleState.AUTHORED, BenchmarkLifecycleState.APPROVED),
    (BenchmarkLifecycleState.APPROVED, BenchmarkLifecycleState.REGISTERED),
    (BenchmarkLifecycleState.REGISTERED, BenchmarkLifecycleState.REVOKED),
}
derived = {(k, v) for k, states in BENCHMARK_LIFECYCLE_TRANSITIONS.items()
           for v in states}
assert derived == admissible, derived
for current in BenchmarkLifecycleState:
    for proposed in BenchmarkLifecycleState:
        expected = (current, proposed) in admissible
        assert is_valid_lifecycle_transition(current, proposed) is expected
        if not expected:
            error = refuses(
                lambda a=current, b=proposed: require_valid_lifecycle_transition(a, b),
                BenchmarkLifecycleError,
            )
            assert error.reason is _R.BENCHMARK_INVALID_LIFECYCLE_TRANSITION
assert BENCHMARK_TERMINAL_LIFECYCLE_STATES == frozenset(
    {BenchmarkLifecycleState.REVOKED}
)
assert list(BENCHMARK_LIFECYCLE_ORDER) == list(BenchmarkLifecycleState)
assert {m.value for m in BenchmarkLifecycleState} == {
    "AUTHORED", "APPROVED", "REGISTERED", "REVOKED"
}

# ---------------------------------------------------------------------- #
# Nothing reaches a resolved or trusted state
# ---------------------------------------------------------------------- #
item = identity()
assert item.structural_status is BenchmarkStructuralStatus.STRUCTURAL_UNVERIFIED
assert item.trusted_resolution_performed is False
assert item.unresolved_reason is _R.BENCHMARK_RESOLUTION_NOT_PERFORMED
assert _R.BENCHMARK_RESOLUTION_NOT_PERFORMED in item.structural_refusals_at(FROM)
refuses(lambda: setattr(item, "publisher_id", "x"), dataclasses.FrozenInstanceError)
for prop in ("structural_status", "trusted_resolution_performed",
             "unresolved_reason"):
    refuses(lambda p=prop: object.__setattr__(item, p, "TRUSTED"), AttributeError)


class Forged(CanonicalBenchmarkDefinitionIdentity):
    @property
    def structural_status(self):
        return "TRUSTED"


forged = Forged(**{f.name: getattr(identity(), f.name)
                   for f in dataclasses.fields(CanonicalBenchmarkDefinitionIdentity)})
# Only the exact registered class canonicalizes; a subclass is refused
# outright, never merely relabeled with its own ``type`` tag.
refuses(lambda: forged.canonical_digest(), BenchmarkCanonicalizationError)
refuses(lambda: canonical_bytes(forged), BenchmarkCanonicalizationError)


class LooksLikeAScope:
    kind = BenchmarkScopeKind.PLATFORM_WIDE
    tenant_id = ""


refuses(lambda: coordinate(scope=LooksLikeAScope()), BenchmarkContractError)

# F-1 — a same-named foreign dataclass, its ``__module__`` forged to match
# this package, must not be able to borrow the genuine bytes or digest.
_genuine_min = coordinate(
    benchmark_id="bmk-min", benchmark_family="family-min", benchmark_version="0.1.0",
    scope=BenchmarkScope.platform_wide(),
    geography=BenchmarkApplicabilityCoordinate.not_applicable(),
    domain=BenchmarkApplicabilityCoordinate.not_applicable(),
)
_genuine_min_digest = _genuine_min.canonical_digest()


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


for _cls, _name in (
    (_ForeignScope, "BenchmarkScope"),
    (_ForeignApplicabilityCoordinate, "BenchmarkApplicabilityCoordinate"),
    (_ForeignCoordinate, "BenchmarkCoordinate"),
):
    _cls.__name__ = _name
    _cls.__qualname__ = _name
    _cls.__module__ = "ugence_benchmark_registry.contracts.identity"

_forged_coordinate = _ForeignCoordinate(
    benchmark_id="bmk-min", benchmark_family="family-min", benchmark_version="0.1.0",
    scope=_ForeignScope(kind=BenchmarkScopeKind.PLATFORM_WIDE, tenant_id=""),
    geography=_ForeignApplicabilityCoordinate(
        declaration=BenchmarkApplicabilityDeclaration.NOT_APPLICABLE, value=""
    ),
    domain=_ForeignApplicabilityCoordinate(
        declaration=BenchmarkApplicabilityDeclaration.NOT_APPLICABLE, value=""
    ),
)
refuses(lambda: canonical_bytes(_forged_coordinate), BenchmarkCanonicalizationError)
assert _genuine_min.canonical_digest() == _genuine_min_digest

# And a same-named foreign class carrying a value the real constructor would
# refuse (a floating ``benchmark_version``) must not slip through by
# bypassing ``__post_init__`` entirely.


@dataclasses.dataclass(frozen=True)
class _ForeignCoordinateWithInvalidVersion:
    benchmark_id: str
    benchmark_family: str
    benchmark_version: str
    scope: object
    geography: object
    domain: object


_ForeignCoordinateWithInvalidVersion.__name__ = "BenchmarkCoordinate"
_ForeignCoordinateWithInvalidVersion.__qualname__ = "BenchmarkCoordinate"
_ForeignCoordinateWithInvalidVersion.__module__ = (
    "ugence_benchmark_registry.contracts.identity"
)
_evil = _ForeignCoordinateWithInvalidVersion(
    benchmark_id="bmk-min", benchmark_family="family-min", benchmark_version="latest",
    scope=BenchmarkScope.platform_wide(),
    geography=BenchmarkApplicabilityCoordinate.not_applicable(),
    domain=BenchmarkApplicabilityCoordinate.not_applicable(),
)
refuses(lambda: canonical_bytes(_evil), BenchmarkCanonicalizationError)

# Cross-tenant replay is detectable.
assert identity().canonical_digest() != identity(
    coordinate=coordinate(scope=BenchmarkScope.for_tenant("tenant-beta"))
).canonical_digest()

# ---------------------------------------------------------------------- #
# BR-2 is not started
# ---------------------------------------------------------------------- #
for name in u.api.__all__:
    lowered = name.lower()
    if name == "BENCHMARK_REGISTRY_CANONICALIZATION_VERSION":
        continue
    for banned in ("registry", "resolver", "store", "registration", "admission",
                   "publisher", "signer", "signature", "trustanchor",
                   "revocation", "successor", "latest", "current", "lookup",
                   "readiness", "forecast", "attribution", "valuation", "roi",
                   "policy", "deploy", "authorize"):
        assert banned not in lowered, name
domains = [n for n in u.api.__all__ if n.endswith("_DIGEST_DOMAIN")]
assert domains == ["BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN"], domains
assert len(BENCHMARK_REFUSAL_REASONS) == 17
assert BENCHMARK_REFUSAL_REASONS == BR1_BENCHMARK_REFUSAL_REASONS
assert [m.value for m in BenchmarkSupersessionStatus] == ["UNDETERMINED"]

# ---------------------------------------------------------------------- #
# The installed surface equals the committed manifest, exactly
# ---------------------------------------------------------------------- #
def kind(obj):
    if isinstance(obj, type):
        if issubclass(obj, enum.Enum):
            return "enum"
        if issubclass(obj, Exception):
            return "exception"
        if dataclasses.is_dataclass(obj):
            return "dataclass"
        return "class"
    if callable(obj):
        return "function"
    return "constant"


def const_value(obj):
    if isinstance(obj, str):
        return obj
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, (tuple, list)):
        return [const_value(v) for v in obj]
    if isinstance(obj, frozenset):
        return sorted(const_value(v) for v in obj)
    if hasattr(obj, "items"):
        return {const_value(k): sorted(const_value(v) for v in value)
                for k, value in obj.items()}
    if isinstance(obj, (int, bool)) or obj is None:
        return obj
    raise AssertionError("unrenderable constant: %r" % (obj,))


documented = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
symbols = {}
for name in sorted(u.api.__all__):
    if name == "__version__":
        continue
    obj = getattr(u.api, name)
    entry = {"kind": kind(obj)}
    if isinstance(obj, type) and issubclass(obj, enum.Enum):
        entry["values"] = [m.value for m in obj]
    elif isinstance(obj, type) and dataclasses.is_dataclass(obj):
        entry["fields"] = [f.name for f in dataclasses.fields(obj)]
    elif entry["kind"] == "constant":
        entry["value"] = const_value(obj)
    symbols[name] = entry

assert documented["distribution"] == "ugence-benchmark-registry"
assert documented["namespace"] == "ugence_benchmark_registry"
assert documented["package_version"] == u.__version__ == "0.1.0"
assert documented["curated_api_module"] == "ugence_benchmark_registry.api"
assert documented["symbols"] == symbols, sorted(
    set(documented["symbols"]) ^ set(symbols)
) or "symbol detail differs"
assert set(u.__all__) - {"api"} == set(u.api.__all__)
assert len([n for n in u.api.__all__ if n != "__version__"]) == 31

print("ISOLATED BENCHMARK-REGISTRY VERIFICATION OK")
'''


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def _safe_rmtree(target: Path, *, label: str) -> None:
    """Remove a package-local build artifact, refusing anything unsafe.

    Cleaning ``build/`` before packaging matters: a stale build tree can leave a
    previous module in the wheel. Doing it safely matters more, so the target
    must be a real directory (never a symlink, at any level of its path) and must
    live strictly inside this package.
    """

    if not target.exists() and not target.is_symlink():
        return
    if target.is_symlink():
        raise SystemExit(f"refusing to remove symlinked {label}: {target}")
    resolved = target.resolve()
    package_root = PKG.resolve()
    if not resolved.is_relative_to(package_root) or resolved == package_root:
        raise SystemExit(f"refusing to remove {label} outside the package: {resolved}")
    if not resolved.is_dir():
        raise SystemExit(f"refusing to remove non-directory {label}: {resolved}")
    for entry in resolved.rglob("*"):
        if entry.is_symlink():
            raise SystemExit(
                f"refusing to remove {label}: it contains a symlink ({entry})"
            )
    print(f"      cleaned {label}: {resolved.relative_to(package_root)}")
    shutil.rmtree(resolved)


def _archive_members(archive_path: Path):
    if archive_path.suffix == ".whl":
        with zipfile.ZipFile(archive_path) as archive:
            return archive.namelist()
    import tarfile

    with tarfile.open(archive_path) as archive:
        return archive.getnames()


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    _safe_rmtree(findlinks, label="find-links directory")
    _safe_rmtree(PKG / "build", label="build tree")
    findlinks.mkdir()

    print(f"[1/6] build the {DISTRIBUTION} wheel and sdist from a clean tree")
    _run([sys.executable, "-m", "build", str(PKG), "-o", str(findlinks)])
    wheel = _latest(findlinks, f"{NAMESPACE}-*.whl")
    sdist = _latest(findlinks, f"{NAMESPACE}-*.tar.gz")
    print(f"      built {wheel.name} and {sdist.name}")
    assert "0.1.0" in wheel.name, wheel.name
    assert "0.1.0" in sdist.name, sdist.name

    print("[2/6] assert the wheel ships exactly one namespace + dist-info + py.typed")
    names = _archive_members(wheel)
    tops = {n.split("/", 1)[0] for n in names if "/" in n}
    foreign = {t for t in tops if not (t == NAMESPACE or t.endswith(".dist-info"))}
    assert not foreign, f"wheel bundles foreign top-level packages: {sorted(foreign)}"
    assert f"{NAMESPACE}/py.typed" in names, "wheel is missing py.typed"
    for name in names:
        lowered = name.lower()
        for banned in ("test", "conftest", "probe", "fixture", "_builders",
                       "build/", "public_api.json", "verify_"):
            assert banned not in lowered, f"wheel contains {name} (matched {banned!r})"
    modules = [n for n in names if n.endswith(".py")]
    assert len(modules) == len(set(modules)), "duplicate module entries in the wheel"
    print(f"      {len(modules)} modules, top-level: {sorted(tops)}")

    print("[3/6] assert the sdist carries no build tree and no foreign package")
    sdist_names = _archive_members(sdist)
    for name in sdist_names:
        assert "/build/" not in name, f"sdist carries a stale build tree: {name}"
        assert "_dist_wheels" not in name, f"sdist carries a wheelhouse: {name}"
        assert "__pycache__" not in name, f"sdist carries bytecode: {name}"
    print(f"      {len(sdist_names)} sdist entries")

    print("[4/6] install into a fresh venv with no index and no dependency")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        python = env / "bin" / "python"

        isolated_env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP")
        }
        isolated_env["PIP_NO_INDEX"] = "1"
        isolated_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        _run([str(python), "-m", "pip", "install", "--quiet", "--no-index",
              "--find-links", str(findlinks), DISTRIBUTION], env=isolated_env)

        installed = subprocess.run(
            [str(python), "-m", "pip", "list", "--format=freeze"],
            capture_output=True, text=True, check=True, env=isolated_env)
        distributions = sorted(
            line for line in installed.stdout.split()
            if not line.lower().startswith(("pip==", "setuptools==", "wheel=="))
        )
        print(f"      installed: {distributions}")
        assert distributions == [f"{DISTRIBUTION}==0.1.0"], distributions

        print("[5/6] run the isolated proof (cwd has no monorepo source)")
        _run([str(python), "-c", _CHECK, str(PKG / "public_api.json")],
             cwd=str(td), env=isolated_env)

        print("[6/6] run the independent adversarial probes against the installed wheel")
        _run([str(python), str(PKG / "adversarial_probes.py")],
             cwd=str(td), env=isolated_env)

    _safe_rmtree(findlinks, label="find-links directory")
    _safe_rmtree(PKG / "build", label="build tree")
    print("\nISOLATED BENCHMARK-REGISTRY DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
