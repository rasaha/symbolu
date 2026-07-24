"""Phase 20 test suite for the EvidenceAssurance track. Tests the corpus invariants, each layer, the
reference component, and the load-bearing scientific claims (so a regression that quietly breaks a
result fails a test). Deterministic; no network. Does not touch prior-track artifacts.
"""
from dataclasses import asdict

import pytest

from evidence_assurance import (dataset, provenance, independence, alignment, counterevidence,
                                assurance, adapter)
from evidence_assurance.assurance import ALL_LAYERS
from evidence_assurance.taxonomy import (EvidenceState as ES, delivered_as_supported,
                                         more_conservative, CONSERVATISM, DELIVERY_EFFECT)

CASES = [asdict(c) for c in dataset.all_cases()]
TRAP = {"CORRELATED_FAILURE", "ADVERSARIAL_PROVENANCE"}


# ---------- corpus invariants --------------------------------------------------------------------

def test_corpus_shape():
    assert dataset.DATASET_VERSION == "ea_corpus_v1_1"
    assert len(CASES) == 624


def test_corpus_has_all_partitions():
    parts = {c["partition"] for c in CASES}
    assert parts == {"CLEAN_INDEPENDENT", "CLEAN_DEPENDENT", "CORRELATED_FAILURE",
                     "ADVERSARIAL_PROVENANCE"}


def test_authority_mismatch_now_present():
    """The v1_1 fix must make AUTHORITY_MISMATCH reachable (it was impossible in v1)."""
    states = {c["gold_state"] for c in CASES}
    assert ES.AUTHORITY_MISMATCH.value in states
    assert sum(1 for c in CASES if c["gold_state"] == ES.AUTHORITY_MISMATCH.value) == 24


def test_gold_from_true_state_not_observed():
    """Anti-circularity: gold must be derivable from TRUE latent fields alone (annotators use them)."""
    for c in CASES:
        a = dataset.annotator_A(c)
        b = dataset.annotator_B(c)
        expected = a if a == b else more_conservative(a, b)
        assert c["gold_state"] == expected


def test_disagreement_only_on_soft_tail():
    """Annotator disagreement must never fall on a safety-critical (hard-precedence) state."""
    hard = {ES.MISALIGNED.value, ES.REJECT_EVIDENCE_STATE.value, ES.CONFLICTED.value,
            ES.AUTHORITY_MISMATCH.value}
    for c in CASES:
        if c["annotator_disagreement"]:
            assert c["gold_state"] not in hard


# ---------- layer behavior -----------------------------------------------------------------------

def test_provenance_not_fooled_by_fake_diversity_without_upstream():
    """Adversarial provenance (fabricated publishers, real common upstream) → not certified independent."""
    adv = [c for c in CASES if c["partition"] == "ADVERSARIAL_PROVENANCE"]
    for c in adv:
        assert independence.assess(c).verdict in ("UNKNOWN", "DUPLICATE", "DEPENDENT")


def test_independence_duplicate_on_dependent_partition():
    dep = [c for c in CASES if c["partition"] == "CLEAN_DEPENDENT"]
    assert all(independence.assess(c).verdict == "DUPLICATE" for c in dep)


def test_alignment_flags_all_misaligned_gold():
    mis = [c for c in CASES if c["gold_state"] == ES.MISALIGNED.value]
    assert all(not alignment.assess(c).aligned for c in mis)


def test_counterevidence_recall_and_false_conflict_present():
    true_counter = [c for c in CASES if c["true_counterevidence_exists"]]
    found = sum(1 for c in true_counter if counterevidence.search(c).found)
    assert 0.85 <= found / len(true_counter) <= 0.95     # imperfect, not oracle
    assert any(counterevidence.search(c).false_conflict for c in CASES)  # noise exists


# ---------- reference component: the headline claims ---------------------------------------------

