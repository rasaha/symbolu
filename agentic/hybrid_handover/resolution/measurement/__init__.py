#!/usr/bin/env python3
"""Repaired, owner-clean measurement layer for Relationship Resolution.

Each metric answers exactly one question and has exactly one owner. Reads only;
modifies no resolver and nothing frozen.
"""
from .owners import METRIC_OWNER, OWNERS, assert_single_owner
from .run_measurement import run
__all__ = ["METRIC_OWNER", "OWNERS", "assert_single_owner", "run"]
