"""Front-door seam 9 (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md FD-13): the vendor
declarations file.

    THIS ROOT OPENS ONE FILE AND HANDS IT ON. IT DECLARES NOTHING ITSELF, AND IT
    ASSESSES NO VENDOR.

``open_vendor_declarations`` opens vendor-dependency's ``SqliteVendorDeclarations`` at
the configured path under the writable runtime volume, bound to this deployment's
tenant (FD-13.1, FD-13.2). A file already bound to another tenant is a deployment
refusal before anything binds. The Vendor screen's only write is ``declare``
(FD-13.4); the declarer it records is presented and unproven; the recording
composition is this deployment's name and version, never a caller's claim; and the
risk posture is recorded uninterpreted, never ranked, scored or approved here or
anywhere else in this deployment.
"""
from __future__ import annotations

from ugence_vendor_dependency import (
    VocabularyBinding,
    CrossTenantRefused,
    DeclarationStorageError,
    SqliteVendorDeclarations,
)

from . import DEPLOYMENT_NAME, DEPLOYMENT_VERSION
from .config import DeploymentConfigError

__all__ = ["open_vendor_declarations", "VENDOR_RECORDED_BY", "VENDOR_POSTURE_VOCABULARY"]

#: FD-13.2: the composition every vendor declaration this deployment records was
#: recorded by.
VENDOR_RECORDED_BY = f"{DEPLOYMENT_NAME}/{DEPLOYMENT_VERSION}"

#: The published vocabulary this image records vendor postures against
#: (``VV-E``, authorized by ``PUB-2``). Pinned at build time, like the recording
#: composition above and for the same reason: which taxonomy this image's screens write
#: under is a property of the image, not of a caller or of a runtime setting. Named for
#: its members by ``PUB-1a`` — citing it confers nothing, since ``VR-3`` forbids implied
#: eligibility. Recorded here and resolved by nobody: this deployment never opens
#: ``docs/vocabularies/``.
VENDOR_POSTURE_VOCABULARY = VocabularyBinding(
    vocabulary="vendor-dependency-assessment-state",
    version="1.0.0",
    specification_digest=(
        "sha256:43fd5b7c37899890afe92a3e908303fcadbbcd225d8c2c155f1364e282206458"),
)


def open_vendor_declarations(path: str, *, tenant_id: str,
                             production_mode: bool) -> SqliteVendorDeclarations:
    """The tenant-bound vendor declarations file, or a typed deployment refusal."""
    try:
        return SqliteVendorDeclarations(path, tenant_id=tenant_id,
                                        production_mode=production_mode)
    except CrossTenantRefused as exc:
        raise DeploymentConfigError(
            "UGENCE_STUDIO_VENDOR_DECLARATIONS_PATH names a declarations file bound to "
            f"another tenant: {exc}") from exc
    except DeclarationStorageError as exc:
        raise DeploymentConfigError(
            f"UGENCE_STUDIO_VENDOR_DECLARATIONS_PATH cannot be opened: {exc}") from exc
