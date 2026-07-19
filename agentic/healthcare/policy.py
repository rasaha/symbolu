"""
Healthcare policy fixtures — HumanPolicyBook, ActionCriticalityRegistry, and the
forbidden-capability PolicyResolution.

These are *configuration for the generic engine*, not new engine logic. Hospital
rules live here (and in criticality.py), never inside GovernanceService or
HumanPolicyEngine.

Authority-mode intent:
  * Bounded, reversible internal access (derived NON_CRITICAL) → BASELINE, so the
    model may tighten. Expressed by leaving `authority_mode=None` and letting the
    criticality registry map `hc_non_critical` → BASELINE.
  * Disclosures / exports / restricted / external / cross-tenant / consent-
    dependent / research-identifiable (derived CRITICAL) → SOURCE_OF_TRUTH, so the
    matched human rule controls. Expressed via `authority_mode=SOURCE_OF_TRUTH` on
    the release/critical rules (belt-and-suspenders with the registry, which maps
    `hc_critical` → SOURCE_OF_TRUTH).
  * Prohibited actions → independent hard blocks via forbidden capabilities.
  * Unknown/missing material facts → conservative REQUIRE_APPROVAL via the
    registry's `UncertainDisposition.REQUIRE_APPROVAL`.
"""

from __future__ import annotations

from typing import Optional, Tuple

from agentic.agentic_framework.human_policy import (
    ActionCriticalityRegistry,
    HumanPolicyBook,
    HumanPolicyMode,
    HumanPolicyRule,
    HumanPolicyVerdict,
    UncertainDisposition,
)
from agentic.agentic_framework.policy_bundle import (
    PolicyBundle,
    PolicyMetadata,
    PolicyResolution,
    SafetyPolicy,
)
from agentic.healthcare.criticality import ALL_HARD_BLOCK_TOKENS

# Healthcare hard-block capability tokens (added to the generic forbidden set).
HEALTHCARE_HARD_BLOCK_CAPABILITIES: Tuple[str, ...] = ALL_HARD_BLOCK_TOKENS

_SOT = HumanPolicyMode.SOURCE_OF_TRUTH


def build_healthcare_criticality_registry() -> ActionCriticalityRegistry:
    """Registry that consumes the healthcare-derived criticality signal facts.

    Criticality is derived deterministically in `criticality.derive_criticality`
    and encoded as `hc_critical` / `hc_non_critical`. Risk-level/tool membership
    is intentionally empty so ONLY the derived facts (plus a caller
    promotion-only fact) drive classification. Promotion always wins.
    """
    return ActionCriticalityRegistry(
        critical_risk_levels=(),
        non_critical_risk_levels=(),
        critical_promoting_facts=("hc_critical", "declared_high_risk"),
        non_critical_facts=("hc_non_critical",),
        uncertain_disposition=UncertainDisposition.REQUIRE_APPROVAL,
    )


