"""CPU tests for the C×R×S MATCH-filter evaluation harness (eval_match_filter.py).

Schema validation, metric correctness on a deterministic synthetic, backend labeling/guards,
unknown-term evaluation without curated glosses, template audit, and JSON serialisation.
No torch/GPU/network.
"""

import json
import sys
import types
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

pytest.importorskip("numpy", reason="numpy required")

from csr_match_filter import DOMAIN_TEMPLATES, derive_ontology_rule, dominant_terms  # noqa: E402
from csr_match_filter import eval_match_filter as EV  # noqa: E402

ROWS = EV.load_eval()
REQUIRED = ("id", "query", "dominant_terms", "candidate_domains", "expected_primary",
            "expected_secondary", "expected_rejected", "unknown_terms", "notes")


# --- 1. eval data schema validation ---------------------------------------------------------------

def test_eval_set_has_at_least_50_cases():
    assert len(ROWS) >= 50


def test_every_row_has_required_schema_fields():
    ids = set()
    for r in ROWS:
        for k in REQUIRED:
            assert k in r, f"{r.get('id')}: missing {k}"
        assert isinstance(r["dominant_terms"], list) and r["dominant_terms"]
        assert isinstance(r["candidate_domains"], list) and r["candidate_domains"]
        assert r["id"] not in ids, f"duplicate id {r['id']}"
        ids.add(r["id"])


def test_expected_sets_are_within_candidate_domains_and_known():
    for r in ROWS:
        cand = set(r["candidate_domains"])
        for d in cand:
            assert d in DOMAIN_TEMPLATES, f"{r['id']}: unknown domain {d}"
        for key in ("expected_primary", "expected_secondary", "expected_rejected"):
            assert set(r[key]) <= cand, f"{r['id']}: {key} not subset of candidates"
        # primary / rejected are disjoint expectations
        assert not (set(r["expected_primary"]) & set(r["expected_rejected"]))


def test_dataset_covers_required_categories():
    cats = {r.get("category") for r in ROWS}
    for c in ("ordinary", "context", "unknown", "adversarial", "ontological", "secondary"):
        assert c in cats, f"missing category {c}"


def test_unknown_terms_are_not_in_demo_glosses():
    from csr_match_filter.registry import DEMO_TERM_GLOSSES
    for r in ROWS:
        for t in r["unknown_terms"]:
            assert t not in DEMO_TERM_GLOSSES, f"{r['id']}: '{t}' marked unknown but is a demo gloss"


# --- 2. metric correctness on a deterministic synthetic -------------------------------------------

class _StubAdapter:
    """similarity = 1.0 for the 'right' domain, 0.0 otherwise (deterministic)."""
    def __init__(self, right):
        self.right = right
        self.audit = {}

    def similarity(self, term, domain):
        return 1.0 if domain == self.right else 0.0


def test_runner_computes_metrics_correctly():
    rows = [{
        "id": "t1", "query": "q", "dominant_terms": ["doctor"],
        "candidate_domains": ["medicine", "commerce"],
        "expected_primary": ["medicine"], "expected_secondary": [], "expected_rejected": ["commerce"],
        "semantic_invalid_domains": ["commerce"], "unknown_terms": [], "notes": "",
    }]
    provider = types.SimpleNamespace(context=None)
    metrics, counts, per = EV.run_eval(rows, _StubAdapter("medicine"), provider)
    assert metrics["primary_frame_accuracy"] == 1.0          # medicine framed primary, no leakage
    assert metrics["rejected_recall"] == 1.0                 # commerce rejected
    assert metrics["rejected_precision"] == 1.0
    assert metrics["semantic_veto_accuracy"] == 1.0          # commerce -> reject_semantic (S=0, C ok)
    assert metrics["trace_completeness"] == 1.0
    assert per[0]["decisions"]["commerce"] == "reject_semantic"


def test_metric_safe_division_returns_none_for_empty_subsets():
    rows = [{
        "id": "t2", "query": "q", "dominant_terms": ["doctor"], "candidate_domains": ["medicine"],
        "expected_primary": ["medicine"], "expected_secondary": [], "expected_rejected": [],
        "unknown_terms": [], "notes": "",
    }]
    provider = types.SimpleNamespace(context=None)
    metrics, _, _ = EV.run_eval(rows, _StubAdapter("medicine"), provider)
    assert metrics["secondary_frame_recall"] is None        # no expected secondary anywhere
    assert metrics["semantic_veto_accuracy"] is None        # no semantic-veto cases


