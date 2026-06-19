"""
runtime_config.py — operational builders for running the trust core on real traffic.

Provides one supported way to instantiate `SafeMCPGateway` for each migration stage, so an
operator never has to poke private attributes:

  * `build_shadow_gateway`   — production SHADOW under REVIEWED (records the flip candidate;
                               legacy still decides and executes).
  * `build_canary_gateway`   — TRUST_CORE + REVIEWED (authoritative JEPA-sole relax; opt-in,
                               NOT a default).
  * `gateway_from_env`       — read TRUST_MODE / TRUST_AUTHORITY_POLICY / GOVERNANCE_AUDIT_DB
                               and build accordingly (defaults: shadow / reviewed / no store).

No ML, no GPU, no platform abstraction — thin wiring over existing constructor controls.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from agentic.agentic_framework.mcp_gateway import SafeMCPGateway


def _make_store(audit_db_path: Optional[str], audit_store: Optional[Any]):
    if audit_store is not None:
        return audit_store
    if audit_db_path:
        from agentic.ledger.governance_audit_store import GovernanceAuditStore
        return GovernanceAuditStore(audit_db_path)
    return None


def build_shadow_gateway(
    *,
    mcp_client: Any,
    audit_db_path: Optional[str] = None,
    audit_store: Optional[Any] = None,
    domain_registry: Optional[Any] = None,
    domain_id: Optional[str] = None,
    shadow_registry: Optional[Any] = None,
    enable_outcome_reputation: bool = False,
    **kwargs: Any,
) -> SafeMCPGateway:
    """Production SHADOW under REVIEWED: trust core computed + recorded; legacy still acts.

    Supply either `audit_db_path` (a durable GovernanceAuditStore is opened) or an existing
    `audit_store`. Records the REVIEWED flip candidate without changing any decision.
    """
    return SafeMCPGateway(
        mcp_client=mcp_client,
        audit_store=_make_store(audit_db_path, audit_store),
        domain_registry=domain_registry, domain_id=domain_id,
        shadow_registry=shadow_registry,
        trust_mode="shadow", trust_authority_policy="reviewed",
        enable_outcome_reputation=enable_outcome_reputation,
        **kwargs,
    )


def build_canary_gateway(
    *,
    mcp_client: Any,
    audit_db_path: Optional[str] = None,
    audit_store: Optional[Any] = None,
    domain_registry: Optional[Any] = None,
    domain_id: Optional[str] = None,
    shadow_registry: Optional[Any] = None,
    enable_outcome_reputation: bool = False,
    **kwargs: Any,
) -> SafeMCPGateway:
    """Canary: TRUST_CORE + REVIEWED — the authoritative JEPA-sole relax (BLOCK → human
    CONFIRM, never silent ALLOW). Opt-in; NOT a default. Route only the canary cohort here.
    """
    return SafeMCPGateway(
        mcp_client=mcp_client,
        audit_store=_make_store(audit_db_path, audit_store),
        domain_registry=domain_registry, domain_id=domain_id,
        shadow_registry=shadow_registry,
        trust_mode="trust_core", trust_authority_policy="reviewed",
        enable_outcome_reputation=enable_outcome_reputation,
        **kwargs,
    )


def gateway_from_env(*, mcp_client: Any, **kwargs: Any) -> SafeMCPGateway:
    """Build a gateway from environment variables (operational entry point).

    TRUST_MODE              legacy | shadow | trust_core   (default: shadow)
    TRUST_AUTHORITY_POLICY  parity | reviewed              (default: reviewed)
    GOVERNANCE_AUDIT_DB     path to the durable store      (default: unset → in-memory only)
    TRUST_OUTCOME_REPUTATION 1/true to enable the reputation observable (default: off)
    """
    mode = os.environ.get("TRUST_MODE", "shadow").lower()
    policy = os.environ.get("TRUST_AUTHORITY_POLICY", "reviewed").lower()
    db = os.environ.get("GOVERNANCE_AUDIT_DB") or None
    rep = os.environ.get("TRUST_OUTCOME_REPUTATION", "").lower() in ("1", "true", "yes", "on")
    return SafeMCPGateway(
        mcp_client=mcp_client,
        audit_store=_make_store(db, None),
        trust_mode=mode, trust_authority_policy=policy,
        enable_outcome_reputation=rep,
        **kwargs,
    )
