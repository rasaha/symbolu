"""Vocabulary for the hiring policy / compiler / IR layer.

These enums are the *governance* vocabulary used by the Hiring Policy Compiler
(PWC) and the ``HiringWorkflowIR`` — distinct from the finer-grained assessment
ontology (:mod:`ugence_ai_hiring.ontology`). They match the normative JSON
Schemas in ``docs/schemas/`` (see ``HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md``).

The two legacy dimensions are intentionally absent and, moreover, *forbidden*:
``CULTURE_FIT`` is replaced by ``OPERATING_ENVIRONMENT_COMPATIBILITY`` and
``RESILIENCE`` by ``ROLE_SUSTAINABILITY_AND_ADAPTATION``. The compiler rejects a
policy that declares either forbidden name (see :mod:`.compiler`).
"""

from __future__ import annotations

from enum import Enum


class LifecycleStatus(str, Enum):
    """Author → review → approve → publish lifecycle (shared by IR and contract)."""

    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"


class DimensionEmphasis(str, Enum):
    """Relative emphasis hints HR declares per dimension.

    These are *not* raw weights; the compiler normalizes them into weights that
    sum to 1.0. Weight points: PRIMARY=3, SECONDARY=2, SUPPORTING=1.
    """

    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    SUPPORTING = "SUPPORTING"

    @property
    def weight_points(self) -> int:
        return {"PRIMARY": 3, "SECONDARY": 2, "SUPPORTING": 1}[self.value]


class MandatoryGateType(str, Enum):
    """Non-compensatory hard-requirement gate types (ActionGate parity)."""

    REQUIRED_SKILLS = "REQUIRED_SKILLS"
    REQUIRED_CERTIFICATIONS = "REQUIRED_CERTIFICATIONS"
    WORK_AUTHORIZATION = "WORK_AUTHORIZATION"
    SECURITY_CLEARANCE = "SECURITY_CLEARANCE"
    INTERVIEW_COMPLETED = "INTERVIEW_COMPLETED"
    ASSESSMENT_COMPLETED = "ASSESSMENT_COMPLETED"
    REQUIRED_EXPERIENCE = "REQUIRED_EXPERIENCE"


class HiringEvidenceClass(str, Enum):
    """Governance evidence classes referenced by policy gates and requirements.

    Coarser than the assessment :class:`~ugence_ai_hiring.ontology.taxonomy.EvidenceType`;
    this is the admissibility vocabulary the contract/gates reason over.
    """

    RESUME = "RESUME"
    PORTFOLIO = "PORTFOLIO"
    INTERVIEW = "INTERVIEW"
    CODING_ASSESSMENT = "CODING_ASSESSMENT"
    REFERENCE_CHECK = "REFERENCE_CHECK"
    BACKGROUND_CHECK = "BACKGROUND_CHECK"
    CERTIFICATION = "CERTIFICATION"
    EMPLOYMENT_HISTORY = "EMPLOYMENT_HISTORY"


class RuntimeAssuranceCheck(str, Enum):
    """Checks Runtime Assurance runs immediately before any HRIS/ATS write."""

    APPROVALS_VALID = "APPROVALS_VALID"
    REFERENCES_COMPLETE = "REFERENCES_COMPLETE"
    BACKGROUND_CHECK_CURRENT = "BACKGROUND_CHECK_CURRENT"
    OFFER_NOT_EXPIRED = "OFFER_NOT_EXPIRED"
    SALARY_POLICY_SATISFIED = "SALARY_POLICY_SATISFIED"
    REQUISITION_OPEN = "REQUISITION_OPEN"


class GateStatus(str, Enum):
    """Runtime status of a mandatory gate.

    In a compiled IR a gate is a *definition*; its status is the pre-evaluation
    default ``INDETERMINATE`` (fail-closed) until the Decision Authority evaluates
    it against admitted evidence.
    """

    PASSED = "PASSED"
    FAILED = "FAILED"
    INDETERMINATE = "INDETERMINATE"


# Canonical dimension identifiers used by the compiler's default derivation.
DIM_TECHNICAL = "TECHNICAL"
DIM_LEADERSHIP = "LEADERSHIP"
DIM_DOMAIN = "DOMAIN"
DIM_BEHAVIOR = "BEHAVIOR"
DIM_LEARNING = "LEARNING"
DIM_OPERATING_ENVIRONMENT = "OPERATING_ENVIRONMENT_COMPATIBILITY"
DIM_ROLE_SUSTAINABILITY = "ROLE_SUSTAINABILITY_AND_ADAPTATION"

# Dimensions removed from the model. Declaring either is a compile error.
FORBIDDEN_DIMENSIONS: frozenset[str] = frozenset({"CULTURE_FIT", "RESILIENCE"})

# Token substrings that mark a non-human principal in an approval chain.
NON_HUMAN_APPROVER_TOKENS: tuple[str, ...] = (
    "ai",
    "bot",
    "svc",
    "service",
    "system",
    "agent",
    "automation",
)
