"""Procurement reference policy pack and its offline approval fixture.

This example encodes the *existing* Ugence Procurement reference workflow as a
structured, reviewed policy pack. It uses Procurement's real behavior and reason
codes as the authoritative reference and invents no controls Procurement does not
implement. The approval record here is a clearly-labeled offline fixture — not a
real reviewer authority.
"""

from __future__ import annotations

from .pack import (
    build_procurement_approval_fixture,
    build_procurement_policy_pack,
)

__all__ = [
    "build_procurement_policy_pack",
    "build_procurement_approval_fixture",
]
