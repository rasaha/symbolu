"""Ugence Workflow Converters (tooling, not a governance authority).

Offline converters from third-party workflow exports into a DRAFT Ugence policy
pack, a content-addressed conversion report and a preview Workflow IR labelled
PREVIEW_UNAPPROVED. Owner ruling CV-1 to CV-5,
docs/architecture/ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md section 23. n8n first; BPMN
2.0 next; LangGraph, CrewAI and AutoGen deferred until a declarative export exists.
"""
from .version import DISTRIBUTION_VERSION as __version__  # noqa: F401

__all__ = ["__version__"]
