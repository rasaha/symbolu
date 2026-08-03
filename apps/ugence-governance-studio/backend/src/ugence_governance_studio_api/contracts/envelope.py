"""Stable response envelope and typed API error model (§17, §18).

One envelope wraps every domain endpoint. Operational metadata (``request_id``,
timestamps) is EXCLUDED from any logical result fingerprint; canonical AWC result
fields are passed through the ``result`` field intact and never re-canonicalized.
Requests reject unknown fields (``extra="forbid"``).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..version import API_CONTRACT_VERSION, SYNTHETIC_NOTICE


class StrictModel(BaseModel):
    """Base for request models: unknown fields are rejected (422)."""

    model_config = ConfigDict(extra="forbid")


class Diagnostic(BaseModel):
    code: str
    message: str = ""
    severity: str = "info"
    field_path: Optional[str] = None


class ApiResponse(BaseModel):
    """Uniform envelope for domain endpoints (§17)."""

    api_version: str = API_CONTRACT_VERSION
    request_id: str
    operation: str
    scenario_id: Optional[str] = None
    source_contract_version: Optional[str] = None
    awc_version: str
    input_digests: Dict[str, str] = Field(default_factory=dict)
    result: Any = None
    diagnostics: List[Diagnostic] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    maturity: Dict[str, Any] = Field(default_factory=lambda: dict(SYNTHETIC_NOTICE))


class ApiError(BaseModel):
    """Typed API error model (§18). Never carries a stack trace in prod."""

    code: str
    message: str
    field_path: Optional[str] = None
    diagnostics: List[Diagnostic] = Field(default_factory=list)
    request_id: str
    safe_details: Dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    api_version: str = API_CONTRACT_VERSION
    error: ApiError
