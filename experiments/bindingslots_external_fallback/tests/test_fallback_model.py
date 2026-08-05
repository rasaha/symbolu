#!/usr/bin/env python3
"""Torch-backed tests: extract integrity, no model parameter/optimizer change, fallback-disabled
equals M0, table-only correctness, provenance on fallback. RESOURCE_BLOCKED (return 0) without torch."""
from __future__ import annotations

import hashlib
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
for p in (str(EXP), str(REPO / "experiments" / "bindingslots_value_path_diagnosis"),
          str(REPO / "hybrid_llm_vnext_lab" / "experiments" / "slot_formation_stabilization")):
    sys.path.insert(0, p)

try:
    import torch  # noqa: F401
    HAVE = True
except Exception:
    HAVE = False


def _model():
    import _nso
    import interventions as IV
    MDL, TA = _nso.models, _nso.tasks_adapter
    vocab = TA.build_corpus()[1]
    m, _, _ = MDL.build_matched("S", len(vocab), 2000000, d=128, h=4, layers=4, max_len=1200,
                                window=TA.WINDOW, num_slots=32)
    IV.install_capture_hooks(m); m.eval()
    return m, vocab, _nso.tasks


def _hash(m):
    h = hashlib.sha256()
    for n, p in sorted(m.named_parameters()):
        h.update(n.encode()); h.update(p.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def test_extract_has_legitimate_key_and_signals():
    import fallback as FB
    m, vocab, T = _model()
    ex = FB.extract(m, vocab, T)
    assert len(ex) == 120
    for e in ex[:20]:
        assert e["entity_id"].isdigit()
        s = e["signals"]
        assert 0.0 <= s["top1_prob"] <= 1.0 and s["entropy"] >= 0.0


def test_no_model_parameter_change():
    import fallback as FB
    from ephemeral_table import EphemeralTable
    m, vocab, T = _model()
    h0 = _hash(m)
    FB.run_arms(m, vocab, T, EphemeralTable(), FB.Trigger(0.5, 0.15, 2.0), session_id="s")
    assert _hash(m) == h0, "inference-only: model weights must not change"


def test_fallback_disabled_equals_m0():
    import fallback as FB
    from ephemeral_table import EphemeralTable
    m, vocab, T = _model()
    # a trigger that never fires (all thresholds trivial) -> F1 == M0
    never = FB.Trigger(prob_min=-1.0, margin_min=-1.0, entropy_max=1e9)
    r = FB.run_arms(m, vocab, T, EphemeralTable(), never, session_id="s")
    assert r["F1"]["fallback_invoked"] == 0
    assert r["F1"]["correct"] == r["M0"]["correct"], "fallback disabled must equal BindingSlots-only"


def test_table_only_correct_and_provenance():
    import fallback as FB
    from ephemeral_table import EphemeralTable
    m, vocab, T = _model()
    always = FB.Trigger(prob_min=2.0, margin_min=2.0, entropy_max=-1.0)  # always fires
    r = FB.run_arms(m, vocab, T, EphemeralTable(), always, session_id="s")
    assert r["T0"]["correct"] == r["n"], "table-only must be fully correct (facts written at write time)"
    assert r["F1"]["provenance_complete"] == r["F1"]["fallback_invoked"], "provenance on every fallback"


def _run_standalone():
    if not HAVE:
        print("fallback-model tests: RESOURCE_BLOCKED (torch unavailable) — 0 run, 0 failed")
        return 0
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"fallback-model tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
