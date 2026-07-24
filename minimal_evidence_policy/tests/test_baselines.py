"""Phase 7 tests: baseline sweep deterministic; minimal policy safe on both sets; rich component fails
adversarial invariants; unsafe shortcuts leak."""
from minimal_evidence_policy import baselines as b


def test_deterministic():
    import json, hashlib
    a = hashlib.sha256(json.dumps(b.compute()["baselines"], sort_keys=True).encode()).hexdigest()
    c = hashlib.sha256(json.dumps(b.compute()["baselines"], sort_keys=True).encode()).hexdigest()
    assert a == c


def test_full_minimal_safe_both_sets():
    m = b.compute()["baselines"]["Full_minimal"]
    assert m["held_out_natural"]["unsafe_allow"] == 0
    assert m["adversarial"]["unsafe_allow"] == 0
    assert m["held_out_natural"]["clean_allow_rate"] > 0.0     # improves on prior 0%


def test_rich_component_fails_adversarial_invariants():
    m = b.compute()["baselines"]["I_rich_component"]
    assert m["adversarial"]["unsafe_allow"] > 30               # lacks hard invariants


def test_global_threshold_unsafe():
    m = b.compute()["baselines"]["B_global_threshold"]
    assert m["held_out_natural"]["unsafe_allow"] > 0
    assert m["adversarial"]["unsafe_allow"] > 0
