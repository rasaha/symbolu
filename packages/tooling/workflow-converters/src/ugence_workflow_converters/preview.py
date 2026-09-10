"""The preview Workflow IR (CV-2, CV-5): synthesized, content-addressed, unapproved.

The compiler refuses to compile a DRAFT pack (``DRAFT -> COMPILED`` is an illegal
lifecycle transition) and a converter must never move a pack past DRAFT, so no
compiled release package exists here. What exists is the compiler's public
:class:`WorkflowSynthesizer` run over the validated draft: the same IR the compiler
would emit at stage 3, with no manifest, no release metadata and no approval. The
document carries a ``preview`` block saying exactly that, and a ``structural_digest``
that is the digest of the preview content, so the composer's adapter can identify the
source it adapted. It is what the Bring Your Workflow screen inspects.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from ugence_policy_workflow_compiler.api import PolicyPack
from ugence_policy_workflow_compiler.compiler import WorkflowSynthesizer
from ugence_policy_workflow_compiler.serialization import hashing

from .report import ConversionReport, PreviewSummary
from .version import CLAIM, PREVIEW_SCHEMA

PREVIEW_STATUS = "PREVIEW_UNAPPROVED"


def build_preview(pack: PolicyPack, report: ConversionReport) -> Optional[Dict[str, Any]]:
    """A preview document, or ``None`` when the draft did not validate."""
    if not report.validation.ok:
        return None
    ir = WorkflowSynthesizer().synthesize(pack).model_dump(mode="json")
    digest = hashing.digest(ir)
    return {
        "schema": PREVIEW_SCHEMA,
        "preview": {
            "status": PREVIEW_STATUS,
            "claim": CLAIM,
            "pack_id": pack.pack_id,
            "pack_status": pack.status.value,
            "converter": report.converter,
            "input_digest": report.source.input_digest,
            "note": ("synthesized from a DRAFT pack by the compiler's public synthesizer; no compiled "
                     "release package, manifest, approval or release metadata exists for it"),
        },
        "structural_digest": digest,
        "workflow_ir": ir,
    }


def summarize_preview(document: Optional[Dict[str, Any]]) -> Optional[PreviewSummary]:
    if document is None:
        return None
    ir = document["workflow_ir"]
    return PreviewSummary(status=PREVIEW_STATUS, ir_version=str(ir.get("ir_version", "")),
                          preview_digest=document["structural_digest"],
                          node_count=len(ir.get("nodes", [])), edge_count=len(ir.get("edges", [])))
