"""``ExecutionTargetScope`` and the two policy references — where, how far, and which policy.

Phase 4's ``CapacitySubject`` answers *which workload was observed*. It deliberately does
**not** answer *which account an action would land in*, and it is frozen — Phase 5A does
not touch it. So the account binding arrives here, as new Phase 5 vocabulary:
:class:`ExecutionTargetScope` is the first artifact in the chain that names a concrete,
account-bound execution target and the bounds an action against it may not exceed.

``account_id`` is **required**. A capacity action that reconciles perfectly against tenant,
region and cluster but lands in the wrong cloud account is exactly the substitution this
field exists to make impossible, and an optional field would not make it impossible.

:class:`PolicyTargetBindingReference` names the policy that bounds that scope. Phase 5A
validates its **structure**, its **internal digest consistency** and its **agreement with
the projection's tenant/action/resource facts**. It does not resolve the policy — there is
no resolver call in this package, and no resolver port to call — and it does not establish
that the policy signature is genuine, that the issuer is authoritative, or that the policy
version is current. Its :attr:`~PolicyTargetBindingReference.trust_state` is fixed at
``PRESENT_BUT_NOT_TRUST_VERIFIED`` for that reason. Phase 5B verifies Policy Authority
provenance and freshness independently, before any envelope is issued.

:class:`PolicyTargetBindingReferenceV2` (5B-1) names *which policy version, exactly*: the
complete six-component Policy Authority coordinate, the framed body digest its issuance
signature covers, and the issuing key. It is carried **beside** the reference above, not
instead of it — the two answer different questions, and the builder refuses a candidate whose
two policy references disagree about the policy they name. Neither is resolved here. Adding a
coordinate to the candidate is what makes a verified policy proof reconcilable against it;
performing that reconciliation is Phase 5B-0B's, and the trust state of both references stays
``PRESENT_BUT_NOT_TRUST_VERIFIED``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Final, Mapping, Optional

from .canonical import (
    canonical_digest,
    require_canonical_digest,
    require_canonical_identifier,
    require_nfc_text,
    require_policy_authority_digest,
)
from .errors import AuthorizationCandidateRejectionReason as _Reason
from .errors import (
    CanonicalFieldError,
    ExactTypeError,
    MagnitudeBoundError,
    PolicyTargetBindingError,
    TargetScopeError,
)
from .identifiers import (
    CANONICAL_ACTION_TYPES,
    CANONICAL_CLOUD_PROVIDERS,
    CLOUD_PROVIDER_AZURE,
)
from .trust import PHASE_5A_TRUST_STATE, EvidenceTrustState

__all__ = [
    "EXECUTION_TARGET_SCOPE_SCHEMA_VERSION",
    "POLICY_TARGET_BINDING_SCHEMA_VERSION",
    "POLICY_TARGET_BINDING_V2_SCHEMA_VERSION",
    "POLICY_COORDINATE_COMPONENTS",
    "POLICY_SCOPE_TENANT",
    "ExecutionTargetScope",
    "PolicyTargetBindingReference",
    "PolicyTargetBindingReferenceV2",
]

EXECUTION_TARGET_SCOPE_SCHEMA_VERSION: Final[str] = "cloud-scaling-execution-target-scope-2"

#: The one ``policy_scope`` value that constrains which tenant a policy may bound (R-9).
#: Duplicated as a literal rather than imported: this package deliberately depends on no
#: Policy Authority and no UVI contracts, which is why the coordinate travels as strings at
#: all. The authoritative definition is ``PolicyScope.TENANT`` in ``uvi-policy-contracts``,
#: whose ``GLOBAL`` counterpart carries the empty tenant — which is exactly why the guard
#: keys on the scope and never on a bare tenant equality.
POLICY_SCOPE_TENANT: Final = "TENANT"
POLICY_TARGET_BINDING_SCHEMA_VERSION: Final[str] = "cloud-scaling-policy-target-binding-1"
POLICY_TARGET_BINDING_V2_SCHEMA_VERSION: Final[str] = "cloud-scaling-policy-target-binding-2"

#: The six components of a Policy Authority coordinate, under this package's field names.
#: **All six, always.** Exact-match lookup is the only lookup the authority's registry
#: performs, so a reference carrying five of them cannot address a policy version — it is not
#: a partially specified coordinate, it is not a coordinate (5B-1 D-5B1-5, from D-5B0B-3).
POLICY_COORDINATE_COMPONENTS: Final[tuple] = (
    "policy_family",
    "policy_id",
    "policy_version",
    "policy_content_digest",
    "policy_scope",
    "policy_tenant_id",
)


def _require_magnitude(name: str, value: Any) -> int:
    """A non-negative ``int``, admitted by **exact type**. ``True`` is not a capacity.

    Exact typing rather than ``isinstance``-plus-``bool``-exclusion: a subclass can override
    the comparison a bound check relies on, and canonicalization renders an ``int`` subclass
    to the identical value, so no digest downstream can tell them apart. ``bool`` was the one
    subclass named explicitly; this closes the rest with it. Matches ``verified.py:339``.
    """

    if type(value) is not int or value < 0:
        raise TargetScopeError(
            f"{name} must be an int >= 0 (got {value!r})", _Reason.MALFORMED_CANONICAL_FIELD
        )
    return value


def _optional_identifier(name: str, value: Any) -> Optional[str]:
    """``None`` stays ``None``: a missing optional is never normalized to ``""``."""

    if value is None:
        return None
    return require_canonical_identifier(name, value)


@dataclass(frozen=True)
class ExecutionTargetScope:
    """The account-bound execution target and the magnitude bounds that apply to it.

    Immutable and exact-typed. Constructing one asserts nothing about authority: it names
    a place an action *would* go and a ceiling it may not pass, and Phase 5A stops there.
    """

    tenant_id: str
    #: Required, and new to Phase 5. The Phase 4 subject has no account identity.
    account_id: str
    #: Required, and new to Phase 5A schema 2 (ETS-3). ``account_id`` alone was ambiguous:
    #: an AWS account number, a GCP project and an Azure subscription are all opaque
    #: strings, nothing upstream carries provider identity, and two clouds' identifiers
    #: can therefore collide. ``(cloud_provider, account_id)`` is the governed account
    #: identity; neither half is sufficient alone.
    #:
    #: Scope-only and reconciled against nothing, like :attr:`namespace` under ETS-6 —
    #: ``CapacitySubject`` is provider-neutral by ruling (ETS-8) so there is no projected
    #: fact to reconcile against. Its protection is the digest binding, not agreement with
    #: an upstream authority; a scope naming the wrong provider is caught only if the
    #: digest it is bound into is checked.
    cloud_provider: str
    action_type: str
    magnitude_before: int
    requested_magnitude: int
    max_permitted_magnitude: int
    max_permitted_delta: int
    #: Optional because the frozen Phase 4 ``CapacitySubject`` makes ``cluster`` and
    #: ``resource_id`` optional. Phase 5A mirrors that contract rather than contradicting
    #: it: requiring them here would make a legitimate projection unbuildable. When present
    #: they must equal the projected subject's, so an optional field is not a loophole —
    #: ``None`` on one side and a value on the other is a target substitution.
    compute_group: Optional[str] = None
    resource_class: Optional[str] = None
    environment: Optional[str] = None
    region: Optional[str] = None
    zone: Optional[str] = None
    #: Present only where the deployment vocabulary supports it (Kubernetes-shaped
    #: targets). ``None`` for targets that have no namespace concept.
    namespace: Optional[str] = None
    #: Azure only, and required there (ETS-4). An ARM resource id needs a subscription
    #: *and* a resource group; ``account_id`` carries the first and nothing carried the
    #: second, so an Azure target was not addressable at all before schema 2. Required to
    #: be ``None`` for every other provider rather than merely optional: canonicalization
    #: retains nulls, so a stray value would sit inside the digest as dead data, and a
    #: digest-bound field nothing reads is a substitution surface.
    #:
    #: Implemented rule, stated because it is narrower than the words of ETS-4: the scope
    #: carries no field distinguishing a resource-level target from any other, and adding
    #: one was not ratified, so the enforceable rule is provider-conditional —
    #: ``cloud_provider == "azure"`` requires it, every other provider forbids it.
    resource_group: Optional[str] = None
    schema_version: str = EXECUTION_TARGET_SCOPE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        # The schema identifier is admitted as an exact plain string before it is
        # compared. Equality here decides which contract this artifact claims to be,
        # and ``!=`` is overridable, so a subclass can claim any identifier it likes.
        require_nfc_text("schema_version", self.schema_version)
        if self.schema_version != EXECUTION_TARGET_SCOPE_SCHEMA_VERSION:
            raise TargetScopeError(
                f"schema_version must be {EXECUTION_TARGET_SCOPE_SCHEMA_VERSION!r}",
                _Reason.UNSUPPORTED_SCHEMA_VERSION,
            )
        require_canonical_identifier("tenant_id", self.tenant_id)
        # An empty or absent account is a MISSING_ACCOUNT_BINDING, not a generic
        # malformed field: it is the specific substitution this scope exists to prevent.
        if self.account_id is None or self.account_id == "":
            raise TargetScopeError(
                "account_id is required — an execution target scope must be account-bound",
                _Reason.MISSING_ACCOUNT_BINDING,
            )
        require_canonical_identifier("account_id", self.account_id)

        # The provider half of the governed account identity. Membership is the whole
        # check: ETS-11 keeps per-provider grammar in governed adapters, not here.
        provider = require_canonical_identifier("cloud_provider", self.cloud_provider)
        if provider not in CANONICAL_CLOUD_PROVIDERS:
            raise TargetScopeError(
                f"cloud_provider {provider!r} is not in the ratified canonical vocabulary "
                f"{sorted(CANONICAL_CLOUD_PROVIDERS)}",
                _Reason.UNSUPPORTED_CLOUD_PROVIDER,
            )

        action = require_canonical_identifier("action_type", self.action_type)
        if action not in CANONICAL_ACTION_TYPES:
            raise TargetScopeError(
                f"action_type {action!r} is not a D-4 ratified canonical action type "
                f"{sorted(CANONICAL_ACTION_TYPES)}",
                _Reason.ACTION_SUBSTITUTION,
            )

        for name in (
            "magnitude_before",
            "requested_magnitude",
            "max_permitted_magnitude",
            "max_permitted_delta",
        ):
            _require_magnitude(name, getattr(self, name))

        for name in ("environment", "region", "zone", "namespace", "compute_group",
                     "resource_class", "resource_group"):
            _optional_identifier(name, getattr(self, name))

        # Provider-conditional, and enforced in both directions. Absent on Azure the scope
        # cannot name an ARM resource; present anywhere else it is dead data inside a
        # digest, which is exactly the substitution surface this scope exists to close.
        if provider == CLOUD_PROVIDER_AZURE:
            if self.resource_group is None:
                raise TargetScopeError(
                    "resource_group is required when cloud_provider is "
                    f"{CLOUD_PROVIDER_AZURE!r} — an ARM resource id needs both the "
                    "subscription and the resource group",
                    _Reason.MISSING_RESOURCE_GROUP_BINDING,
                )
        elif self.resource_group is not None:
            raise TargetScopeError(
                f"resource_group is meaningful only for {CLOUD_PROVIDER_AZURE!r} targets, "
                f"not {provider!r}",
                _Reason.RESOURCE_GROUP_NOT_APPLICABLE,
            )

        # The bounds are enforced at construction, so a scope that exceeds its own ceiling
        # cannot exist to be handed on — the check is not merely performed downstream.
        if self.requested_magnitude > self.max_permitted_magnitude:
            raise MagnitudeBoundError(
                f"requested_magnitude {self.requested_magnitude} exceeds the permitted "
                f"maximum {self.max_permitted_magnitude}",
                _Reason.REQUESTED_MAGNITUDE_ABOVE_MAXIMUM,
            )
        if self.requested_delta > self.max_permitted_delta:
            raise MagnitudeBoundError(
                f"requested delta {self.requested_delta} exceeds the permitted maximum "
                f"delta {self.max_permitted_delta}",
                _Reason.DELTA_ABOVE_MAXIMUM,
            )

    @property
    def requested_delta(self) -> int:
        """The magnitude of the requested change. Absolute: a scale-down is bounded too."""

        return abs(self.requested_magnitude - self.magnitude_before)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tenant_id": self.tenant_id,
            "account_id": self.account_id,
            "cloud_provider": self.cloud_provider,
            "environment": self.environment,
            "region": self.region,
            "zone": self.zone,
            "namespace": self.namespace,
            "resource_group": self.resource_group,
            "compute_group": self.compute_group,
            "resource_class": self.resource_class,
            "action_type": self.action_type,
            "magnitude_before": self.magnitude_before,
            "requested_magnitude": self.requested_magnitude,
            "requested_delta": self.requested_delta,
            "max_permitted_magnitude": self.max_permitted_magnitude,
            "max_permitted_delta": self.max_permitted_delta,
        }

    def digest(self) -> str:
        return canonical_digest(self.to_canonical_dict())

    #: ``ClassVar``, not ``Final``: ``Final`` alone does not make a name a class
    #: variable, so a bare ``Final`` annotation inside a dataclass body becomes a
    #: real **field** — reachable as a constructor keyword, present in
    #: ``dataclasses.fields()`` and part of ``__eq__``. A caller could then hand in
    #: its own key set. ``ClassVar`` is what actually excludes it from the fields.
    _ALLOWED_KEYS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema_version",
            "tenant_id",
            "account_id",
            "cloud_provider",
            "environment",
            "region",
            "zone",
            "namespace",
            "resource_group",
            "compute_group",
            "resource_class",
            "action_type",
            "magnitude_before",
            "requested_magnitude",
            "max_permitted_magnitude",
            "max_permitted_delta",
        }
    )
    _REQUIRED_KEYS: ClassVar[frozenset[str]] = frozenset(
        {
            "tenant_id",
            "account_id",
            "cloud_provider",
            "action_type",
            "magnitude_before",
            "requested_magnitude",
            "max_permitted_magnitude",
            "max_permitted_delta",
        }
    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExecutionTargetScope":
        """Strict canonical deserializer. ``requested_delta`` is derived, never accepted."""

        if not isinstance(data, Mapping):
            raise ExactTypeError(
                "execution target scope data must be a mapping",
                _Reason.UNSUPPORTED_EXACT_TYPE,
            )
        keys = set(data)
        unknown = keys - cls._ALLOWED_KEYS
        if unknown:
            raise CanonicalFieldError(
                f"unknown execution-target-scope field(s): {sorted(unknown)}",
                _Reason.UNKNOWN_FIELD,
            )
        missing = cls._REQUIRED_KEYS - keys
        if missing:
            reason = (
                _Reason.MISSING_ACCOUNT_BINDING
                if "account_id" in missing
                else _Reason.MALFORMED_CANONICAL_FIELD
            )
            raise CanonicalFieldError(
                f"missing execution-target-scope field(s): {sorted(missing)}", reason
            )
        return cls(
            schema_version=data.get("schema_version", EXECUTION_TARGET_SCOPE_SCHEMA_VERSION),
            tenant_id=data["tenant_id"],
            account_id=data["account_id"],
            cloud_provider=data["cloud_provider"],
            environment=data.get("environment"),
            region=data.get("region"),
            zone=data.get("zone"),
            namespace=data.get("namespace"),
            resource_group=data.get("resource_group"),
            compute_group=data.get("compute_group"),
            resource_class=data.get("resource_class"),
            action_type=data["action_type"],
            magnitude_before=data["magnitude_before"],
            requested_magnitude=data["requested_magnitude"],
            max_permitted_magnitude=data["max_permitted_magnitude"],
            max_permitted_delta=data["max_permitted_delta"],
        )


@dataclass(frozen=True)
class PolicyTargetBindingReference:
    """A reference to the policy that bounds one :class:`ExecutionTargetScope`.

    A **reference**, not a resolution. Phase 5A never asks Policy Authority whether this
    policy exists, is current, or was issued by this issuer — it checks that the reference
    is well-formed, that it binds this exact scope by digest, and that its bounds agree
    with the scope's. :attr:`trust_state` is fixed at ``PRESENT_BUT_NOT_TRUST_VERIFIED``.
    """

    policy_id: str
    policy_version: str
    policy_artifact_digest: str
    policy_issuer: str
    policy_key_id: str
    #: Binds this reference to one exact scope. A binding for a different target simply
    #: will not match, so a policy cannot be transplanted onto another account or cluster.
    target_scope_digest: str
    max_permitted_magnitude: int
    max_permitted_delta: int
    #: The carried policy signature, matching the repository's existing convention of
    #: carrying a signature alongside its algorithm and key id. Never verified here.
    policy_signature: str
    policy_signature_algorithm: str
    binding_digest: str
    schema_version: str = POLICY_TARGET_BINDING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_nfc_text("schema_version", self.schema_version)
        if self.schema_version != POLICY_TARGET_BINDING_SCHEMA_VERSION:
            raise PolicyTargetBindingError(
                f"schema_version must be {POLICY_TARGET_BINDING_SCHEMA_VERSION!r}",
                _Reason.UNSUPPORTED_SCHEMA_VERSION,
            )
        require_canonical_identifier("policy_id", self.policy_id)
        require_canonical_identifier("policy_version", self.policy_version)
        require_canonical_digest("policy_artifact_digest", self.policy_artifact_digest)
        require_canonical_identifier("policy_issuer", self.policy_issuer)
        require_canonical_identifier("policy_key_id", self.policy_key_id)
        require_canonical_digest("target_scope_digest", self.target_scope_digest)
        require_nfc_text("policy_signature", self.policy_signature)
        require_canonical_identifier(
            "policy_signature_algorithm", self.policy_signature_algorithm
        )
        for name in ("max_permitted_magnitude", "max_permitted_delta"):
            value = getattr(self, name)
            # Exact, not ``isinstance``, and for the same reason as ``verified.py:339``.
            # These two ceilings are the only bound the builder enforces the request
            # against: ``candidate.py:620`` compares them with ``!=`` and
            # ``candidate.py:678`` with ``>``, and ``>`` hands the *subclass* operand
            # priority through its reflected ``__lt__``. An ``int`` subclass lying in
            # both admits a magnitude the signed binding caps far lower, with
            # ``binding_digest`` unmoved, because the canonical payload renders the
            # subclass to the honest number. The type is the only place the difference
            # survives. ``bool`` needs no separate clause: it is not ``int`` exactly.
            if type(value) is not int or value < 0:
                raise PolicyTargetBindingError(
                    f"{name} must be an int >= 0 (got {value!r})",
                    _Reason.MALFORMED_CANONICAL_FIELD,
                )
        require_canonical_digest("binding_digest", self.binding_digest)

        expected = canonical_digest(self.binding_payload())
        if self.binding_digest != expected:
            raise PolicyTargetBindingError(
                "binding_digest does not equal the digest of the canonical binding payload",
                _Reason.MALFORMED_POLICY_TARGET_BINDING,
            )

    @property
    def trust_state(self) -> EvidenceTrustState:
        """Always ``PRESENT_BUT_NOT_TRUST_VERIFIED``. A property, so it cannot be set."""

        return PHASE_5A_TRUST_STATE

    def binding_payload(self) -> dict[str, Any]:
        """The canonical binding body. Excludes the signature, which cannot cover itself."""

        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_artifact_digest": self.policy_artifact_digest,
            "policy_issuer": self.policy_issuer,
            "policy_key_id": self.policy_key_id,
            "target_scope_digest": self.target_scope_digest,
            "max_permitted_magnitude": self.max_permitted_magnitude,
            "max_permitted_delta": self.max_permitted_delta,
            "policy_signature_algorithm": self.policy_signature_algorithm,
        }

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self.binding_payload(),
            "policy_signature": self.policy_signature,
            "binding_digest": self.binding_digest,
            "trust_state": self.trust_state.value,
        }

    def digest(self) -> str:
        return canonical_digest(self.to_canonical_dict())

    #: ``ClassVar``, not ``Final``: ``Final`` alone does not make a name a class
    #: variable, so a bare ``Final`` annotation inside a dataclass body becomes a
    #: real **field** — reachable as a constructor keyword, present in
    #: ``dataclasses.fields()`` and part of ``__eq__``. A caller could then hand in
    #: its own key set. ``ClassVar`` is what actually excludes it from the fields.
    _ALLOWED_KEYS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema_version",
            "policy_id",
            "policy_version",
            "policy_artifact_digest",
            "policy_issuer",
            "policy_key_id",
            "target_scope_digest",
            "max_permitted_magnitude",
            "max_permitted_delta",
            "policy_signature",
            "policy_signature_algorithm",
            "binding_digest",
        }
    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PolicyTargetBindingReference":
        """Strict canonical deserializer. ``trust_state`` is derived, never accepted."""

        if not isinstance(data, Mapping):
            raise ExactTypeError(
                "policy target binding data must be a mapping",
                _Reason.UNSUPPORTED_EXACT_TYPE,
            )
        keys = set(data)
        unknown = keys - cls._ALLOWED_KEYS
        if unknown:
            reason = (
                _Reason.FORGED_TRUST_STATE
                if {"trust_state", "verified", "trusted", "authentic"} & unknown
                else _Reason.UNKNOWN_FIELD
            )
            raise CanonicalFieldError(
                f"unknown policy-target-binding field(s): {sorted(unknown)}", reason
            )
        missing = cls._ALLOWED_KEYS - {"schema_version"} - keys
        if missing:
            raise CanonicalFieldError(
                f"missing policy-target-binding field(s): {sorted(missing)}",
                _Reason.MALFORMED_CANONICAL_FIELD,
            )
        return cls(
            schema_version=data.get("schema_version", POLICY_TARGET_BINDING_SCHEMA_VERSION),
            policy_id=data["policy_id"],
            policy_version=data["policy_version"],
            policy_artifact_digest=data["policy_artifact_digest"],
            policy_issuer=data["policy_issuer"],
            policy_key_id=data["policy_key_id"],
            target_scope_digest=data["target_scope_digest"],
            max_permitted_magnitude=data["max_permitted_magnitude"],
            max_permitted_delta=data["max_permitted_delta"],
            policy_signature=data["policy_signature"],
            policy_signature_algorithm=data["policy_signature_algorithm"],
            binding_digest=data["binding_digest"],
        )


@dataclass(frozen=True)
class PolicyTargetBindingReferenceV2:
    """The **complete Policy Authority coordinate** the bounding policy lives at.

    Why this exists beside :class:`PolicyTargetBindingReference` rather than inside it
    -----------------------------------------------------------------------------------
    5B-0B measured that a Phase 5A binding *cannot name a coordinate*: three of the six
    components are absent from it, and its fourth, ``policy_artifact_digest``, requires a
    ``sha256:`` prefix no Policy Authority digest carries. So a verified policy proof could
    not be reconciled against the candidate it accompanied — one genuine proof verified
    alongside any candidate whatsoever, including one whose binding named a different policy
    entirely. That is ADR residual R-4, and closing it is what this type is for.

    Widening the existing binding in place was measured against carrying this beside it: it
    moves **two** of Phase 5A's ten pinned digests where an additive field moves **one**, and
    one is the floor — every field of a candidate enters its digest payload, so no in-candidate
    binding can move none (5B-1 D-5B1-1). The existing binding also keeps doing work this type
    does not: it carries the bounds the builder checks against the target scope.

    What it still does not establish
    ---------------------------------
    Nothing about authenticity. This is a *reference* in exactly the sense the Phase 5A type
    is: the coordinate is **named**, never resolved. No registry is consulted, no signature is
    checked, no issuer is trusted and no instant is evaluated — Phase 5A has no resolver, no
    port to call one through, and no clock. :attr:`trust_state` is fixed at
    ``PRESENT_BUT_NOT_TRUST_VERIFIED`` for that reason. What the candidate gains is the
    *ability* to be reconciled against a verified policy proof, which Phase 5B-0B performs.

    Two digest namespaces on one class
    -----------------------------------
    :attr:`policy_content_digest` and :attr:`policy_body_digest` are **bare** lowercase 64-hex
    Policy Authority digests, validated by
    :func:`~.canonical.require_policy_authority_digest`. :attr:`target_scope_digest` and
    :attr:`binding_digest` are ``sha256:``-prefixed Phase 5A digests. Each is checked by its
    own predicate and the two are never interchanged or converted (D-5B1-4).

    The content/body equality, re-asserted here
    --------------------------------------------
    The authority's issuance path enforces ``coordinate.content_digest ==
    policy_body_digest``; its resolution path does not re-enforce it (ADR residual R-3). The
    two symbol names are deliberately not written here: this package must contain no
    executable-looking reference to a policy resolver, and ``tests/test_non_reachability.py``
    scans for exactly that. A coordinate that named one
    body while the signature covered another would be reconcilable against a proof about
    neither, so this boundary refuses the divergence rather than carrying it — the same
    refusal 5B-0B makes on its own artifact.
    """

    # --- the coordinate: all six components, none optional, none defaulted --------------
    policy_family: str
    policy_id: str
    policy_version: str
    policy_content_digest: str
    policy_scope: str
    #: May be empty, and only because the authority's own global tenant is the empty string.
    #: It is never *omitted*: a coordinate with no tenant component is not a coordinate.
    policy_tenant_id: str
    # --- the content binding the issuance signature covers (D-5B0B-2) -------------------
    policy_body_digest: str
    # --- who issued it, and under which key ---------------------------------------------
    issuing_authority_id: str
    key_id: str
    signature_alg: str
    #: Binds this coordinate to one exact execution target scope, exactly as the Phase 5A
    #: binding does. A coordinate that named no scope could be transplanted onto any target.
    target_scope_digest: str
    binding_digest: str
    schema_version: str = POLICY_TARGET_BINDING_V2_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_nfc_text("schema_version", self.schema_version)
        if self.schema_version != POLICY_TARGET_BINDING_V2_SCHEMA_VERSION:
            raise PolicyTargetBindingError(
                f"schema_version must be {POLICY_TARGET_BINDING_V2_SCHEMA_VERSION!r}",
                _Reason.UNSUPPORTED_SCHEMA_VERSION,
            )
        for name in (
            "policy_family",
            "policy_id",
            "policy_version",
            "policy_scope",
            "issuing_authority_id",
            "key_id",
            "signature_alg",
        ):
            require_canonical_identifier(name, getattr(self, name))
        # The one component that may legitimately be empty — and only empty, never absent.
        tenant = require_nfc_text("policy_tenant_id", self.policy_tenant_id, allow_empty=True)
        if tenant != tenant.strip():
            raise PolicyTargetBindingError(
                "policy_tenant_id must not carry leading or trailing whitespace",
                _Reason.NON_CANONICAL_IDENTIFIER,
            )
        for name in ("policy_content_digest", "policy_body_digest"):
            require_policy_authority_digest(name, getattr(self, name))
        require_canonical_digest("target_scope_digest", self.target_scope_digest)
        require_canonical_digest("binding_digest", self.binding_digest)

        if self.policy_content_digest != self.policy_body_digest:
            raise PolicyTargetBindingError(
                "policy_content_digest must equal policy_body_digest: issuance enforces the "
                "equality and resolution does not re-enforce it (ADR residual R-3), so a "
                "coordinate naming a body its signature never covered is refused here",
                _Reason.MALFORMED_POLICY_COORDINATE_BINDING,
            )

        expected = canonical_digest(self.coordinate_payload())
        if self.binding_digest != expected:
            raise PolicyTargetBindingError(
                "binding_digest does not equal the digest of the canonical coordinate payload",
                _Reason.MALFORMED_POLICY_COORDINATE_BINDING,
            )

    @property
    def trust_state(self) -> EvidenceTrustState:
        """Always ``PRESENT_BUT_NOT_TRUST_VERIFIED``. A property, so it cannot be set.

        Carrying a complete coordinate is not resolving it. Phase 5A still verifies nothing.
        """

        return PHASE_5A_TRUST_STATE

    def coordinate_payload(self) -> dict[str, Any]:
        """The canonical body :attr:`binding_digest` covers. Excludes the digest itself."""

        return {
            "schema_version": self.schema_version,
            "policy_family": self.policy_family,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_content_digest": self.policy_content_digest,
            "policy_scope": self.policy_scope,
            "policy_tenant_id": self.policy_tenant_id,
            "policy_body_digest": self.policy_body_digest,
            "issuing_authority_id": self.issuing_authority_id,
            "key_id": self.key_id,
            "signature_alg": self.signature_alg,
            "target_scope_digest": self.target_scope_digest,
        }

    def policy_coordinate(self) -> dict[str, Any]:
        """The six coordinate components alone, for a consumer that reconciles them.

        Returned as a plain mapping, deliberately: assembling the authority's own
        ``PolicyCoordinate`` here would mean Phase 5A importing the Policy Authority, and
        Phase 5A depends on neither authority. The consumer that resolves this coordinate is
        the one that owns that dependency.
        """

        return {name: getattr(self, name) for name in POLICY_COORDINATE_COMPONENTS}

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self.coordinate_payload(),
            "binding_digest": self.binding_digest,
            "trust_state": self.trust_state.value,
        }

    def digest(self) -> str:
        return canonical_digest(self.to_canonical_dict())

    #: ``ClassVar``, not ``Final`` — see the note on the sibling type for why the distinction
    #: is load-bearing rather than stylistic.
    _ALLOWED_KEYS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema_version",
            "policy_family",
            "policy_id",
            "policy_version",
            "policy_content_digest",
            "policy_scope",
            "policy_tenant_id",
            "policy_body_digest",
            "issuing_authority_id",
            "key_id",
            "signature_alg",
            "target_scope_digest",
            "binding_digest",
        }
    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PolicyTargetBindingReferenceV2":
        """Strict canonical deserializer. ``trust_state`` is derived, never accepted."""

        if not isinstance(data, Mapping):
            raise ExactTypeError(
                "policy coordinate binding data must be a mapping",
                _Reason.UNSUPPORTED_EXACT_TYPE,
            )
        keys = set(data)
        unknown = keys - cls._ALLOWED_KEYS
        if unknown:
            reason = (
                _Reason.FORGED_TRUST_STATE
                if {"trust_state", "verified", "trusted", "authentic", "resolved"} & unknown
                else _Reason.UNKNOWN_FIELD
            )
            raise CanonicalFieldError(
                f"unknown policy-coordinate-binding field(s): {sorted(unknown)}", reason
            )
        missing = cls._ALLOWED_KEYS - {"schema_version"} - keys
        if missing:
            raise CanonicalFieldError(
                f"missing policy-coordinate-binding field(s): {sorted(missing)}",
                _Reason.MALFORMED_POLICY_COORDINATE_BINDING,
            )
        return cls(
            schema_version=data.get(
                "schema_version", POLICY_TARGET_BINDING_V2_SCHEMA_VERSION
            ),
            policy_family=data["policy_family"],
            policy_id=data["policy_id"],
            policy_version=data["policy_version"],
            policy_content_digest=data["policy_content_digest"],
            policy_scope=data["policy_scope"],
            policy_tenant_id=data["policy_tenant_id"],
            policy_body_digest=data["policy_body_digest"],
            issuing_authority_id=data["issuing_authority_id"],
            key_id=data["key_id"],
            signature_alg=data["signature_alg"],
            target_scope_digest=data["target_scope_digest"],
            binding_digest=data["binding_digest"],
        )
