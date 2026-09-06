"""Front-door seam 1: the studio's activation root (FD-1, FD-5).

The Constitution screen's preflight needs an ``ActivationRoot``. This deployment
composes one from the constitution authority's own deny-by-default parts and a
durable sqlite policy registry, and holds no key material:

* the signer refuses every act (there is no key; nothing can be issued);
* the signature verifier and the approval verifier are the authority's
  ``DenyAll`` implementations (nothing verifies, nothing is approved);
* the registry is ``SqlitePolicyRegistry`` (Posture B) at the configured path under
  the writable runtime volume, with the constitution family's own codec.

So preflight reports its real result over that registry, and issuance and activation
refuse. The root is immutable after construction. Seam 2 (FD-6) adds the Authority
screen's read-only, tenant-bound view over the same registry instance. Nothing here
grants, authorizes, signs, activates or executes.
"""
from __future__ import annotations

from typing import Any

__all__ = ["RefusingPolicySigner", "AgentConstitutionArtifactCodec", "SigningRefused",
           "open_studio_policy_registry", "build_studio_activation_root",
           "build_studio_activation_root_over", "ReadOnlyTenantBoundRegistry"]


class SigningRefused(RuntimeError):
    """Raised by the refusing signer: this deployment holds no key material."""

    code = "GOVERNANCE_STUDIO_P3E_SIGNING_REFUSED"


class RefusingPolicySigner:
    """The ``PolicySigner`` shape with no key. Every ``sign`` refuses."""

    authority_id = "governance-studio-private-hosted/unconfigured-authority"
    key_id = "none"
    signature_alg = "none"

    def sign(self, payload: bytes) -> bytes:
        raise SigningRefused("signing is refused: the studio holds no key material and issues nothing")


class AgentConstitutionArtifactCodec:
    """The constitution family's registry codec: the canonical structure both ways.

    ``encode`` is the authority's canonical projection of the artifact and ``decode``
    the authority's strict typed decoder; a record of any other adapter or type is a
    storage integrity failure, not an absent record.
    """

    def __init__(self) -> None:
        from ugence_agent_constitution_policy import (
            AGENT_CONSTITUTION_ADAPTER_ID,
            AGENT_CONSTITUTION_POLICY_TYPE,
            AgentConstitutionPolicy,
        )

        self.adapter_id = AGENT_CONSTITUTION_ADAPTER_ID
        self._policy_type = AGENT_CONSTITUTION_POLICY_TYPE
        self._cls = AgentConstitutionPolicy

    def encode(self, policy: object) -> Any:
        from ugence_policy_authority import PolicyAuthorityRequestError, to_canonical_obj

        if type(policy) is not self._cls:
            raise PolicyAuthorityRequestError(
                f"{type(policy).__name__!r} is not an agent-constitution artifact")
        return to_canonical_obj(policy, path="$")

    def decode(self, *, adapter_id: str, policy_type: str, canonical: Any) -> object:
        from ugence_policy_authority import PolicyAuthorityRequestError, decode_dataclass

        if adapter_id != self.adapter_id or policy_type != self._policy_type:
            raise PolicyAuthorityRequestError(
                f"this registry holds agent-constitution artifacts only; refusing "
                f"{adapter_id!r}/{policy_type!r}")
        return decode_dataclass(self._cls, canonical, path="$")


def open_studio_policy_registry(path: str, *, production_mode: bool) -> Any:
    """The one durable policy registry this deployment opens (Posture B), once."""
    from ugence_policy_authority import SqlitePolicyRegistry

    return SqlitePolicyRegistry(path, codec=AgentConstitutionArtifactCodec(),
                                production_mode=production_mode)


def build_studio_activation_root_over(registry: Any) -> Any:
    """The root the studio context receives, over an already opened registry.
    Deny-by-default throughout; no key."""
    from ugence_agent_constitution_activation import build_activation_root
    from ugence_policy_authority import DenyAllApprovalVerifier, DenyAllSignatureVerifier

    return build_activation_root(
        registry=registry,
        signer=RefusingPolicySigner(),
        signature_verifier=DenyAllSignatureVerifier(),
        approval_verifier=DenyAllApprovalVerifier(),
    )


def build_studio_activation_root(path: str, *, production_mode: bool) -> Any:
    """Open the registry at ``path`` and build the root over it (seam 1 alone)."""
    return build_studio_activation_root_over(
        open_studio_policy_registry(path, production_mode=production_mode))


class ReadOnlyTenantBoundRegistry:
    """Front-door seam 2 (FD-6): the Authority screen's view of the registry.

    Exactly the four reads the screen makes, over the same registry instance the
    activation root holds, bound to one tenant: an identity or coordinate of another
    tenant is refused with the authority's own request error, and a record whose
    coordinate carries another tenant is never returned. There is no append of any
    kind on this object; the studio cannot reach one through it.
    """

    def __init__(self, registry: Any, *, tenant_id: str) -> None:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        self._registry = registry
        self._tenant = tenant_id

    @property
    def tenant_id(self) -> str:
        return self._tenant

    def _refuse_tenant(self, tenant: str, what: str) -> None:
        from ugence_policy_authority import PolicyAuthorityRequestError

        if tenant != self._tenant:
            raise PolicyAuthorityRequestError(
                f"cross-tenant read refused: this deployment displays tenant {self._tenant!r} "
                f"and the {what} names another tenant")

    def _bound(self, records):
        return tuple(r for r in records if getattr(r.coordinate, "tenant_id", None) == self._tenant)

    def issued_records_for_identity(self, *, policy_family: str, policy_id: str, scope: str,
                                    tenant_id: str):
        self._refuse_tenant(tenant_id, "policy identity")
        return self._bound(self._registry.issued_records_for_identity(
            policy_family=policy_family, policy_id=policy_id, scope=scope, tenant_id=tenant_id))

    def get_issued(self, coordinate: Any):
        self._refuse_tenant(getattr(coordinate, "tenant_id", None), "coordinate")
        record = self._registry.get_issued(coordinate)
        return record if record is not None and record.coordinate.tenant_id == self._tenant else None

    def revocations_for(self, coordinate: Any):
        self._refuse_tenant(getattr(coordinate, "tenant_id", None), "coordinate")
        return tuple(self._registry.revocations_for(coordinate))

    def supersessions_for(self, coordinate: Any):
        self._refuse_tenant(getattr(coordinate, "tenant_id", None), "coordinate")
        return tuple(self._registry.supersessions_for(coordinate))
