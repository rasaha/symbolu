"""Version and maturity metadata for the Ugence Governance Studio API (P3B).

The API distribution/product version is defined here. All AWC and compiler
version facts are read from the installed public packages at call time — never
hard-coded — so the ``/version`` endpoint cannot drift from the real dependency.
Wall-clock values are deliberately excluded from any logical result fingerprint;
build metadata (commit, build id) is operational only.
"""
from __future__ import annotations

from typing import Any, Dict

# API distribution + product version (single source; consumed by pyproject).
VERSION: str = "0.1.0"
PRODUCT_VERSION: str = "0.1.0"
__version__: str = VERSION

# Frozen API contract identity (advertised in OpenAPI + every response envelope).
API_CONTRACT_VERSION: str = "governance_studio.api.v1"

# The ADDITIVE v2 contract (GAS-4). It is a SEPARATE document alongside the frozen
# v1 one, generated from its own application: adding v2 routes to the v1 app would
# change ``canonical_openapi_bytes()`` and break the v1 freeze test, which must keep
# passing unchanged. v1 is not touched, re-versioned or deprecated by v2's existence.
API_V2_CONTRACT_VERSION: str = "governance_studio.api.v2"

# Supported AWC minor line (P3B packaging protection P1). The backend is pinned to
# the 0.2.x compatibility surface: it requires >= the minimum tested version and
# refuses anything at or above the next minor, which may change the awc.v1 /
# awc.composition.v1 / awc.compiler_adapter.v2 contracts. The reproducible demo
# environment locks the exact tested version (see backend/constraints.txt).
SUPPORTED_AWC_MIN: str = "0.2.1"
SUPPORTED_AWC_MAX_EXCLUSIVE: str = "0.3.0"
PINNED_AWC_VERSION: str = "0.2.1"


def _parse_version(text: str) -> tuple:
    """Parse a dotted release version into a comparable integer tuple.

    Only the numeric release segment is considered (a trailing pre/post/dev
    suffix is ignored) — sufficient for the bounded 0.2.x range check.
    """
    release = ""
    for ch in str(text).strip():
        if ch.isdigit() or ch == ".":
            release += ch
        else:
            break
    parts = [p for p in release.split(".") if p != ""]
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            break
    return tuple(nums) or (0,)


def awc_version_supported(version: str) -> bool:
    """True iff ``version`` is within ``[SUPPORTED_AWC_MIN, SUPPORTED_AWC_MAX_EXCLUSIVE)``."""
    v = _parse_version(version)
    return _parse_version(SUPPORTED_AWC_MIN) <= v < _parse_version(SUPPORTED_AWC_MAX_EXCLUSIVE)

# Honest maturity flags (§27). These describe exactly what P3B does and does not
# implement. They are asserted by the test-suite and surfaced by ``/version``.
MATURITY_FLAGS: Dict[str, bool] = {
    "governance_studio_foundation_implemented": True,
    "deterministic_demo_api_implemented": True,
    "scenario_execution_implemented": True,
    "workflow_ir_v1_supported": True,
    "workflow_ir_v2_supported": True,
    "eligibility_api_implemented": True,
    "ranking_api_implemented": True,
    "composition_api_implemented": True,
    "permission_proposal_api_implemented": True,
    "fallback_api_implemented": True,
    "plan_replay_api_implemented": True,
    "plan_comparison_api_implemented": True,
    "what_if_api_implemented": True,
    # GAS-4: the six Governed Agent Studio screens and their backend. The backend is
    # thin orchestration over allowlisted public entry points; the six screens ship
    # under /studio on the studio's own React Flow canvas. Langflow import is deferred
    # and customer-gated by owner ruling (roadmap §11.3), so it stays False.
    "studio_v2_contract_implemented": True,
    "constitution_preflight_api_implemented": True,
    "policy_compile_api_implemented": True,
    "authority_read_api_implemented": True,
    "simulate_api_implemented": True,
    "publish_shadow_api_implemented": True,
    "observe_audit_api_implemented": True,
    "langflow_import_implemented": False,
    "studio_screens_implemented": True,
    "constitution_issuance_implemented": False,
    "policy_issuance_implemented": False,
    "frontend_implemented": False,
    "authentication_implemented": False,
    "private_deployment_implemented": False,
    "runtime_handoff_implemented": False,
    "agent_execution_implemented": False,
    "permission_granting_implemented": False,
    "live_enterprise_data_supported": False,
    "pilot_validated": False,
    "production_certified": False,
}

# The synthetic / planning-only notice attached to every domain response.
SYNTHETIC_NOTICE = {
    "synthetic_demonstration_data": True,
    "planning_only": True,
    "no_agent_execution": True,
    "no_permission_grant": True,
    "no_business_action_authorization": True,
}


def awc_version_facts() -> Dict[str, Any]:
    """Read AWC + compiler version facts from the installed public packages."""
    import ugence_agent_workforce_composer.api as awc

    facts: Dict[str, Any] = {
        "awc_distribution": "ugence-agent-workforce-composer",
        "awc_distribution_version": awc.__version__,
        "awc_product_version": awc.__version__,
        "awc_contract_versions": [
            awc.CONTRACT_VERSION,
            awc.COMPOSITION_CONTRACT_VERSION,
            awc.COMPILER_ADAPTER_CONTRACT_VERSION,
        ],
        "supported_workflow_contracts": list(awc.SUPPORTED_COMPILER_CONTRACTS),
        "supported_awc_range": f">={SUPPORTED_AWC_MIN},<{SUPPORTED_AWC_MAX_EXCLUSIVE}",
        "pinned_awc_version": PINNED_AWC_VERSION,
        "awc_version_supported": awc_version_supported(awc.__version__),
    }
    # The compiler is NOT a direct API dependency: P3B consumes serialized
    # workflow_ir.v1 / workflow_ir.v2 artifacts THROUGH the AWC public adapter
    # surface. We therefore report the compiler *contract* versions (which AWC
    # advertises) but do not import the compiler package or hard-code its
    # distribution version here.
    facts["compiler_distribution"] = "ugence-policy-workflow-compiler"
    facts["compiler_distribution_version"] = None
    facts["compiler_dependency"] = "indirect_via_awc_adapter"
    facts["compiler_contract_versions"] = list(awc.SUPPORTED_COMPILER_CONTRACTS)
    return facts


def version_info(build_commit: str | None = None, build_id: str | None = None) -> Dict[str, Any]:
    """Full version payload for the ``/version`` endpoint (§7)."""
    info: Dict[str, Any] = {
        "api_distribution": "ugence-governance-studio-api",
        "api_distribution_version": VERSION,
        "api_product_version": PRODUCT_VERSION,
        "api_contract_version": API_CONTRACT_VERSION,
        "build_commit": build_commit,
        "build_id": build_id,
        "maturity": dict(MATURITY_FLAGS),
        "notice": dict(SYNTHETIC_NOTICE),
    }
    info.update(awc_version_facts())
    return info
