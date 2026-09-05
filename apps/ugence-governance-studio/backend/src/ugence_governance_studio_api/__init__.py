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
from .clients.console import CONSOLE_ALLOWED_ROUTES, ConsoleClient, ConsoleUnavailable
from .version import (
    API_CONTRACT_VERSION,
    API_V2_CONTRACT_VERSION,
    VERSION,
    __version__,
    version_info,
)

__all__ = [
    "create_app",
    "create_v2_app",
    "create_combined_app",
    "build_studio_context",
    "ConsoleClient",
    "ConsoleUnavailable",
    "CONSOLE_ALLOWED_ROUTES",
    "API_V2_CONTRACT_VERSION",
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


# --------------------------------------------------------------------------- #
# v2 surface — imported lazily, on purpose
# --------------------------------------------------------------------------- #
# The v2 application depends on the governance packages on the SD-1 allowlist
# (compiler, activation, Policy/Decision Authority, Agent Runtime). Importing it
# eagerly here would make every v1 consumer — including the v1 OpenAPI verifier —
# require v2's whole dependency footprint just to import this package. v1 must not
# acquire v2's dependencies by v2 existing, so these resolve on first access.
_V2_EXPORTS = {
    "create_v2_app": ".app_v2",
    "create_combined_app": ".app_v2",
    "build_studio_context": ".app_v2",
}


def __getattr__(name: str):  # PEP 562
    module_path = _V2_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    return getattr(import_module(module_path, __name__), name)


def __dir__():
    return sorted(set(globals()) | set(_V2_EXPORTS))
