"""The research-only advisor demo calls the real Slice 2 advisor; its displayed output
corresponds exactly to the underlying advisory object; presentation cannot change the
advisory digest; and it makes no prediction, ranking or production claim."""

from __future__ import annotations

import ast
import dataclasses
import io
import json
import os
import pathlib
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from enum import Enum
from typing import get_args, get_origin, get_type_hints

import pytest

from experiments.reasoning_method_advisor_demo import demo
from ugence_reasoning_method_advisor import api as adv_api
from ugence_reasoning_method_advisor.api import (
    AdvisoryClassification,
    AdvisoryEligibility,
    NoPrimaryReason,
    ReasoningMethodAdvisory,
    validate_against_request,
)
from ugence_reasoning_method_governance.api import ContractError, ContractErrorCode, ReasoningMethodCatalogRef, ReasoningMethodRef

REPO = pathlib.Path(__file__).resolve().parents[3]
DEMO_SRC = REPO / "experiments" / "reasoning_method_advisor_demo" / "demo.py"
FORBIDDEN_WORDS = ("%", "score", "rank", "faster", "cheaper", "best", "recommend", "production-ready", "confidence", "probab", "benchmark-derived", "BENCHMARK_DERIVED")


# --------------------------------------------------------------------------- independent walkers
def _same(obj, rendered) -> None:
    """Independent field-for-field check that the rendered JSON is exactly the object."""
    if obj is None or isinstance(obj, (str, bool)):
        assert rendered == obj
    elif isinstance(obj, Enum):
        assert rendered == obj.value
    elif isinstance(obj, datetime):
        assert rendered == obj.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    elif dataclasses.is_dataclass(obj):
        assert set(rendered) == {f.name for f in dataclasses.fields(obj)}, "rendered keys must be exactly the object's fields"
        for f in dataclasses.fields(obj):
            _same(getattr(obj, f.name), rendered[f.name])
    elif isinstance(obj, tuple):
        assert isinstance(rendered, list) and len(rendered) == len(obj)
        for o, r in zip(obj, rendered):
            _same(o, r)
    else:
        raise AssertionError(f"unexpected type {type(obj)}")


def _build(cls, data):
    """Rebuild a contract object from its rendered JSON using the declared field types."""
    hints = get_type_hints(cls)
    kwargs = {}
    for f in dataclasses.fields(cls):
        kwargs[f.name] = _coerce(hints[f.name], data[f.name])
    return cls(**kwargs)


def _coerce(tp, value):
    origin = get_origin(tp)
    if origin is not None and type(None) in get_args(tp):  # Optional[X]
        if value is None:
            return None
        return _coerce([a for a in get_args(tp) if a is not type(None)][0], value)
    if origin is tuple:
        inner = get_args(tp)[0]
        return tuple(_coerce(inner, v) for v in value)
    if tp is datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(tp, type) and issubclass(tp, Enum):
        return tp(value)
    if dataclasses.is_dataclass(tp):
        return _build(tp, value)
    return value


def rebuild(rendered: dict) -> ReasoningMethodAdvisory:
    return _build(ReasoningMethodAdvisory, rendered)


# --------------------------------------------------------------------------- the four examples
@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_examples_are_deterministic_and_rendered_exactly(n):
    a, b = demo.run_example(n), demo.run_example(n)
    assert a == b and a.advisory_digest == b.advisory_digest
    rendered = demo.to_jsonable(a)
    _same(a, rendered)
    assert rendered["advisory_digest"] == a.advisory_digest
    rebuilt = rebuild(json.loads(demo.advisory_json(a)))
    assert rebuilt == a and rebuilt.advisory_digest == a.advisory_digest
    assert a.usage_scope == "RESEARCH_ONLY" and a.evidence_status == "COMPARISON_EVIDENCE_ABSENT"
    assert all(q.label.value == "RULE_DERIVED" for q in a.qualifying) and all(e.label.value == "RULE_DERIVED" for e in a.excluded)
    assert len(a.qualifying) + len(a.excluded) == 7


