"""
Healthcare taxonomies — configurable, NON-exhaustive classifications.

These enums are deliberately a *starting configuration*, not a claim of legal
completeness. A deploying hospital replaces/extends them (and the category
sensitivity sets) to match its own information-governance policy, jurisdiction,
and data model. Nothing here encodes a legal determination.
"""

from __future__ import annotations

from enum import Enum


class Operation(str, Enum):
    """Patient-data operations governed by the pilot."""

    READ = "READ"
    SUMMARIZE = "SUMMARIZE"
    SEARCH = "SEARCH"
    REDACT = "REDACT"
    DISCLOSE = "DISCLOSE"
    EXPORT = "EXPORT"
    BULK_EXPORT = "BULK_EXPORT"


class Purpose(str, Enum):
    """Purpose-of-use for the access request."""

    TREATMENT = "treatment"
    PAYMENT = "payment"
    OPERATIONS = "healthcare_operations"
    PATIENT_ACCESS = "patient_requested_access"
    RESEARCH = "research"
    QUALITY_REVIEW = "quality_review"
    LEGAL = "legal_or_regulatory"
    MARKETING = "marketing"
    UNSPECIFIED = "unspecified"


class Role(str, Enum):
    """Actor role (human or AI)."""

    TREATING_CLINICIAN = "treating_clinician"
    CONSULTING_CLINICIAN = "consulting_clinician"
    NURSE = "nurse"
    BILLING_STAFF = "billing_staff"
    MEDICAL_RECORDS_STAFF = "medical_records_staff"
    RESEARCHER = "researcher"
    HOSPITAL_ADMIN = "hospital_administrator"
    EXTERNAL_PARTNER = "external_partner"
    PATIENT = "patient"
    AI_CLINICAL_SUMMARIZER = "ai_clinical_summarizer"
    AI_BILLING_AGENT = "ai_billing_agent"
    AI_RESEARCH_AGENT = "ai_research_agent"
    UNKNOWN_ACTOR = "unknown_actor"


# Roles that are AI automations (for audit / posture, not authorization by itself).
AI_ROLES = frozenset({
    Role.AI_CLINICAL_SUMMARIZER,
    Role.AI_BILLING_AGENT,
    Role.AI_RESEARCH_AGENT,
})

# Roles expected to carry a verified clinician identity.
CLINICIAN_ROLES = frozenset({
    Role.TREATING_CLINICIAN,
    Role.CONSULTING_CLINICIAN,
    Role.NURSE,
})


class DataCategory(str, Enum):
    """Category of patient data requested. NON-exhaustive; hospital-configurable."""

    DEMOGRAPHIC = "demographic"
    APPOINTMENT = "appointment"
    DIAGNOSIS = "diagnosis"
    MEDICATION = "medication"
    LABORATORY = "laboratory"
    IMAGING = "imaging"
    PROCEDURE = "procedure"
    BILLING = "billing"
    CLINICAL_NOTE = "clinical_note"
    PSYCH_BEHAVIORAL = "psychiatric_behavioral_narrative"
    REPRODUCTIVE_HEALTH = "reproductive_health"
    HIV_INFECTIOUS = "hiv_infectious_disease_sensitive"
    GENOMIC = "genomic"
    IDENTITY_DOCUMENT = "identity_document"
    AUTH_CREDENTIAL = "authentication_credential"
    FULL_MEDICAL_RECORD = "full_medical_record"


# Restricted narrative / specially-protected categories (configurable).
RESTRICTED_CATEGORIES = frozenset({
    DataCategory.PSYCH_BEHAVIORAL,
    DataCategory.REPRODUCTIVE_HEALTH,
    DataCategory.HIV_INFECTIOUS,
    DataCategory.GENOMIC,
})

# Categories that must never be served as data by this boundary (hard block).
PROHIBITED_CATEGORIES = frozenset({
    DataCategory.AUTH_CREDENTIAL,
})

# Categories that are direct identifiers (relevant to de-identification checks).
DIRECT_IDENTIFIER_CATEGORIES = frozenset({
    DataCategory.DEMOGRAPHIC,
    DataCategory.IDENTITY_DOCUMENT,
})

# Categories implied by a FULL_MEDICAL_RECORD request (expanded for min-necessary).
_FULL_RECORD_EXPANSION = frozenset(
    c for c in DataCategory
    if c not in (DataCategory.FULL_MEDICAL_RECORD, DataCategory.AUTH_CREDENTIAL)
)


def expand_full_record(categories: frozenset) -> frozenset:
    """Expand FULL_MEDICAL_RECORD into concrete categories (never credentials)."""
    if DataCategory.FULL_MEDICAL_RECORD in categories:
        return (categories - {DataCategory.FULL_MEDICAL_RECORD}) | _FULL_RECORD_EXPANSION
    return categories


class RecipientType(str, Enum):
    """Who receives the data."""

    INTERNAL = "internal"
    PATIENT = "patient"
    THIRD_PARTY = "third_party"
    EXTERNAL_PARTNER = "external_partner"
    UNKNOWN = "unknown"


class DestinationClass(str, Enum):
    """Classification of the destination system."""

    INTERNAL = "internal"
    APPROVED_EXTERNAL = "approved_external"
    UNAPPROVED_EXTERNAL = "unapproved_external"
    UNKNOWN = "unknown"


class ConsentState(str, Enum):
    """Consent posture for the requested use. The POLICY BOOK decides whether
    consent is required for a given (purpose, action); this enum only records
    the observed state — it encodes no legal conclusion."""

    PRESENT = "present"
    ABSENT = "absent"
    WITHDRAWN = "withdrawn"
    NOT_REQUIRED = "not_required"
    UNKNOWN = "unknown"
