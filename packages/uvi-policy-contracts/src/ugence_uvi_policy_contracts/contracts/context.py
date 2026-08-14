"""The governed assessment context — the binding seam for one UVI assessment.

An :class:`AssessmentContext` binds the versioned, digest-bound policy context an
assessment is performed under. Placed in this package (rather than the neutral
``governance-contracts`` leaf) because it references :class:`PolicyReference`,
which is a UVI-policy concept — a neutral leaf could not hold it without a
reverse dependency on UVI policy shapes.

Structural invariants enforced here:

* **Mandatory G/D/O.** A context always binds a Geography, a Domain, and an
  Intended-Outcome policy reference, each of the correct family (ADR §15, §6
  precondition). Valuation and Readiness references are optional.
* **No floating references.** Every bound reference is digest-bound (guaranteed
  by :class:`PolicyReference`).
* **Cross-tenant rejection.** A ``TENANT``-scoped reference must belong to the
  context's tenant; a reference for another tenant is rejected. ``GLOBAL``
  references are always admissible. (There is **no** cross-*subject* rejection:
  policies are tenant-scoped, not subject-scoped, so there is no subject
  dimension on a policy to compare against.)
* **Distinct artifacts.** The same ``policy_id`` cannot occupy two slots.
* **Immutability.** ``additional_policy_refs`` is normalized to a real tuple at
  construction (scalar substitutes rejected), so mutating a caller-owned list
  afterward cannot alter the bound context or its ``canonical_digest()``.

Subject binding uses the existing repository convention (plain ``tenant_id`` /
``subject_id``); only cross-tenant consistency is enforced. ``AssessedSystemBinding``
/ ``SubjectContext`` (RA-owned, PR #1425, unmerged) are a **deferred dependency**
and intentionally not defined here (ADR D-14, §16).

Two time inputs are kept deliberately distinct: ``bind_policies``'s mandatory
``as_of`` is *when policy applicability is evaluated*, while ``assessment_window``
records *the period the assessment evidence was drawn from*. ``as_of`` is not
derived from ``assessment_window``, and the policy effective period is not
required to cover the evidence window (evidence freshness is a downstream rule).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_governance_contracts.api import AssessmentWindow

from ._util import (
    canonical_digest,
    coerce_tuple,
    require_nonempty,
    require_tzaware,
    validate_digest,
)
from .enums import AssessmentPurpose, PolicyFamily, PolicyLifecycleState, PolicyScope
from .errors import PolicyContractError
from .metadata import PolicyReference
from .policies import (
    DomainPolicy,
    GeographyPolicy,
    IntendedOutcomePolicy,
    ReadinessPolicy,
    ValuationPolicy,
)

__all__ = ["AssessmentContext"]


@dataclass(frozen=True)
class AssessmentContext:
    """The governed policy context an assessment is performed under."""

    context_id: str
    tenant_id: str
    subject_id: str
    geography_ref: PolicyReference
    domain_ref: PolicyReference
    intended_outcome_ref: PolicyReference
    purpose: AssessmentPurpose = AssessmentPurpose.PRE_ROI_READINESS
    valuation_ref: Optional[PolicyReference] = None
    readiness_ref: Optional[PolicyReference] = None
    additional_policy_refs: tuple[PolicyReference, ...] = ()
    assessment_window: Optional[AssessmentWindow] = None
    created_at: Optional[datetime] = None
    content_digest: str = ""

    def __post_init__(self) -> None:
        require_nonempty(self.context_id, "AssessmentContext.context_id")
        require_nonempty(self.tenant_id, "AssessmentContext.tenant_id")
        require_nonempty(self.subject_id, "AssessmentContext.subject_id")
        if not isinstance(self.purpose, AssessmentPurpose):
            raise PolicyContractError("AssessmentContext.purpose must be an AssessmentPurpose")

        # Mandatory G/D/O references, each of the correct family.
        _require_ref(self.geography_ref, PolicyFamily.GEOGRAPHY, "AssessmentContext.geography_ref")
        _require_ref(self.domain_ref, PolicyFamily.DOMAIN, "AssessmentContext.domain_ref")
        _require_ref(
            self.intended_outcome_ref,
            PolicyFamily.INTENDED_OUTCOME,
            "AssessmentContext.intended_outcome_ref",
        )
        if self.valuation_ref is not None:
            _require_ref(self.valuation_ref, PolicyFamily.VALUATION, "AssessmentContext.valuation_ref")
        if self.readiness_ref is not None:
            _require_ref(self.readiness_ref, PolicyFamily.READINESS, "AssessmentContext.readiness_ref")
        # Normalize the caller's sequence into an immutable tuple, rejecting scalar
        # substitutes, so a later mutation of the caller's list cannot inject an
        # extra / duplicate / cross-family / cross-tenant reference after validation.
        additional = coerce_tuple(self.additional_policy_refs, "AssessmentContext.additional_policy_refs")
        for ref in additional:
            if not isinstance(ref, PolicyReference):
                raise PolicyContractError(
                    "AssessmentContext.additional_policy_refs entries must be PolicyReference"
                )
        object.__setattr__(self, "additional_policy_refs", additional)

        # Cross-tenant rejection + distinct-artifact check over every bound ref.
        seen_ids: set[str] = set()
        for ref in self._all_refs():
            if ref.scope is PolicyScope.TENANT and ref.tenant_id != self.tenant_id:
                raise PolicyContractError(
                    f"cross-tenant policy binding: {ref.policy_id!r} belongs to tenant "
                    f"{ref.tenant_id!r} but the context tenant is {self.tenant_id!r}"
                )
            if ref.policy_id in seen_ids:
                raise PolicyContractError(
                    f"AssessmentContext binds policy_id {ref.policy_id!r} in more than one slot"
                )
            seen_ids.add(ref.policy_id)

        if self.assessment_window is not None and not isinstance(self.assessment_window, AssessmentWindow):
            raise PolicyContractError("AssessmentContext.assessment_window must be an AssessmentWindow")
        if self.created_at is not None:
            require_tzaware(self.created_at, "AssessmentContext.created_at")
        validate_digest(self.content_digest, "AssessmentContext.content_digest", required=False)

    def _all_refs(self) -> tuple[PolicyReference, ...]:
        refs = [self.geography_ref, self.domain_ref, self.intended_outcome_ref]
        if self.valuation_ref is not None:
            refs.append(self.valuation_ref)
        if self.readiness_ref is not None:
            refs.append(self.readiness_ref)
        refs.extend(self.additional_policy_refs)
        return tuple(refs)

    @property
    def policy_refs(self) -> tuple[PolicyReference, ...]:
        """Every bound policy reference, mandatory then optional then extra."""

        return self._all_refs()

    def canonical_digest(self) -> str:
        return canonical_digest(self)

    # ------------------------------------------------------------------ #
    # Fail-closed binder over full artifacts
    # ------------------------------------------------------------------ #
    @classmethod
    def bind_policies(
        cls,
        *,
        context_id: str,
        tenant_id: str,
        subject_id: str,
        geography: GeographyPolicy,
        domain: DomainPolicy,
        intended_outcome: IntendedOutcomePolicy,
        as_of: datetime,
        valuation: Optional[ValuationPolicy] = None,
        readiness: Optional[ReadinessPolicy] = None,
        purpose: AssessmentPurpose = AssessmentPurpose.PRE_ROI_READINESS,
        assessment_window: Optional[AssessmentWindow] = None,
        created_at: Optional[datetime] = None,
    ) -> "AssessmentContext":
        """Build a context from full policy artifacts, **failing closed**.

        ``as_of`` is **mandatory** and keyword-only — the explicit instant at
        which policy applicability is evaluated. It must be a timezone-aware
        ``datetime``; there is no default and it is **never** read from the
        system clock, so binding is deterministic and reproducible. Every bound
        artifact (required *and* any supplied optional Valuation/Readiness) must
        be ``APPROVED_ACTIVE``, belong to the context tenant, and be within its
        declared effective period at ``as_of``; any temporally-invalid or
        inactive artifact fails the binding closed.

        ``as_of`` is distinct from ``assessment_window`` (below) and is **not**
        derived from it: ``as_of`` is *when the policy applies*, whereas
        ``assessment_window`` is *the period the assessment evidence was drawn
        from*. An older evidence window may legitimately be evaluated under a
        policy applicable at ``as_of``; whether that evidence is *fresh enough*
        is a downstream evidence/readiness rule, not a policy-binding rule, and
        this binder deliberately does not require the policy's effective period
        to cover the evidence window.

        This is a *structural* fail-closed gate, **not** a trust check: the
        ``lifecycle_state`` and every ``content_digest`` remain caller-supplied
        structural inputs. The binder never verifies a signature, approval,
        issuance, or revocation, and never resolves a referenced policy body —
        that is Policy-Authority and registry work, out of scope here.
        """

        require_tzaware(as_of, "bind_policies.as_of")

        artifacts = [
            ("geography", geography, GeographyPolicy),
            ("domain", domain, DomainPolicy),
            ("intended_outcome", intended_outcome, IntendedOutcomePolicy),
        ]
        if valuation is not None:
            artifacts.append(("valuation", valuation, ValuationPolicy))
        if readiness is not None:
            artifacts.append(("readiness", readiness, ReadinessPolicy))

        for label, artifact, expected_type in artifacts:
            if not isinstance(artifact, expected_type):
                raise PolicyContractError(
                    f"bind_policies.{label} must be a {expected_type.__name__}"
                )
            meta = artifact.metadata
            if meta.lifecycle_state is not PolicyLifecycleState.APPROVED_ACTIVE:
                raise PolicyContractError(
                    f"bind_policies fails closed: {label} policy {meta.policy_id!r} is "
                    f"{meta.lifecycle_state.value}, not APPROVED_ACTIVE"
                )
            if meta.scope is PolicyScope.TENANT and meta.tenant_id != tenant_id:
                raise PolicyContractError(
                    f"cross-tenant policy binding: {label} policy {meta.policy_id!r} belongs to "
                    f"tenant {meta.tenant_id!r} but the context tenant is {tenant_id!r}"
                )
            if not meta.is_effective_at(as_of):
                raise PolicyContractError(
                    f"bind_policies fails closed: {label} policy {meta.policy_id!r} is not "
                    f"effective at as_of {as_of.isoformat()}"
                )

        return cls(
            context_id=context_id,
            tenant_id=tenant_id,
            subject_id=subject_id,
            geography_ref=geography.reference,
            domain_ref=domain.reference,
            intended_outcome_ref=intended_outcome.reference,
            purpose=purpose,
            valuation_ref=valuation.reference if valuation is not None else None,
            readiness_ref=readiness.reference if readiness is not None else None,
            assessment_window=assessment_window,
            created_at=created_at,
        )


def _require_ref(ref: PolicyReference, family: PolicyFamily, name: str) -> None:
    if not isinstance(ref, PolicyReference):
        raise PolicyContractError(f"{name} must be a PolicyReference")
    if ref.policy_family is not family:
        raise PolicyContractError(
            f"{name} must reference a {family.value} policy (got {ref.policy_family.value})"
        )
