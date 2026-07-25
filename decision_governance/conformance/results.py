"""Shared result type for conformance checks."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    dimension: str
    name: str
    passed: bool
    detail: str = ""


def ok(dimension: str, name: str, detail: str = "") -> CheckResult:
    return CheckResult(dimension, name, True, detail)


def fail(dimension: str, name: str, detail: str = "") -> CheckResult:
    return CheckResult(dimension, name, False, detail)
