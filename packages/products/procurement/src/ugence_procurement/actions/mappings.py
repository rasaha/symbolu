"""Procurement action mappings — decision → governed action.

These are ordinary kernel :class:`ActionMapping` records. A purchase decision is
mapped onto exactly one permitted action type (create purchase order, cancel,
route to a senior approver, or request more information). There is no
procurement-specific execution lifecycle — each becomes a standard
``ActionRequest`` handled by the kernel.
"""

from __future__ import annotations

from ugence_decision_authority.api.contracts import ActionMapping, DecisionOutcome, ParameterSchema

#: The decision type procurement cases carry.
PROCUREMENT_DECISION_TYPE = "purchase_approval"
#: The external system procurement actions target.
SUPPLIER_SYSTEM_TYPE = "SUPPLIER"

# Permitted action types.
CREATE_PURCHASE_ORDER = "CREATE_PURCHASE_ORDER"
CANCEL_REQUEST = "CANCEL_REQUEST"
ROUTE_TO_SENIOR_APPROVER = "ROUTE_TO_SENIOR_APPROVER"
REQUEST_MORE_INFORMATION = "REQUEST_MORE_INFORMATION"


def create_purchase_order_mapping() -> ActionMapping:
    return ActionMapping(
        mapping_id="proc.create_po", version=1, domain_id="procurement",
        decision_type=PROCUREMENT_DECISION_TYPE, decision_outcome=DecisionOutcome.ADVANCE,
        permitted_action_type=CREATE_PURCHASE_ORDER, target_system_type=SUPPLIER_SYSTEM_TYPE,
        parameter_schema=ParameterSchema(
            required_fields=("amount", "supplier_id", "budget_id")))


def cancel_request_mapping() -> ActionMapping:
    return ActionMapping(
        mapping_id="proc.cancel", version=1, domain_id="procurement",
        decision_type=PROCUREMENT_DECISION_TYPE, decision_outcome=DecisionOutcome.REJECT,
        permitted_action_type=CANCEL_REQUEST, target_system_type=SUPPLIER_SYSTEM_TYPE,
        parameter_schema=ParameterSchema(required_fields=("request_id",)))


def route_to_senior_mapping() -> ActionMapping:
    return ActionMapping(
        mapping_id="proc.route_senior", version=1, domain_id="procurement",
        decision_type=PROCUREMENT_DECISION_TYPE, decision_outcome=DecisionOutcome.HOLD,
        permitted_action_type=ROUTE_TO_SENIOR_APPROVER, target_system_type=SUPPLIER_SYSTEM_TYPE,
        parameter_schema=ParameterSchema(required_fields=("request_id",)))


def request_more_information_mapping() -> ActionMapping:
    return ActionMapping(
        mapping_id="proc.request_info", version=1, domain_id="procurement",
        decision_type=PROCUREMENT_DECISION_TYPE, decision_outcome=DecisionOutcome.DEFER,
        permitted_action_type=REQUEST_MORE_INFORMATION, target_system_type=SUPPLIER_SYSTEM_TYPE,
        parameter_schema=ParameterSchema(required_fields=("request_id",)))


def all_mappings() -> tuple[ActionMapping, ...]:
    """Every standard procurement action mapping."""
    return (
        create_purchase_order_mapping(),
        cancel_request_mapping(),
        route_to_senior_mapping(),
        request_more_information_mapping(),
    )
