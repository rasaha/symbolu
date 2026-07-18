"""Deterministic downstream-task benchmark (information-preservation proxy).

IMPORTANT — HONEST SCOPE: no runnable open-weights LLM is present in this
environment (no transformers, no checkpoints; only a canned MockLLMAdapter). A real
LLM accuracy benchmark is therefore DEFERRED and requires plugging in open weights.

This proxy measures whether the information needed to answer a question survives
compression: a question is "answerable" from a compressed context iff the span(s)
that determine its ground-truth answer are retained. It separates:
  * decision_relevant questions — answer carried by a gate-critical span (the
    product's actual task: preserve what governs the action).
  * incidental questions — answer carried by a filler span (nice-to-have detail).

Accuracy here is an UPPER BOUND on real LLM accuracy (a span being present does not
guarantee an LLM uses it), and is labelled as such wherever reported.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import annotation


@dataclass
class TaskResult:
    decision_accuracy: float      # answerable decision-relevant questions
    incidental_accuracy: float    # answerable incidental questions
    n_decision: int
    n_incidental: int


def _critical_units(run) -> set:
    return (run.decision_units | run.envelope_units | run.assurance_units
            | run.structure_units | run.redundant_units | run.interaction_units)


def build_questions(item, run):
    """Return list of (answer_span_ids, kind). A question is decision_relevant if its
    answer is carried by a gate-critical span, else incidental."""
    crit = _critical_units(run)
    qs = []
    for u in item.context.units:
        if u.id in crit:
            # decision-relevant: the answer depends on this span (or, for redundant
            # facts, on any member of its redundancy set)
            if u.redundancy_set:
                span_set = frozenset(x.id for x in item.context.units
                                     if x.redundancy_set == u.redundancy_set)
            else:
                span_set = frozenset({u.id})
            qs.append((span_set, "decision"))
        else:
            qs.append((frozenset({u.id}), "incidental"))
    return qs


def score(item, run, surviving_ids) -> TaskResult:
    surviving = set(surviving_ids)
    dok = dtot = iok = itot = 0
    for span_set, kind in build_questions(item, run):
        answerable = bool(span_set & surviving)   # answer survives if any carrier remains
        if kind == "decision":
            dtot += 1
            dok += 1 if answerable else 0
        else:
            itot += 1
            iok += 1 if answerable else 0
    return TaskResult(
        decision_accuracy=(dok / dtot if dtot else 1.0),
        incidental_accuracy=(iok / itot if itot else 1.0),
        n_decision=dtot, n_incidental=itot)
