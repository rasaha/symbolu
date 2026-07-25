"""Hiring-domain adapters — canonical import surface.

Adapters bridge hiring-domain records onto the kernel's neutral ports. The
``HiringAssessmentLinkedRecordAdapter`` implements the kernel
``LinkedRecordPort`` over finalized hiring assessments, projecting only
governance-relevant fields onto a neutral ``LinkedRecordSnapshot`` (no evidence
or assessment content crosses the boundary).

The implementation lives physically under ``ai_hiring.adapters`` (retained for
import stability); this module is the canonical import location and preserves
object identity.
"""

from __future__ import annotations

from ai_hiring.adapters.linked_records import HiringAssessmentLinkedRecordAdapter

__all__ = ["HiringAssessmentLinkedRecordAdapter"]
