"""Strict request models for the additive ``governance_studio.api.v2`` contract (GAS-4).

Same discipline as v1: every model forbids unknown fields, no field accepts a
filesystem path, code, or policy script, and artifacts are carried as JSON objects
validated by the owning package's own models inside the service.

Nothing here describes an authority act. There is no issue, activate, revoke, grant,
authorize, clear or execute request in this module, and ``test_v2_operation_ids.py``
asserts the same of every route built from it.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .envelope import StrictModel


# --------------------------------------------------------------------------- #
# Constitution
# --------------------------------------------------------------------------- #
class ConstitutionValidateRequest(StrictModel):
    """Structural validation of a constitution document. Mutation-free."""

    constitution: Dict[str, Any]


class ConstitutionPreflightRequest(StrictModel):
    """Dry-run every pre-signing check.

    ``preflight_issuance`` is documented as mutation-free, which is exactly why it is
    the only activation entry point the studio may reach (SD-2): it reports what
    issuance *would* find without performing it.
    """

    constitution: Dict[str, Any]
    record_id: str
    approval_reference: Optional[str] = None
    expected_reference_tenant_id: Optional[str] = None


# --------------------------------------------------------------------------- #
# Policy
# --------------------------------------------------------------------------- #
class PolicyPackRequest(StrictModel):
    """A policy pack as authored on the canvas, carried as a JSON object."""

    pack: Dict[str, Any]


class PolicyCompileRequest(StrictModel):
    """Compile a reviewed pack.

    ``approval`` is required and is never defaulted: the compiler's
    ``require_approval`` defaults to True and the studio never overrides it.
    """

    pack: Dict[str, Any]
    approval: Dict[str, Any]


# --------------------------------------------------------------------------- #
# Simulate
# --------------------------------------------------------------------------- #
class SimulateRunRequest(StrictModel):
    """Run a workflow against fixtures, recording every governance decision.

    ``execution_mode`` is constrained to the non-mutating modes. LIVE is not a member
    of the accepted set and cannot be requested.
    """

    workflow: Dict[str, Any]
    execution_mode: str = "DRY_RUN"
    max_quanta: int = 16
    correlation_id: Optional[str] = None


# --------------------------------------------------------------------------- #
# Publish
# --------------------------------------------------------------------------- #
class PublishShadowRequest(StrictModel):
    """Hand a compiled release package to the console's SHADOW governed loop.

    There is no non-shadow variant of this request, by construction.
    """

    compiled_package: Dict[str, Any]
    scenario_id: Optional[str] = None
