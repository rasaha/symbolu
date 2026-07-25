"""Job-relevance and prohibited-field quarantine.

Operates on the *named fields* of structured evidence. Each field is classified:

* **PROHIBITED** — matches a configured protected-attribute rule (age, race,
  gender, ...). Withheld and stored separately; never deleted, never exposed to
  evaluation.
* **JOB_RELEVANT** — on the job-relevant allowlist (if one is configured) or,
  when no allowlist is configured, any non-prohibited field. Proceeds downstream.
* **NON_JOB_RELEVANT** — matches a configured not-relevant rule. Quarantined.
* **UNKNOWN** — neither allowlisted nor recognized when an allowlist *is*
  configured. Quarantined (unknown goes to quarantine).

Rules are configurable via :class:`QuarantinePolicy`. Matching is
case-insensitive and alias-aware (e.g. ``dob`` → age, ``sex`` → gender). This
module never inspects free-text semantics — it only classifies field identity;
no scoring or inference occurs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping

from .models import QuarantineCategory, QuarantinedField, RelevanceClass

# Default protected-attribute field names / aliases (normalized, lowercase).
DEFAULT_PROHIBITED: dict[str, tuple[str, ...]] = {
    "age": ("age", "dob", "dateofbirth", "birthdate", "birthday"),
    "race": ("race", "ethnicity", "ethnic", "skincolor"),
    "gender": ("gender", "sex"),
    "religion": ("religion", "faith", "religiousaffiliation"),
    "pregnancy": ("pregnancy", "pregnant", "maternity"),
    "national_origin": ("nationalorigin", "nationality", "citizenship", "birthcountry"),
    "political_affiliation": ("political", "politicalaffiliation", "party"),
    "medical_history": ("medical", "medicalhistory", "health", "healthcondition"),
    "disability": ("disability", "disabled", "handicap"),
    "sexual_orientation": ("sexualorientation", "orientation", "lgbt"),
    "marital_status": ("maritalstatus", "married", "spouse"),
}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


@dataclass(frozen=True)
class QuarantinePolicy:
    """Configurable quarantine rules.

    * ``prohibited`` maps a protected category to the field-name aliases that
      trigger it.
    * ``job_relevant_allowlist`` — if non-empty, fields not on it are UNKNOWN and
      quarantined; if empty, any non-prohibited field is treated JOB_RELEVANT.
    * ``non_job_relevant`` — explicit not-relevant field aliases.
    """

    prohibited: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: dict(DEFAULT_PROHIBITED)
    )
    job_relevant_allowlist: frozenset[str] = frozenset()
    non_job_relevant: frozenset[str] = frozenset()

    def _prohibited_category(self, normalized_name: str) -> str | None:
        for category, aliases in self.prohibited.items():
            if any(normalized_name == _norm(a) or normalized_name.find(_norm(a)) == 0
                   for a in aliases):
                return category
        return None

    def classify(self, field_name: str) -> tuple[RelevanceClass, QuarantineCategory | None, str]:
        """Return (relevance, quarantine_category_or_None, reason)."""
        norm = _norm(field_name)
        prohibited_cat = self._prohibited_category(norm)
        if prohibited_cat is not None:
            return (
                RelevanceClass.NON_JOB_RELEVANT,
                QuarantineCategory.PROHIBITED,
                f"matches prohibited attribute '{prohibited_cat}'",
            )
        if norm in {_norm(a) for a in self.non_job_relevant}:
            return (
                RelevanceClass.NON_JOB_RELEVANT,
                QuarantineCategory.NON_JOB_RELEVANT,
                "configured non-job-relevant field",
            )
        if self.job_relevant_allowlist:
            if norm in {_norm(a) for a in self.job_relevant_allowlist}:
                return (RelevanceClass.JOB_RELEVANT, None, "on job-relevant allowlist")
            return (
                RelevanceClass.UNKNOWN,
                QuarantineCategory.UNKNOWN,
                "not on job-relevant allowlist (unknown -> quarantine)",
            )
        return (RelevanceClass.JOB_RELEVANT, None, "no allowlist configured; non-prohibited")


DEFAULT_POLICY = QuarantinePolicy()


@dataclass(frozen=True)
class QuarantineResult:
    clean_fields: dict[str, str]
    quarantined: tuple[QuarantinedField, ...]


class QuarantineEngine:
    """Applies a :class:`QuarantinePolicy` to a field mapping."""

    def __init__(self, policy: QuarantinePolicy = DEFAULT_POLICY) -> None:
        self._policy = policy

    def apply(self, fields: Mapping[str, str]) -> QuarantineResult:
        clean: dict[str, str] = {}
        quarantined: list[QuarantinedField] = []
        for name, value in fields.items():
            relevance, category, reason = self._policy.classify(name)
            if category is None and relevance is RelevanceClass.JOB_RELEVANT:
                clean[name] = value
            else:
                quarantined.append(
                    QuarantinedField(
                        field_name=name,
                        category=category or QuarantineCategory.UNKNOWN,
                        reason=reason,
                        value=value,
                    )
                )
        return QuarantineResult(clean_fields=clean, quarantined=tuple(quarantined))
