"""
Ontological Contracts Package
=============================

Dataclasses for projection requests and responses.
"""

from agentic.ontology.contracts.projection_contract import (
    ProjectionReasonCode,
    ProjectionRequest,
    ProjectionRequestOptions,
    ProjectionResponse,
    create_failed_response,
    create_success_response,
)

__all__ = [
    "ProjectionReasonCode",
    "ProjectionRequest",
    "ProjectionRequestOptions",
    "ProjectionResponse",
    "create_failed_response",
    "create_success_response",
]
