"""Reference Account-Takeover StoryPolicyPack (§11).

A complete, governed pack that faithfully encodes the existing *frozen*
ACCOUNT_TAKEOVER_TRANSFER graph and its verified counter-stories. The compiler test
asserts the compiled graph's freeze-style digest equals the frozen graph digest — i.e.
this pack changes NO StoryGraph semantics; it only declares the frozen slice as
customer-configurable policy. The StoryGraph layer remains advisory.
"""

from __future__ import annotations

from .. import financial as F

# generic source categories (no vendor adapter is claimed)
_EVENT_MAPPINGS = [
    {"source_system": "identity_provider", "source_event_type": "password_reset",
     "canonical_event_type": "CREDENTIAL_RESET", "fragment_id": F.CRED_RESET,
     "schema_version": "ctd.event_mapping/1.0.0",
     "field_map": {"event_id": "id", "tenant_id": "tenant", "actor": "user",
                   "account": "account_id"}},
    {"source_system": "mobile_banking_app", "source_event_type": "device_register",
     "canonical_event_type": "DEVICE_ENROLLMENT", "fragment_id": F.DEVICE_NEW,
     "schema_version": "ctd.event_mapping/1.0.0",
     "field_map": {"event_id": "id", "tenant_id": "tenant", "actor": "user",
                   "account": "account_id", "device": "device_id"}},
    {"source_system": "beneficiary_management_system", "source_event_type": "add_payee",
     "canonical_event_type": "BENEFICIARY_ADD", "fragment_id": F.BENEFICIARY_ADD,
     "schema_version": "ctd.event_mapping/1.0.0",
     "field_map": {"event_id": "id", "tenant_id": "tenant", "actor": "user",
                   "account": "account_id", "beneficiary": "payee_id"}},
    {"source_system": "core_account_system", "source_event_type": "limit_increase",
     "canonical_event_type": "LIMIT_INCREASE", "fragment_id": F.LIMIT_UP,
     "schema_version": "ctd.event_mapping/1.0.0",
     "field_map": {"event_id": "id", "tenant_id": "tenant", "actor": "user",
                   "account": "account_id"}},
    {"source_system": "payment_engine", "source_event_type": "transfer_proposal",
     "canonical_event_type": "TRANSFER", "fragment_id": F.TRANSFER,
     "schema_version": "ctd.event_mapping/1.0.0",
     "field_map": {"event_id": "id", "tenant_id": "tenant", "actor": "user",
                   "account": "account_id", "beneficiary": "payee_id",
                   "device": "device_id", "amount": "amount"}},
]

_PROVIDER_MAPPINGS = [
    {"provider_id": "customer_account_recovery", "provider_type": "case_management",
     "authority_source": "fraud-operations", "evidence_schema": "recovery_case/1.0",
     "supported_operations": ["PASSWORD_RESET", "DEVICE_REGISTER"],
     "covered_entities": ["account"], "scope_matching_fields": ["account"],
     "validity_window": "72h", "revocation_semantics": "explicit_revoke",
     "supersession_semantics": "latest_wins", "availability_behavior": "OBSERVE",
     "verification_method": "signed_case_record", "tenant_isolation": True,
     "replay_fixture_format": "authorization_record",
     "schema_version": "ctd.provider_mapping/1.0.0"},
    {"provider_id": "bank_assisted_transaction", "provider_type": "payment_workflow",
     "authority_source": "assisted-banking", "evidence_schema": "bank_txn/1.1",
     "supported_operations": ["BENEFICIARY_ADD", "TRANSFER"],
     "covered_entities": ["account", "beneficiary"],
     "scope_matching_fields": ["account", "beneficiary", "destination"],
     "validity_window": "24h", "revocation_semantics": "explicit_revoke",
     "supersession_semantics": "latest_wins",
     "availability_behavior": "REQUIRE_ADDITIONAL_EVIDENCE",
     "verification_method": "signed_txn_record", "tenant_isolation": True,
     "replay_fixture_format": "authorization_record",
     "schema_version": "ctd.provider_mapping/1.0.0"},
]

