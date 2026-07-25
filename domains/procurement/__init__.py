"""Procurement domain — a reference domain on the Decision Governance kernel.

A small but complete procurement approval domain that consumes the frozen DGM
kernel (``decision_governance``) exactly as the hiring domain does: it supplies
domain contracts (purchase requests, policy assessments) and adapters onto the
kernel ports (linked-record, control-plane, external-execution), and drives the
same governance lifecycle. It depends on the kernel and never the reverse.
"""
from __future__ import annotations

__all__ = ["errors"]
