"""Hiring-domain adapters that implement the DGM kernel ports.

The application injects these adapters so kernel services operate on the neutral
port contracts without importing hiring record types.
"""

from __future__ import annotations

from .linked_records import HiringAssessmentLinkedRecordAdapter

__all__ = ["HiringAssessmentLinkedRecordAdapter"]
