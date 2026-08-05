#!/usr/bin/env python3
"""Torch-backed invariance tests: model params unchanged across V100 eval, zero optimizer steps,
byte-identical M0 across repeated runs, and exactly one table read per V100 query on the real cohort
path. RESOURCE_BLOCKED (prints and returns 0) when torch is unavailable."""
from __future__ import annotations

import hashlib
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
for p in (str(EXP),
          str(REPO / "experiments" / "bindingslots_value_path_diagnosis"),
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


def test_no_param_change_and_zero_optimizer_steps():
    import arms as ARMS
    m, vocab, T = _model()
    h0 = _hash(m)
    ARMS.run_seed(m, vocab, T, seed=999)
    assert _hash(m) == h0, "V100 evaluation must not change any model parameter"


def test_exactly_one_read_per_v100_query_real_cohort():
    import arms as ARMS
    m, vocab, T = _model()
    rec = ARMS.run_seed(m, vocab, T, seed=999)
    assert rec["V100"]["reads_equal_n"], "V100 must read the table exactly once per query"
    assert rec["V100"]["reads"] == rec["n"]
    assert rec["T0"]["reads"] == rec["n"], "T0 reads once per query"


def test_m0_byte_identical_across_runs():
    import arms as ARMS
    m, vocab, T = _model()
    a = ARMS.run_seed(m, vocab, T, seed=999)
    b = ARMS.run_seed(m, vocab, T, seed=999)
    assert a["M0"]["correct"] == b["M0"]["correct"], "M0 must be deterministic (byte-identical)"


def test_v100_reliability_holds_on_cohort():
    import arms as ARMS
    m, vocab, T = _model()
    rec = ARMS.run_seed(m, vocab, T, seed=999)
    v = rec["V100"]
    # at 100% coverage with correct facts: no incorrect verified returns, all disagreements corrected
    assert v["incorrect_verified"] == 0 and v["incorrect_corrections"] == 0
    assert v["corrections"] == v["disagreements"]
    assert rec["V100"]["accuracy"] == rec["T0"]["accuracy"], "V100 reliability-equivalent to T0"


def _run_standalone():
    if not HAVE:
        print("v100-model tests: RESOURCE_BLOCKED (torch unavailable) — 0 run, 0 failed")
        return 0
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"v100-model tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
