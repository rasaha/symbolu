"""Shared fixtures for the Ugence Procurement package tests (canonical imports)."""

from __future__ import annotations

import pytest

from ugence_procurement import ProcurementConfiguration, build_in_memory_platform
from ugence_procurement.routes import ProcurementAPI
from ugence_procurement.requests import (
    BudgetReference,
    PurchaseItem,
    PurchaseRequest,
    SupplierReference,
)

TENANT = "t1"
REQUESTER = "requester-1"
APPROVER = "approver-1"
AI_ACTOR = "ai-1"


def make_request(
    request_id: str = "pr-1",
    *,
    unit_cost: int = 100_000,
    quantity: int = 2,
    supplier_id: str = "sup-1",
    budget_id: str = "bud-1",
    available: int = 100_000_000,
    justification: str = "operational need",
) -> PurchaseRequest:
    return PurchaseRequest(
        request_id=request_id, tenant_id=TENANT, requester=REQUESTER,
        supplier=SupplierReference(supplier_id=supplier_id, name="Acme"),
        items=(PurchaseItem(description="widgets", quantity=quantity, unit_cost=unit_cost),),
        budget=BudgetReference(budget_id=budget_id, available_amount=available),
        justification=justification)


def build_platform(config: ProcurementConfiguration | None = None):
    platform = build_in_memory_platform(config)
    for actor in (REQUESTER, APPROVER):
        platform.identity_provider.register_human(actor)
        platform.policy_adapter.grant_all(actor, TENANT)
    platform.identity_provider.register_ai(AI_ACTOR)
    platform.policy_adapter.grant_all(AI_ACTOR, TENANT)
    platform.publish_standard_mappings(actor=APPROVER, tenant_id=TENANT)
    return platform


@pytest.fixture
def platform():
    return build_platform()


@pytest.fixture
def api(platform):
    return ProcurementAPI(platform)


@pytest.fixture
def request_factory():
    return make_request
