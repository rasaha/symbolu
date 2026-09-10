"""Bring Your Workflow phase 3A (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §24, BW-3A): the
workflow drafts file.

    THIS ROOT OPENS ONE FILE AND HANDS IT ON. IT KEEPS NOTHING ITSELF, AND IT
    APPROVES, COMPILES, PUBLISHES OR EXPORTS NO DRAFT.

``open_workflow_drafts`` opens workflow-drafts' ``SqliteWorkflowDrafts`` at the
configured path under the writable runtime volume, bound to this deployment's tenant
(BW-3A.2: the tenant is trusted server configuration, never a value the browser sent).
A file already bound to another tenant is a deployment refusal before anything binds.
The Bring Your Workflow screen's only write is ``save``; a claimed owner it records is
presented and unproven; the recording composition is this deployment's name and
version, never a caller's claim; and a draft's lifecycle is the constant ``DRAFT``.
"""
from __future__ import annotations

from ugence_workflow_drafts import CrossTenantRefused, DraftStorageError, SqliteWorkflowDrafts

from . import DEPLOYMENT_NAME, DEPLOYMENT_VERSION
from .config import DeploymentConfigError

__all__ = ["open_workflow_drafts", "DRAFTS_RECORDED_BY"]

#: BW-3A: the composition every draft this deployment keeps was recorded by.
DRAFTS_RECORDED_BY = f"{DEPLOYMENT_NAME}/{DEPLOYMENT_VERSION}"


def open_workflow_drafts(path: str, *, tenant_id: str, production_mode: bool) -> SqliteWorkflowDrafts:
    """The tenant-bound drafts file, or a typed deployment refusal."""
    try:
        return SqliteWorkflowDrafts(path, tenant_id=tenant_id, production_mode=production_mode)
    except CrossTenantRefused as exc:
        raise DeploymentConfigError(
            f"UGENCE_STUDIO_WORKFLOW_DRAFTS_PATH names a drafts file bound to another tenant: {exc}") from exc
    except DraftStorageError as exc:
        raise DeploymentConfigError(
            f"UGENCE_STUDIO_WORKFLOW_DRAFTS_PATH cannot be opened: {exc}") from exc
