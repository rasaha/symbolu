"""Synthetic tests for the realization-factored primitive-sequence recovery scaffold.

Proves (no real data, no real result, no Stage A):
  - canonical representation contains only OPAQUE atom IDs,
  - canonical representation is invariant under different realizations,
  - real vs scrambled is INVISIBLE at the canonical opaque level (relabeling invariance),
  - a realization is REQUIRED for scoring (opaque atoms cannot be scored),
  - English-gloss concatenation is treated as ONE realization, not ontology,
  - MRR scoring works,
  - the assignment-scramble null works (signal beats scramble; noise does not),
  - cross-realization-invariant signal -> ONTOLOGICAL_SIGNAL,
  - signal in only one realization -> REALIZATION_ARTIFACT,
  - no realization signal -> NO_SIGNAL,
  - encoder disagreement -> REALIZER_DEPENDENT; inconclusive -> INCONCLUSIVE,
  - runner returns NOT_RUN on real data.

    python3 experiments/primitive_sequence_recovery/test_primitive_sequence_recovery.py
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))
import canonical as C            # noqa: E402
import realization as R          # noqa: E402
import scoring as S              # noqa: E402
import decision as D             # noqa: E402
import run_primitive_recovery as RUN  # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


VARNAS = list("abcdef")
WORDS = ["ab", "bc", "cd", "de", "ef", "fa", "abc", "bcd", "cde", "def", "efa", "fab"]
ATOMS = list(range(len(VARNAS)))


def _tau():
    return C.real_assignment(VARNAS, seed=1)


def test_canonical_is_opaque_atom_ids_only():
    tau = _tau()
    seq = C.canonical_sequence("abc", tau)
    _check("canonical: sequence is a tuple", isinstance(seq, tuple))
    _check("canonical: every element is an opaque int atom ID",
           all(isinstance(a, int) for a in seq))
    # opaque = no content: an atom carries no gloss/vector attribute anywhere in canonical.py
    _check("canonical: module exposes no gloss/content mapping",
           not any(hasattr(C, n) for n in ("GLOSS", "glosses", "content", "meanings")))


def test_canonical_invariant_under_realizations():
    tau = _tau()
    seq = C.canonical_sequence("bcd", tau)
    # canonical_sequence takes NO realization; rendering with different R_j cannot change it
    atoms = sorted(set(tau.values()))
    r1 = R.make_signal_realization("r1", WORDS, atoms, tau, seed=1)
    r2 = R.make_noise_realization("r2", WORDS, atoms, seed=2)
    _check("canonical: identical regardless of realization",
           C.canonical_sequence("bcd", tau) == seq)
    _check("canonical: rendering r1 vs r2 does not alter the canonical sequence",
           C.canonical_sequence("bcd", tau) == seq
           and r1.render_query(seq).shape == r2.render_query(seq).shape)


def test_real_vs_scrambled_invisible_at_opaque_level():
    tau = _tau()
    tau_s = C.scramble_assignment(tau, seed=5)     # relabeling of atoms
    M_real = C.opaque_similarity_matrix(WORDS, tau)
    M_scram = C.opaque_similarity_matrix(WORDS, tau_s)
    _check("relabeling invariance: opaque similarity identical for real and scrambled",
           np.allclose(M_real, M_scram))
    # sanity: the assignments really do differ as label maps
    _check("relabeling: the two assignments are genuinely different label maps", tau != tau_s)


def test_realization_required_for_scoring():
    raised = False
    try:
        S.score_opaque(C.canonical_sequence("ab", _tau()))
    except ValueError:
        raised = True
    _check("scoring: opaque atoms cannot be scored (realization required)", raised)


def test_english_is_one_realization_not_ontology():
    tau = _tau()
    atoms = sorted(set(tau.values()))
    eng = R.make_english_gloss_realization(WORDS, atoms, tau, seed=1)
    _check("english: same Realization interface as any other", isinstance(eng, R.Realization))
    _check("english: canonical sequence carries no english gloss",
           all(isinstance(a, int) for a in C.canonical_sequence("abc", tau)))
    # english is not privileged: signal only in english -> REALIZATION_ARTIFACT, not ONTOLOGICAL
    recs = [{"positive": True, "inconclusive": False, "encoder_disagreement": False},   # english
            {"positive": False, "inconclusive": False, "encoder_disagreement": False},
            {"positive": False, "inconclusive": False, "encoder_disagreement": False}]
    _check("english: english-only positive -> REALIZATION_ARTIFACT (not privileged)",
           D.cross_realization_decision(recs) == "REALIZATION_ARTIFACT")


def test_mrr_scoring():
    # hand-built realization with known ranking
    atom_vecs = {0: np.array([1.0, 0.0]), 1: np.array([0.0, 1.0])}
    tau = {"x": 0, "y": 1}
    words = ["x", "y"]
    # meanings SWAPPED -> query('x')=[1,0] closest to meaning('y') -> rank 2 -> RR 0.5
    mv_swapped = {"x": np.array([0.0, 1.0]), "y": np.array([1.0, 0.0])}
    rr = S.reciprocal_rank("x", words, R.Realization("m", atom_vecs, mv_swapped), tau)
    _check("mrr: reciprocal rank 0.5 for a rank-2 hit", abs(rr - 0.5) < 1e-9)
    # aligned meanings -> rank 1 -> RR 1.0
    mv_aligned = {"x": np.array([1.0, 0.0]), "y": np.array([0.0, 1.0])}
    rr2 = S.reciprocal_rank("x", words, R.Realization("m", atom_vecs, mv_aligned), tau)
    _check("mrr: reciprocal rank 1.0 for a rank-1 hit", abs(rr2 - 1.0) < 1e-9)


def test_scramble_null_signal_vs_noise():
    tau = _tau()
    atoms = sorted(set(tau.values()))
    sig = R.make_signal_realization("sig", WORDS, atoms, tau, seed=3)
    noi = R.make_noise_realization("noi", WORDS, atoms, seed=4)
    d_sig = S.delta_j(WORDS, sig, tau, n_scram=60, seed=0)
    d_noi = S.delta_j(WORDS, noi, tau, n_scram=60, seed=0)
    _check("scramble: signal real MRR is 1.0 (real τ recovers planted meanings)",
           abs(d_sig["mrr_real"] - 1.0) < 1e-9)
    _check("scramble: signal Δ > 0 (real beats scrambled)", d_sig["delta"] > 0.1)
    _check("scramble: signal beats the scramble null (high percentile)", d_sig["scramble_pct"] >= 0.95)
    _check("scramble: noise Δ ≈ 0 (real does not beat scrambled)", abs(d_noi["delta"]) < 0.1)
    _check("scramble: noise does not clear the percentile gate", d_noi["scramble_pct"] < 0.95)


def _verdicts_from(realizations, tau):
    return [D.per_realization_verdict(S.delta_j(WORDS, r, tau, n_scram=60, seed=0))
            for r in realizations]


def test_cross_realization_ontological_signal():
    tau = _tau()
    atoms = sorted(set(tau.values()))
    reals = [R.make_signal_realization(f"sig{i}", WORDS, atoms, tau, seed=10 + i) for i in range(3)]
    recs = _verdicts_from(reals, tau)
    _check("ontological: all realizations positive", all(r["positive"] for r in recs))
    _check("ontological: decision == ONTOLOGICAL_SIGNAL",
           D.cross_realization_decision(recs) == "ONTOLOGICAL_SIGNAL")


def test_cross_realization_artifact():
    tau = _tau()
    atoms = sorted(set(tau.values()))
    reals = [R.make_signal_realization("sig", WORDS, atoms, tau, seed=20),
             R.make_noise_realization("noi1", WORDS, atoms, seed=21),
             R.make_noise_realization("noi2", WORDS, atoms, seed=22)]
    recs = _verdicts_from(reals, tau)
    _check("artifact: signal in some but not all", any(r["positive"] for r in recs)
           and not all(r["positive"] for r in recs))
    _check("artifact: decision == REALIZATION_ARTIFACT",
           D.cross_realization_decision(recs) == "REALIZATION_ARTIFACT")


def test_cross_realization_no_signal():
    tau = _tau()
    atoms = sorted(set(tau.values()))
    reals = [R.make_noise_realization(f"noi{i}", WORDS, atoms, seed=30 + i) for i in range(3)]
    recs = _verdicts_from(reals, tau)
    _check("no_signal: no realization positive", not any(r["positive"] for r in recs))
    _check("no_signal: decision == NO_SIGNAL",
           D.cross_realization_decision(recs) == "NO_SIGNAL")


def test_realizer_dependent_and_inconclusive():
    dep = [{"positive": True, "inconclusive": False, "encoder_disagreement": True},
           {"positive": True, "inconclusive": False, "encoder_disagreement": False}]
    _check("realizer_dependent: encoder disagreement -> REALIZER_DEPENDENT",
           D.cross_realization_decision(dep) == "REALIZER_DEPENDENT")
    inc = [{"positive": True, "inconclusive": True, "encoder_disagreement": False},
           {"positive": True, "inconclusive": False, "encoder_disagreement": False}]
    _check("inconclusive: an inconclusive realization -> INCONCLUSIVE",
           D.cross_realization_decision(inc) == "INCONCLUSIVE")


def test_runner_not_run():
    res = RUN.run()
    _check("runner: NOT_RUN", res["status"] == "NOT_RUN")
    _check("runner: computed False", res["computed"] is False)
    _check("runner: no result", res["result"] is None)
    _check("runner: NOT_RUN even with a config", RUN.run({"dataset": "x"})["status"] == "NOT_RUN")


def main():
    print("primitive_sequence_recovery — realization-factored scaffold tests (no real result)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll primitive_sequence_recovery scaffolding tests passed.")


if __name__ == "__main__":
    main()