def test_example_1_one_qualifying_method_is_primary():
    a = demo.run_example(1)
    assert [q.method.method_id for q in a.qualifying] == ["map_reduce"]
    assert a.primary.method_id == "map_reduce" and a.primary_basis == "SOLE_QUALIFYING_METHOD" and a.trade_offs == ()
    assert a.classification is AdvisoryClassification.GOVERNED_TASK_CLASS and a.eligibility is AdvisoryEligibility.JOINABLE_BY_TASK_CLASS_DIGEST


def test_example_2_multiple_qualifiers_no_primary_unranked_trade_offs():
    a = demo.run_example(2)
    assert [q.method.method_id for q in a.qualifying] == ["iterative_refinement", "map_reduce", "tree_of_thought"]
    assert a.primary is None and a.no_primary_reason is NoPrimaryReason.MULTIPLE_QUALIFYING_METHODS
    assert [t.method for t in a.trade_offs] == [q.method for q in a.qualifying]
    assert [[r.rule_id for r in t.distinguishing_reasons] for t in a.trade_offs] == [["research.signal.creative_synthesis"], ["research.signal.comparison_request"], ["research.signal.ambiguity_detected"]]
    text = demo.explain(a)
    assert "ALTERNATIVES (no ordering" in text and "NO PRIMARY: MULTIPLE_QUALIFYING_METHODS" in text


def test_example_3_no_qualifying_method():
    a = demo.run_example(3)
    assert a.qualifying == () and a.primary is None and a.no_primary_reason is NoPrimaryReason.NO_QUALIFYING_METHOD
    assert all(e.exclusion_reasons[0].rule_id == "NO_SUPPORTING_RULE" for e in a.excluded)


def test_example_4_unclassified_is_labelled_explicitly():
    a = demo.run_example(4)
    assert a.task_class_digest is None
    assert a.classification is AdvisoryClassification.UNCLASSIFIED_EXPLORATORY and a.eligibility is AdvisoryEligibility.INELIGIBLE_UNCLASSIFIED
    text = demo.explain(a)
    for label in ("UNCLASSIFIED_EXPLORATORY", "INELIGIBLE_UNCLASSIFIED", "COMPARISON_EVIDENCE_ABSENT", "exploratory only"):
        assert label in text
    assert json.loads(demo.advisory_json(a))["classification"] == "UNCLASSIFIED_EXPLORATORY"


# --------------------------------------------------------------------------- presentation cannot change the digest
@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_presentation_variants_never_change_the_digest(n):
    a = demo.run_example(n)
    before = dataclasses.replace(a)
    variants = [demo.advisory_json(a, indent=i, sort_keys=s) for i in (None, 2, 4) for s in (False, True)]
    demo.explain(a)
    assert a == before, "presentation must not mutate the advisory"
    assert {json.loads(v)["advisory_digest"] for v in variants} == {a.advisory_digest}
    assert {rebuild(json.loads(v)).advisory_digest for v in variants} == {a.advisory_digest}
    assert {rebuild(json.loads(v)) for v in variants} == {a}
    assert demo.explain(a).splitlines()[-1] == f"advisory_digest={a.advisory_digest}"


def test_a_tampered_rendering_cannot_carry_the_original_digest():
    a = demo.run_example(2)
    rendered = json.loads(demo.advisory_json(a))
    rendered["qualifying"][0]["inclusion_reasons"][0]["rationale_statement"] = "edited in presentation"
    with pytest.raises(ContractError) as ei:
        rebuild(rendered)
    assert ei.value.code is ContractErrorCode.DIGEST_MALFORMED
    rendered2 = json.loads(demo.advisory_json(a))
    rendered2["primary"] = rendered2["qualifying"][0]["method"]
    rendered2["primary_basis"] = "SOLE_QUALIFYING_METHOD"
    rendered2["no_primary_reason"] = None
    with pytest.raises(Exception) as ei2:
        rebuild(rendered2)
    assert getattr(ei2.value, "code", None) is not None  # refused by the contract, never re-digested silently


