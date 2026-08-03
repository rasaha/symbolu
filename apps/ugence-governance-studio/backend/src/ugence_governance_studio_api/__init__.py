"""Ugence Governance Studio API (P3B) — deterministic, offline demo API.

A THIN orchestration + serialization layer over the public Agent Workforce
Composer package. It exposes scenario discovery and execution, workflow
adaptation (workflow_ir.v1 + workflow_ir.v2), eligibility, ranking, team
composition, permission-bound proposals, fallback planning, AgentTeamPlan replay,
plan comparison, controlled what-if analysis and artifact export.

It implements NO planning logic of its own, and ships NO frontend, authentication,
deployment, database, agent execution, permission granting or runtime handoff.

Public service surface (import from this package):
    create_app, ApiSettings, ScenarioCatalog, ScenarioService,
    AwcOrchestrationService, ApiResponse, ApiError, version_info,
    VERSION, API_CONTRACT_VERSION
"""
from __future__ import annotations

from .app import create_app
from .contracts.envelope import ApiError, ApiResponse
from .scenarios.catalog import ScenarioCatalog
from .services.orchestration import AwcOrchestrationService
from .services.scenario_service import ScenarioService
from .settings import ApiSettings
from .version import (
    API_CONTRACT_VERSION,
    VERSION,
    __version__,
    version_info,
)

__all__ = [
    "create_app",
    "ApiSettings",
    "ScenarioCatalog",
    "ScenarioService",
    "AwcOrchestrationService",
    "ApiResponse",
    "ApiError",
    "version_info",
    "VERSION",
    "API_CONTRACT_VERSION",
    "__version__",
]
