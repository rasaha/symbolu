"""Tests: metrics correctness, economics, origin lock, determinism."""

from __future__ import annotations

import pytest

from actiongate_context_ablation import (
    adapter, ablation, economics, metrics, origin, runner, verdict,
)
from actiongate_context_ablation.corpus import tier1_fixtures as T
from actiongate_context_ablation.units import Context, SemanticUnit as U


@pytest.fixture(scope="module")
def sp():
    return adapter.default_signed_policy()


def test_token_fractions_correct():
    # A hand-checkable context: 2 units, known token counts.
    ctx = Context(
        id="mini", data_origin=origin.SYNTHETIC,
        base={"tool": "terraform", "verb": "apply", "target": ["svc://x"], "args": {}},
        units=(U(id="a", source_type="sentence", text="one two three"),
               U(id="b", source_type="sentence", text="four five")))
    assert ctx.unit("a").token_count == 3
    assert ctx.unit("b").token_count == 2
    assert ctx.total_tokens == 5


def test_overlapping_critical_not_double_counted(sp):
    # 'sink' carries decision+envelope+assurance labels but counts once in the union.
    run = ablation.run_ablations(T.hidden_negation(), sp)
    cm = metrics.context_metrics(run)
    assert "sink" in cm.critical_union_ids
    union_tokens = sum(run.ctx.unit(i).token_count for i in cm.critical_union_ids)
    # f_critical_union * total must equal the union token count (no triple counting)
    assert abs(cm.f_critical_union * cm.total_tokens - union_tokens) < 1e-6


def test_ceilings_bounds(sp):
    run = ablation.run_ablations(T.coherent_one_commitment(), sp)
    cm = metrics.context_metrics(run)
    assert 0.0 <= cm.oracle_ceiling <= 1.0
    assert 0.0 <= cm.deployable_ceiling <= 1.0
    # a mostly-filler context should have a high oracle ceiling
    assert cm.oracle_ceiling > 0.5


def test_prompt_cache_adjustment_reduces_savings():
    res = runner.run_study()
    e = res.econ
    # caching + overhead must make net savings strictly below the naive ratio
    assert e.cache_adjusted_savings_ratio < e.naive_savings_ratio
    assert e.cacheable_tokens > 0


def test_recall_favoring_detector_creates_precision_gap(sp):
    # The conservative detector over-marks: on at least one fixture precision < 1.
    gaps = []
    for f in (T.rollback_reversibility, T.table_contained_constraint, T.json_contained_field):
        cm = metrics.context_metrics(ablation.run_ablations(f(), sp))
        gaps.append(cm.precision_p0)
    assert min(gaps) < 1.0


def test_synthetic_origin_cannot_produce_scientific_verdict():
    res = runner.run_study()
    assert res.verdict.scientific is False
    assert res.verdict.verdict in (origin.SYNTHETIC_NO_SCIENTIFIC_VERDICT,
                                   origin.MOCK_NO_SCIENTIFIC_VERDICT)
    # even if the indicative verdict were "supported", it is not emitted as the verdict
    assert res.verdict.verdict != verdict.ABLATION_OPPORTUNITY_SUPPORTED


def test_scientific_verdict_would_fire_on_real_provenance():
    # With REAL origins and healthy synthetic metrics, decide() emits a scientific verdict.
    res = runner.run_study()
    real_origins = [origin.FIELD_REAL] * len(res.origins)
    v = verdict.decide(res.agg, res.econ, real_origins)
    assert v.scientific is True
    assert v.verdict == v.indicative_scientific_verdict


def test_heldout_split_untouched(sp):
    # Tier 3 must run with dev=False: no interaction-mode ablations there.
    res = runner.run_study()
    t3 = next(t for t in res.tiers if t.name == "Tier3_heldout")
    for run in t3.runs:
        assert all(r.mode != ablation.INTERACTION for r in run.records)
    # thresholds are frozen module constants, not derived from data
    assert verdict.MIN_P0_RECALL == 1.0
    assert verdict.MAX_EXTRACTOR_INSTABILITY == 0.10


def test_deterministic_reruns_identical():
    a = runner.render_results_md(runner.run_study())
    b = runner.render_results_md(runner.run_study())
    assert a == b


def test_origin_helpers():
    assert origin.run_is_scientific([origin.FIELD_REAL, origin.NATURALISTIC_REPO])
    assert not origin.run_is_scientific([origin.FIELD_REAL, origin.SYNTHETIC])
    assert origin.locked_verdict([origin.MOCK]) == origin.MOCK_NO_SCIENTIFIC_VERDICT
    assert origin.locked_verdict([origin.SYNTHETIC]) == origin.SYNTHETIC_NO_SCIENTIFIC_VERDICT