# --- 3/4. derived-rule + dominant-term sanity -----------------------------------------------------

def test_derived_ontology_rule_sanity_on_eval_domains():
    for d in ("medicine", "authority", "fruit", "furniture"):
        rule = derive_ontology_rule(d)
        assert rule.required_high
        assert d not in ("fruit", "furniture") or rule.blocked_high  # blockers exist where expected


def test_dominant_term_extraction_on_eval_queries():
    # the extractor should recover the labelled dominant term for clear single-term queries
    hits = 0
    for r in ROWS:
        if len(r["dominant_terms"]) == 1:
            ext = set(dominant_terms(r["query"]))
            hits += int(r["dominant_terms"][0] in ext)
    assert hits / sum(1 for r in ROWS if len(r["dominant_terms"]) == 1) > 0.6


# --- 5. semantic veto overrides high C/R (through the runner) -------------------------------------

def test_semantic_veto_through_runner_overrides_high_cr():
    rows = [{
        "id": "v1", "query": "q", "dominant_terms": ["doctor"], "candidate_domains": ["medicine"],
        "expected_primary": [], "expected_secondary": [], "expected_rejected": ["medicine"],
        "semantic_invalid_domains": ["medicine"], "unknown_terms": [], "notes": "",
    }]
    provider = types.SimpleNamespace(context=None)
    # S=0 everywhere → even high-C/R medicine is vetoed
    metrics, _, per = EV.run_eval(rows, _StubAdapter("nothing"), provider)
    assert per[0]["decisions"]["medicine"] == "reject_semantic"
    assert metrics["semantic_veto_accuracy"] == 1.0


# --- 6. unknown term evaluated without TERM_GLOSSES -----------------------------------------------

def test_unknown_term_evaluated_via_external_definition_not_demo_gloss():
    kb = EV.load_kb()
    rows = [r for r in ROWS if r["id"] == "unk01"]      # surgeon
    res, _ = EV.run_one("hashing", rows, kb)
    u = res["usage"]
    assert u["definition_provider_used"] is True
    assert u["demo_fixture_used"] is False
    assert u["pct_external_definition"] == 1.0          # scored from KB, not curated gloss
    assert res["metrics"]["trace_completeness"] == 1.0


# --- 7. trace JSON serialisation ------------------------------------------------------------------

def test_eval_traces_serialise(tmp_path):
    kb = EV.load_kb()
    res, _ = EV.run_one("hashing", ROWS[:5], kb)
    blob = {k: v for k, v in res.items() if k != "per"}
    s = json.dumps(blob)                                 # whole report is JSON-serialisable
    assert "metrics" in json.loads(s)


# --- 8/9. backend labeling + production guards ----------------------------------------------------

def test_lexical_backend_is_labeled_fallback_not_production():
    kb = EV.load_kb()
    res, _ = EV.run_one("lexical", ROWS[:8], kb)
    assert res["usage"]["semantic_backend"] == "lexical_fallback"
    assert res["usage"]["production_valid"] is False
    assert res["usage"]["lexical_used"] is True


def test_demo_fixture_backend_cannot_be_treated_as_production():
    assert EV.BACKEND_LABEL["demo"][0] == "demo_curated_fixture"
    assert EV.BACKEND_LABEL["demo"][1] is False          # production_valid False
    assert EV.BACKEND_LABEL["hashing"][1] is False
    assert EV.BACKEND_LABEL["lexical"][1] is False
    assert EV.BACKEND_LABEL["real"][1] is True           # only real is production-valid


def test_template_audit_flags_confusable_and_strict_blocked():
    rows = EV.template_audit(["medicine", "fruit", "authority", "finance"])
    by = {r["domain"]: r for r in rows}
    assert by["fruit"]["too_strict_blocked"] is True     # fruit blocks >=5 lanes
    # authority/finance are near-duplicates → flagged confusable with each other
    assert "finance" in by["authority"]["confusable_with"] or \
           "authority" in by["finance"]["confusable_with"]
