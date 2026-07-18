"""Machinery tests for the controllability pilot (not the hypothesis).

Run: python symbolu_neural/controllability_pilot/tests/test_pilot.py
"""
from __future__ import annotations

import numpy as np

from symbolu_neural.controllability_pilot.data import make_corpus, AXES, axis_lexicons
from symbolu_neural.controllability_pilot.codes import build_all
from symbolu_neural.controllability_pilot.generator import Vocab, train_model, generate, perplexity
from symbolu_neural.controllability_pilot.evaluator import LexiconScorer, ProxyClassifier
from symbolu_neural.controllability_pilot import pilot


def test_corpus_deterministic_and_labeled():
    a = make_corpus(per_axis=10, seed=0)
    b = make_corpus(per_axis=10, seed=0)
    assert a == b
    assert {ax for _, ax in a} == set(AXES)
    assert len(a) == 30


def test_codes_all_arms_present_and_distinct_dims():
    c = make_corpus(per_axis=20)
    codes = build_all(c, u_backend="pse_meaning")
    for arm in ["symbolu", "random", "shuffled", "sentiment", "relabel"]:
        assert set(codes[arm].keys()) == set(AXES)
    # relabel is a permutation of symbolu dims -> same per-axis norms
    for a in AXES:
        assert abs(np.linalg.norm(codes["relabel"][a]) - np.linalg.norm(codes["symbolu"][a])) < 1e-9


def test_random_codes_more_separable_than_symbolu():
    c = make_corpus(per_axis=40)
    codes = build_all(c, u_backend="pse_meaning")

    def sep(d):
        M = np.stack([d[a] for a in AXES])
        M = M / (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)
        return np.mean([np.linalg.norm(M[i] - M[j]) for i in range(3) for j in range(i + 1, 3)])
    assert sep(codes["random"]) > sep(codes["symbolu"])  # the core mechanism


def test_generator_trains_and_generates():
    c = make_corpus(per_axis=20)
    vocab = Vocab([t for t, _ in c], extra=AXES)
    m = train_model(c, vocab, code_dim=0, steps=60)
    out = generate(m, vocab, "the", None, max_len=8, seed=1)
    assert isinstance(out, str)
    assert perplexity(m, vocab, "the quiet lake rests") > 0


def test_proxy_classifier_learns_axes():
    c = make_corpus(per_axis=40)
    clf = ProxyClassifier([w for t, _ in c for w in t.split()])
    clf.fit([t for t, _ in c], [a for _, a in c])
    # in-domain text should classify to its axis
    assert clf.argmax("the quiet gentle lake rests") == "calm"
    assert clf.argmax("the swift runner sprints fast") == "active"


def test_lexicon_scorer_axes():
    lex = LexiconScorer()
    assert lex.argmax("quiet gentle serene calm") == "calm"
    assert lex.argmax("grim heavy gloom burden") == "heavy"


def test_pilot_runs_end_to_end_tiny():
    r = pilot.run(per_axis=12, steps=60, n_seeds=1)
    assert "symbolu" in r["arms"] and "random" in r["arms"]
    for arm in ["base", "symbolu", "random", "shuffled", "sentiment", "relabel", "prompt"]:
        assert 0.0 <= r["arms"][arm]["clf_steer_acc"] <= 1.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} tests passed")
