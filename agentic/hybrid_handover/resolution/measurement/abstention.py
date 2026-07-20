#!/usr/bin/env python3
"""
Abstention as a DECISION problem (replaces the gameable single-number abstention
metric). An always-abstain resolver must score poorly overall.

Confusion counts over all cases:
  TA true abstention   (gold abstain,  resolver abstain)
  FA false abstention  (gold answer,   resolver abstain)   <- the harm
  MA missed abstention (gold abstain,  resolver answer)
  TN true answer       (gold answer,   resolver answer)

Metrics:
  abstention_precision = TA / (TA + FA)     — of what it refused, how much deserved it
  abstention_recall    = TA / (TA + MA)     — of what deserved refusal, how much it caught
  answer_coverage      = (answered) / N     — how often it actually answers
  selective_accuracy   = correct answers on ANSWERED cases / answered
An always-abstain resolver: recall 1.0 but precision low, coverage 0, selective
accuracy undefined→0 → overall useless.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.gold import GOLD
from agentic.hybrid_handover.resolution.modes import mode_oracle


def _answer_correct(result, expected, gold) -> bool:
    if gold.abstain:
        return result.governance.abstain
    if result.governance.abstain:
        return False
    return (result.tfc, result.notice_days, result.penalty) == (
        expected.termination_for_convenience, expected.notice_days, expected.penalty)


def _governance_owned(gold) -> bool:
    # pure-coverage abstention (OCR) is SafetyGate-owned, not the resolver's
    return not (gold.capabilities == ["coverage"])


def abstention_metrics(resolver, cases):
    TA = FA = MA = TN = 0
    answered = correct_answered = 0
    for case in cases:
        gold = GOLD[case.case_id]
        if not _governance_owned(gold):
            continue
        res = resolver.resolve(case.question, mode_oracle(case))
        ab = res.governance.abstain
        if gold.abstain and ab:
            TA += 1
        elif not gold.abstain and ab:
            FA += 1
        elif gold.abstain and not ab:
            MA += 1
        else:
            TN += 1
        if not ab:
            answered += 1
            if _answer_correct(res, case.expected_answer, gold):
                correct_answered += 1
    return {
        "abstention_precision": _r(TA, TA + FA),
        "abstention_recall": _r(TA, TA + MA),
        "answer_coverage": _r(answered, len(cases)),
        "selective_accuracy": _r(correct_answered, answered),
        "_counts": {"TA": TA, "FA": FA, "MA": MA, "TN": TN},
    }


def _r(a, b):
    return round(a / b, 4) if b else 0.0
