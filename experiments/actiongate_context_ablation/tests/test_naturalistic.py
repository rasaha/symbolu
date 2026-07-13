"""Tests for the naturalistic corpus, annotation, stratified metrics, and verdicts."""

from __future__ import annotations

import collections

import pytest

from actiongate_context_ablation import (
    adapter, annotation, naturalistic_metrics, naturalistic_runner as NR, origin,
    verdict,
)
from actiongate_context_ablation.corpus import manifest as M
from actiongate_context_ablation.corpus import registry
from actiongate_context_ablation.corpus.schema import (
    AUTHORED, HELDOUT, PUBLIC, SPLITS, STRUCTURE_FAMILIES,
)
from actiongate_context_ablation.labels import ANNOTATION_LABELS
from actiongate_context_ablation.corpus.core import CORES


@pytest.fixture(scope="module")
def items():
    return registry.load_all()


@pytest.fixture(scope="module")
def study():
    return NR.run_study()


# ---- corpus composition / coverage ----
def test_required_coverage(items):
    assert len(items) >= 75
    parts = collections.Counter(i.partition for i in items)
    assert parts[PUBLIC] >= 40
    assert parts[AUTHORED] >= 35
    assert len({i.domain for i in items}) >= 5
    assert len({i.action_type for i in items}) >= 10
    assert {i.structure_family for i in items} == set(STRUCTURE_FAMILIES)


def test_both_partitions_in_heldout(items):
    ho = {i.partition for i in items if i.split == HELDOUT}
    assert PUBLIC in ho and AUTHORED in ho


# ---- provenance completeness ----
def test_provenance_completeness(items):
    for it in items:
        p = it.provenance
        for fld in (p.source, p.title, p.license, p.action_type, p.tool_domain,
                    p.expected_envelope, p.adaptations):
            assert isinstance(fld, str) and fld.strip(), f"{it.item_id}: empty provenance field"
        if it.partition == PUBLIC:
            assert p.adapted is True
            assert "repo" in p.license or "/" in p.source or p.source.endswith(".yml")


# ---- anti-leakage ----
def test_no_template_or_content_leakage_across_splits(items):
    tf_split = collections.defaultdict(set)
    ch_split = collections.defaultdict(set)
    for it in items:
        tf_split[it.template_family].add(it.split)
        ch_split[it.content_hash()].add(it.split)
    assert all(len(s) == 1 for s in tf_split.values()), "template_family leaks across splits"
    assert all(len(s) == 1 for s in ch_split.values()), "content hash leaks across splits"


def test_no_duplicate_content_hashes(items):
    hashes = [it.content_hash() for it in items]
    assert len(hashes) == len(set(hashes)), "duplicate/near-duplicate contexts"


# ---- annotations valid ----
def test_annotations_reference_valid_spans(items):
    for it in items:
        ids = {u.id for u in it.context.units}
        for u in it.context.units:
            assert u.expected is None or u.expected in ANNOTATION_LABELS
            for ref in (*u.references, *u.dependency_links):
                assert ref in ids, f"{it.item_id}:{u.id} dangling ref {ref}"


# ---- oracle reproduces expected envelope ----
def test_oracle_reproduces_expected_envelope(items):
    sp = adapter.default_signed_policy()
    from actiongate_context_ablation import extractor
    for it in items[:20]:
        ids = [u.id for u in it.context.units]
        r = extractor.extract_and_eval(it.context, ids, sp, mode=extractor.ORACLE)
        env = r["envelope"]
        assert env["tool"]["server_id"] == it.context.base["tool"]
        assert env["operation"]  # a real frozen operation was assigned


# ---- held-out untouched ----
def test_heldout_untouched(study):
    from actiongate_context_ablation import ablation
    for it, run in zip(study.items, study.runs):
        if it.split == HELDOUT:
            assert all(r.mode != ablation.INTERACTION for r in run.records)
    # thresholds remain the preregistered constants
    assert verdict.MIN_P0_RECALL == 1.0 and verdict.MAX_EXTRACTOR_INSTABILITY == 0.10


# ---- origins preserved ----
def test_public_and_authored_origins_preserved(study):
    assert study.partitions[PUBLIC].items
    assert study.partitions[AUTHORED].items
    assert all(it.partition == PUBLIC for it in study.partitions[PUBLIC].items)
    assert origin.is_naturalistic(PUBLIC) and origin.is_naturalistic(AUTHORED)


