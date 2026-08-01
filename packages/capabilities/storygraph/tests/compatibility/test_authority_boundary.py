"""S8 — StoryGraph remains advisory (cannot authorize/clear/decide/execute).

Confirms the authority ceiling survived the migration: the signal vocabulary is
exactly {OBSERVE, ESCALATE, UNAVAILABLE}, advisory evidence is classed
ADVISORY with an OBSERVE/ESCALATE effect ceiling, and no binding verb
(ALLOW/DENY/AUTHORIZE/BLOCK/EXECUTE/CLEAR/PERMIT) is exposed on the public API or
emitted by the evidence adapter.
"""

from __future__ import annotations

from ugence_storygraph import (
    BY_CASE,
    DIGITAL_ONTOLOGY,
    SequenceRiskAnalyzer,
    signals,
    to_advisory_evidence,
)
from ugence_storygraph import api
from ugence_storygraph.demos import scenarios

_BINDING_VERBS = {"ALLOW", "DENY", "AUTHORIZE", "BLOCK", "EXECUTE", "CLEAR", "PERMIT"}


def _harmful_finding():
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY)
    out = []
    for ev in scenarios.exfiltration_events:
        out.extend(az.observe(ev))
    esc = [f for f in out if f.signal == signals.ESCALATE]
    assert esc, "expected an escalating finding"
    return esc[0]


def test_signal_vocabulary_is_advisory_only():
    assert {signals.OBSERVE, signals.ESCALATE, signals.UNAVAILABLE} == {
        "OBSERVE", "ESCALATE", "UNAVAILABLE"}
    for v in _BINDING_VERBS:
        assert not hasattr(signals, v), v


def test_advisory_evidence_is_classed_advisory_with_effect_ceiling():
    finding = _harmful_finding()
    ev = to_advisory_evidence(finding, bound_to="act:abc", generated_at="2026-01-01T00:00:00Z")
    payload = ev["payload"]
    assert payload["authority"] == "ADVISORY"
    assert payload["effect"] in ("OBSERVE", "ESCALATE")   # never a binding effect
    assert ev["evidence_hash"].startswith("sha-256:")


def test_public_api_exposes_no_binding_verb():
    # No PUBLIC_STABLE symbol name is a binding verb.
    for name in api.__all__:
        assert name.upper() not in _BINDING_VERBS, name


def test_analyzer_only_ever_emits_advisory_signals():
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY)
    seen = set()
    for ev in scenarios.exfiltration_events:
        for f in az.observe(ev):
            seen.add(f.signal)
    assert seen <= {signals.OBSERVE, signals.ESCALATE, signals.UNAVAILABLE}
