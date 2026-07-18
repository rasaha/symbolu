"""Tests for the real-LLM validation harness (plumbing + honesty, no fabrication)."""

from __future__ import annotations

import pytest

from actiongate_context_ablation import (
    adapter, llm_client, llm_tasks, real_llm_bench as R,
)
from actiongate_context_ablation.corpus import registry


@pytest.fixture(scope="module")
def dry():
    return R.run(contexts_limit=20)


def test_no_real_model_is_reported_honestly():
    client, avail = llm_client.probe_available_client()
    assert avail.real_available is False           # this environment: no real LLM
    assert client.is_real is False
    assert "transformers" in avail.tried


def test_recommendation_blocked_not_fabricated(dry):
    # without a real LLM, the harness must emit BLOCKED_NO_MODEL, never GO/LIMITED_GO/STOP
    assert dry.is_real is False
    assert dry.recommendation == "BLOCKED_NO_MODEL"
    assert dry.recommendation not in ("GO", "LIMITED_GO", "STOP")
    assert dry.success["measured_with_real_llm"] is False


def test_tasks_have_ground_truth_from_frozen_gate():
    items = registry.load_all()
    sp = adapter.default_signed_policy()
    tasks = llm_tasks.build_tasks(items[0], sp)
    assert tasks and all("answer_key" in t and "scorer" in t for t in tasks)
    types = {t["type"] for t in tasks}
    assert {"tool_selection", "reasoning", "instruction_following"} <= types


def test_scorers_grade_text_outputs():
    items = registry.load_all()
    sp = adapter.default_signed_policy()
    t = next(t for t in llm_tasks.build_tasks(items[0], sp) if t["type"] == "tool_selection")
    assert t["scorer"](t["answer_key"]) == 1.0
    assert t["scorer"]("totally wrong answer") == 0.0


def test_methods_use_frozen_compressor_and_split_at_high_compression(dry):
    prot = [c for c in dry.cells if c.method == "protected"]
    unaware = [c for c in dry.cells if c.method == "protection_unaware"]
    # protected: decision & envelope preservation 100% at EVERY budget (frozen guarantee)
    assert all(abs(c.decision_preservation - 1.0) < 1e-9 for c in prot)
    assert all(abs(c.envelope_preservation - 1.0) < 1e-9 for c in prot)
    # protection-unaware degrades decision preservation at the highest budget
    assert min(c.decision_preservation for c in unaware) < 1.0


def test_original_baseline_present(dry):
    assert any(c.method == "original" for c in dry.cells)
    orig = next(c for c in dry.cells if c.method == "original")
    assert orig.token_reduction == 0.0


def test_dry_run_deterministic():
    a = R.run(contexts_limit=15)
    b = R.run(contexts_limit=15)
    assert [(c.method, c.budget, round(c.task_accuracy, 6)) for c in a.cells] == \
           [(c.method, c.budget, round(c.task_accuracy, 6)) for c in b.cells]
    assert a.recommendation == b.recommendation


def test_mock_reader_needs_span_present():
    c = llm_client.MockReaderClient()
    task = {"answer_key": "ANSWER", "answer_span": "secret token"}
    hit = c.generate("", "context has the secret token here", task=task)
    miss = c.generate("", "context lacks it", task=task)
    assert hit.text == "ANSWER" and miss.text == "INSUFFICIENT_CONTEXT"
    assert hit.is_real is False
