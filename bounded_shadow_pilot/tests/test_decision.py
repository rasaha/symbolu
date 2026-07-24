"""Phase 21 test: the architectural decision is evidence-gated and selects Option 4 (gate the external
pilot on utility calibration) given safe + auditable + native-preserved but utility does not transfer.
"""
from bounded_shadow_pilot import architectural_decision as ad


def test_decision_is_gate_external_on_utility():
    m = ad.decide()
    d = m["dimension_findings"]
    assert d["safe"] and d["auditable"] and d["actiongate_native_preserved"]
    assert d["useful"] is False and d["stopped"] is False and d["enough_evidence"] is True
    assert m["chosen_option_index"] == 4                     # do not proceed external; gate it
    # safety/actiongate/evidence "fix-first/stop/insufficient" options are NOT chosen
    chosen = [v for v in m["option_verdicts"] if v["chosen"]]
    assert len(chosen) == 1


def test_no_stop_and_no_unhandled_failures():
    m = ad.decide()
    assert m["dimension_findings"]["unhandled_new_failures"] is False
