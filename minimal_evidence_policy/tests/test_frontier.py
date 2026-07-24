"""Phase 16 tests: a safe-and-useful region exists; risk-only is inadmissible (unsafe); the minimal
policy earns its use on safety."""
from minimal_evidence_policy import frontier as f


def test_safe_useful_region_exists():
    m = f.compute()
    assert "Full_minimal" in m["admissible_safe_and_useful"]
    assert len(m["admissible_safe_and_useful"]) >= 3


def test_risk_only_inadmissible():
    m = f.compute()
    assert "D_risk_only" not in m["admissible_safe_and_useful"]


def test_minimal_earns_use_on_safety():
    e = f.compute()["minimal_earns_use"]
    assert e["beats_risk_only_on_safety"] is True
    assert e["beats_rich_component_on_safety"] is True
