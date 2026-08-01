"""Backward-compat: the original prototype's entry point still illustrates.

The first version exposed ``CompositeThreatMonitor(...).observe(event)`` grouped
by correlation. The facade preserves that so the firearm and exfiltration
illustrations keep working; new code should use ``SequenceRiskAnalyzer``.
"""

from __future__ import annotations

from composite_threat_detector import (
    DIGITAL_ONTOLOGY,
    PHYSICAL_FIREARM_ONTOLOGY,
    CompositeThreatMonitor,
    signals,
)
from demos import scenarios


def test_firearm_illustration_still_escalates():
    mon = CompositeThreatMonitor(PHYSICAL_FIREARM_ONTOLOGY)
    out = []
    for ev in scenarios.firearm_events:
        out.extend(mon.observe(ev))
    assert any(f.signal == signals.ESCALATE for f in out)
    assert all(f.signal in (signals.OBSERVE, signals.ESCALATE) for f in out)


def test_exfiltration_illustration_still_escalates():
    mon = CompositeThreatMonitor(DIGITAL_ONTOLOGY)
    out = []
    for ev in scenarios.exfiltration_events:
        out.extend(mon.observe(ev))
    assert any(f.signal == signals.ESCALATE and f.recipe_id == "DATA_EXFILTRATION_ASSEMBLY"
               for f in out)


def test_partial_assembly_is_observe():
    mon = CompositeThreatMonitor(PHYSICAL_FIREARM_ONTOLOGY)
    mon.observe(scenarios.firearm_events[0])          # barrel only (1/3)
    out = mon.observe(scenarios.firearm_events[1])    # + firing mechanism (2/3)
    assert out and out[0].signal == signals.OBSERVE
