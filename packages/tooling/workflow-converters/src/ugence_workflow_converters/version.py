"""Distribution version and honest maturity metadata.

Owner ruling CV-1 to CV-5 (docs/architecture/ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md
section 23). Every boolean here is ``True`` only because a test in this package
proves it in this build; the deferred converters are ``False`` by ruling, and the two
claims a converter may never make are ``False`` by construction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

DISTRIBUTION_VERSION = "0.1.0"
DISTRIBUTION_NAME = "ugence-workflow-converters"
PRODUCT_NAME = "Ugence Workflow Converters"

#: The report schema every converter emits.
CONVERSION_REPORT_SCHEMA = "ugence.workflow-converters.conversion-report.v1"
#: The preview document's schema (a synthesized, unapproved Workflow IR).
PREVIEW_SCHEMA = "ugence.workflow-converters.preview-workflow-ir.v1"

#: Source formats, in ruling order. Only the first is implemented in this build.
IMPLEMENTED_FORMATS: Tuple[str, ...] = ("n8n",)
NEXT_FORMAT = "bpmn-2.0"
DEFERRED_FORMATS: Tuple[str, ...] = ("langgraph", "crewai", "autogen")
DEFERRED_REASON = ("deferred until a declarative export exists; converting these today would "
                   "mean importing or executing customer code, which CV-2 forbids")

#: The only claim a converter may make (CV-5), verbatim in every report.
CLAIM = ("Constructs were translated per the mapping table and nothing more. This report "
         "makes no claim of semantic equivalence, governance, approval, validation or "
         "executability. The emitted pack is a DRAFT for human review; the preview "
         "Workflow IR is unapproved.")


@dataclass(frozen=True)
class VersionInfo:
    distribution_name: str = DISTRIBUTION_NAME
    distribution_version: str = DISTRIBUTION_VERSION
    product_name: str = PRODUCT_NAME
    ruling: str = "ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md section 23, CV-1 to CV-5"
    implemented_formats: Tuple[str, ...] = IMPLEMENTED_FORMATS
    next_format: str = NEXT_FORMAT
    deferred_formats: Tuple[str, ...] = DEFERRED_FORMATS
    maturity: Dict[str, bool] = field(default_factory=lambda: {
        "n8n_converter_implemented": True,
        "bpmn_converter_implemented": False,
        "langgraph_converter_implemented": False,
        "crewai_converter_implemented": False,
        "autogen_converter_implemented": False,
        "offline_only": True,
        "emits_draft_pack_only": True,
        "preview_ir_unapproved": True,
        "semantic_equivalence_claimed": False,
        "governance_or_approval_conferred": False,
        "pilot_validated": False,
        "production_certified": False,
    })


def version_info() -> VersionInfo:
    return VersionInfo()
