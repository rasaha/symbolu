"""Mutation-free preflight (`ACC-IA-4`): every pre-signing check, as a report.

``preflight_issuance`` replays, through public API calls only, the checks
``issue_policy`` runs **before** it signs or touches a registry: artifact
recognition and coordinate derivation, the expected-tenant comparison,
supersession admissibility, the canonical body-digest equalities, lifecycle and
effectivity, and approval verification with the same re-checks the authority
applies to a verifier's answer. It takes no signer and no registry, so it
*cannot* sign or mutate — the guarantee is structural, not behavioural.

Two disclosed differences from the real issuance, both inherent to a dry run:
the check that the approving authority differs from the *issuing* authority
runs only at issuance, because preflight has no signer identity to compare
against; and a verifier consulted twice may lawfully answer differently, so a
passing report is evidence about this instant, never a reservation.

A failed check is a report row, not an exception: the report exists to say what
would refuse. Exceptions are reserved for inputs the call itself cannot accept.
When a prerequisite row fails, dependent rows are omitted rather than guessed —
``ready`` is ``True`` only when every check ran and every check passed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from ugence_policy_authority.api import (
    AdapterRegistry,
    ApprovalEvidenceRef,
    ApprovalVerification,
    ApprovalVerificationStatus,
    PolicyAuthorityError,
)

from .errors import ActivationRequestError

__all__ = ["PreflightCheck", "PreflightReport", "preflight_issuance"]


@dataclass(frozen=True)
class PreflightCheck:
    """One named check: what ran, whether it passed, and a short reason if not."""

    name: str
    ok: bool
    detail: str = ""

    def __post_init__(self) -> None:
        if type(self.name) is not str or not self.name.strip():
            raise ActivationRequestError("PreflightCheck.name must be a non-empty str")
        if type(self.ok) is not bool:
            raise ActivationRequestError("PreflightCheck.ok must be a bool")
        if type(self.detail) is not str:
            raise ActivationRequestError("PreflightCheck.detail must be a str")


@dataclass(frozen=True)
class PreflightReport:
    """The structured outcome of one dry run. A report, never a reservation."""

    checks: Tuple[PreflightCheck, ...]
    policy_body_digest: str = ""

    def __post_init__(self) -> None:
        if type(self.checks) is not tuple or not self.checks:
            raise ActivationRequestError(
                "PreflightReport.checks must be a non-empty tuple"
            )
        for check in self.checks:
            if type(check) is not PreflightCheck:
                raise ActivationRequestError(
                    "every PreflightReport check must be a PreflightCheck"
                )
        if type(self.policy_body_digest) is not str:
            raise ActivationRequestError(
                "PreflightReport.policy_body_digest must be a str"
            )

    @property
    def ready(self) -> bool:
        """Every check ran and passed. Omitted rows can never count as passed."""

        return all(check.ok for check in self.checks)


def _require_tzaware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.tzinfo.utcoffset(value) is None
    ):
        raise ActivationRequestError(
            f"{name} must be a timezone-aware datetime; a naive datetime is never "
            "assumed to be UTC"
        )
    return value


def preflight_issuance(
    *,
    policy: object,
    record_id: str,
    approval: ApprovalEvidenceRef,
    approval_verifier: object,
    adapters: AdapterRegistry,
    as_of: datetime,
    expected_reference_tenant_id: Optional[str] = None,
) -> PreflightReport:
    """Run every pre-signing check and report; sign nothing, store nothing."""

    if type(record_id) is not str or not record_id.strip():
        raise ActivationRequestError("record_id must be a non-empty str")
    if type(approval) is not ApprovalEvidenceRef:
        raise ActivationRequestError(
            "approval must be exactly an ApprovalEvidenceRef"
        )
    if approval_verifier is None or not hasattr(approval_verifier, "verify_approval"):
        raise ActivationRequestError(
            "approval_verifier is required and must implement verify_approval; "
            "there is no default"
        )
    if not isinstance(adapters, AdapterRegistry):
        raise ActivationRequestError("adapters must be an AdapterRegistry")
    _require_tzaware(as_of, "as_of")
    if expected_reference_tenant_id is not None and type(
        expected_reference_tenant_id
    ) is not str:
        raise ActivationRequestError(
            "expected_reference_tenant_id must be a str or None"
        )

    checks: List[PreflightCheck] = []

    # -- artifact recognition and coordinate derivation --------------------
    try:
        descriptor = adapters.describe(policy)
    except PolicyAuthorityError:
        checks.append(
            PreflightCheck(
                name="artifact-recognition",
                ok=False,
                detail="no registered adapter recognizes this artifact",
            )
        )
        return PreflightReport(checks=tuple(checks))
    checks.append(PreflightCheck(name="artifact-recognition", ok=True))
    coordinate = descriptor.coordinate

    # -- expected reference tenant ----------------------------------------
    if expected_reference_tenant_id is not None:
        checks.append(
            PreflightCheck(
                name="reference-tenant",
                ok=coordinate.tenant_id == expected_reference_tenant_id,
                detail=(
                    ""
                    if coordinate.tenant_id == expected_reference_tenant_id
                    else "the artifact's declared tenant is not the expected one"
                ),
            )
        )

    # -- supersession admissibility ---------------------------------------
    checks.append(
        PreflightCheck(
            name="supersession",
            ok=not descriptor.declares_supersession,
            detail=(
                ""
                if not descriptor.declares_supersession
                else "the artifact declares an unstructured supersession "
                "reference, which issuance refuses"
            ),
        )
    )

    # -- canonical body digest and declared-digest equality ----------------
    policy_body_digest = descriptor.body_digest()
    digest_ok = (
        descriptor.declared_content_digest == policy_body_digest
        and coordinate.content_digest == policy_body_digest
    )
    checks.append(
        PreflightCheck(
            name="body-digest",
            ok=digest_ok,
            detail=(
                ""
                if digest_ok
                else "the declared content digest does not bind the canonical body"
            ),
        )
    )

    # -- lifecycle and effectivity at the explicit instant -----------------
    checks.append(
        PreflightCheck(
            name="lifecycle",
            ok=descriptor.lifecycle_is_active,
            detail=(
                ""
                if descriptor.lifecycle_is_active
                else "only an active lifecycle state is issuable"
            ),
        )
    )
    effectivity_ok = descriptor.effective_to is None or as_of < descriptor.effective_to
    checks.append(
        PreflightCheck(
            name="effectivity",
            ok=effectivity_ok,
            detail=(
                ""
                if effectivity_ok
                else "the effective period has already elapsed at this instant"
            ),
        )
    )

    # -- approval verification, with the authority's own re-checks ---------
    checks.append(
        _approval_check(
            approval_verifier=approval_verifier,
            coordinate=coordinate,
            policy_body_digest=policy_body_digest,
            approval=approval,
            as_of=as_of,
        )
    )

    return PreflightReport(
        checks=tuple(checks), policy_body_digest=policy_body_digest
    )


def _approval_check(
    *,
    approval_verifier: object,
    coordinate: object,
    policy_body_digest: str,
    approval: ApprovalEvidenceRef,
    as_of: datetime,
) -> PreflightCheck:
    """Consult the verifier and replay the authority's re-checks on its answer.

    Mirrors the issuance-time defence in depth, minus the one comparison that
    needs a signer identity (the issuing authority may not approve its own
    policy — checked only at issuance, and disclosed above).
    """

    name = "approval"
    try:
        verification = approval_verifier.verify_approval(
            coordinate=coordinate,
            policy_body_digest=policy_body_digest,
            approval=approval,
            as_of=as_of,
        )
    except Exception:
        return PreflightCheck(
            name=name, ok=False, detail="the approval verifier raised instead of answering"
        )

    if type(verification) is not ApprovalVerification:
        return PreflightCheck(
            name=name,
            ok=False,
            detail="the approval verifier did not return an ApprovalVerification",
        )
    if (
        not verification.verified
        or verification.status is not ApprovalVerificationStatus.APPROVED
    ):
        return PreflightCheck(
            name=name, ok=False, detail="approval was not granted for this policy"
        )
    if verification.coordinate != coordinate:
        return PreflightCheck(
            name=name,
            ok=False,
            detail="the verification binds a different policy coordinate",
        )
    if verification.policy_body_digest != policy_body_digest:
        return PreflightCheck(
            name=name,
            ok=False,
            detail="the verification binds a different policy body digest",
        )
    if (
        verification.approval_ref != approval.approval_ref
        or verification.approval_digest != approval.approval_digest
        or verification.approving_authority_id != approval.approving_authority_id
    ):
        return PreflightCheck(
            name=name,
            ok=False,
            detail="the verification does not bind the supplied approval evidence",
        )
    if verification.approved_from is not None and as_of < verification.approved_from:
        return PreflightCheck(
            name=name,
            ok=False,
            detail="the approved period does not yet admit this instant",
        )
    if verification.approved_to is not None and as_of >= verification.approved_to:
        return PreflightCheck(
            name=name,
            ok=False,
            detail="the approved period no longer admits this instant",
        )
    return PreflightCheck(name=name, ok=True)
