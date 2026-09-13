"""Governance Studio — private hosted deployment (P3E).

A single-process, HTTPS-only, authenticated wrapper that packages the FROZEN
Governance Studio frontend build and the FROZEN P3B backend (``create_app``) into
one privately hosted, synthetic-data-only demonstration deployment. It changes no
governance decision semantics, grants no permissions, authorizes no business
actions, and executes no agent against any non-fixture provider (FD-7.1).

Deployment bundle identity is distinct from the component versions it packages.
"""
from __future__ import annotations

DEPLOYMENT_NAME = "governance-studio-private-hosted"
DEPLOYMENT_VERSION = "0.13.0"

# Frozen component identities this deployment packages (never relabelled).
FRONTEND_VERSION = "0.2.0"
BACKEND_API_VERSION = "0.1.0"
API_CONTRACT = "governance_studio.api.v1"
AWC_VERSION = "0.2.1"
COMPILER_VERSION = "0.2.0"
OPENAPI_SHA256 = "dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656"
#: How many operations the frozen v1 manifest approves. Seventeen through P3E; twenty
#: since owner ruling BW-3 (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md section 22) moved the
#: three workflow operations from forbidden to approved. The OpenAPI hash did not move.
APPROVED_OPERATION_COUNT = 20
DATA_CLASSIFICATION = "SYNTHETIC_DEMONSTRATION_ONLY"

__all__ = [
    "DEPLOYMENT_NAME",
    "DEPLOYMENT_VERSION",
    "FRONTEND_VERSION",
    "BACKEND_API_VERSION",
    "API_CONTRACT",
    "APPROVED_OPERATION_COUNT",
    "AWC_VERSION",
    "COMPILER_VERSION",
    "OPENAPI_SHA256",
    "DATA_CLASSIFICATION",
]
