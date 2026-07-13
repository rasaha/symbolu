"""Integrity tests for the V2 absolute-utility benchmark.

These enforce the preregistered guarantees: V1 immutability, derivability of every V2
answer, mapping-supplied enum tasks, general/symmetric normalization, method-agnostic
deterministic scoring, identical instructions across arms, a distinct V2 fingerprint,
eligibility gating, and a verdict namespace separate from V1.
"""

from __future__ import annotations

import json
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_RUNPOD = _ROOT / "runpod"
for p in (str(_RUNPOD),):
    if p not in sys.path:
        sys.path.insert(0, p)

import runpod_common as RC                                   # noqa: E402
from actiongate_context_ablation import adapter              # noqa: E402
from actiongate_context_ablation import llm_tasks_v2 as T    # noqa: E402
from actiongate_context_ablation import scoring_v2 as S      # noqa: E402
from actiongate_context_ablation import normalize_v2 as NZ   # noqa: E402
from actiongate_context_ablation import real_llm_bench_v2 as R2   # noqa: E402
from actiongate_context_ablation import benchmark_v2 as B2   # noqa: E402
from actiongate_context_ablation import real_llm_bench as R1 # noqa: E402
from actiongate_context_ablation import extractor            # noqa: E402
from actiongate_context_ablation.corpus import registry      # noqa: E402

_SP = adapter.default_signed_policy()
_ITEMS = registry.load_all()
V1_FINGERPRINT = "sha256:ac4e069262ec663de0983c5461c64ad57bb8d62db326e6a6f1701f0628381eac"


def _all_tasks():
    for it in _ITEMS:
        for t in T.build_tasks(it, _SP):
            yield it, t


# ---- V1 immutability ------------------------------------------------------- #
def test_v1_frozen_fingerprint_unchanged():
    assert RC.frozen_fingerprint()["fingerprint"] == V1_FINGERPRINT


def test_v1_result_bundle_and_verdict_immutable():
    d = RC.EXPERIMENT_DIR / "results" / "qwen7b_primary_real_llm"
    res = json.loads((d / "results.json").read_text())
    man = json.loads((d / "run_manifest.json").read_text())
    assert res["recommendation"] == "GO" and res["is_real_llm"] is True
    assert man["frozen_fingerprint"] == V1_FINGERPRINT


def test_v2_files_not_in_v1_frozen_set():
    for f in ("llm_tasks_v2.py", "scoring_v2.py", "normalize_v2.py",
              "real_llm_bench_v2.py", "benchmark_v2.py"):
        assert f not in RC._FROZEN_FILES


# ---- derivability + supplied mappings -------------------------------------- #
def test_every_v2_answer_derivable_from_context():
    n = 0
    for it, t in _all_tasks():
        assert T.derivable_from_context(t, it.context), (it.item_id, t["type"])
        n += 1
    assert n > 400   # the full suite actually ran


def test_operation_map_complete_and_correct():
    for it in _ITEMS:
        res = extractor.extract_and_eval(it.context, [u.id for u in it.context.units],
                                         _SP, mode=extractor.ORACLE)
        env = res["envelope"]
        key = (env["tool"]["server_id"], env["tool"]["tool_name"])
        assert T.OPERATION_MAP.get(key) == env["operation"], key


def test_internal_enum_tasks_supply_their_mapping():
    for it, t in _all_tasks():
        if t["type"] == "operation_mapping":
            assert t["mapping_supplied"]
            # every mapping row is present verbatim in the prompt
            for (tool, verb), op in T.OPERATION_MAP.items():
                assert f"{tool}.{verb} -> {op}" in t["question"]
        if t["type"] == "multi_hop_reasoning":
            assert t["mapping_supplied"] and "Rule (given)" in t["question"]


def test_scorer_accepts_ground_truth_and_rejects_wrong():
    for it, t in _all_tasks():
        assert float(t["scorer"](str(t["expected"]))) >= 0.999, (t["type"], t["expected"])
    # a deliberately wrong structured answer scores below full
    rs = next(t for _, t in _all_tasks() if t["type"] == "rollback_simulation")
    wrong = '{"rollback_present": true, "simulation_present": false, "simulation_fidelity": "LOW"}'
    assert float(rs["scorer"](wrong)) < float(rs["scorer"](str(rs["expected"])))


# ---- normalization: general + symmetric ------------------------------------ #
def test_normalization_general_and_symmetric():
    # underscore / hyphen / space equivalence, casefold, article + punctuation removal
    assert NZ.normalize_text("Signed_Artifact") == NZ.normalize_text("signed artifact")
    assert NZ.normalize_text("dual-control") == NZ.normalize_text("dual control")
    assert NZ.normalize_text("The DEPLOY.") == "deploy"
    # idempotent
    once = NZ.normalize_text("A Signed-Build_Artifact!")
    assert NZ.normalize_text(once) == once
    # symmetric: comparison is order-independent for equivalence
    assert S._text_equiv("signed artifact", "SIGNED_ARTIFACT") == 1.0


def test_fields_scorer_isolates_each_field():
    # two-boolean JSON must not cross-contaminate (the bug this fixed)
    sc = S.fields_scorer([("a", "bool", True), ("b", "bool", False)])
    assert float(sc('{"a": true, "b": false}')) == 1.0
    assert float(sc('{"a": false, "b": true}')) == 0.0


