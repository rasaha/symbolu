"""Front-door seam 5 (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md FD-9): the system registry.

    THIS ROOT OPENS ONE FILE AND HANDS IT ON. IT REGISTERS NOTHING ITSELF.

``open_system_registry`` opens ai-system-registry's ``SqliteSystemRegistry`` at the
configured path under the writable runtime volume, bound to this deployment's tenant
(FD-9.1, FD-9.2). A file already bound to another tenant is a deployment refusal
before anything binds. The Registration screen's only write is ``register``
(FD-9.5); the registrant it records is presented and unproven (FD-9.3); and
``registered_by`` is this deployment's name and version, never a caller's claim.
"""
from __future__ import annotations

from ugence_ai_system_registry import CrossTenantRefused, RegistryStorageError, SqliteSystemRegistry

from . import DEPLOYMENT_NAME, DEPLOYMENT_VERSION
from .config import DeploymentConfigError

__all__ = ["open_system_registry", "REGISTERED_BY"]

#: FD-9.3: what every registration this deployment records is ``registered_by``.
REGISTERED_BY = f"{DEPLOYMENT_NAME}/{DEPLOYMENT_VERSION}"


def open_system_registry(path: str, *, tenant_id: str, production_mode: bool) -> SqliteSystemRegistry:
    """The tenant-bound registry file, or a typed deployment refusal."""
    try:
        return SqliteSystemRegistry(path, tenant_id=tenant_id, production_mode=production_mode)
    except CrossTenantRefused as exc:
        raise DeploymentConfigError(
            f"UGENCE_STUDIO_SYSTEM_REGISTRY_PATH names a registry bound to another tenant: {exc}") from exc
    except RegistryStorageError as exc:
        raise DeploymentConfigError(f"UGENCE_STUDIO_SYSTEM_REGISTRY_PATH cannot be opened: {exc}") from exc
