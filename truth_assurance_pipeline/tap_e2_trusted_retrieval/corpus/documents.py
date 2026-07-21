"""
Synthetic enterprise corpus for TAP-E2 (NEW; no TAP-E1 prompt reused).

Documents span policies, SOPs, manuals, API docs, contracts, technical specs, design
docs, and regulatory text. Each document is chunked into sentence-level evidence units
with structured annotations (authority, effective year, supersession, conflict
claim keys, entities).

HONESTY: synthetic and author-written for this study; annotations are author-assigned.
A positive retrieval result is mechanism/construction validation on synthetic text, not
evidence of real-world retrieval quality.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import (
    AuthorityLevel as A, Document, DocumentType as DT, EvidenceUnit, ExtractionMethod,
)

_UNITS: List[EvidenceUnit] = []
_DOCS: List[Document] = []


def _doc(doc_id, title, dtype, authority, year, units_spec):
    units = []
    for i, spec in enumerate(units_spec, start=1):
        text = spec["text"]
        u = EvidenceUnit(
            unit_id=f"{doc_id}#u{i}", doc_id=doc_id, text=text,
            location=spec.get("loc", f"section {i}"),
            doc_type=dtype, authority=spec.get("authority", authority),
            effective_year=spec.get("year", year),
            superseded_by=spec.get("superseded_by"),
            claim_key=spec.get("claim_key"), claim_value=spec.get("claim_value"),
            entities=tuple(spec.get("entities", ())),
            extraction_method=spec.get("extraction", ExtractionMethod.SENTENCE_SPLIT))
        units.append(u)
        _UNITS.append(u)
    d = Document(doc_id, title, dtype, authority, year, tuple(units))
    _DOCS.append(d)


# --- Data retention (current official) --------------------------------------
_doc("POL-RET-2025", "Data Retention Policy", DT.POLICY, A.OFFICIAL_POLICY, 2025, [
    {"text": "Customer personal data is retained for 24 months after account closure.",
     "loc": "3.1", "claim_key": "retention_customer_data", "claim_value": "24 months",
     "entities": ["customer personal data"]},
    {"text": "After the retention period expires, customer records must be permanently deleted.",
     "loc": "3.2", "entities": ["customer records"]},
    {"text": "Backup copies of customer data are excluded from the standard retention window.",
     "loc": "3.3", "entities": ["customer data", "backup"]},
])

# --- Data retention (OLD, deprecated) ---------------------------------------
_doc("POL-RET-2021", "Data Retention Policy (2021, superseded)", DT.POLICY, A.DEPRECATED, 2021, [
    {"text": "Customer personal data is retained for 12 months after account closure.",
     "loc": "3.1", "claim_key": "retention_customer_data", "claim_value": "12 months",
     "superseded_by": "POL-RET-2025#u1", "entities": ["customer personal data"]},
])

# --- GDPR regulatory ---------------------------------------------------------
_doc("REG-GDPR", "GDPR Article 17 Summary", DT.REGULATORY, A.REGULATORY, 2018, [
    {"text": "Personal data must be erased without undue delay when it is no longer necessary for its purpose.",
     "loc": "Art.17(1)", "entities": ["personal data"]},
    {"text": "Data subjects have the right to request deletion of their personal data.",
     "loc": "Art.17(1)(a)", "entities": ["personal data", "data subject"]},
])

# --- Access control SOP ------------------------------------------------------
_doc("SOP-ACCESS", "Access Control Standard Operating Procedure", DT.SOP, A.OFFICIAL_POLICY, 2025, [
    {"text": "Granting administrator access requires manager approval and multi-factor authentication.",
     "loc": "2.1", "claim_key": "admin_access_requirement",
     "claim_value": "manager approval + MFA", "entities": ["administrator access"]},
    {"text": "Access reviews are performed quarterly for all privileged accounts.",
     "loc": "2.4", "entities": ["privileged accounts"]},
    {"text": "Contractor accounts are disabled automatically after 90 days of inactivity.",
     "loc": "2.6", "entities": ["contractor accounts"]},
])

# --- Password policy (current official) -------------------------------------
_doc("POL-PW-2025", "Password Policy", DT.POLICY, A.OFFICIAL_POLICY, 2025, [
    {"text": "User passwords must be at least 12 characters long.",
     "loc": "1.1", "claim_key": "password_min_length", "claim_value": "12",
     "entities": ["password"]},
    {"text": "Passwords must be rotated every 180 days.",
     "loc": "1.2", "entities": ["password"]},
])

# --- Security standard (regulatory, conflicts on password length) -----------
_doc("REG-SEC-STD", "External Security Standard", DT.REGULATORY, A.REGULATORY, 2025, [
    {"text": "Account passwords shall be a minimum of 14 characters.",
     "loc": "5.2", "claim_key": "password_min_length", "claim_value": "14",
     "entities": ["password"]},
    {"text": "Multi-factor authentication is mandatory for all remote access.",
     "loc": "5.5", "entities": ["multi-factor authentication", "remote access"]},
])

# --- API documentation (reference) ------------------------------------------
_doc("API-DOC", "Public API Reference", DT.API_DOC, A.REFERENCE, 2026, [
    {"text": "The API enforces a rate limit of 100 requests per minute per API key.",
     "loc": "rate-limits", "claim_key": "api_rate_limit", "claim_value": "100/min",
     "entities": ["API", "rate limit"]},
    {"text": "Requests that exceed the rate limit receive an HTTP 429 response.",
     "loc": "rate-limits", "entities": ["rate limit"]},
    {"text": "The default request timeout is 30 seconds.",
     "loc": "timeouts", "claim_key": "api_timeout", "claim_value": "30s",
     "entities": ["timeout"]},
    {"text": "Failed webhook deliveries are retried up to five times with exponential backoff.",
     "loc": "webhooks", "entities": ["webhook"]},
])

# --- Vendor contract (contract) ---------------------------------------------
_doc("CONTRACT-VENDOR", "Vendor Master Services Agreement", DT.CONTRACT, A.OFFICIAL_POLICY, 2024, [
    {"text": "Either party may terminate this agreement with 30 days written notice.",
     "loc": "12.1", "claim_key": "vendor_termination_notice", "claim_value": "30 days",
     "entities": ["termination"]},
    {"text": "The vendor's aggregate liability is capped at the fees paid in the preceding 12 months.",
     "loc": "14.2", "entities": ["liability", "vendor"]},
    {"text": "The vendor must notify the customer of any data breach within 72 hours.",
     "loc": "9.3", "entities": ["data breach", "vendor"]},
])

# --- Encryption technical spec ----------------------------------------------
_doc("SPEC-ENCRYPT", "Encryption Technical Specification", DT.TECH_SPEC, A.REFERENCE, 2025, [
    {"text": "Data at rest is encrypted using AES-256.",
     "loc": "2", "claim_key": "encryption_at_rest", "claim_value": "AES-256",
     "entities": ["encryption", "data at rest"]},
    {"text": "Data in transit is protected with TLS 1.3.",
     "loc": "3", "entities": ["encryption", "data in transit", "TLS"]},
])

# --- Incident response manual ------------------------------------------------
_doc("MAN-INCIDENT", "Incident Response Manual", DT.MANUAL, A.REFERENCE, 2025, [
    {"text": "A postmortem must be published within five business days of an incident.",
     "loc": "4.2", "claim_key": "postmortem_deadline", "claim_value": "5 business days",
     "entities": ["postmortem", "incident"]},
    {"text": "Severity-1 incidents require an on-call engineer to respond within 15 minutes.",
     "loc": "3.1", "entities": ["incident", "on-call"]},
])

# --- Backup SOP --------------------------------------------------------------
_doc("SOP-BACKUP", "Backup and Recovery SOP", DT.SOP, A.OFFICIAL_POLICY, 2025, [
    {"text": "Production databases are backed up daily and retained for 35 days.",
     "loc": "2.1", "claim_key": "backup_retention", "claim_value": "35 days",
     "entities": ["backup", "database"]},
    {"text": "A restore test is performed monthly to verify backup integrity.",
     "loc": "2.5", "entities": ["backup", "restore"]},
])

# --- Deployment design doc (DRAFT, not authoritative) -----------------------
_doc("DESIGN-DEPLOY", "Blue-Green Deployment Design (draft)", DT.DESIGN_DOC, A.DRAFT, 2026, [
    {"text": "This design proposes a blue-green deployment to achieve zero-downtime releases.",
     "loc": "1", "entities": ["deployment", "blue-green"]},
    {"text": "The proposal has not yet been approved and is subject to change.",
     "loc": "1.1", "entities": ["deployment"]},
])

# --- Audit logging policy ----------------------------------------------------
_doc("POL-AUDIT", "Audit Logging Policy", DT.POLICY, A.OFFICIAL_POLICY, 2025, [
    {"text": "Audit logs are retained for one year and stored in immutable storage.",
     "loc": "2.2", "claim_key": "audit_log_retention", "claim_value": "1 year",
     "entities": ["audit logs"]},
    {"text": "Access to audit logs is restricted to the security team.",
     "loc": "2.4", "entities": ["audit logs", "security team"]},
])

# --- Scratch notes (INCOMPLETE provenance -> distractors) -------------------
# location intentionally empty so attached provenance is incomplete; the provenance
# filter (baseline D+) must drop these.
_doc("SCRATCH-NOTES", "Unsourced scratch notes", DT.DESIGN_DOC, A.DRAFT, None, [
    {"text": "Someone mentioned customer data might be kept for 6 months, unverified.",
     "loc": "", "entities": ["customer data"]},
    {"text": "Rumor: the rate limit could be raised to 500 requests per minute soon.",
     "loc": "", "entities": ["rate limit"]},
])


DOCUMENTS: Tuple[Document, ...] = tuple(_DOCS)
UNITS: Tuple[EvidenceUnit, ...] = tuple(_UNITS)


def units() -> Tuple[EvidenceUnit, ...]:
    return UNITS


def documents() -> Tuple[Document, ...]:
    return DOCUMENTS


def unit_ids() -> Tuple[str, ...]:
    return tuple(u.unit_id for u in UNITS)
