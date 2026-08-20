"""The resolution seam — how this package reaches the Policy Authority, and nothing else.

D-5B0B-4, ratified as option (a): policy signatures are verified through the Policy
Authority's own ``PolicyKeyRing``, not through a Trusted Evidence Authority trust anchor.
This module is where that ruling is wired.

What the seam is, and what it deliberately is not
--------------------------------------------------
A :class:`PolicyResolutionPort` is a **narrow** protocol: given an exact coordinate, an
expected reference tenant and an injected instant, return the Policy Authority's own
``PolicyResolution``. It resolves; it decides nothing. Every gate that turns a resolution
into a determination lives in :mod:`.verification`, so a port cannot admit anything on its
own and a port that answers ``RESOLVED`` still faces every check.

This package holds **no keys, no key ring, no registry and no anchor records**. It
introduces no second trust store. A composition root wires
:class:`PolicyAuthorityResolutionPort` with the authority's registry, key ring and adapter
registry, and this package never sees the key material.

What the port pins, and why the knobs are absent
-------------------------------------------------
``resolve_policy`` takes a ``historical_resolution`` rule. The port does **not** expose it:
it pins :data:`~.identifiers.REQUIRED_HISTORICAL_RESOLUTION_RULE` (``DENY_ALWAYS``, the
authority's own fail-closed default). Belt and braces, deliberately — a historical answer is
also refused at admission by the verifier, so even a custom port that returned one cannot
produce a determination. Offering the knob here would create a posture in which a caller
asks for an answer about the past and receives something that looks like an answer about
now.

``approval_verifier`` **is** exposed, and is optional, because the authority treats it that
way: when supplied, the approval proof is re-verified at ``as_of``, so an approval withdrawn
after issuance invalidates resolution; when omitted, the approval bound into the issuance
signature stands. Supplying one is strictly stronger, and a deployment that has an approval
authority should.

Trust-configuration identity
-----------------------------
D-5B0B-1 requires a verified proof to name *the trust configuration the resolution ran
under*. :func:`policy_trust_configuration_digest` computes that identity from the key ring's
registered anchors — key id, authority, tenant binding, entitlements, algorithm, revocation
state and window — together with the adapter ids and the pinned historical rule. It
deliberately digests **no public key bytes**: the identity answers "which trust
configuration", and a rotation that replaces a key under the same id must move the digest,
which it does through the window and revocation state, without this package handling key
material it has no business holding.

A port reports its own digest, so an artifact minted under one trust configuration cannot be
mistaken for one minted under another.

Production postures
--------------------
Two things are refused under ``production_mode=True``, both at construction:

* a **reference-grade port type**, or any subclass of one — subclassing does not change what
  a thing is;
* a port that has not explicitly opted in with ``is_production_authoritative = True``.
  Silence is refusal, so a port that has never considered the question cannot drift into
  production.

A :class:`PolicyAuthorityResolutionPort` standing on the authority's ``InMemoryPolicyRegistry``
declines the opt-in on its own: that registry's own module documents it as reference-grade
rather than production persistence, so a deployment cannot reach a production determination
through it. :class:`DenyAllPolicyResolutionPort` is production-admissible because it can only
refuse.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from ugence_policy_authority.api import (
    AdapterRegistry,
    ApprovalVerifier,
    InMemoryPolicyRegistry,
    PolicyCoordinate,
    PolicyKeyRing,
    PolicyRegistry,
    PolicyResolution,
    PolicyResolutionReason,
    PolicySignatureVerifier,
    resolve_policy,
)

from .canonical import framed_digest
from .errors import PolicyAuthenticityConfigurationError as _ConfigError
from .identifiers import (
    POLICY_TRUST_CONFIGURATION_DIGEST_DOMAIN,
    REQUIRED_HISTORICAL_RESOLUTION_RULE,
    REQUIRED_KEY_ENTITLEMENT,
)

__all__ = [
    "PolicyResolutionPort",
    "PolicyAuthorityResolutionPort",
    "DenyAllPolicyResolutionPort",
    "REFERENCE_GRADE_PORTS",
    "REFERENCE_GRADE_REGISTRIES",
    "policy_trust_configuration_digest",
    "require_production_resolution_port",
]

#: Registry types the Policy Authority documents as reference-grade rather than production
#: persistence. A production port standing on one declines the production opt-in.
REFERENCE_GRADE_REGISTRIES: tuple = (InMemoryPolicyRegistry,)


@runtime_checkable
class PolicyResolutionPort(Protocol):
    """Resolve one exact policy coordinate under configured policy trust, at one instant."""

    #: Must be ``True`` for a port admitted under ``production_mode=True``. Silence refuses.
    is_production_authoritative: bool

    #: The identity of the trust configuration this port resolves under. Bare 64-hex.
    trust_configuration_digest: str

    def resolve_policy_version(
        self,
        *,
        coordinate: PolicyCoordinate,
        expected_reference_tenant_id: str,
        as_of: datetime,
    ) -> PolicyResolution:
        """Return the authority's own resolution. Never a bool, never a bare policy."""
        ...


