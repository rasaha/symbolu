"""
ablations.py — §14 causal ablations for V3-ABC via eval-time control overrides.

Each override is applied through SelectiveComplexPhaseV3._controls (no retraining), so the
gain can be attributed to meaningful input-dependent controls. Predicted effects (§17):
    A_t fixed/shuffled/detached  → retention loses input dependence → focus decode drops
    B_t forced_one               → dense write (v1-like dilution) → drop
    B_t forced_zero              → nothing written → chance
    B_t shuffled                 → wrong write pattern → drop
    C_t forced_zero              → readout suppressed → chance
    omega forced_zero            → no rotation (still may retain) → smaller effect
    gamma fixed                  → no selective persistence → drop

Also isolates the marginal value of each selection axis (write / retention / read alone
and in pairs) using the same overrides.
"""
from __future__ import annotations

from .focus_probe import probe_all

# (label, overrides) — overrides passed to model.features(..., overrides=...)
SINGLE = [
    ("baseline", {}),
    ("A_fixed", {"a_mode": "fixed"}),
    ("A_shuffled", {"a_mode": "shuffled"}),
    ("A_detached", {"a_mode": "detached"}),
    ("B_forced_one", {"b_mode": "forced_one"}),
    ("B_forced_zero", {"b_mode": "forced_zero"}),
    ("B_shuffled", {"b_mode": "shuffled"}),
    ("B_detached", {"b_mode": "detached"}),
    ("C_forced_one", {"c_mode": "forced_one"}),
    ("C_forced_zero", {"c_mode": "forced_zero"}),
    ("C_shuffled", {"c_mode": "shuffled"}),
    ("C_detached", {"c_mode": "detached"}),
    ("omega_zero", {"omega_mode": "forced_zero"}),
    ("gamma_fixed", {"gamma_mode": "fixed"}),
]

# isolate selection axes (§14): which controls remain input-dependent
ISOLATE = [
    ("write_only", {"gamma_mode": "fixed", "omega_mode": "forced_zero", "c_mode": "forced_one"}),
    ("retention_only", {"b_mode": "forced_one", "c_mode": "forced_one"}),
    ("read_only", {"gamma_mode": "fixed", "omega_mode": "forced_zero", "b_mode": "forced_one"}),
    ("write+retention", {"c_mode": "forced_one"}),
    ("write+read", {"gamma_mode": "fixed", "omega_mode": "forced_zero"}),
    ("full_ABC", {}),
]


def _probe_with_override(model, vocab, dcfg, distance, overrides, seed):
    # temporarily install overrides by monkey-passing through model.features via a closure
    orig = model.features

    def patched(ids, overrides=overrides):
        return orig(ids, overrides=overrides)
    model.features = patched
    try:
        r = probe_all(model, vocab, dcfg, distance, seed=seed, n_train=500, n_eval=350)
    finally:
        model.features = orig
    return r


def run_ablations(model, vocab, dcfg, distance=256, seed=0):
    out = {"single": {}, "isolate": {}}
    for label, ov in SINGLE:
        r = _probe_with_override(model, vocab, dcfg, distance, ov, seed)
        out["single"][label] = {"state_top1": r["state"]["top1"],
                                "selective_top1": r["selective_readout"]["top1"],
                                "relevance_f1": r["relevance"]["f1"]}
    for label, ov in ISOLATE:
        r = _probe_with_override(model, vocab, dcfg, distance, ov, seed)
        out["isolate"][label] = {"state_top1": r["state"]["top1"],
                                 "selective_top1": r["selective_readout"]["top1"]}
    return out