def build_healthcare_policy_book(
    *, name: str = "hospital-data-access", version: str = "1.0.0",
) -> HumanPolicyBook:
    """A deterministic, human-curated healthcare policy book (pilot fixture)."""
    A = HumanPolicyVerdict.ALLOW
    AWC = HumanPolicyVerdict.ALLOW_WITH_CONSTRAINTS
    RA = HumanPolicyVerdict.REQUIRE_APPROVAL
    D = HumanPolicyVerdict.DENY

    rules = (
        # ---- Denials / restrictions (high priority) ------------------------
        # Billing actor explicitly requesting a restricted narrative → deny.
        HumanPolicyRule(
            rule_id="HC-BILLING-RESTRICTED-DENY", verdict=D, priority=30,
            when_facts=("purpose:payment", "explicit_restricted_request"),
            authority_mode=_SOT,
            description="Billing may not access restricted narratives."),
        # Unknown actor requesting restricted data → deny.
        HumanPolicyRule(
            rule_id="HC-UNKNOWN-ACTOR-RESTRICTED-DENY", verdict=D, priority=30,
            when_facts=("unknown_actor_role", "restricted_category_requested"),
            authority_mode=_SOT,
            description="Unknown actor may not access restricted data."),

        # ---- External / cross-tenant release (SOURCE_OF_TRUTH) -------------
        # External release with approved destination + consent → human ALLOW.
        HumanPolicyRule(
            rule_id="HC-EXTERNAL-APPROVED-ALLOW", verdict=A, priority=25,
            when_facts=("external_recipient", "destination_approved",
                        "consent_present"),
            authority_mode=_SOT,
            constraints={"no_onward_disclosure": True, "min_necessary": True},
            description="Approved external disclosure with consent is permitted."),
        # External release without approval → require approval.
        HumanPolicyRule(
            rule_id="HC-EXTERNAL-UNAPPROVED-REVIEW", verdict=RA, priority=15,
            when_facts=("external_recipient",),
            unless_facts=("destination_approved",),
            authority_mode=_SOT, approver_policy="privacy_officer",
            description="External disclosure without approval requires review."),

        # ---- Research -----------------------------------------------------
        # De-identified, authorized research → baseline allow.
        HumanPolicyRule(
            rule_id="HC-RESEARCH-DEID-ALLOW", verdict=A, priority=20,
            when_facts=("purpose:research", "research_deidentified",
                        "research_authorized"),
            authority_mode=HumanPolicyMode.BASELINE,
            constraints={"deidentified_only": True, "min_necessary": True},
            description="Authorized de-identified research access is permitted."),
        # Identifiable research without authorization → require approval.
        HumanPolicyRule(
            rule_id="HC-RESEARCH-IDENTIFIABLE-REVIEW", verdict=RA, priority=20,
            when_facts=("purpose:research", "research_identifiable"),
            unless_facts=("research_authorized",),
            authority_mode=_SOT, approver_policy="irb",
            description="Identifiable research needs authorization/approval."),

        # ---- Patient self-access ------------------------------------------
        HumanPolicyRule(
            rule_id="HC-PATIENT-SELF-ALLOW", verdict=AWC, priority=20,
            when_facts=("patient_self_access", "identity_verified"),
            constraints={"patient_scope": True, "min_necessary": True},
            description="Patient may access their own record (identity verified)."),
        HumanPolicyRule(
            rule_id="HC-PATIENT-SELF-UNVERIFIED-REVIEW", verdict=RA, priority=18,
            when_facts=("patient_self_access",),
            unless_facts=("identity_verified",), authority_mode=_SOT,
            description="Patient self-access without verified identity → review."),

        # ---- Billing minimum-necessary ------------------------------------
        HumanPolicyRule(
            rule_id="HC-BILLING-FULLRECORD-CONSTRAIN", verdict=AWC, priority=12,
            when_facts=("purpose:payment", "full_record_requested"),
            unless_facts=("explicit_restricted_request",),
            constraints={"min_necessary": True, "scope": "billing"},
            description="Billing full-record request reduced to minimum-necessary."),

        # ---- Export / disclose (critical) ---------------------------------
        HumanPolicyRule(
            rule_id="HC-EXPORT-REVIEW", verdict=RA, priority=8,
            when_facts=("is_export",), unless_facts=("destination_approved",),
            authority_mode=_SOT, approver_policy="privacy_officer",
            description="Export requires review unless destination pre-approved."),
        HumanPolicyRule(
            rule_id="HC-DISCLOSE-REVIEW", verdict=RA, priority=8,
            when_facts=("is_disclose",), unless_facts=("destination_approved",),
            authority_mode=_SOT, approver_policy="privacy_officer",
            description="Disclosure requires review unless pre-approved."),

        # ---- Restricted fallback (low priority conservative) --------------
        HumanPolicyRule(
            rule_id="HC-RESTRICTED-FALLBACK-REVIEW", verdict=RA, priority=2,
            when_facts=("restricted_category_requested",),
            authority_mode=_SOT,
            description="Restricted access defaults to review unless a more "
                        "specific rule applies."),

        # ---- Bounded, reversible internal access (BASELINE) ---------------
        HumanPolicyRule(
            rule_id="HC-BOUNDED-INTERNAL-ALLOW", verdict=A, priority=1,
            when_facts=("hc_non_critical",),
            constraints={"min_necessary": True, "encounter_scope": True},
            description="Bounded internal access; model governance may tighten."),

        # ---- Conservative catch-all (lowest priority) ---------------------
        # Anything not matched by a specific rule defaults to review. Its mode is
        # left to the criticality registry (unknown → conservative), so an
        # unclassified sensitive request is escalated, never silently allowed.
        HumanPolicyRule(
            rule_id="HC-DEFAULT-REVIEW", verdict=RA, priority=0,
            description="Unmatched requests default to human review."),
    )
    return HumanPolicyBook(rules=rules, name=name, version=version)


def build_healthcare_forbidden_policy_resolution() -> PolicyResolution:
    """A PolicyResolution whose forbidden_capabilities include the healthcare
    hard-block tokens, so those tokens trigger the generic engine's independent
    fail-closed hard-block layer (final_authority = HARD_BLOCK)."""
    base_forbidden = SafetyPolicy().forbidden_capabilities
    safety = SafetyPolicy(
        forbidden_capabilities=tuple(base_forbidden) + HEALTHCARE_HARD_BLOCK_CAPABILITIES,
    )
    bundle = PolicyBundle(
        metadata=PolicyMetadata(
            policy_id="healthcare-forbidden",
            version="1.0.0",
            description="Healthcare hard-block capabilities.",
        ),
        safety=safety,
    )
    return PolicyResolution(
        effective_policy=bundle,
        base_policy_id="healthcare-forbidden",
        base_version="1.0.0",
    )