ACCOUNT_TAKEOVER_PACK = {
    "schema_version": "ctd.storypolicypack/1.0.0",
    "policy_identity": {
        "policy_id": "ACCOUNT_TAKEOVER_TRANSFER",
        "policy_name": "Account takeover and unauthorized transfer",
        "policy_version": "1.0.0",
        "schema_version": "ctd.storypolicypack/1.0.0",
        "domain": "financial.account", "status": "SHADOW_ACTIVE",
        "effective_from": "2026-08-01", "expires_at": None,
        "supersedes": None, "change_reason": "reference pack for the frozen slice",
    },
    "business_objective": {
        "prevent": "unauthorized transfer following an account takeover",
        "protect": ["customer funds", "customer trust", "regulatory standing"],
        "rationale": "Takeover-then-transfer is a high-loss, hard-to-reverse pattern.",
        "risk_classification": "tier-0",
    },
    "scope": {
        "tenants": ["enterprise-bank-a"], "environments": ["production"],
        "business_units": ["digital-banking"], "applications": ["payments-platform"],
        "customer_segments": ["retail"], "action_types": ["TRANSFER"],
        "resource_types": ["account"], "data_classification": ["regulated"],
        "risk_tier": "tier-0",
    },
    "canonical_action": {
        "operation": "TRANSFER", "actor": "required", "account": "required",
        "resource": "required", "device": "required", "beneficiary": "required",
        "amount": "required", "currency": "required", "environment": "production",
        "requested_at": "required", "canonical_action_id": "required",
        "payload_digest": "required",
    },
    "harmful_story": {
        "story_id": "ACCOUNT_TAKEOVER_TRANSFER", "version": "1.0.0",
        "name": "Account takeover and unauthorized transfer",
        "graph_version": "ctd.storygraph/1.1.0",
        "matcher_version": "ctd.storygraph.matcher/2.0.0",
        "severity": "CRITICAL", "recommended_consequence": "HOLD_FOR_REVIEW",
        "nodes": [
            {"node_id": "reset", "fragment_id": F.CRED_RESET, "title": "Credential reset",
             "specificity_class": "COMMON"},
            {"node_id": "device", "fragment_id": F.DEVICE_NEW, "title": "New device",
             "specificity_class": "COMMON"},
            {"node_id": "benef", "fragment_id": F.BENEFICIARY_ADD,
             "title": "Beneficiary added", "specificity_class": "DISCRIMINATING"},
            {"node_id": "limit", "fragment_id": F.LIMIT_UP, "title": "Limit increase",
             "required": False, "specificity_class": "COMMON"},
            {"node_id": "xfer", "fragment_id": F.TRANSFER, "title": "Value transfer",
             "is_completion": True, "specificity_class": "DISCRIMINATING"},
        ],
        "edges": [
            {"kind": "ORDER", "a": "reset", "b": "xfer", "is_discriminating": True},
            {"kind": "ORDER", "a": "device", "b": "xfer"},
            {"kind": "ORDER", "a": "benef", "b": "xfer"},
            {"kind": "ORDER", "a": "limit", "b": "xfer"},
            {"kind": "SAME_ENTITY", "a": "reset", "b": "xfer", "dim": "account"},
            {"kind": "SAME_ENTITY", "a": "benef", "b": "xfer", "dim": "beneficiary",
             "is_discriminating": True},
            {"kind": "SAME_ENTITY", "a": "device", "b": "xfer", "dim": "device",
             "is_discriminating": True},
            {"kind": "WITHIN", "a": "reset", "b": "xfer", "max_gap": 1000.0,
             "is_discriminating": True},
        ],
        "gates": {"entity_gate": 0.999, "ordering_gate": 0.999, "timing_gate": 0.999,
                  "material_floor": 0.40, "threat_threshold": 0.70},
    },
    "legitimate_stories": [
        {"story_id": "ACCOUNT_RECOVERY", "version": "1.0.0",
         "name": "Verified customer account recovery",
         "accepted_tags": ["customer_account_recovery"],
         "rules": [
             {"node_id": "reset", "operation": "PASSWORD_RESET", "match_dims": ["account"]},
             {"node_id": "device", "operation": "DEVICE_REGISTER", "match_dims": ["account"]},
         ]},
        {"story_id": "BANK_ASSISTED_TRANSFER", "version": "1.1.0",
         "name": "Verified bank-assisted transaction",
         "accepted_tags": ["bank_assisted_transaction"],
         "rules": [
             {"node_id": "benef", "operation": "BENEFICIARY_ADD",
              "match_dims": ["account", "beneficiary"]},
             {"node_id": "xfer", "operation": "TRANSFER",
              "match_dims": ["account", "beneficiary", "destination"],
              "amount_dim": "amount"},
         ]},
    ],
    "consequences": {
        "NO_MATERIAL_PATTERN": "OBSERVE",
        "PARTIAL_HARMFUL_STORY": "OBSERVE",
        "AMBIGUOUS_COMPETING_STORIES": "REQUIRE_REVIEW",
        "VERIFIED_LEGITIMATE_STORY": "OBSERVE",
        "LEGITIMATE_STORY_PARTIAL_COVERAGE": "REQUIRE_REVIEW",
        "ADDITIONAL_CONTEXT_REQUIRED": "ADDITIONAL_CONTEXT_REQUIRED",
        "THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT": "REQUIRE_REVIEW",
        "WOULD_COMPLETE_PROHIBITED_CAPABILITY": "WOULD_HOLD_FOR_REVIEW",
        "HARD_POLICY_VIOLATION": "DENY",
        "ANALYZER_UNAVAILABLE": "UNAVAILABLE",
    },
    "event_mappings": _EVENT_MAPPINGS,
    "provider_mappings": _PROVIDER_MAPPINGS,
    "governance": {
        "business_owner": "fraud-operations",
        "control_owner": "enterprise-risk",
        "technical_owner": "platform-engineering",
        "required_approvers": ["security", "compliance", "fraud-operations"],
        "review_frequency": "quarterly", "rollback_version": None,
        "human_publication_confirmed": False,
        "approvals": {},
    },
    "validation": {
        "required_synthetic_scenarios": [
            "correct_harmful_completion", "wrong_account", "wrong_device",
            "wrong_beneficiary", "expired_approval", "revoked_approval",
            "partial_legitimate_coverage", "provider_unavailable",
            "delayed_provider_evidence", "duplicate_events", "ambiguous_ordering",
            "payload_change_after_evaluation", "tenant_mismatch",
        ],
        "required_historical_replay_scenarios": [
            "account_takeover_completion", "account_recovery_benign",
            "provider_unavailable_window",
        ],
        "acceptance_gates": {
            "max_benign_false_completion_rate": 0.0,
            "min_encoded_completion_detection_rate": 1.0,
        },
        "shadow_mode_requirements": ["two_week_shadow", "review_agreement_baseline"],
        "enforcement_promotion_requirements": ["risk_signoff", "historical_replay_pass"],
    },
}


def account_takeover_pack() -> dict:
    """Return a deep copy of the reference pack (callers may mutate freely)."""
    import copy
    return copy.deepcopy(ACCOUNT_TAKEOVER_PACK)
