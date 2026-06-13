"""Tests for the cross-stack KV-quant quality client (pure-stdlib paths only).

The `run` subcommand needs `openai` + a live GPU server; these tests exercise
the parts that decide the verdict — prompt construction, scoring, greedy
agreement, and the decision rule — against an injected MOCK generator, so they
run on CPU with no model and no network.
"""
from __future__ import annotations

from ndol.experiments.openai_kv_eval import (
    _verdict,
    agreement,
    compare,
    make_prompts,
    run_endpoint,
    score,
)


def _oracle(prompts):
    """A perfect generator: answers every needle/hard-needle exactly."""
    ans = {p["id"]: p["answer"] for p in prompts}

    def g(prompt):
        # find the matching prompt by content (1:1 with answer text)
        for p in prompts:
            if p["prompt"] == prompt:
                return ans[p["id"]], 3
        return "", 1

    return g


def test_make_prompts_shape_and_determinism():
    a = make_prompts(n_needle=5, n_hard=7, ctx_sentences=20, seed=0)
    b = make_prompts(n_needle=5, n_hard=7, ctx_sentences=20, seed=0)
    assert [p["prompt"] for p in a] == [p["prompt"] for p in b]      # seed-deterministic
    assert sum(p["kind"] == "needle" for p in a) == 5
    assert sum(p["kind"] == "hard_needle" for p in a) == 7
    # every prompt carries the gold answer and it appears nowhere else as the query
    for p in a:
        assert p["answer"].isdigit()
        assert p["answer"] in p["prompt"]                            # planted in context


def test_hard_needle_targets_one_of_several_codes():
    a = make_prompts(n_needle=0, n_hard=1, ctx_sentences=20, seed=3)
    p = a[0]
    # the hard prompt has multiple planted codes; the gold answer is one of them
    import re

    codes = re.findall(r"code is (\d+)", p["prompt"])
    assert len(codes) >= 2                                           # distractors present
    assert p["answer"] in codes


def test_oracle_scores_perfect(tmp_path):
    prompts = make_prompts(n_needle=4, n_hard=4, ctx_sentences=16, seed=1)
    recs = run_endpoint(prompts, label="oracle", generate=_oracle(prompts),
                        out_path=str(tmp_path / "o.jsonl"))
    s = score(recs)
    assert s["needle"] == 1.0 and s["hard_needle"] == 1.0
    assert (tmp_path / "o.jsonl").exists()


def test_score_partial_and_agreement():
    recs = [
        {"id": "needle_0", "kind": "needle", "answer": "12345", "output": "12345"},
        {"id": "needle_1", "kind": "needle", "answer": "67890", "output": "nope"},
        {"id": "hard_0", "kind": "hard_needle", "answer": "11111", "output": "11111"},
        {"id": "hard_1", "kind": "hard_needle", "answer": "22222", "output": "x"},
    ]
    s = score(recs)
    assert s["needle"] == 0.5 and s["hard_needle"] == 0.5
    # agreement vs an identical reference is perfect; vs a divergent one is lower
    assert agreement(recs, recs)["exact_match"] == 1.0
    ref = [{**r, "output": "different"} for r in recs]
    assert agreement(recs, ref)["exact_match"] < 1.0


def _rows_for(saw_hard, prot_hard):
    recs_saw = [{"id": "hard_0", "kind": "hard_needle", "answer": "1",
                 "output": "1" if saw_hard else "x", "label": "bdr"}]
    recs_prot = [{"id": "hard_0", "kind": "hard_needle", "answer": "1",
                  "output": "1" if prot_hard else "x", "label": "int4_protected"}]
    return compare({"bdr": recs_saw, "int4_protected": recs_prot}, "bdr")


def test_verdict_quality_edge_when_protected_wins_tail():
    rows = _rows_for(saw_hard=False, prot_hard=True)               # +1.0 hard-needle margin
    assert "QUALITY-EDGE" in _verdict(rows)


def test_verdict_dominated_when_saw_wins_tail():
    rows = _rows_for(saw_hard=True, prot_hard=False)               # -1.0 margin
    assert "DOMINATED" in _verdict(rows)


def test_verdict_parity_when_tied():
    rows = _rows_for(saw_hard=True, prot_hard=True)                # 0 margin
    assert "PARITY" in _verdict(rows)


def test_verdict_needs_both_labels():
    rows = compare({"bdr": [{"id": "x", "kind": "hard_needle", "answer": "1",
                             "output": "1", "label": "bdr"}]}, "bdr")
    assert "need both" in _verdict(rows)
