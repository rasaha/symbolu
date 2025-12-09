"""
Routing Drift Guardrail Test Suite
===================================

This test suite enforces the canonical mapper switching rules (v2.0) and ensures
that the routing system produces deterministic, contract-compliant behavior.

Test Modules:
- test_mapper_activation_regions: Grid-based validation of HRM/LCM/LAM activation zones
- test_pipeline_routing_profiles: End-to-end routing profile validation

Purpose:
- Prevent unintentional drift in routing logic
- Ensure TTOR + MLCR compliance with canonical formulas
- Provide CI-driven contract enforcement
- Enable safe refactoring and feature additions

Contract Reference: docs/routing_contract.md
"""

__all__ = [
    "test_mapper_activation_regions",
    "test_pipeline_routing_profiles",
]
