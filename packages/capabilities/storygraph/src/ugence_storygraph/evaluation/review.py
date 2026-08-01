"""Operator-review simulation (§12).

A replayable review-feedback schema. For each escalation a reviewer fixture
records a disposition; the module computes review-burden and false-escalation
diagnostics. Review feedback is **read-only** with respect to the analyzer — it
MUST NOT be used to mutate rules during the same frozen evaluation run (§12).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# disposition categories (§12)
AGREE_RISK = "agree_genuine_risk"
AGREE_HOLD = "agree_hold_required"
BENIGN_VERIFIED = "benign_verified_approved"
BENIGN_LINKAGE_ERROR = "benign_analyzer_linkage_error"
BENIGN_RECIPE_BROAD = "benign_recipe_too_broad"
AMBIGUOUS_MORE_EVIDENCE = "ambiguous_more_evidence"
MISSED_CONTEXT = "missed_context"
INCORRECT_PURPOSE = "incorrect_purpose_verification"
DUPLICATE_ALERT = "duplicate_alert"
UNACTIONABLE = "unactionable_explanation"

AGREE = {AGREE_RISK, AGREE_HOLD}
FALSE_ESCALATION = {BENIGN_VERIFIED, BENIGN_LINKAGE_ERROR, BENIGN_RECIPE_BROAD}
DISPOSITIONS = (AGREE | FALSE_ESCALATION |
                {AMBIGUOUS_MORE_EVIDENCE, MISSED_CONTEXT, INCORRECT_PURPOSE,
                 DUPLICATE_ALERT, UNACTIONABLE})


@dataclass
class ReviewRecord:
    finding_id: str
    recipe_id: str
    disposition: str
    reviewer: str = ""
    time_to_disposition: float | None = None
    evidence_complete: bool = True
    note: str = ""

    def __post_init__(self):
        if self.disposition not in DISPOSITIONS:
            raise ValueError(f"unknown disposition {self.disposition!r}")


@dataclass
class ReviewLedger:
    """Records dispositions and computes read-only review metrics."""

    records: list = field(default_factory=list)

    def record(self, rec: ReviewRecord) -> None:
        self.records.append(rec)

    def metrics(self) -> dict:
        n = len(self.records)
        if n == 0:
            return {"reviewed": 0, "note": "no reviews recorded"}
        agree = sum(1 for r in self.records if r.disposition in AGREE)
        false_esc = sum(1 for r in self.records if r.disposition in FALSE_ESCALATION)
        dupes = sum(1 for r in self.records if r.disposition == DUPLICATE_ALERT)
        causes: dict = {}
        for r in self.records:
            if r.disposition in FALSE_ESCALATION:
                causes[r.disposition] = causes.get(r.disposition, 0) + 1
        by_recipe: dict = {}
        for r in self.records:
            by_recipe.setdefault(r.recipe_id, 0)
            by_recipe[r.recipe_id] += 1
        times = [r.time_to_disposition for r in self.records
                 if r.time_to_disposition is not None]
        return {
            "reviewed": n,
            "review_agreement_rate": round(agree / n, 4),
            "false_escalation_reviews": false_esc,
            "duplicate_alert_burden": dupes,
            "review_workload": n,
            "top_false_escalation_causes": dict(sorted(
                causes.items(), key=lambda kv: (-kv[1], kv[0]))),
            "reviews_by_recipe": dict(sorted(by_recipe.items())),
            "noisiest_recipe": max(by_recipe, key=lambda k: by_recipe[k]),
            "avg_evidence_completeness": round(
                sum(1 for r in self.records if r.evidence_complete) / n, 4),
            "mean_time_to_disposition": (round(sum(times) / len(times), 3)
                                         if times else "NOT RUN"),
            "note": ("Review feedback is read-only; it MUST NOT mutate rules "
                     "during a frozen evaluation run (§12)."),
        }
