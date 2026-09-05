"""The composition root (`ACC-IA-2`): wiring, not authority.

``build_activation_root`` assembles, in one construction, everything the first
genuine issuance needs wired together: the registry, the adapter registry with
this family guard-registered, the signer, the signature verifier, and the
always-required approval verifier. Every act the assembled root performs is a
call into ``ugence_policy_authority.api`` or into the two constitution
distributions' surfaces — the root defines no signing, approval,
canonicalization, registry or resolution semantics of its own.

Custody stays outside (`ACC-IA-2`). The signer and both verifiers arrive
**already constructed**, typed to the authority's existing protocols; this
package cannot mint, read or persist key material, and its own suite proves
that over the source with an AST and import scan. There is no default for any
trust dependency: an incompletely wired deployment fails to construct, never
quietly composes.

The `ACC-S1-Q3` family-collision guard runs on **every** path: once here at
construction, through ``with_agent_constitution_adapter`` (hosted by the
conformance package's composition module, which the ruled scope names as the
required seam), and again inside ``build_constitution_resolver`` whenever a
resolver is built. A registry in which this family does not answer exactly once
fails before any request is served.

There is deliberately no revocation seam here. Revocation remains the Policy
Authority's own signed act under its own entitlement; a root that could revoke
would be an authority, not an orchestration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Mapping, Optional, Tuple

from ugence_agent_constitution_conformance import (
    PolicyAuthorityConstitutionResolver,
    build_constitution_resolver,
)
from ugence_agent_constitution_conformance.composition import (
    with_agent_constitution_adapter,
)
from ugence_policy_authority.api import (
    AdapterRegistry,
    ApprovalEvidenceRef,
    IssuedPolicyRecord,
    PolicyCoordinate,
    issue_policy,
)

from .errors import ActivationCompositionError, ActivationRequestError
from .preflight import PreflightReport, preflight_issuance
from .receipts import ActivationReceipt, IssuanceReceipt
from .reference_map import populate_reference_map

__all__ = ["ActivationRoot", "build_activation_root"]


class ActivationRoot:
    """One wired deployment: preflight, issuance, activation, resolver assembly.

    Immutable after construction: the configured trust dependencies are not
    rebindable, for the same reason the conformance resolver's are not.
    Construct through :func:`build_activation_root`, which validates every seam.
    """

    __slots__ = (
        "_registry",
        "_adapters",
        "_signer",
        "_signature_verifier",
        "_approval_verifier",
    )

    def __init__(
        self,
        *,
        registry: object,
        adapters: AdapterRegistry,
        signer: object,
        signature_verifier: object,
        approval_verifier: object,
    ) -> None:
        object.__setattr__(self, "_registry", registry)
        object.__setattr__(self, "_adapters", adapters)
        object.__setattr__(self, "_signer", signer)
        object.__setattr__(self, "_signature_verifier", signature_verifier)
        object.__setattr__(self, "_approval_verifier", approval_verifier)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"ActivationRoot is immutable; cannot set {name!r}")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"ActivationRoot is immutable; cannot delete {name!r}")

    # ------------------------------------------------------------------
    # Preflight (mutation-free)
    # ------------------------------------------------------------------
    def preflight_issuance(
        self,
        *,
        policy: object,
        record_id: str,
        approval: ApprovalEvidenceRef,
        as_of: datetime,
        expected_reference_tenant_id: Optional[str] = None,
    ) -> PreflightReport:
        """Dry-run every pre-signing check against this root's configured trust."""

        return preflight_issuance(
            policy=policy,
            record_id=record_id,
            approval=approval,
            approval_verifier=self._approval_verifier,
            adapters=self._adapters,
            as_of=as_of,
            expected_reference_tenant_id=expected_reference_tenant_id,
        )

    # ------------------------------------------------------------------
    # Issuance (the authority's act, orchestrated)
    # ------------------------------------------------------------------
    def issue_constitution(
        self,
        *,
        policy: object,
        record_id: str,
        approval: ApprovalEvidenceRef,
        issued_at: datetime,
        expected_reference_tenant_id: Optional[str] = None,
    ) -> IssuanceReceipt:
        """Issue one exact constitution version through ``issue_policy``.

        Every check, the signature, and the registry append are the authority's
        own; this method contributes wiring and derives the receipt. On any
        refusal the authority's typed error propagates unchanged and no receipt
        exists.
        """

        record = issue_policy(
            policy=policy,
            record_id=record_id,
            approval=approval,
            approval_verifier=self._approval_verifier,
            signer=self._signer,
            registry=self._registry,
            adapters=self._adapters,
            issued_at=issued_at,
            expected_reference_tenant_id=expected_reference_tenant_id,
        )
        return _issuance_receipt(record)

    # ------------------------------------------------------------------
    # Activation (reference-map derivation, receipted)
    # ------------------------------------------------------------------
    def activate_constitution(
        self,
        *,
        coordinate: PolicyCoordinate,
        activated_at: datetime,
        existing: Optional[Mapping[Tuple[str, str], PolicyCoordinate]] = None,
    ) -> Tuple[Mapping[Tuple[str, str], PolicyCoordinate], ActivationReceipt]:
        """Derive the governed reference map from the issued record under
        ``coordinate`` and receipt every entry (`ACC-IA-3`).

        Returns ``(reference_map, receipt)``: the merged read-only mapping ready
        to hand to :meth:`constitution_resolver`, and the receipt listing
        exactly the entries this activation derived. Writes no agent, role or
        registry state — the derived mapping is a value the caller composes
        into a resolver, not a stored transition.
        """

        if type(coordinate) is not PolicyCoordinate:
            raise ActivationRequestError(
                "coordinate must be exactly a PolicyCoordinate"
            )
        record = self._registry.get_issued(coordinate)
        if record is None or type(record) is not IssuedPolicyRecord:
            raise ActivationRequestError(
                "no issued record exists under this exact coordinate; activation "
                "derives from an issued record only"
            )
        reference_map = populate_reference_map(
            record=record, adapters=self._adapters, existing=existing
        )
        entries = tuple(
            sorted(
                (record.coordinate.tenant_id, role_ref)
                for role_ref in record.policy.governed_role_refs
            )
        )
        receipt = ActivationReceipt(
            record_id=record.record_id,
            coordinate=record.coordinate,
            activated_entries=entries,
            activated_at=activated_at,
        )
        return reference_map, receipt

    # ------------------------------------------------------------------
    # Resolver assembly (the conformance package's act, orchestrated)
    # ------------------------------------------------------------------
    def constitution_resolver(
        self,
        *,
        reference_map: Mapping[Tuple[str, str], PolicyCoordinate],
    ) -> PolicyAuthorityConstitutionResolver:
        """A resolver over this root's trust and the given mapping.

        Delegates to ``build_constitution_resolver``, so the `ACC-S1-Q3` guard
        runs again on this path too.
        """

        return build_constitution_resolver(
            reference_map=reference_map,
            registry=self._registry,
            signature_verifier=self._signature_verifier,
            approval_verifier=self._approval_verifier,
            adapters=self._adapters,
        )


