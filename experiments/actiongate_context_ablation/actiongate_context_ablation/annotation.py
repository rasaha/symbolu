"""Two-pass annotation consistency check.

Pass 1 (declared): each unit carries an authored ``expected`` criticality label.
Pass 2 (independent, deterministic): the frozen gate + ablation engine derive the
unit's actual criticality. The two are compared; DISAGREEMENTS ARE RECORDED, not
silently resolved (task requirement). Agreement rate is a proxy for annotation
quality and is reported alongside results.
"""

from __future__ import annotations

from dataclasses import dataclass

from .labels import (
    ASSURANCE_CRITICAL, DECISION_CRITICAL, ENVELOPE_CRITICAL, NON_CRITICAL,
    REDUNDANT, STRUCTURE_CRITICAL, UNCERTAIN,
)

# priority when a unit carries several derived effects
_PRIORITY = [DECISION_CRITICAL, ENVELOPE_CRITICAL, ASSURANCE_CRITICAL,
             STRUCTURE_CRITICAL, REDUNDANT, NON_CRITICAL]


def derive_primary(run, uid: str) -> str:
    labels = set()
    if uid in run.decision_units:
        labels.add(DECISION_CRITICAL)
    if uid in run.envelope_units:
        labels.add(ENVELOPE_CRITICAL)
    if uid in run.assurance_units:
        labels.add(ASSURANCE_CRITICAL)
    if uid in run.structure_units:
        labels.add(STRUCTURE_CRITICAL)
    if uid in run.redundant_units:
        labels.add(REDUNDANT)
    for lab in _PRIORITY:
        if lab in labels:
            return lab
    return NON_CRITICAL


@dataclass
class Disagreement:
    item_id: str
    unit_id: str
    declared: str
    derived: str


@dataclass
class ReviewResult:
    n_units: int
    n_annotated: int
    n_agree: int
    n_disagree: int
    n_uncertain: int
    disagreements: list

    @property
    def agreement_rate(self) -> float:
        base = self.n_annotated - self.n_uncertain
        return (self.n_agree / base) if base else 1.0


def review(items, runs) -> ReviewResult:
    n_units = n_annot = n_agree = n_dis = n_unc = 0
    disagreements = []
    for it, run in zip(items, runs):
        for u in it.context.units:
            n_units += 1
            declared = u.expected
            if declared is None:
                continue
            n_annot += 1
            if declared == UNCERTAIN:
                n_unc += 1
                continue
            derived = derive_primary(run, u.id)
            if declared == derived:
                n_agree += 1
            else:
                n_dis += 1
                disagreements.append(Disagreement(it.item_id, u.id, declared, derived))
    return ReviewResult(n_units=n_units, n_annotated=n_annot, n_agree=n_agree,
                        n_disagree=n_dis, n_uncertain=n_unc, disagreements=disagreements)
