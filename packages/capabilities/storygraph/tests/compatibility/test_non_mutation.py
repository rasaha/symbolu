"""S8 — proposed-action evaluation is non-mutating.

``evaluate_proposed_action`` simulates whether a proposed action would complete a
harmful story. It must not mutate the graph, the assembled event history, or the
proposed action — it only reports. Verified against the frozen account-takeover
reference graph.
"""

from __future__ import annotations

import copy

from ugence_storygraph import (
    ACCOUNT_TAKEOVER_TRANSFER as ATO,
    evaluate_proposed_action,
)
from ugence_storygraph import financial as F
from ugence_storygraph.storygraph import ObservedEvent


def _oe(fragment_id, eid, pos, **entities):
    return ObservedEvent(fragment_id, eid, pos, pos, "actor://u", dict(entities))


def _scenario():
    assembly = [
        _oe(F.CRED_RESET, "r", 1, account="a1"),
        _oe(F.DEVICE_NEW, "d", 2, account="a1", device="d1"),
        _oe(F.BENEFICIARY_ADD, "bn", 3, account="a1", beneficiary="bob"),
    ]
    proposed = _oe(F.TRANSFER, "x", 9, account="a1", beneficiary="bob",
                   device="d1", amount="9000")
    return assembly, proposed


def test_evaluate_proposed_action_does_not_mutate_inputs():
    assembly, proposed = _scenario()
    assembly_before = copy.deepcopy(assembly)
    proposed_before = copy.deepcopy(proposed)

    r1 = evaluate_proposed_action(assembly, proposed, ATO)

    # inputs untouched
    assert assembly == assembly_before
    assert proposed == proposed_before

    # deterministic + repeatable: same digest on a second run
    r2 = evaluate_proposed_action(assembly, proposed, ATO)
    assert r1.verdict_digest == r2.verdict_digest


def test_reference_account_takeover_behavior_is_stable():
    assembly, proposed = _scenario()
    r = evaluate_proposed_action(assembly, proposed, ATO)
    # the proposed transfer completes the harmful account-takeover story, and the
    # verdict stays advisory (ESCALATE), never a binding effect
    assert r.category == "WOULD_COMPLETE_PROHIBITED_CAPABILITY"
    assert r.harmful_after_complete is True
    assert r.completion_witness["completes"] is True
    assert r.signal == "ESCALATE"
