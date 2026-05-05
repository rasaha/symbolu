"""CycloneDX SBOM generator for the BCVF Autonomy Runtime.

The SBOM is the *"where's your dependency manifest with versions
+ licenses?"* answer the procurement gate asks. CycloneDX 1.5 is
the format the SOTIF / ISO 26262 packages standardised on.

Public surface (provisional):

* :class:`SBOMComponent` — typed component dataclass.
* :func:`generate_cyclonedx_bom` — build the CycloneDX 1.5 dict.
* :func:`write_cyclonedx_bom` — serialize to JSON on disk.
* :func:`runtime_components` — auto-discovered runtime
  dependencies (numpy + stdlib for the autonomy runtime).

See ``ROS2_DDS_SBOM_DESIGN.md`` §6 for the design rationale.
"""

from .generator import (
    SBOMComponent,
    generate_cyclonedx_bom,
    runtime_components,
    write_cyclonedx_bom,
)


__all__ = [
    "SBOMComponent",
    "generate_cyclonedx_bom",
    "runtime_components",
    "write_cyclonedx_bom",
]
