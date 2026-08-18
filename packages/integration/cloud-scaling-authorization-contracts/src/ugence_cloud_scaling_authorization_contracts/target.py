"""``ExecutionTargetScope`` and ``PolicyTargetBindingReference`` — where, and how far.

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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Mapping, Optional

from .canonical import (
    canonical_digest,
    require_canonical_digest,
    require_canonical_identifier,
    require_nfc_text,
)
from .errors import AuthorizationCandidateRejectionReason as _Reason
from .errors import (
    CanonicalFieldError,
    ExactTypeError,
    MagnitudeBoundError,
    PolicyTargetBindingError,
    TargetScopeError,
)
from .identifiers import CANONICAL_ACTION_TYPES
from .trust import PHASE_5A_TRUST_STATE, EvidenceTrustState

__all__ = [
    "EXECUTION_TARGET_SCOPE_SCHEMA_VERSION",
    "POLICY_TARGET_BINDING_SCHEMA_VERSION",
    "ExecutionTargetScope",
    "PolicyTargetBindingReference",
]

EXECUTION_TARGET_SCOPE_SCHEMA_VERSION: Final[str] = "cloud-scaling-execution-target-scope-1"
POLICY_TARGET_BINDING_SCHEMA_VERSION: Final[str] = "cloud-scaling-policy-target-binding-1"


def _require_magnitude(name: str, value: Any) -> int:
    """A non-negative ``int``. ``bool`` is refused — ``True`` is not a capacity."""

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
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
    schema_version: str = EXECUTION_TARGET_SCOPE_SCHEMA_VERSION

    def __post_init__(self) -> None:
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

        for name in ("environment", "region", "zone", "namespace", "compute_group", "resource_class"):
            _optional_identifier(name, getattr(self, name))

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
            "environment": self.environment,
            "region": self.region,
            "zone": self.zone,
            "namespace": self.namespace,
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

    _ALLOWED_KEYS: Final[frozenset[str]] = frozenset(
        {
            "schema_version",
            "tenant_id",
            "account_id",
            "environment",
            "region",
            "zone",
            "namespace",
            "compute_group",
            "resource_class",
            "action_type",
            "magnitude_before",
            "requested_magnitude",
            "max_permitted_magnitude",
            "max_permitted_delta",
        }
    )
    _REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
        {
            "tenant_id",
            "account_id",
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
            environment=data.get("environment"),
            region=data.get("region"),
            zone=data.get("zone"),
            namespace=data.get("namespace"),
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
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
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

    _ALLOWED_KEYS: Final[frozenset[str]] = frozenset(
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
