"""Request shapes — exactly one exact locator, and no convenience anywhere.

Two request types, and they are **not** interchangeable:

* :class:`BenchmarkExactResolutionRequest` asks the present-tense question "may I
  rely on this benchmark right now?". It accepts an exact BR-1 locator **and
  nothing else**. It has no ``as_of`` — not an optional one, not a defaulted
  one, none at all — because trusted resolution is a present-tense question and
  a caller-supplied instant is precisely how a revoked artifact would be argued
  back into admissibility.
* :class:`BenchmarkHistoricalInspectionRequest` asks "what did the registry
  hold, and when?". Its ``as_of`` is **mandatory** and caller-supplied, and it
  is disclosed on the result. It never relaxes authorization, and under D-09's
  ``DENY_ALWAYS`` it never makes a revoked artifact currently admissible.

No selection, in either
-----------------------
D-07 as ratified: **no** ``latest``, ``active``, ``current``, ``stable``,
``default``, version selection, implicit default, fallback or compatibility
coercion exists on any request type in this package. Not disabled — *absent*.
There is no parameter to pass and no code path to reach.

Nothing here re-implements that ban, because nothing here has to. Both requests
carry an exact :class:`~ugence_benchmark_registry.BenchmarkCoordinate`, which
already refused — **at its own construction, in the frozen BR-1 layer** — every
floating token (``latest``, ``current``, ``newest``, ``head``, ``tip``, ``any``,
``default``, ``active``, ``stable``, ``*``, ``-``, ``?``, in any letter case),
every wildcard and range character, every partial version, every comparator, and
every ``+build`` metadata spelling. Re-implementing those rules here would be a
second source of truth that could drift; requiring the type that enforces them
is one source of truth that cannot.

``ugence_governance_contracts.BenchmarkReference`` is **never** accepted by
either request, or by anything else in this package. It is verified to admit
``latest``, ``*``, ``>=1.2.3``, ``1.2`` and ``1.2.3+build``, and to carry no
family, scope, geography or domain — so it names a set, not a coordinate. It may
appear only as an explicitly-named **untrusted inbound hint** that a caller must
re-express as a :class:`~ugence_benchmark_registry.BenchmarkCoordinate` before
anything in BR-2 will look at it, and this package does not import it, name it in
a field, or provide a conversion for it.

One version, one scope, one source of truth for each
------------------------------------------------------
Each request contains **exactly one** coordinate and **no second version
field**: :attr:`BenchmarkCoordinate.benchmark_version` is the version, full stop.

The same discipline governs scope. The coordinate already carries an exact
:class:`~ugence_benchmark_registry.BenchmarkScope`, so a *second* scope field on
the request would be a second spelling that could disagree with it — and §09
prefers making the conflicting representation unconstructible over detecting the
conflict. :attr:`~BenchmarkExactResolutionRequest.registry_scope_expectation` is
therefore a **derived read-only property**, built from ``coordinate.scope``.
There is no constructor argument for it, so a platform-wide locator can never
arrive carrying a tenant expectation.

The two expectation types are distinct exact contracts differing **only in the
kind their constructors admit**, so the platform case and the tenant case cannot
be confused at a type boundary, and each has its own canonical byte space.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Union

from ugence_benchmark_registry import (
    BenchmarkCoordinate,
    BenchmarkScope,
    BenchmarkScopeKind,
)

from ._authority import permanently_unverified_authority
from ._validation import require_aware_datetime, require_exact_type
from .canonical import (
    BENCHMARK_EXACT_RESOLUTION_REQUEST_DIGEST_DOMAIN,
    BENCHMARK_HISTORICAL_INSPECTION_REQUEST_DIGEST_DOMAIN,
    BENCHMARK_PLATFORM_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN,
    BENCHMARK_TENANT_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN,
    _register_contract_type,
)
from .errors import BenchmarkRegistryContractError

__all__ = [
    "PlatformRegistryScopeExpectation",
    "TenantRegistryScopeExpectation",
    "BenchmarkRegistryScopeExpectation",
    "BenchmarkExactResolutionRequest",
    "BenchmarkHistoricalInspectionRequest",
]


@permanently_unverified_authority
@dataclass(frozen=True)
class PlatformRegistryScopeExpectation:
    """An expectation that a locator's registry scope is explicitly platform-wide.

    Carries a BR-1 :class:`~ugence_benchmark_registry.BenchmarkScope` and admits
    **only** ``PLATFORM_WIDE``. It mints no scope semantics of its own: the
    vocabulary stays BR-1's, and BR-1 already cross-checks that a
    ``PLATFORM_WIDE`` scope carries an empty ``tenant_id``.

    **Constructing this grants no authorization.** Declaring ``PLATFORM_WIDE`` is
    not a grant of platform-wide trust — it records the intended applicability
    scope, and whether a caller may resolve anything at that scope is a question
    for a registry that does not exist at BR-2A. :attr:`authorization_granted` is
    permanently ``False`` and ``tests/contract/test_scope_expectations.py``
    asserts it.
    """

    #: The exact BR-1 scope. Its ``kind`` must be ``PLATFORM_WIDE``.
    scope: BenchmarkScope

    def __post_init__(self) -> None:
        require_exact_type(self.scope, BenchmarkScope, "scope")
        if self.scope.kind is not BenchmarkScopeKind.PLATFORM_WIDE:
            raise BenchmarkRegistryContractError(
                "PlatformRegistryScopeExpectation admits only a PLATFORM_WIDE "
                f"scope (got {self.scope.kind.value}); the tenant case has its "
                "own exact type, TenantRegistryScopeExpectation, so the two "
                "can never be confused at a type boundary"
            )

    @property
    def authorization_granted(self) -> bool:
        """Permanently ``False``. Expressing an expectation authorizes nothing."""

        return False


@permanently_unverified_authority
@dataclass(frozen=True)
class TenantRegistryScopeExpectation:
    """An expectation that a locator's registry scope is an exact tenant.

    Carries a BR-1 :class:`~ugence_benchmark_registry.BenchmarkScope` and admits
    **only** ``TENANT``. BR-1 already requires a ``TENANT`` scope to carry a
    non-empty exact ``tenant_id``, and §27.1's discipline that a tenant is never
    inferred or defaulted is what makes the distinction load-bearing.

    **Constructing this grants no authorization**, and naming a tenant is not
    being entitled to that tenant's data. Cross-tenant enforcement lives in a
    registry that does not exist at BR-2A; when it does, §17.6 requires a
    cross-tenant denial and a genuine miss to be externally indistinguishable.
    """

    #: The exact BR-1 scope. Its ``kind`` must be ``TENANT``.
    scope: BenchmarkScope

    def __post_init__(self) -> None:
        require_exact_type(self.scope, BenchmarkScope, "scope")
        if self.scope.kind is not BenchmarkScopeKind.TENANT:
            raise BenchmarkRegistryContractError(
                "TenantRegistryScopeExpectation admits only a TENANT scope "
                f"(got {self.scope.kind.value}); the platform-wide case has "
                "its own exact type, PlatformRegistryScopeExpectation"
            )

    @property
    def tenant_id(self) -> str:
        """The exact tenant, derived through the nested BR-1 scope.

        One source of truth: this expectation declares no tenant of its own, so
        there is no second spelling to disagree with the scope it carries.
        """

        return self.scope.tenant_id

    @property
    def authorization_granted(self) -> bool:
        """Permanently ``False``. Naming a tenant is not entitlement to it."""

        return False


#: The union of the two expectation types. A type alias for annotation only —
#: it is not a third type, is not constructible, and nothing dispatches on it.
BenchmarkRegistryScopeExpectation = Union[
    PlatformRegistryScopeExpectation, TenantRegistryScopeExpectation
]


def _expectation_for(scope: BenchmarkScope):
    """Build the exact expectation type matching ``scope``'s kind.

    Total over :class:`~ugence_benchmark_registry.BenchmarkScopeKind`'s two
    members. A third kind would land in the final ``raise`` rather than being
    guessed at — an unknown scope fails closed, it does not default to
    platform-wide.
    """

    if scope.kind is BenchmarkScopeKind.PLATFORM_WIDE:
        return PlatformRegistryScopeExpectation(scope=scope)
    if scope.kind is BenchmarkScopeKind.TENANT:
        return TenantRegistryScopeExpectation(scope=scope)
    raise BenchmarkRegistryContractError(  # pragma: no cover - closed vocabulary
        f"no registry scope expectation exists for scope kind {scope.kind!r}; "
        "an unrecognized scope fails closed rather than defaulting"
    )


@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkExactResolutionRequest:
    """The trusted-resolution request: an exact locator, and nothing else.

    **No** ``as_of``. Trusted resolution is a present-tense question, and D-09's
    ``DENY_ALWAYS`` means a revoked artifact never resolves as admissible at any
    instant. An ``as_of`` parameter here would be the exact affordance an
    attacker needs to argue a revoked benchmark back into currency, so it does
    not exist — ``tests/contract/test_requests.py`` asserts the absence of any
    field or property by that name.

    Constructing a request performs no resolution. There is no resolver in this
    package to hand it to.
    """

    #: The exact BR-1 locator: nine scalar elements, exact SemVer, no floating
    #: token, no wildcard, no range, no partial version, no build metadata —
    #: all refused by BR-1 at the coordinate's own construction.
    coordinate: BenchmarkCoordinate

    def __post_init__(self) -> None:
        require_exact_type(self.coordinate, BenchmarkCoordinate, "coordinate")

    @property
    def registry_scope_expectation(self):
        """The exact scope expectation, **derived** from the locator's own scope.

        Not a constructor argument. A second scope field would be a second
        spelling that could disagree with the coordinate; deriving makes the
        disagreement unconstructible.
        """

        return _expectation_for(self.coordinate.scope)

    @property
    def benchmark_version(self) -> str:
        """The exact version, derived. There is no second version field."""

        return self.coordinate.benchmark_version


@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkHistoricalInspectionRequest:
    """The historical-inspection request: an exact locator **and a mandatory ``as_of``**.

    ``as_of`` is caller-supplied, timezone-aware, required, digest-participating,
    and disclosed on the resulting
    :class:`~.read_payloads.BenchmarkHistoricalRecordPayload`. It is the only
    ``as_of`` anywhere in this package, and it lives on the *explicitly
    historical* API — which is what keeps a historical answer from being
    consumed as a current one.

    ``as_of`` never relaxes authorization. The same tenant check applies, first,
    before any temporal or lifecycle consideration; a caller cannot see another
    tenant's history by asking about the past.
    """

    #: The exact BR-1 locator.
    coordinate: BenchmarkCoordinate

    #: The instant the caller is asking about. Mandatory and explicit: an
    #: implicit "now" would silently make this a present-tense question, which
    #: is the other API's job and the other API's return type.
    as_of: datetime

    def __post_init__(self) -> None:
        require_exact_type(self.coordinate, BenchmarkCoordinate, "coordinate")
        require_aware_datetime(self.as_of, "as_of")

    @property
    def registry_scope_expectation(self):
        """The exact scope expectation, derived from the locator's own scope."""

        return _expectation_for(self.coordinate.scope)

    @property
    def benchmark_version(self) -> str:
        """The exact version, derived. There is no second version field."""

        return self.coordinate.benchmark_version


for _cls, _domain in (
    (
        PlatformRegistryScopeExpectation,
        BENCHMARK_PLATFORM_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN,
    ),
    (
        TenantRegistryScopeExpectation,
        BENCHMARK_TENANT_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN,
    ),
    (
        BenchmarkExactResolutionRequest,
        BENCHMARK_EXACT_RESOLUTION_REQUEST_DIGEST_DOMAIN,
    ),
    (
        BenchmarkHistoricalInspectionRequest,
        BENCHMARK_HISTORICAL_INSPECTION_REQUEST_DIGEST_DOMAIN,
    ),
):
    _register_contract_type(_cls, _domain, root_canonicalizable=True)
del _cls, _domain
