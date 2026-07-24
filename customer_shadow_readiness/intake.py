"""Secure artifact intake (M6). Validates, bounds, and de-identifies an incoming artifact before it may
enter the read-only runtime. NON-ENFORCING, shadow-only. Deterministic. Fails closed on oversize/
malformed/non-permitted artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import data_controls as dc

MAX_TEXT_CHARS = 20000
ALLOWED_FORMS = {"text", "claim_set"}


@dataclass
class IntakeResult:
    accepted: bool
    artifact_class: str = ""
    redacted_text: str = ""
    reason_codes: List[str] = field(default_factory=list)


def intake(text: str, request_clearance: str, output_form: str = "text") -> IntakeResult:
    codes: List[str] = []
    if not isinstance(text, str) or not text.strip():
        return IntakeResult(False, reason_codes=["INTAKE.EMPTY"])
    if len(text) > MAX_TEXT_CHARS:
        return IntakeResult(False, reason_codes=["INTAKE.OVERSIZE"])
    if output_form not in ALLOWED_FORMS:
        return IntakeResult(False, reason_codes=[f"INTAKE.BAD_FORM:{output_form}"])
    cls = dc.classify(text)
    if not dc.permitted_use(cls, request_clearance):
        return IntakeResult(False, artifact_class=cls,
                            reason_codes=[f"INTAKE.NOT_PERMITTED:{cls}>{request_clearance}"])
    return IntakeResult(True, artifact_class=cls, redacted_text=dc.redact(text),
                        reason_codes=["INTAKE.ACCEPTED"])
