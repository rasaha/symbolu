"""Strict request models (§9-§16, §21).

Every request model forbids unknown fields. Domain endpoints accept EITHER a
reference to a frozen built-in scenario (``scenario_id``, optionally with an
injected ``logical_time``) OR fully inline pinned artifacts. Inline artifacts are
carried as JSON objects and validated by the AWC public model classes inside the
service — there is no bespoke deserialization here. No field accepts a filesystem
path, code, or policy script.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field, model_validator

from .envelope import StrictModel


# --------------------------------------------------------------------------- #
# workflow validation / adaptation
# --------------------------------------------------------------------------- #
class ValidateWorkflowRequest(StrictModel):
    contract_version: str
    workflow: Dict[str, Any]
    source_digest: Optional[str] = None


class AdaptWorkflowRequest(StrictModel):
    workflow: Dict[str, Any]
    contract_version: Optional[str] = None  # unknown/absent → declared version; fail-closed
    overlay: Optional[Dict[str, Any]] = None
    source_package_digest: Optional[str] = None


class CompareAdaptationsRequest(StrictModel):
    """Compare a v1 (full overlay) and v2 (reduced overlay) adaptation.

    Provide a ``scenario_id`` to use the frozen P2.1 conformance fixtures, or
    supply explicit v1/v2 workflow + overlay documents.
    """
    scenario_id: Optional[str] = None
    v1_workflow: Optional[Dict[str, Any]] = None
    v2_workflow: Optional[Dict[str, Any]] = None
    v1_overlay: Optional[Dict[str, Any]] = None
    v2_overlay: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def _check(self):
        if self.scenario_id is None and not (self.v1_workflow and self.v2_workflow):
            raise ValueError("provide scenario_id or both v1_workflow and v2_workflow")
        return self


# --------------------------------------------------------------------------- #
# inline pinned inputs (shared by eligibility / ranking / composition)
# --------------------------------------------------------------------------- #
class InlineInputs(StrictModel):
    workflow: Dict[str, Any]
    overlay: Optional[Dict[str, Any]] = None
    registry: Dict[str, Any]
    enterprise_policy: Dict[str, Any]
    eligibility_policy: Dict[str, Any]
    ranking_policy: Dict[str, Any]
    composition_policy: Dict[str, Any]
    permission_policy: Dict[str, Any]
    fallback_policy: Dict[str, Any]


class ScenarioComputeRequest(StrictModel):
    """Compute an eligibility / ranking / composition result from a scenario
    reference or inline pinned inputs, with an optional injected logical time."""
    scenario_id: Optional[str] = None
    logical_time: Optional[float] = None
    inputs: Optional[InlineInputs] = None

    @model_validator(mode="after")
    def _check(self):
        if self.scenario_id is None and self.inputs is None:
            raise ValueError("provide scenario_id or inline inputs")
        return self


# --------------------------------------------------------------------------- #
# explanations
# --------------------------------------------------------------------------- #
class ExplanationRequest(ScenarioComputeRequest):
    role_id: Optional[str] = None


# --------------------------------------------------------------------------- #
# replay / comparison
# --------------------------------------------------------------------------- #
class ReplayRequest(StrictModel):
    """Replay a plan against pinned inputs. ``scenario_id`` replays a built-in
    scenario against its frozen expected plan; ``replay_record`` + inline inputs
    replays an externally supplied plan. No filesystem paths are accepted (§14)."""
    scenario_id: Optional[str] = None
    logical_time: Optional[float] = None
    replay_record: Optional[Dict[str, Any]] = None
    expected_plan: Optional[Dict[str, Any]] = None
    inputs: Optional[InlineInputs] = None

    @model_validator(mode="after")
    def _check(self):
        if self.scenario_id is None and self.inputs is None:
            raise ValueError("provide scenario_id or inline inputs")
        return self


class PerturbationSpec(StrictModel):
    operation: str
    params: Dict[str, Any] = Field(default_factory=dict)


class PlanSource(StrictModel):
    """A deterministic source of a plan: a scenario with an optional injected
    logical time and an optional bounded perturbation."""
    scenario_id: str
    logical_time: Optional[float] = None
    perturbation: Optional[PerturbationSpec] = None


class ComparePlansRequest(StrictModel):
    left: PlanSource
    right: PlanSource


# --------------------------------------------------------------------------- #
# what-if (§15)
# --------------------------------------------------------------------------- #
class WhatIfOperation(str, Enum):
    FORBID_PROVIDER = "FORBID_PROVIDER"
    REQUIRE_RESIDENCY = "REQUIRE_RESIDENCY"
    TIGHTEN_COST_CEILING = "TIGHTEN_COST_CEILING"
    TIGHTEN_LATENCY_CEILING = "TIGHTEN_LATENCY_CEILING"
    REVOKE_AGENT_VERSION = "REVOKE_AGENT_VERSION"
    EXPIRE_EVIDENCE = "EXPIRE_EVIDENCE"
    TIGHTEN_PERMISSION_POLICY = "TIGHTEN_PERMISSION_POLICY"
    TIGHTEN_PROVIDER_CONCENTRATION = "TIGHTEN_PROVIDER_CONCENTRATION"
    REMOVE_CANDIDATE = "REMOVE_CANDIDATE"


class WhatIfRequest(StrictModel):
    operation: WhatIfOperation
    params: Dict[str, Any] = Field(default_factory=dict)
    logical_time: Optional[float] = None