def build_activation_root(
    *,
    registry: object,
    signer: object,
    signature_verifier: object,
    approval_verifier: object,
    adapters: Optional[AdapterRegistry] = None,
) -> ActivationRoot:
    """Validate every seam, guard-register the family, and return the root.

    No dependency has a default. The signer and both verifiers are shape-checked
    against the authority's protocols here so a mis-wired deployment fails at
    composition; the deny-by-default implementations the authority ships pass
    these checks and then refuse every act, which is the ratified posture for an
    incompletely configured deployment.
    """

    for attribute in ("append_issuance", "get_issued"):
        if not hasattr(registry, attribute):
            raise ActivationCompositionError(
                "registry must implement PolicyRegistry (append_issuance, "
                "get_issued)"
            )
    for attribute in ("authority_id", "key_id", "signature_alg", "sign"):
        if not hasattr(signer, attribute):
            raise ActivationCompositionError(
                "signer must implement PolicySigner; it arrives already "
                "constructed, and no key material is accepted here"
            )
    if signature_verifier is None or not hasattr(signature_verifier, "verify"):
        raise ActivationCompositionError(
            "signature_verifier is required and must implement verify"
        )
    if approval_verifier is None or not hasattr(approval_verifier, "verify_approval"):
        raise ActivationCompositionError(
            "approval_verifier is required and must implement verify_approval; "
            "there is no default"
        )
    if adapters is not None and not isinstance(adapters, AdapterRegistry):
        raise ActivationCompositionError("adapters must be an AdapterRegistry or None")

    return ActivationRoot(
        registry=registry,
        adapters=with_agent_constitution_adapter(adapters),
        signer=signer,
        signature_verifier=signature_verifier,
        approval_verifier=approval_verifier,
    )


def _issuance_receipt(record: IssuedPolicyRecord) -> IssuanceReceipt:
    """Restate an issued record as its key-material-free receipt."""

    return IssuanceReceipt(
        record_id=record.record_id,
        coordinate=record.coordinate,
        policy_body_digest=record.policy_body_digest,
        issuing_authority_id=record.issuing_authority_id,
        key_id=record.key_id,
        signature_alg=record.signature_alg,
        approving_authority_id=record.approving_authority_id,
        approval_ref=record.approval_ref,
        approval_digest=record.approval_digest,
        issued_at=record.issued_at,
    )