def policy_trust_configuration_digest(
    *,
    key_ring: object,
    adapters: object,
    approval_verifier_configured: bool,
) -> str:
    """The identity of one policy trust configuration. Bare 64-hex, domain-framed.

    Digests the registered anchors' *governing* attributes and the adapter identities, never
    public key bytes (see this module's docstring). Anchors are sorted by key id so the
    digest is a function of the configuration, not of insertion order.
    """

    keys = getattr(key_ring, "keys", None)
    anchors = []
    if keys is not None:
        for key_id in sorted(keys):
            key = keys[key_id]
            anchors.append(
                {
                    "key_id": key.key_id,
                    "authority_id": key.authority_id,
                    "tenant_id": key.tenant_id,
                    "signature_alg": key.signature_alg,
                    "revoked": bool(key.revoked),
                    "not_before": key.not_before,
                    "not_after": key.not_after,
                    "entitlements": sorted(e.value for e in key.entitlements),
                }
            )
    adapter_ids = sorted(
        adapter.adapter_id for adapter in getattr(adapters, "adapters", ())
    )
    return framed_digest(
        domain=POLICY_TRUST_CONFIGURATION_DIGEST_DOMAIN,
        body={
            "verifier_type": type(key_ring).__name__,
            "anchors": anchors,
            "adapters": list(adapter_ids),
            "required_entitlement": REQUIRED_KEY_ENTITLEMENT.value,
            "historical_resolution": REQUIRED_HISTORICAL_RESOLUTION_RULE.value,
            "approval_verifier_configured": bool(approval_verifier_configured),
        },
    )


class PolicyAuthorityResolutionPort:
    """The one production-grade port: the Policy Authority's own trusted-resolution path.

    Immutable after construction. Rebinding the registry, the key ring or the adapter
    registry is exactly the component swap the production guard exists to prevent, so
    ``__setattr__`` raises.
    """

    __slots__ = ("_registry", "_signature_verifier", "_adapters", "_approval", "_digest")

    def __init__(
        self,
        *,
        registry: PolicyRegistry,
        signature_verifier: PolicySignatureVerifier,
        adapters: AdapterRegistry,
        approval_verifier: Optional[ApprovalVerifier] = None,
    ) -> None:
        if registry is None:
            raise _ConfigError("a policy registry is required; there is no ambient registry")
        if signature_verifier is None:
            raise _ConfigError(
                "a policy signature verifier is required; there is no default key ring, no "
                "ambient trust store and no permissive fallback"
            )
        if not isinstance(adapters, AdapterRegistry):
            raise _ConfigError(
                "adapters must be a Policy Authority AdapterRegistry; family recognition is "
                "the authority's, not this package's"
            )
        for attribute in ("get_issued", "revocations_for"):
            if not hasattr(registry, attribute):
                raise _ConfigError(
                    f"the policy registry must implement {attribute}(...)"
                )
        if not hasattr(signature_verifier, "verify"):
            raise _ConfigError(
                "the policy signature verifier must implement verify(...) -> KeyVerification"
            )
        object.__setattr__(self, "_registry", registry)
        object.__setattr__(self, "_signature_verifier", signature_verifier)
        object.__setattr__(self, "_adapters", adapters)
        object.__setattr__(self, "_approval", approval_verifier)
        object.__setattr__(
            self,
            "_digest",
            policy_trust_configuration_digest(
                key_ring=signature_verifier,
                adapters=adapters,
                approval_verifier_configured=approval_verifier is not None,
            ),
        )

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"PolicyAuthorityResolutionPort is immutable; cannot set {name!r}. Build a new "
            "port instead — rebinding the registry or the key ring after construction is a "
            "trust-store swap."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"PolicyAuthorityResolutionPort is immutable; cannot delete {name!r}"
        )

    @property
    def is_production_authoritative(self) -> bool:
        """``True`` only when nothing in the wiring is documented as reference-grade.

        Today that is one condition: the Policy Authority's ``InMemoryPolicyRegistry`` is
        explicitly reference-grade, process-local and not production persistence, so a port
        standing on one declines the opt-in rather than letting a deployment reach a
        production determination through it.
        """

        return not isinstance(self._registry, REFERENCE_GRADE_REGISTRIES)

    @property
    def trust_configuration_digest(self) -> str:
        return self._digest

    @property
    def approval_verifier_configured(self) -> bool:
        """Whether approval evidence is re-verified at ``as_of``. Bound into the digest."""

        return self._approval is not None

    def resolve_policy_version(
        self,
        *,
        coordinate: PolicyCoordinate,
        expected_reference_tenant_id: str,
        as_of: datetime,
    ) -> PolicyResolution:
        """Delegate to the authority. This method adds no rule and relaxes none."""

        return resolve_policy(
            reference=coordinate,
            expected_reference_tenant_id=expected_reference_tenant_id,
            as_of=as_of,
            registry=self._registry,
            signature_verifier=self._signature_verifier,
            adapters=self._adapters,
            approval_verifier=self._approval,
            historical_resolution=REQUIRED_HISTORICAL_RESOLUTION_RULE,
        )

    def __repr__(self) -> str:
        return (
            "PolicyAuthorityResolutionPort(registry="
            f"{type(self._registry).__name__}, verifier="
            f"{type(self._signature_verifier).__name__}, production_authoritative="
            f"{self.is_production_authoritative})"
        )