# ---- no customer-data claim can be emitted ----
def test_no_real_customer_validated_emitted(study):
    for label in (PUBLIC, AUTHORED):
        v = study.partitions[label].verdict
        assert v.verdict != "REAL_CUSTOMER_VALIDATED"
        assert v.scientific is False
    # the forbidden label is not in any emittable naturalistic set
    assert not hasattr(verdict, "REAL_CUSTOMER_VALIDATED")


def test_naturalistic_verdict_labels_are_corpus_scoped(study):
    valid = {verdict.PUBLIC_CORPUS_OPPORTUNITY_SUPPORTED,
             verdict.AUTHORED_CORPUS_OPPORTUNITY_SUPPORTED, verdict.MIXED_BY_DOMAIN,
             verdict.DETECTOR_PRECISION_BOTTLENECK, verdict.CONTEXT_INTRINSICALLY_DENSE,
             verdict.EXTRACTOR_NOT_RELIABLE, verdict.SINGLE_ABLATION_INADEQUATE,
             verdict.ECONOMICS_NOT_SUPPORTED, verdict.NOT_ELIGIBLE}
    for label in (PUBLIC, AUTHORED):
        assert study.partitions[label].verdict.verdict in valid


# ---- domain stratification ----
def test_domain_stratified_metrics(study):
    domains = {it.domain for it in study.items}
    assert set(study.combined.by_domain) == domains
    for a in study.combined.by_domain.values():
        assert 0.0 <= a.f_critical_union <= 1.0
        assert 0.0 <= a.oracle_ceiling <= 1.0


def test_mixed_by_domain_fires_when_domains_disagree(study):
    # construct a per-domain dict with one supported + one dense; MIXED_BY_DOMAIN.
    from actiongate_context_ablation import economics, metrics

    class _A(metrics.AggregateMetrics):
        pass
    good = metrics.AggregateMetrics(
        n_contexts=10, total_units=100, total_ablations=200, total_tokens=10000,
        f_decision=0.05, f_envelope=0.02, f_assurance=0.02, f_critical_union=0.10,
        f_protected=0.14, recall_p0=1.0, precision_p0=0.7, oracle_ceiling=0.90,
        deployable_ceiling=0.86, interaction_miss_rate=0.0,
        extractor_instability_rate=0.0, per_context=[])
    dense = metrics.AggregateMetrics(
        n_contexts=10, total_units=100, total_ablations=200, total_tokens=10000,
        f_decision=0.5, f_envelope=0.2, f_assurance=0.1, f_critical_union=0.8,
        f_protected=0.85, recall_p0=1.0, precision_p0=0.7, oracle_ceiling=0.2,
        deployable_ceiling=0.15, interaction_miss_rate=0.0,
        extractor_instability_rate=0.0, per_context=[])
    # aggregate that itself passes gates so base==SUPPORTED, then domains disagree
    agg = good
    econ = economics.model(agg)
    v = verdict.decide_naturalistic(agg, econ, {"k8s": good, "iam": dense}, PUBLIC)
    assert v.verdict == verdict.MIXED_BY_DOMAIN


# ---- annotation two-pass ----
def test_annotation_two_pass_records_disagreements(study):
    r = study.review
    assert r.n_annotated > 0
    assert len(r.disagreements) == r.n_disagree
    assert 0.0 <= r.agreement_rate <= 1.0


# ---- manifest hashing / determinism ----
def test_manifest_hash_stable():
    assert M.build_manifest()["manifest_hash"] == M.build_manifest()["manifest_hash"]


def test_every_item_has_content_hash(items):
    for it in items:
        assert it.content_hash().startswith("sha256:")


def test_deterministic_reruns():
    a, b = NR.run_study(), NR.run_study()
    assert a.manifest["manifest_hash"] == b.manifest["manifest_hash"]
    assert a.combined.agg.f_critical_union == b.combined.agg.f_critical_union
    assert a.combined.ci == b.combined.ci
    assert (a.partitions[PUBLIC].verdict.verdict
            == b.partitions[PUBLIC].verdict.verdict)


# ---- economics present ----
def test_prompt_cache_adjustment_present(study):
    e = study.econ
    assert e.cache_adjusted_savings_ratio <= e.naive_savings_ratio
    assert e.cacheable_tokens > 0
