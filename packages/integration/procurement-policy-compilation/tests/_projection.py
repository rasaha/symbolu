"""A Procurement policy artifact projection, as a resolution would carry it."""

from __future__ import annotations

FULL = {
    "policy_id": "policy.purchase_approval",
    "title": "Purchase approval policy",
    "document_version": "4",
    "action_type": "CREATE_PURCHASE_ORDER",
    "amount_fact_key": "amount",
    "approval_threshold": 1_000_000,
    "hard_limit": 10_000_000,
    "approval_roles": [
        {"role_label": "requester", "decision_scope": "CREATE_PURCHASE_ORDER"},
        {"role_label": "approver", "decision_scope": "CREATE_PURCHASE_ORDER"},
    ],
    "evidence_requirements": [
        {"fact_key": "supplier_id", "description": "supplier identity"},
    ],
    "prohibited_facts": [
        {"fact_key": "supplier_sanctioned", "comparator": "EQ", "value": True},
    ],
    "declared_data_classifications": ["classification.supplier_pii"],
    "declared_permission_intents": ["permission.create_purchase_order"],
    "declared_required_tools": ["tool.erp"],
    "authority_level": "board",
}

#: The same policy stating only what it must: no roles, evidence, prohibitions or
#: declared semantics. What the artifact omits, the pack must omit too.
MINIMAL = {
    "policy_id": "policy.minimal",
    "title": "Minimal purchase policy",
    "document_version": "1",
    "action_type": "CREATE_PURCHASE_ORDER",
    "amount_fact_key": "amount",
    "approval_threshold": 500,
    "hard_limit": 5_000,
}