class DenyAllPolicyResolutionPort:
    """The ratified deny-all posture: resolves nothing, ever.

    Production-admissible precisely because it can only refuse. It is what a deployment wires
    when policy trust has not been configured yet, so "not configured" fails closed instead of
    reaching for a permissive default.
    """

    __slots__ = ()

    #: Admissible in production: a port that always refuses cannot admit anything.
    is_production_authoritative: bool = True

    @property
    def trust_configuration_digest(self) -> str:
        """The identity of the empty trust configuration. Distinct from any populated one."""

        return policy_trust_configuration_digest(
            key_ring=PolicyKeyRing(),
            adapters=AdapterRegistry(),
            approval_verifier_configured=False,
        )

    def resolve_policy_version(
        self,
        *,
        coordinate: PolicyCoordinate,
        expected_reference_tenant_id: str,
        as_of: datetime,
    ) -> PolicyResolution:
        return PolicyResolution.unresolved(
            PolicyResolutionReason.NOT_FOUND,
            requested_coordinate=coordinate,
            as_of=as_of,
            detail="no policy trust is configured; this port refuses every coordinate",
        )

    def __repr__(self) -> str:
        return "DenyAllPolicyResolutionPort()"


#: Port types this repository documents as reference grade. Refused in production, **including
#: every subclass**. Empty today: the only shipped ports are the Policy Authority port, which
#: judges itself by its registry, and the deny-all port, which can only refuse. The tuple
#: exists so a later reference port has somewhere to be named, and so the production guard's
#: shape does not have to change when one is.
REFERENCE_GRADE_PORTS: tuple = ()


def require_production_resolution_port(port: object) -> object:
    """Refuse a reference-grade or unattested port under production mode.

    Two independent conditions, both fail-closed:

    * a port that **is** a reference-grade port — that type or any subclass of it — is refused
      outright, before the opt-in is consulted. ``isinstance`` is used here deliberately, and
      the reasoning runs opposite to this package's usual exact-type posture: here the class
      is what is being *refused*, so exact-type matching would be the hole rather than the
      guard, and a one-line subclass would walk straight through it;
    * every other port must explicitly opt in with ``is_production_authoritative = True``.
      Silence is refusal.
    """

    if REFERENCE_GRADE_PORTS and isinstance(port, REFERENCE_GRADE_PORTS):
        raise _ConfigError(
            f"{type(port).__name__} is a reference-grade resolution port and cannot reach a "
            "production determination, and neither can a subclass of one"
        )
    if getattr(port, "is_production_authoritative", False) is not True:
        raise _ConfigError(
            "a production PolicyResolutionPort must be production-authoritative "
            "(is_production_authoritative=True). A port standing on the Policy Authority's "
            "reference-grade in-memory registry declines this on its own, and a port that "
            "has never considered the question is refused rather than assumed safe (got "
            f"{type(port).__name__})"
        )
    return port
