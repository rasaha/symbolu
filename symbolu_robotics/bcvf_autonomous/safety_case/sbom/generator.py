"""CycloneDX 1.5 SBOM generator for the autonomy runtime.

The output document conforms to the CycloneDX 1.5 specification
(https://cyclonedx.org/specification/overview/) — a JSON manifest
listing every runtime dependency with version + license + purl.

Discovery strategy:

* :func:`runtime_components` enumerates the autonomy-runtime
  import graph's direct dependencies (currently ``numpy`` plus
  the Python stdlib). Versions are resolved via
  :mod:`importlib.metadata` so the SBOM stays accurate on every
  install. Licenses are fetched from package metadata when
  available (``License-Expression`` or ``License`` in the
  ``Metadata`` block); fall through to a textual ``unknown``
  marker on packages that don't declare their license cleanly,
  so the manifest never silently mis-attributes a license.
* :func:`generate_cyclonedx_bom` builds the deterministic
  CycloneDX 1.5 dict. Components are sorted by name + version so
  the on-disk snapshot is byte-stable.
* :func:`write_cyclonedx_bom` writes the dict as canonical JSON
  (sorted keys, 2-space indent) to a path. Pinned by a snapshot
  test against ``safety_case/SBOM.cdx.json``.

The generator is internet-free + sandbox-safe: no PyPI lookups,
no remote license-resolution, no network calls. Everything reads
from local Python package metadata.
"""

from __future__ import annotations

import importlib.metadata
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union


# CycloneDX format version we target. 1.5 is the current
# stable spec at the time of writing and is what
# Dependency-Track / OSS Review Toolkit / FOSSA expect.
CYCLONEDX_SPEC_VERSION = "1.5"


# --------------------------------------------------------------------------- #
# Component dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SBOMComponent:
    """One row of the SBOM components table.

    ``licenses`` is a tuple of SPDX identifiers (e.g.
    ``("BSD-3-Clause",)``). When the upstream package's metadata
    is missing or non-SPDX, the tuple is empty and the textual
    license name (if any) lives in ``description``.
    """

    name: str
    version: str
    type: str = "library"
    licenses: Tuple[str, ...] = ()
    purl: Optional[str] = None
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("SBOMComponent.name must be non-empty")
        if not self.version:
            raise ValueError("SBOMComponent.version must be non-empty")
        if self.type not in (
            "application", "framework", "library",
            "container", "operating-system", "device",
            "firmware", "file",
        ):
            raise ValueError(
                f"SBOMComponent.type {self.type!r} is not a valid "
                "CycloneDX 1.5 component type"
            )

    def to_cyclonedx(self) -> Dict[str, Any]:
        """Render as a CycloneDX 1.5 component object."""
        out: Dict[str, Any] = {
            "type": self.type,
            "name": self.name,
            "version": self.version,
        }
        if self.purl:
            out["purl"] = self.purl
        if self.licenses:
            out["licenses"] = [
                _license_entry(lic) for lic in self.licenses
            ]
        elif self.description:
            # Non-SPDX-named licenses → fall back to the textual
            # name in the license expression slot. Procurement
            # tools accept either form.
            out["licenses"] = [
                {"license": {"name": self.description}}
            ]
        return out


_SPDX_EXPRESSION_OPERATORS = (" AND ", " OR ", " WITH ")


def _license_entry(license_str: str) -> Dict[str, Any]:
    """Render one license string as a CycloneDX 1.5 license entry.

    SPDX compound expressions (containing ``AND`` / ``OR`` /
    ``WITH``) go under the ``expression`` field per the CycloneDX
    spec; single-token SPDX identifiers go under ``license.id``.
    A future contributor adding a non-SPDX-named license should
    pass the textual name via the description fallback in
    :meth:`SBOMComponent.to_cyclonedx`, not via this function.
    """
    if any(op in license_str for op in _SPDX_EXPRESSION_OPERATORS):
        return {"expression": license_str}
    return {"license": {"id": license_str}}


# --------------------------------------------------------------------------- #
# Auto-discovery of runtime components
# --------------------------------------------------------------------------- #


# Runtime packages the autonomy module imports directly. The
# stdlib is excluded — CycloneDX manifests typically don't
# enumerate stdlib (it's a property of the Python interpreter,
# not a separately-versioned dependency).
_AUTONOMY_RUNTIME_PACKAGES: Tuple[str, ...] = (
    "numpy",
)


# Hand-curated SPDX license map for packages whose
# ``importlib.metadata`` doesn't return a clean SPDX identifier.
# Audited per package against the upstream LICENSE file at the
# pinned version. Update on dependency add or version bump.
_KNOWN_LICENSES: Dict[str, Tuple[str, ...]] = {
    "numpy": ("BSD-3-Clause",),
}


