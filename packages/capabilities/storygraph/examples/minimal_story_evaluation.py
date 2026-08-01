#!/usr/bin/env python3
"""Minimal StoryGraph evaluation — advisory sequence-risk over an event stream.

Feeds a synthetic *admitted-action* stream (each action already cleared a
per-action gate) to the advisory ``SequenceRiskAnalyzer`` and prints its findings.
A harmful assembly escalates; a benign look-alike does not. StoryGraph only ever
emits OBSERVE / ESCALATE / UNAVAILABLE — never ALLOW/DENY/AUTHORIZE.

Deterministic, synthetic data only. Public API only. Runs against the installed
``ugence_storygraph`` wheel:  python examples/minimal_story_evaluation.py
"""

from __future__ import annotations

from ugence_storygraph import BY_CASE, DIGITAL_ONTOLOGY, SequenceRiskAnalyzer, signals

# Shipped synthetic illustrations (not a benchmark, not enterprise data).
from ugence_storygraph.demos import scenarios


def _run(events):
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,))
    found = []
    for event in events:
        found.extend(az.observe(event))
    return found


def main() -> int:
    harmful = _run(scenarios.exfiltration_events)
    benign = _run(scenarios.benign_migration_events)

    harmful_signals = {f.signal for f in harmful}
    benign_signals = {f.signal for f in benign}

    print("harmful assembly  -> signals:", sorted(harmful_signals))
    for f in harmful:
        if f.signal == signals.ESCALATE:
            print("   ESCALATE:", f.explanation)
            break
    print("benign look-alike -> signals:", sorted(benign_signals) or ["(none)"])

    # Advisory invariants: harmful escalates; benign does not; nothing binding.
    assert signals.ESCALATE in harmful_signals, harmful_signals
    assert signals.ESCALATE not in benign_signals, benign_signals
    assert harmful_signals <= {signals.OBSERVE, signals.ESCALATE, signals.UNAVAILABLE}
    print("OK — StoryGraph produced advisory-only findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