# --------------------------------------------------------------------------- what the explanation shows and never says
@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_explanation_shows_every_required_element_and_no_forbidden_claim(n):
    a = demo.run_example(n)
    text = demo.explain(a)
    for q in a.qualifying:
        assert q.method.method_id in text
        for r in q.inclusion_reasons:
            assert r.rule_id in text and r.rationale_statement in text
    for e in a.excluded:
        assert e.method.method_id in text
        for r in e.exclusion_reasons:
            assert r.rule_id in text and r.rationale_statement in text
    for needle in (a.classification.value, a.eligibility.value, a.evidence_status, a.usage_scope, a.advisory_digest, a.rule_set.rule_set_id, a.catalog.catalog_id):
        assert needle in text
    assert any(line.startswith("PRIMARY: ") for line in text.splitlines()) == (a.primary is not None)
    lowered = text.lower()
    for word in FORBIDDEN_WORDS:
        assert word.lower() not in lowered, word
    rendered = demo.advisory_json(a)
    assert not any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in _leaves(json.loads(rendered))), "no number appears in the machine output"


def _leaves(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _leaves(v)
    elif isinstance(value, list):
        for v in value:
            yield from _leaves(v)
    else:
        yield value


# --------------------------------------------------------------------------- it is the real advisor, on the research data
def test_demo_calls_the_real_advisor_and_binds_to_its_request(monkeypatch):
    calls = []
    real = adv_api.advise

    def spy(request, *, advised_at, **kw):
        calls.append(request)
        return real(request, advised_at=advised_at, **kw)

    monkeypatch.setattr(demo, "advise", spy)
    a = demo.run_example(1)
    assert len(calls) == 1
    validate_against_request(a, calls[0])
    assert a.advisor_identity == adv_api.ADVISOR_IDENTITY and a.advisor_version == adv_api.__version__


def test_research_rule_set_and_catalog_match_the_package_fixture():
    sys.path[:0] = [str(REPO / "packages" / "capabilities" / "reasoning-method-advisor" / "tests"), str(REPO / "packages" / "capabilities" / "reasoning-method-governance" / "tests")]
    import rule_fixtures as rf  # noqa: E402
    import matrix_fixtures as fx  # noqa: E402

    assert demo.SIGNAL_MAP_TRANSCRIPTION == rf.SIGNAL_MAP_TRANSCRIPTION
    assert demo.research_rules_v0().rules == rf.research_rules_v0().rules
    assert demo.research_rules_v0().admissibility == rf.admissibility()
    assert [e.method_id for e in demo.research_catalog().entries] == [e.method_id for e in fx.c4_catalog().entries]


def test_demo_module_reads_no_clock_and_reproduces_no_rule_logic():
    text = DEMO_SRC.read_text(encoding="utf-8")
    for needle in ("datetime.now(", "utcnow(", "time.time(", "date.today("):
        assert needle not in text
    tree = ast.parse(text)
    imported = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imported <= {"__future__", "argparse", "dataclasses", "json", "sys", "datetime", "enum", "pathlib", "typing", "ugence_reasoning_method_advisor", "ugence_reasoning_method_governance", "ugence_uvi_policy_contracts"}, imported
    # The demo never constructs an advisory or a rule outcome itself: only the advisor does.
    assert "ReasoningMethodAdvisory(" not in text and "RuleOutcome(" not in text and "QualifyingMethod(" not in text


def test_cli_json_output_equals_the_object_rendering_and_is_stable_across_processes():
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert demo.main(["--example", "2", "--json"]) == 0
    assert json.loads(buf.getvalue()) == demo.to_jsonable(demo.run_example(2))
    outs = set()
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": ":".join(sys.path)}
        r = subprocess.run([sys.executable, "-m", "experiments.reasoning_method_advisor_demo.demo", "--example", "2", "--json"], check=True, capture_output=True, text=True, env=env, cwd=str(REPO))
        outs.add(json.loads(r.stdout)["advisory_digest"])
    assert outs == {demo.run_example(2).advisory_digest}


def test_cli_profile_path_requires_an_explicit_instant(tmp_path):
    profile = demo.EXAMPLES_DIR / "profile_1_single.json"
    with pytest.raises(SystemExit):
        demo.main(["--profile", str(profile)])
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert demo.main(["--profile", str(profile), "--task-class", str(demo.EXAMPLES_DIR / "task_class_support.json"), "--advised-at", "2026-09-02T12:00:00Z", "--json"]) == 0
    out = json.loads(buf.getvalue())
    assert out["primary"]["method_id"] == "map_reduce" and out["advisory_id"] == "demo.request:advisory"
    with pytest.raises(ValueError):
        demo.parse_instant("2026-09-02T12:00:00")