def _escape_stats(enabled=ALL_LAYERS):
    esc = fb = trap_esc = 0
    n_unsup = n_sup = n_trap = 0
    for c in CASES:
        st = assurance.assess(c, enabled=enabled).state
        gs = delivered_as_supported(c["gold_state"])
        ps = delivered_as_supported(st)
        n_sup += gs
        n_unsup += (not gs)
        if c["partition"] in TRAP:
            n_trap += 1
            trap_esc += ps
        esc += (ps and not gs)
        fb += (not ps and gs)
    return trap_esc / n_trap, esc / n_unsup, fb / n_sup


def test_component_zero_correlated_failure_escape():
    cf, overall, _ = _escape_stats()
    assert cf == 0.0
    assert overall == 0.0


def test_component_false_block_is_the_noise_floor():
    """False-block must equal the injected NLI-noise floor (15/132), not a structural refusal."""
    _, _, fb = _escape_stats()
    assert abs(fb - 15 / 132) < 1e-6


def test_reject_gold_never_delivered_as_supported():
    """Correlated-failure / adversarial (gold REJECT) must never surface as supported."""
    for c in CASES:
        if c["gold_state"] == ES.REJECT_EVIDENCE_STATE.value:
            assert not delivered_as_supported(assurance.assess(c).state)


def test_missing_provenance_abstains_not_certifies():
    """A case with emptied provenance must not be certified VERIFIED — it abstains."""
    clean = next(c for c in CASES if c["gold_state"] == ES.VERIFIED.value)
    d = dict(clean)
    d["observed_upstream_ids"] = []
    d["observed_distinct_publishers"] = 0
    d["observed_content_hashes"] = []
    d["metadata_complete"] = False
    d["observed_provenance_confidence"] = 0.0
    assert assurance.assess(d).state != ES.VERIFIED.value


def test_no_tell_correlated_failure_escapes():
    """Honest ceiling: a false claim with NO observable tell must escape (bounds the method)."""
    base = next(c for c in CASES if c["gold_state"] == ES.VERIFIED.value)
    d = dict(base)
    d["true_claim_correct"] = False
    d["observed_alignment_signal"] = True
    d["true_counterevidence_exists"] = False
    d["observed_upstream_ids"] = ["u0", "u1", "u2", "u3"]
    d["observed_provenance_confidence"] = 0.95
    # every observable signal says supported → the component cannot see the failure
    assert delivered_as_supported(assurance.assess(d).state)


def test_independence_alone_insufficient_under_fabrication():
    """Defense-in-depth: independence alone must leak under fully-fabricated provenance; FULL must not.
    Uses the canonical fabrication from the ablation study so test and report cannot drift."""
    from evidence_assurance.eval_ablation import _fully_fabricate
    trap = [c for c in CASES if c["partition"] in TRAP]
    attacked = [_fully_fabricate(c) for c in trap]

    def cf(enabled):
        e = sum(1 for c in attacked
                if delivered_as_supported(assurance.assess(c, enabled=enabled).state))
        return e / len(attacked)

    assert cf(frozenset({"independence"})) >= 0.4      # independence alone leaks badly
    assert cf(ALL_LAYERS) == 0.0                        # full stack holds


# ---------- adapter contract (delivery level) ----------------------------------------------------

def test_delivery_level_no_escape():
    for c in CASES:
        gate = adapter.thin_assertion_gate(adapter.evidence_to_delivery(c))
        gold_supported = c["gold_delivery"] in ("ALLOW", "QUALIFY")
        assert not (gate["surface_claim"] and not gold_supported), c["case_id"]


# ---------- taxonomy sanity ----------------------------------------------------------------------

def test_only_verified_states_are_supported():
    supported = {s for s in [e.value for e in ES] if delivered_as_supported(s)}
    assert supported == {ES.VERIFIED.value, ES.VERIFIED_WITH_LIMITATIONS.value}


def test_conservatism_monotone_and_complete():
    assert set(CONSERVATISM) == {e.value for e in ES}
    assert more_conservative(ES.VERIFIED.value, ES.REJECT_EVIDENCE_STATE.value) == \
        ES.REJECT_EVIDENCE_STATE.value


def test_delivery_effect_covers_all_states():
    assert set(DELIVERY_EFFECT) == set(ES)
