"""Front-door seam 8 (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md FD-12): the data-use
declarations file.

    THIS ROOT OPENS ONE FILE AND HANDS IT ON. IT DECLARES NOTHING ITSELF.

``open_data_use_declarations`` opens data-use-admission's ``SqliteDataUseDeclarations``
at the configured path under the writable runtime volume, bound to this deployment's
tenant (FD-12.2). A file already bound to another tenant is a deployment refusal before
anything binds. The Data use screen's only write is ``declare`` (FD-12.5); the declarer
it records is presented and unproven (FD-12.3); and the recording composition is this
deployment's name and version, never a caller's claim.
"""
from __future__ import annotations

from ugence_data_use_admission import (
    VocabularyBinding,
    CrossTenantRefused,
    DeclarationStorageError,
    SqliteDataUseDeclarations,
)

from . import DEPLOYMENT_NAME, DEPLOYMENT_VERSION
from .config import DeploymentConfigError

__all__ = ["open_data_use_declarations", "RECORDED_BY",
           "DATA_CLASSIFICATION_VOCABULARY", "DATA_USE_PURPOSE_VOCABULARY"]

#: FD-12.3: the composition every declaration this deployment records was recorded by.
RECORDED_BY = f"{DEPLOYMENT_NAME}/{DEPLOYMENT_VERSION}"

#: The two published vocabularies this image records data uses against (``VV-E``,
#: authorized by ``PUB-2``). **Two, independently:** ``VV-D`` forbids the purpose binding
#: from being borrowed from the classification one, because an open shape still has a
#: source. Both pinned at build time; neither resolved by anything here.
DATA_CLASSIFICATION_VOCABULARY = VocabularyBinding(
    vocabulary="data-classification",
    version="1.0.0",
    specification_digest=(
        "sha256:cc9462e5350d8721f2074314c3e4e3b241db4dcd86df2f7f16f26faf8a8f3925"),
)
DATA_USE_PURPOSE_VOCABULARY = VocabularyBinding(
    vocabulary="data-use-purpose",
    version="1.0.0",
    specification_digest=(
        "sha256:615fb22f4986b009cb923ff08bda721645d37e410ab05338c1cbe561d43e5613"),
)


def open_data_use_declarations(path: str, *, tenant_id: str,
                               production_mode: bool) -> SqliteDataUseDeclarations:
    """The tenant-bound declarations file, or a typed deployment refusal."""
    try:
        return SqliteDataUseDeclarations(path, tenant_id=tenant_id,
                                        production_mode=production_mode)
    except CrossTenantRefused as exc:
        raise DeploymentConfigError(
            "UGENCE_STUDIO_DATA_USE_DECLARATIONS_PATH names a declarations file bound to "
            f"another tenant: {exc}") from exc
    except DeclarationStorageError as exc:
        raise DeploymentConfigError(
            f"UGENCE_STUDIO_DATA_USE_DECLARATIONS_PATH cannot be opened: {exc}") from exc