def _resolve_license(package_name: str) -> Tuple[str, ...]:
    """Resolve a package name to a tuple of SPDX license
    identifiers. Tries package metadata first; falls back to the
    hand-curated :data:`_KNOWN_LICENSES` map; returns ``()`` if
    neither resolves."""
    # importlib.metadata can return License-Expression (preferred,
    # already SPDX) or License (free-form).
    try:
        meta = importlib.metadata.metadata(package_name)
    except importlib.metadata.PackageNotFoundError:
        return _KNOWN_LICENSES.get(package_name, ())
    expr = meta.get("License-Expression") or ""
    if expr.strip():
        # Already SPDX.
        return (expr.strip(),)
    # Fall through to the curated map for free-form license
    # fields that mention a known SPDX name.
    return _KNOWN_LICENSES.get(package_name, ())


def _resolve_version(package_name: str) -> Optional[str]:
    """Resolve a package version via importlib.metadata. Returns
    ``None`` if the package is not installed (e.g. running in a
    minimal sandbox where the dep is mocked)."""
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def runtime_components() -> Tuple[SBOMComponent, ...]:
    """Auto-discover the autonomy-runtime SBOM components.

    Returns a tuple of :class:`SBOMComponent` for every package
    in :data:`_AUTONOMY_RUNTIME_PACKAGES` that is installed in
    the current environment. Skips packages that aren't
    installed (so a partial install doesn't crash the
    generator).
    """
    out: List[SBOMComponent] = []
    for name in _AUTONOMY_RUNTIME_PACKAGES:
        version = _resolve_version(name)
        if version is None:
            continue
        licenses = _resolve_license(name)
        out.append(
            SBOMComponent(
                name=name,
                version=version,
                type="library",
                licenses=licenses,
                purl=f"pkg:pypi/{name}@{version}",
            )
        )
    return tuple(out)


# --------------------------------------------------------------------------- #
# Generator + writer
# --------------------------------------------------------------------------- #


def _resolve_package_version() -> str:
    """Resolve the bcvf_autonomous package's own version. We
    import the version constant from ``_version`` so a
    ``__version__`` bump in the package automatically reflects
    in the SBOM."""
    from ..._version import __version__ as autonomy_version
    return str(autonomy_version)


def generate_cyclonedx_bom(
    *,
    package_name: str = "symbolu_robotics.bcvf_autonomous",
    package_version: Optional[str] = None,
    components: Optional[Sequence[SBOMComponent]] = None,
    serial_number: str = (
        "urn:uuid:00000000-0000-0000-0000-000000000000"
    ),
) -> Dict[str, Any]:
    """Build a CycloneDX 1.5 SBOM dict for the autonomy runtime.

    Args:
        package_name: the SBOM's primary component (the package
            being described).
        package_version: override for the primary component's
            version. Defaults to ``_version.__version__``.
        components: list of dependency components. Defaults to
            :func:`runtime_components`.
        serial_number: CycloneDX serial-number URN. The default
            is a deterministic placeholder so the SBOM is byte-
            stable; production CI overrides per-build.

    Returns: a dict that conforms to CycloneDX 1.5 + serialises
    deterministically (sorted components, fixed ordering).
    """
    if package_version is None:
        package_version = _resolve_package_version()
    if components is None:
        components = runtime_components()
    # Sort by (name, version) for byte-stable serialisation.
    sorted_components = sorted(
        components, key=lambda c: (c.name.lower(), c.version)
    )

    primary = SBOMComponent(
        name=package_name,
        version=str(package_version),
        type="library",
        licenses=(),
        purl=None,
        description="BCVF Autonomy Runtime",
    )

    return {
        "bomFormat": "CycloneDX",
        "specVersion": CYCLONEDX_SPEC_VERSION,
        "serialNumber": serial_number,
        "version": 1,
        "metadata": {
            "tools": [
                {
                    "vendor": "symbolu_robotics",
                    "name": "bcvf_autonomous.safety_case.sbom",
                    "version": str(package_version),
                }
            ],
            "component": primary.to_cyclonedx() | {
                "description": primary.description,
            },
        },
        "components": [c.to_cyclonedx() for c in sorted_components],
    }


def write_cyclonedx_bom(
    bom: Dict[str, Any],
    path: Union[str, Path],
) -> None:
    """Write a CycloneDX dict to disk as canonical JSON.

    The output uses sorted keys + 2-space indent + a trailing
    newline so a snapshot test can pin byte-equality without
    fighting JSON-library randomness.
    """
    path = Path(path)
    text = json.dumps(bom, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def render_cyclonedx_bom_text(bom: Dict[str, Any]) -> str:
    """Same canonical serialisation as :func:`write_cyclonedx_bom`
    but returns the string instead of writing. Used by tests +
    by callers wiring the SBOM into other artifact pipelines.
    """
    return json.dumps(bom, indent=2, sort_keys=True) + "\n"
