"""
Deterministic healthcare criticality derivation + minimum-necessary policy.

The classifier derives criticality and hard-block signals ONLY from request
content and registered metadata. Caller-declared facts may PROMOTE criticality
but are never sufficient to downgrade it, and a caller-declared risk/criticality
label is ignored entirely.

Precedence (safest first):
    1. hard-block conditions      → CRITICAL + hard-block capability token(s);
    2. missing material facts      → UNKNOWN (conservative review/deny);
    3. critical conditions         → CRITICAL (SOURCE_OF_TRUTH);
    4. bounded/reversible internal → NON_CRITICAL (BASELINE);
    5. otherwise                   → UNKNOWN (conservative).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from agentic.healthcare.request import HealthcareAccessRequest
from agentic.healthcare.taxonomy import (
    AI_ROLES,
    CLINICIAN_ROLES,
    ConsentState,
    DataCategory,
    DIRECT_IDENTIFIER_CATEGORIES,
    DestinationClass,
    Operation,
    Purpose,
    PROHIBITED_CATEGORIES,
    RESTRICTED_CATEGORIES,
    RecipientType,
    Role,
    expand_full_record,
)

# Record count above which a request is treated as bulk regardless of the flag.
BULK_RECORD_THRESHOLD = 50

# ---- Hard-block capability tokens (routed through the generic forbidden layer) --
HB_CREDENTIAL = "phi.credential_access"
HB_BULK_EXPORT_UNAPPROVED = "phi.bulk_identifiable_export_unapproved"
HB_EXPORT_UNAPPROVED_DEST = "phi.export_unapproved_destination"
HB_CROSS_TENANT = "phi.cross_tenant_unapproved"
HB_NO_ACTOR = "identity.no_actor_established"
HB_UNAUTHORIZED_CLINICIAN = "identity.unauthorized_clinician"
HB_CONSENT_WITHDRAWN = "consent.withdrawn_bypass"

ALL_HARD_BLOCK_TOKENS: Tuple[str, ...] = (
    HB_CREDENTIAL, HB_BULK_EXPORT_UNAPPROVED, HB_EXPORT_UNAPPROVED_DEST,
    HB_CROSS_TENANT, HB_NO_ACTOR, HB_UNAUTHORIZED_CLINICIAN, HB_CONSENT_WITHDRAWN,
)

_READ_LIKE = frozenset({
    Operation.READ, Operation.SUMMARIZE, Operation.SEARCH, Operation.REDACT,
})
_EXPORT_LIKE = frozenset({Operation.EXPORT, Operation.BULK_EXPORT})


@dataclass(frozen=True)
class CriticalityDerivation:
    """Result of deterministic criticality derivation."""

    signal: str  # "critical" | "non_critical" | "unknown"
    facts: Dict[str, Any]
    hard_block_capabilities: Tuple[str, ...]
    basis: Tuple[str, ...]

    @property
    def hard_blocked(self) -> bool:
        return bool(self.hard_block_capabilities)


def _is_bulk(request: HealthcareAccessRequest) -> bool:
    return (
        request.operation == Operation.BULK_EXPORT
        or request.bulk
        or request.record_count > BULK_RECORD_THRESHOLD
    )


def _is_external(request: HealthcareAccessRequest) -> bool:
    return (
        request.recipient_type in (RecipientType.THIRD_PARTY,
                                   RecipientType.EXTERNAL_PARTNER)
        or request.destination_class in (DestinationClass.APPROVED_EXTERNAL,
                                         DestinationClass.UNAPPROVED_EXTERNAL)
        or request.external_side_effect
    )


def _is_cross_tenant(request: HealthcareAccessRequest) -> bool:
    if request.cross_tenant:
        return True
    return bool(
        request.patient_tenant_id
        and request.patient_tenant_id != request.tenant_id
    )


def derive_criticality(request: HealthcareAccessRequest) -> CriticalityDerivation:
    """Derive criticality, hard blocks, and rule-matching facts deterministically."""
    requested = frozenset(request.requested_categories)
    expanded = expand_full_record(requested)

    # "restricted" for criticality/consent purposes means an EXPLICITLY requested
    # restricted narrative. A FULL_MEDICAL_RECORD request is handled by its own
    # `full_record` critical signal and by minimum-necessary field reduction
    # (which excludes restricted narratives) — expanding it to "restricted" would
    # wrongly force consent-review on every full-record min-necessary request.
    explicit_restricted = any(c in RESTRICTED_CATEGORIES for c in requested)
    has_restricted = explicit_restricted
    has_prohibited = any(c in PROHIBITED_CATEGORIES for c in requested)
    full_record = DataCategory.FULL_MEDICAL_RECORD in requested
    identifiable = any(c in DIRECT_IDENTIFIER_CATEGORIES for c in expanded) or full_record

    is_export = request.operation in _EXPORT_LIKE
    is_disclose = request.operation == Operation.DISCLOSE
    is_read_like = request.operation in _READ_LIKE
    bulk = _is_bulk(request)
    external = _is_external(request)
    cross_tenant = _is_cross_tenant(request)
    unapproved_dest = (
        request.destination_class == DestinationClass.UNAPPROVED_EXTERNAL
        or (external and request.destination_class == DestinationClass.UNKNOWN)
    )
    no_actor = not (request.actor_id and request.actor_id.strip())
    research_identifiable = (
        request.purpose == Purpose.RESEARCH and not request.deidentified
    )

    # ---- rule-matching facts (also used for audit provenance) --------------
    facts: Dict[str, Any] = {
        "restricted_category_requested": has_restricted,
        "explicit_restricted_request": explicit_restricted,
        "prohibited_category_requested": has_prohibited,
        "full_record_requested": full_record,
        "identifiable": identifiable,
        "is_export": is_export,
        "is_disclose": is_disclose,
        "is_read_like": is_read_like,
        "bulk": bulk,
        "external_recipient": external,
        "cross_tenant": cross_tenant,
        "destination_approved": request.destination_approved,
        "destination_unapproved": unapproved_dest,
        "research_identifiable": research_identifiable,
        "research_deidentified": request.purpose == Purpose.RESEARCH and request.deidentified,
        "research_authorized": request.research_authorization,
        "identity_verified": request.identity_verified,
        "own_record": request.own_record,
        "patient_self_access": request.actor_role == Role.PATIENT and request.own_record,
        "purpose_unspecified": request.purpose == Purpose.UNSPECIFIED,
        "consent_present": request.consent_state == ConsentState.PRESENT,
        "consent_absent": request.consent_state == ConsentState.ABSENT,
        "consent_withdrawn": request.consent_state == ConsentState.WITHDRAWN,
        "consent_unknown": request.consent_state == ConsentState.UNKNOWN,
        "consent_not_required": request.consent_state == ConsentState.NOT_REQUIRED,
        "unknown_actor_role": request.actor_role == Role.UNKNOWN_ACTOR,
        "no_actor_identity": no_actor,
        "is_ai_actor": request.actor_role in AI_ROLES,
        # Boolean role/purpose facts for human-policy rule matching.
        f"actor_role:{request.actor_role.value}": True,
        f"purpose:{request.purpose.value}": True,
    }

    # Caller-declared facts may only be ADDED (promotion inputs); reserved
    # control keys are stripped so a caller cannot self-classify.
    for k, v in dict(request.declared_facts).items():
        if k in ("hc_critical", "hc_non_critical"):
            continue
        facts.setdefault(f"declared_{k}", v)

    basis: List[str] = []
    hard_blocks: List[str] = []

    # ---- 1. Hard blocks ----------------------------------------------------
    if no_actor:
        hard_blocks.append(HB_NO_ACTOR)
        basis.append("hard_block:no_actor_identity")
    if has_prohibited:
        hard_blocks.append(HB_CREDENTIAL)
        basis.append("hard_block:credential_category")
    if request.actor_role in CLINICIAN_ROLES and not request.identity_verified:
        hard_blocks.append(HB_UNAUTHORIZED_CLINICIAN)
        basis.append("hard_block:unauthorized_clinician_identity")
    if cross_tenant and not request.destination_approved:
        hard_blocks.append(HB_CROSS_TENANT)
        basis.append("hard_block:cross_tenant_unapproved")
    if request.consent_state == ConsentState.WITHDRAWN and (is_disclose or is_export):
        hard_blocks.append(HB_CONSENT_WITHDRAWN)
        basis.append("hard_block:consent_withdrawn_bypass")
    if is_export and unapproved_dest:
        if bulk and not request.deidentified:
            hard_blocks.append(HB_BULK_EXPORT_UNAPPROVED)
            basis.append("hard_block:bulk_identifiable_export_unapproved")
        else:
            hard_blocks.append(HB_EXPORT_UNAPPROVED_DEST)
            basis.append("hard_block:export_unapproved_destination")

    # suspected reclassification (a read-like op carrying export/exfiltration
    # indicators, or a model advisory challenge). Advisory → escalation only.
    suspected_reclassification = bool(
        (is_read_like and external and (bulk or request.record_count > BULK_RECORD_THRESHOLD))
        or request.model_flags_reclassification
    )
    facts["suspected_reclassification"] = suspected_reclassification

    if hard_blocks:
        facts["hc_critical"] = True
        facts["missing_material_facts"] = False
        return CriticalityDerivation(
            signal="critical", facts=facts,
            hard_block_capabilities=tuple(dict.fromkeys(hard_blocks)),
            basis=tuple(basis))

    # ---- 2. Record missing material facts (for audit + conservative floor) -
    #   Recorded here but NOT yet dispositive: an unambiguously CRITICAL action
    #   (step 3) stays critical even with a missing fact — the missing fact adds
    #   a review reason, it does not erase the classification. Only when the
    #   action is otherwise unclassifiable does "missing" force conservative
    #   UNKNOWN (step 4).
    sensitive = (
        has_restricted or is_disclose or is_export or external
        or cross_tenant or full_record
    )
    missing_reasons: List[str] = []
    if request.purpose == Purpose.UNSPECIFIED and sensitive:
        missing_reasons.append("missing:purpose_on_sensitive")
    if request.consent_state == ConsentState.UNKNOWN and (
        is_disclose or is_export or has_restricted
    ):
        missing_reasons.append("missing:consent_on_sensitive")
    if (is_disclose or is_export) and request.destination_class == DestinationClass.UNKNOWN:
        missing_reasons.append("missing:destination_on_release")
    facts["missing_material_facts"] = bool(missing_reasons)
    basis.extend(missing_reasons)

    # ---- 3. Critical (takes precedence over a missing fact) ----------------
    critical_reasons: List[str] = []
    if is_disclose or is_export:
        critical_reasons.append("critical:release_operation")
    if has_restricted:
        critical_reasons.append("critical:restricted_category")
    if external:
        critical_reasons.append("critical:external_recipient")
    if cross_tenant:
        critical_reasons.append("critical:cross_tenant")
    if full_record:
        critical_reasons.append("critical:full_record")
    if research_identifiable:
        critical_reasons.append("critical:identifiable_research")
    if request.consent_state == ConsentState.ABSENT and (
        is_disclose or is_export or has_restricted
    ):
        critical_reasons.append("critical:consent_absent_sensitive")
    if critical_reasons:
        facts["hc_critical"] = True
        basis.extend(critical_reasons)
        return CriticalityDerivation(
            signal="critical", facts=facts,
            hard_block_capabilities=(), basis=tuple(basis))

    # ---- 4. Missing material facts (and not critical) → conservative UNKNOWN
    if missing_reasons:
        return CriticalityDerivation(
            signal="unknown", facts=facts,
            hard_block_capabilities=(), basis=tuple(basis))

    # ---- 5. Non-critical (bounded, reversible, internal) -------------------
    bounded_purpose = request.purpose in (
        Purpose.TREATMENT, Purpose.PAYMENT, Purpose.OPERATIONS,
        Purpose.PATIENT_ACCESS, Purpose.QUALITY_REVIEW, Purpose.LEGAL,
    )
    if (
        is_read_like and not external and not cross_tenant
        and not has_restricted and not full_record
        and request.destination_class == DestinationClass.INTERNAL
        and bounded_purpose
    ):
        facts["hc_non_critical"] = True
        basis.append("non_critical:bounded_internal_access")
        return CriticalityDerivation(
            signal="non_critical", facts=facts,
            hard_block_capabilities=(), basis=tuple(basis))

    # ---- 5. Otherwise → conservative UNKNOWN ------------------------------
    basis.append("unknown:unclassified_context")
    return CriticalityDerivation(
        signal="unknown", facts=facts,
        hard_block_capabilities=(), basis=tuple(basis))


# =============================================================================
# Minimum-necessary permitted categories (configurable domain policy)
# =============================================================================

# Clinical category set (excludes restricted narratives + credentials).
_CLINICAL_BASE = frozenset({
    DataCategory.DEMOGRAPHIC, DataCategory.APPOINTMENT, DataCategory.DIAGNOSIS,
    DataCategory.MEDICATION, DataCategory.LABORATORY, DataCategory.IMAGING,
    DataCategory.PROCEDURE, DataCategory.CLINICAL_NOTE,
})

_BILLING_SCOPE = frozenset({
    DataCategory.DEMOGRAPHIC, DataCategory.APPOINTMENT, DataCategory.BILLING,
    DataCategory.PROCEDURE, DataCategory.DIAGNOSIS,
})

# De-identified research scope: clinical facts without direct identifiers or
# restricted narratives.
_RESEARCH_DEID_SCOPE = frozenset({
    DataCategory.DIAGNOSIS, DataCategory.MEDICATION, DataCategory.LABORATORY,
    DataCategory.PROCEDURE, DataCategory.IMAGING,
})

# Patient's own-record scope (their record, minus credentials).
_PATIENT_SCOPE = frozenset(
    c for c in DataCategory
    if c not in (DataCategory.AUTH_CREDENTIAL, DataCategory.FULL_MEDICAL_RECORD)
)


def minimum_necessary_categories(
    role: Role, purpose: Purpose, operation: Operation,
) -> frozenset:
    """Return the permitted category set for a (role, purpose) — configurable.

    Conservative default: demographic + appointment only. A treating clinician
    for treatment may also see restricted narratives; an AI summarizer may not.
    """
    # Treating clinician (human) for treatment — broadest clinical view.
    if role == Role.TREATING_CLINICIAN and purpose == Purpose.TREATMENT:
        return _CLINICAL_BASE | RESTRICTED_CATEGORIES

    if role in (Role.CONSULTING_CLINICIAN, Role.NURSE,
                Role.AI_CLINICAL_SUMMARIZER) and purpose == Purpose.TREATMENT:
        return _CLINICAL_BASE

    if role in (Role.BILLING_STAFF, Role.AI_BILLING_AGENT) and purpose == Purpose.PAYMENT:
        return _BILLING_SCOPE

    if role in (Role.RESEARCHER, Role.AI_RESEARCH_AGENT) and purpose == Purpose.RESEARCH:
        return _RESEARCH_DEID_SCOPE

    if role == Role.PATIENT and purpose == Purpose.PATIENT_ACCESS:
        return _PATIENT_SCOPE

    if role == Role.MEDICAL_RECORDS_STAFF and purpose in (
        Purpose.OPERATIONS, Purpose.PATIENT_ACCESS, Purpose.LEGAL,
    ):
        return _CLINICAL_BASE | {DataCategory.BILLING}

    # Conservative default.
    return frozenset({DataCategory.DEMOGRAPHIC, DataCategory.APPOINTMENT})
