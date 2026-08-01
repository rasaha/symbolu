#!/usr/bin/env python3
"""Proposed-action evaluation — would this action complete a harmful story?

``evaluate_proposed_action`` simulates whether a proposed action would complete
the frozen account-takeover story, given the already-assembled events. It is
**non-mutating** (it only reports) and **advisory** (signal ESCALATE, never a
binding effect). Deterministic; synthetic data; public API only.

    python examples/proposed_action_evaluation.py
"""

from __future__ import annotations

import copy

from ugence_storygraph import ACCOUNT_TAKEOVER_TRANSFER, evaluate_proposed_action
from ugence_storygraph import financial as F
from ugence_storygraph.storygraph import ObservedEvent


def _event(fragment_id, eid, position, **entities):
    # ObservedEvent(fragment_id, event_id, position, epoch, actor, entities)
    return ObservedEvent(fragment_id, eid, position, position, "actor://user", dict(entities))


def main() -> int:
    assembly = [
        _event(F.CRED_RESET, "r", 1, account="a1"),
        _event(F.DEVICE_NEW, "d", 2, account="a1", device="d1"),
        _event(F.BENEFICIARY_ADD, "bn", 3, account="a1", beneficiary="bob"),
    ]
    proposed = _event(F.TRANSFER, "x", 9, account="a1", beneficiary="bob",
                      device="d1", amount="9000")

    assembly_before = copy.deepcopy(assembly)
    proposed_before = copy.deepcopy(proposed)

    result = evaluate_proposed_action(assembly, proposed, ACCOUNT_TAKEOVER_TRANSFER)

    print("category:", result.category)
    print("signal:  ", result.signal, "(advisory — never ALLOW/DENY)")
    print("completes harmful story:", result.completion_witness["completes"])
    print("verdict digest:", result.verdict_digest)

    # Non-mutation: inputs are untouched, and the verdict is reproducible.
    assert assembly == assembly_before and proposed == proposed_before
    assert result.signal == "ESCALATE"
    assert result.category == "WOULD_COMPLETE_PROHIBITED_CAPABILITY"
    again = evaluate_proposed_action(assembly, proposed, ACCOUNT_TAKEOVER_TRANSFER)
    assert again.verdict_digest == result.verdict_digest
    print("OK — non-mutating, deterministic, advisory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
