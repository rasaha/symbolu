"""Phase 2 - Natural-artifact intake protocol.

Turns a naturally occurring repository artifact (documentation, docstring, comment) into a
pilot-eligible, de-identified, use-case-classified intake record - or fails closed.

This module ADDS a natural-artifact protocol on top of the inherited, read-only shadow-grade controls
(`customer_shadow_readiness.intake`, `customer_shadow_readiness.data_controls`). It does not modify
them. Deterministic, stdlib-only, non-enforcing.

Fail-closed rules (any one rejects the artifact, none is permissive):
  - empty / oversize / malformed          -> inherited intake failure
  - PII / sensitive (restricted class)    -> PROHIBITED_DATA
  - unknown provenance                    -> UNKNOWN_PROVENANCE
  - excluded use case (clinical, trading, -> EXCLUDED_USE_CASE
    permission change, deletion,
    employment, legal, autonomous
    security, ...)
  - no eligible use case can be assigned  -> UNCLASSIFIABLE_USE_CASE

An accepted record carries only what governance needs; the raw text is redacted.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Optional

# Inherited, read-only. Translation only - no decision logic is re-implemented here.
from customer_shadow_readiness import data_controls as dc
from customer_shadow_readiness import intake as csr_intake

# The pilot handles de-identified / permitted data only. Natural repository text is "internal" at
# most; anything the inherited classifier marks "restricted" (PII/PHI/secret markers) is prohibited
# and fails closed under this clearance.
PILOT_CLEARANCE = "internal"

# Provenance the pilot accepts: real repository text not authored for a governance corpus.
ELIGIBLE_SOURCE_KINDS = ("doc", "docstring", "comment")

# Eligible first-pilot use cases (advisory / review only). Order matters: first match wins, with a
# software-engineering default because the host repository is a software governance codebase.
ELIGIBLE_USE_CASES = (
    "enterprise_policy_interpretation",
    "technical_support_review",
    "software_engineering_recommendation_review",
    "cybersecurity_advisory_review",
    "compliance_summary_review",
    "contract_summary_review",
    "procurement_policy_review",
    "it_operations_guidance",
    "customer_communication_quality_review",
)
_DEFAULT_USE_CASE = "software_engineering_recommendation_review"

# Keyword signatures for eligible use-case assignment (deterministic, conservative).
_USE_CASE_MARKERS = [
    ("cybersecurity_advisory_review",
     re.compile(r"\b(security|vulnerab|attack|threat|exploit|cve|hardening|cryptograph|auth)\w*", re.I)),
    ("compliance_summary_review",
     re.compile(r"\b(complian|audit|regulat|control|governance|policy\s+check)\w*", re.I)),
    ("enterprise_policy_interpretation",
     re.compile(r"\b(policy|procedure|standard|guideline|handbook)\w*", re.I)),
    ("it_operations_guidance",
     re.compile(r"\b(deploy|rollback|runbook|incident|operat|monitor|observab)\w*", re.I)),
    ("procurement_policy_review",
     re.compile(r"\b(procure|vendor|supplier|purchase|sourcing)\w*", re.I)),
    ("contract_summary_review",
     re.compile(r"\b(contract|agreement|clause|sla|terms)\w*", re.I)),
    ("technical_support_review",
     re.compile(r"\b(support|troubleshoot|ticket|help\s?desk|faq)\w*", re.I)),
    ("customer_communication_quality_review",
     re.compile(r"\b(customer\s+(email|message|communication)|tone|reply\s+quality)\w*", re.I)),
]

# HARD exclusions. Any match rejects the artifact - the pilot never processes excluded use cases.
_EXCLUDED_MARKERS = re.compile(
    r"\b("
    r"prescrib\w*|diagnos\w*|dosage|clinical\s+trial|patient\s+care|"          # clinical
    r"trade\s+execution|place\s+(an?\s+)?order|buy\s+shares|sell\s+shares|wire\s+transfer|"  # financial/trading
    r"grant\s+(access|permission)|revoke\s+(access|permission)|change\s+role|"  # permission changes
    r"delete\s+(all|production|database)|drop\s+table|irreversible\s+delet|"    # irreversible deletion
    r"terminate\s+employ|fire\s+the\s+employee|hiring\s+decision|"             # employment
    r"legal\s+(ruling|determination|verdict)|adjudicat|"                        # legal determination
    r"auto(nomous)?\s+(remediat|response|block|quarantine)"                     # autonomous security
    r")\b",
    re.I,
)


@dataclass
class NaturalIntakeRecord:
    accepted: bool
    artifact_id: str = ""
    source_path: str = ""
    source_kind: str = ""
    use_case: str = ""
    artifact_class: str = ""
    redacted_text: str = ""
    char_len: int = 0
    reason_codes: List[str] = field(default_factory=list)


def _artifact_id(source_path: str, source_kind: str, text: str) -> str:
    h = hashlib.sha256(f"{source_path}|{source_kind}|{text}".encode()).hexdigest()
    return f"nat-{h[:16]}"


def assign_use_case(text: str) -> Optional[str]:
    """Deterministic eligible use-case assignment. Returns None only if an excluded marker is present
    (caller rejects); otherwise falls back to the software-engineering default because the artifact is
    repository text. Excluded detection is handled separately and takes precedence."""
    for name, rx in _USE_CASE_MARKERS:
        if rx.search(text or ""):
            return name
    return _DEFAULT_USE_CASE


def intake_natural(text: str, source_path: str, source_kind: str) -> NaturalIntakeRecord:
    codes: List[str] = []

    # 1. Provenance must be a known natural-artifact kind from a real repository path.
    if source_kind not in ELIGIBLE_SOURCE_KINDS or not source_path:
        return NaturalIntakeRecord(False, source_path=source_path, source_kind=source_kind,
                                   reason_codes=["INTAKE.UNKNOWN_PROVENANCE"])

    # 2. Hard exclusion check BEFORE anything else - excluded use cases never enter the runtime.
    if _EXCLUDED_MARKERS.search(text or ""):
        return NaturalIntakeRecord(False, source_path=source_path, source_kind=source_kind,
                                   reason_codes=["INTAKE.EXCLUDED_USE_CASE"])

    # 3. Inherited secure intake: bounds, format, classification, permitted-use, redaction.
    #    Fails closed on empty/oversize/malformed and on PII (restricted) under pilot clearance.
    r = csr_intake.intake(text, PILOT_CLEARANCE, output_form="text")
    if not r.accepted:
        # Translate the inherited reason into a pilot-facing prohibited/reject code.
        raw = r.reason_codes[0] if r.reason_codes else "INTAKE.REJECTED"
        if raw.startswith("INTAKE.NOT_PERMITTED"):
            code = "INTAKE.PROHIBITED_DATA"      # restricted/PII class under de-identified clearance
        else:
            code = raw
        return NaturalIntakeRecord(False, source_path=source_path, source_kind=source_kind,
                                   artifact_class=r.artifact_class, reason_codes=[code])

    # 4. Assign an eligible use case (excluded already rejected at step 2).
    use_case = assign_use_case(text)
    if use_case not in ELIGIBLE_USE_CASES:
        return NaturalIntakeRecord(False, source_path=source_path, source_kind=source_kind,
                                   artifact_class=r.artifact_class,
                                   reason_codes=["INTAKE.UNCLASSIFIABLE_USE_CASE"])

    return NaturalIntakeRecord(
        accepted=True,
        artifact_id=_artifact_id(source_path, source_kind, text),
        source_path=source_path,
        source_kind=source_kind,
        use_case=use_case,
        artifact_class=r.artifact_class,
        redacted_text=r.redacted_text,
        char_len=len(text),
        reason_codes=["INTAKE.ACCEPTED"],
    )
