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
refuse. The root is immutable after construction. Nothing here grants, authorizes,
signs, activates or executes.
"""
from __future__ import annotations

from typing import Any

__all__ = ["RefusingPolicySigner", "AgentConstitutionArtifactCodec", "SigningRefused",
           "build_studio_activation_root"]


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


def build_studio_activation_root(path: str, *, production_mode: bool) -> Any:
    """The root the studio context receives. Deny-by-default throughout; no key."""
    from ugence_agent_constitution_activation import build_activation_root
    from ugence_policy_authority import (
        DenyAllApprovalVerifier,
        DenyAllSignatureVerifier,
        SqlitePolicyRegistry,
    )

    registry = SqlitePolicyRegistry(path, codec=AgentConstitutionArtifactCodec(),
                                    production_mode=production_mode)
    return build_activation_root(
        registry=registry,
        signer=RefusingPolicySigner(),
        signature_verifier=DenyAllSignatureVerifier(),
        approval_verifier=DenyAllApprovalVerifier(),
    )
