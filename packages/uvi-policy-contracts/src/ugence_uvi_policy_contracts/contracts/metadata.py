"""Policy identity/envelope and immutable digest-bound policy references.

A :class:`PolicyReference` is the only thing an assessment context holds about a
policy: an immutable pointer that binds ``policy_id + family + version +
content_digest``. There are **no floating references** — a reference without a
content digest is rejected, so a consumer can never dereference an ambiguous or
swappable artifact (ADR §23 invariant 5).

A :class:`PolicyArtifactMetadata` is the envelope embedded in every policy
artifact: identity, family, version, content digest, scope, asserted lifecycle
state, effective period, and the issuing/approval/supersession references set by
the Policy Authority. This package **carries** those fields; it does not sign,
approve, issue, or revoke anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ._util import canonical_digest, require_nonempty, require_tzaware, validate_digest
from .enums import PolicyFamily, PolicyLifecycleState, PolicyScope
from .errors import PolicyContractError

__all__ = ["PolicyReference", "PolicyArtifactMetadata"]


@dataclass(frozen=True)
class PolicyReference:
    """An immutable, digest-bound reference to a specific policy version.

    Binds identity, family, version, and a content digest so a bound artifact
    can never be silently swapped or replayed. A ``TENANT``-scoped reference
    carries its ``tenant_id``; a ``GLOBAL`` reference carries none.
    """

    policy_id: str
    policy_family: PolicyFamily
    version: str
    content_digest: str
    scope: PolicyScope = PolicyScope.GLOBAL
    tenant_id: str = ""

    def __post_init__(self) -> None:
        require_nonempty(self.policy_id, "PolicyReference.policy_id")
        require_nonempty(self.version, "PolicyReference.version")
        if not isinstance(self.policy_family, PolicyFamily):
            raise PolicyContractError("PolicyReference.policy_family must be a PolicyFamily")
        if not isinstance(self.scope, PolicyScope):
            raise PolicyContractError("PolicyReference.scope must be a PolicyScope")
        # No floating references: the content digest is mandatory.
        validate_digest(self.content_digest, "PolicyReference.content_digest", required=True)
        _validate_scope_tenant(self.scope, self.tenant_id, "PolicyReference")

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class PolicyArtifactMetadata:
    """The identity/envelope embedded in every UVI policy artifact.

    ``content_digest`` is the authority-attested digest of the policy *content*
    (mandatory — a policy with no content digest is untrusted and rejected). The
    ``lifecycle_state`` is what the artifact asserts about itself; it is carried
    for audit and for the fail-closed binder, and is never trust-verified here.
    """

    policy_id: str
    policy_family: PolicyFamily
    version: str
    content_digest: str
    scope: PolicyScope = PolicyScope.GLOBAL
    tenant_id: str = ""
    lifecycle_state: PolicyLifecycleState = PolicyLifecycleState.DRAFT
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    issuer_ref: str = ""
    approval_ref: str = ""
    supersedes_ref: str = ""
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        require_nonempty(self.policy_id, "PolicyArtifactMetadata.policy_id")
        require_nonempty(self.version, "PolicyArtifactMetadata.version")
        if not isinstance(self.policy_family, PolicyFamily):
            raise PolicyContractError("PolicyArtifactMetadata.policy_family must be a PolicyFamily")
        if not isinstance(self.scope, PolicyScope):
            raise PolicyContractError("PolicyArtifactMetadata.scope must be a PolicyScope")
        if not isinstance(self.lifecycle_state, PolicyLifecycleState):
            raise PolicyContractError(
                "PolicyArtifactMetadata.lifecycle_state must be a PolicyLifecycleState"
            )
        validate_digest(self.content_digest, "PolicyArtifactMetadata.content_digest", required=True)
        _validate_scope_tenant(self.scope, self.tenant_id, "PolicyArtifactMetadata")

        for name in ("effective_from", "effective_to", "created_at"):
            value = getattr(self, name)
            if value is not None:
                require_tzaware(value, f"PolicyArtifactMetadata.{name}")
        if self.effective_from is not None and self.effective_to is not None:
            if not self.effective_from < self.effective_to:
                raise PolicyContractError(
                    "PolicyArtifactMetadata.effective_from must be before effective_to"
                )
        # SUPERSEDED asserts this artifact was replaced; a superseding reference
        # is not knowable from this artifact, but a self-declared supersession
        # (this artifact supersedes a prior one) must name the prior version.
        # We do not force supersedes_ref on SUPERSEDED (that names the successor,
        # which this artifact does not carry).

    def to_reference(self) -> PolicyReference:
        """Derive the immutable digest-bound reference to this artifact."""

        return PolicyReference(
            policy_id=self.policy_id,
            policy_family=self.policy_family,
            version=self.version,
            content_digest=self.content_digest,
            scope=self.scope,
            tenant_id=self.tenant_id,
        )

    def is_effective_at(self, moment: datetime) -> bool:
        """Whether ``moment`` falls within the declared effective period.

        A structural, half-open ``[effective_from, effective_to)`` check only;
        it is **not** a trust or revocation check.
        """

        require_tzaware(moment, "moment")
        if self.effective_from is not None and moment < self.effective_from:
            return False
        if self.effective_to is not None and moment >= self.effective_to:
            return False
        return True

    def canonical_digest(self) -> str:
        return canonical_digest(self)


def _validate_scope_tenant(scope: PolicyScope, tenant_id: str, owner: str) -> None:
    if scope is PolicyScope.TENANT:
        require_nonempty(tenant_id, f"{owner}.tenant_id (required for TENANT scope)")
    elif scope is PolicyScope.GLOBAL:
        if tenant_id:
            raise PolicyContractError(
                f"{owner}.tenant_id must be empty for GLOBAL scope "
                f"(got {tenant_id!r})"
            )