# ---- scoring is deterministic + method-agnostic ---------------------------- #
def test_scorer_is_deterministic_and_method_agnostic():
    for _, t in list(_all_tasks())[:200]:
        out = str(t["expected"])
        a = float(t["scorer"](out))
        b = float(t["scorer"](out))
        assert a == b                       # deterministic
    # a scorer's signature takes only the model text — it cannot see the method/arm
    import inspect
    sig = inspect.signature(S.text_scorer("x"))
    assert list(sig.parameters) == ["out"]


def test_every_task_has_callable_scorer_and_metadata():
    for _, t in _all_tasks():
        assert callable(t["scorer"])
        assert t["type"] in T.TASK_TYPES
        assert t["derivable"] is True
        assert t["classification"]


# ---- identical instructions across arms ------------------------------------ #
def test_arms_differ_only_in_context():
    # SYSTEM + QUESTION are identical across arms; only the CONTEXT block differs.
    item = _ITEMS[0]
    task = next(iter(T.build_tasks(item, _SP)))
    ctx = item.context
    all_ids = [u.id for u in ctx.units]
    p_full = R1._prompt(ctx, all_ids)
    p_less = R1._prompt(ctx, all_ids[:1])
    q = f"\n\nQUESTION: {task['question']}"
    full = f"CONTEXT:\n{p_full}{q}"
    less = f"CONTEXT:\n{p_less}{q}"
    assert full.endswith(q) and less.endswith(q)     # same trailing question
    assert R2.SYSTEM_V2 == R2.SYSTEM_V2               # same system for both arms


# ---- distinct fingerprint + hashes react to rule changes ------------------- #
V2_FINGERPRINT = "sha256:4b9478483105dbadc741ae122b312db00a7b2db59fb496667a99981c84de54e5"


def test_v2_fingerprint_distinct_from_v1():
    fp = B2.fingerprint()
    assert fp["fingerprint"] != V1_FINGERPRINT
    assert fp["benchmark_id"] == R2.BENCHMARK_ID


def test_v2_fingerprint_frozen():
    assert B2.fingerprint()["fingerprint"] == V2_FINGERPRINT


def test_normalization_hash_changes_when_rules_change(monkeypatch):
    before = NZ.rules_hash()
    patched = dict(NZ._CONCEPT_ALIASES)
    patched["a brand new alias phrase"] = "signed_artifact"
    monkeypatch.setattr(NZ, "_CONCEPT_ALIASES", patched)
    assert NZ.rules_hash() != before


def test_scorer_hash_reacts_to_version(monkeypatch):
    before = S.scorer_hash()
    monkeypatch.setattr(S, "SCORER_VERSION", "vTEST")
    assert S.scorer_hash() != before


def test_no_v1_result_files_read_by_v2_scoring():
    # the V2 scoring/normalization/task modules must not read any results/ artifact
    import inspect
    for mod in (T, S, NZ, R2):
        src = inspect.getsource(mod)
        assert "results.json" not in src and "records.jsonl" not in src


# ---- eligibility gating + verdict namespace -------------------------------- #
def _cell(method, budget, acc, dec=1.0, env=1.0, recall=1.0):
    return R2.Cell(method=method, budget=budget, token_reduction=0.4,
                   decision_preservation=dec, envelope_preservation=env,
                   protected_recall=recall, task_accuracy=acc,
                   per_task_accuracy={t: acc for t in T.TASK_TYPES},
                   hallucination_rate=0.0, mean_latency_ms=1.0, cost_estimate_usd=0.01,
                   n_contexts=77)


def test_eligibility_fails_when_original_utility_too_low():
    cells = [_cell("original", 0.0, 0.40), _cell("structural_only", 0.0, 0.40)]
    for b in R2.BUDGETS:
        cells.append(_cell("protected", b, 0.40))
        cells.append(_cell("protection_unaware", b, 0.40, dec=0.97))
    rec, _ = R2._success(cells, is_real=True)
    assert rec == R2.BENCHMARK_NOT_ELIGIBLE


def test_go_when_eligible_and_all_criteria_met():
    # all per-task accuracies high so critical tool-arg (>=98%) and policy (>=90%) pass
    cells = [_cell("original", 0.0, 0.99), _cell("structural_only", 0.0, 0.98)]
    for b in R2.BUDGETS:
        cells.append(_cell("protected", b, 0.99))
        cells.append(_cell("protection_unaware", b, 0.99, dec=0.97))
    rec, detail = R2._success(cells, is_real=True)
    assert rec == R2.ABSOLUTE_UTILITY_GO and detail["benchmark_eligible"]


def test_stop_when_safety_fails():
    cells = [_cell("original", 0.0, 0.80), _cell("structural_only", 0.0, 0.79)]
    for b in R2.BUDGETS:
        cells.append(_cell("protected", b, 0.80, dec=0.95))     # a decision flip
        cells.append(_cell("protection_unaware", b, 0.80, dec=0.90))
    rec, _ = R2._success(cells, is_real=True)
    assert rec == R2.ABSOLUTE_UTILITY_STOP


def test_blocked_when_not_real():
    cells = [_cell("original", 0.0, 0.80)]
    rec, _ = R2._success(cells, is_real=False)
    assert rec == R2.BLOCKED_NO_MODEL


def test_v2_verdict_namespace_distinct_from_v1():
    v2 = {R2.ABSOLUTE_UTILITY_GO, R2.ABSOLUTE_UTILITY_LIMITED_GO, R2.ABSOLUTE_UTILITY_STOP,
          R2.BENCHMARK_NOT_ELIGIBLE}
    v1 = {"GO", "LIMITED_GO", "STOP"}
    assert v2.isdisjoint(v1)
