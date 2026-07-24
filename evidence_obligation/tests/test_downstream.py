"""Phase 15 tests: downstream utility eval is deterministic; the obligation CONCEPT (oracle) improves
utility at zero unsafe; unsafe shortcuts leak clean allows; the reference classifier's residual safety
gap is present and honestly non-zero.
"""
from evidence_obligation import downstream as ds


def test_downstream_deterministic():
    import json, hashlib
    a = hashlib.sha256(json.dumps(ds.compute()["policies"], sort_keys=True).encode()).hexdigest()
    b = hashlib.sha256(json.dumps(ds.compute()["policies"], sort_keys=True).encode()).hexdigest()
    assert a == b


def test_oracle_improves_utility_at_zero_unsafe():
    m = ds.compute()["policies"]
    o = m["R_oracle"]
    assert o["held_out_natural"]["clean_allow_rate"] > 0.20           # >> prior 0%
    assert o["held_out_natural"]["unsafe_allow"] == 0                 # concept is safe
    assert o["adversarial"]["unsafe_allow"] == 0


def test_prior_uniform_reproduces_failure():
    m = ds.compute()["policies"]
    p = m["prior_derivation_uniform"]["held_out_natural"]
    assert p["clean_allow_rate"] == 0.0
    assert p["over_qualification_rate"] >= 0.85


def test_unsafe_shortcuts_leak_clean_allows():
    m = ds.compute()["policies"]
    assert m["K_global_threshold_reduction"]["adversarial"]["unsafe_allow"] > 0
    assert m["O_nogate_all_lowrisk"]["adversarial"]["unsafe_allow"] > 0


def test_reference_classifier_has_honest_residual_gap():
    # the study reports Q's safety gap rather than hiding it: it is non-zero
    m = ds.compute()["policies"]
    q = m["Q_reference"]
    assert q["held_out_natural"]["clean_allow_rate"] > 0.5           # big utility gain
    assert q["adversarial"]["unsafe_allow"] > 0                      # honest residual safety gap
