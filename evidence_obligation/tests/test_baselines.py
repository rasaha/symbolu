"""Phase 8 tests: baseline sweep is deterministic; unsafe shortcuts leak adversarial unsafe; safe
policies (C/P/Q/S) do not; oracle is perfect.
"""
from evidence_obligation import baselines as b


def test_baseline_sweep_deterministic():
    import json, hashlib
    a = hashlib.sha256(json.dumps(b.compute()["baselines"], sort_keys=True).encode()).hexdigest()
    c = hashlib.sha256(json.dumps(b.compute()["baselines"], sort_keys=True).encode()).hexdigest()
    assert a == c


def test_unsafe_shortcuts_leak_adversarial_unsafe():
    m = b.compute()["baselines"]
    for name in ("D_domain_only", "F_source_role_only", "K_global_threshold_reduction",
                 "N_impl_always_auth", "O_nogate_all_lowrisk"):
        assert m[name]["adversarial"]["unsafe_assignments"] > 0, name


def test_safe_policies_zero_adversarial_unsafe():
    m = b.compute()["baselines"]
    for name in ("C_risk_only", "P_simple_contextual", "Q_reference", "S_learned"):
        assert m[name]["adversarial"]["unsafe_assignments"] == 0, name


def test_oracle_perfect():
    m = b.compute()["baselines"]
    assert m["R_oracle"]["held_out_natural"]["exact_accuracy"] == 1.0
