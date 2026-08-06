"""Fixture-only structural + mock tests for training / evaluation / replay / evidence / manifest.

NO training, evaluation, or replay is actually executed: the model is never run. Training is checked
structurally (encoding + frozen-recipe assertions); evaluation and replay use injected decode/
reconstruct functions; evidence and manifest are checked as pure file/schema assembly. Uses only
fixture seeds 993000-993004.
"""
from __future__ import annotations

import os

import pytest

from experiments.unseen_identifier_copy_selection.config import FIXTURE_SEEDS
from experiments.unseen_identifier_copy_selection.evaluation import (
    build_prompt_ids,
    build_trace,
    evaluate_cohort,
)
from experiments.unseen_identifier_copy_selection.evidence import (
    EvidenceError,
    atomic_write_json,
    finalize_run_dir,
    is_incomplete,
    prepare_run_dir,
    write_run_evidence,
)
from experiments.unseen_identifier_copy_selection.manifest import (
    RUN_MANIFEST_DIGEST_FIELDS,
    build_run_manifest,
    canonical_json,
    digest_json,
)
from experiments.unseen_identifier_copy_selection.parser import OutputCategory
from experiments.unseen_identifier_copy_selection.replay import (
    REPLAYED_DIGEST_FIELDS,
    ReplayMismatch,
    replay_run,
)
from experiments.unseen_identifier_copy_selection.runner import (
    FAIL_CLOSED_REJECTIONS,
    ORCHESTRATION_ORDER,
    build_cohort,
)
from experiments.unseen_identifier_copy_selection.tasks import generate_split
from experiments.unseen_identifier_copy_selection.training import (
    encode_cohort,
    encode_example,
)

FS = FIXTURE_SEEDS[0]


# ---- training orchestration (structural; no training) --------------------

def test_encode_example_masks_prompt_and_supervises_gold():
    ex = generate_split("C1", "unseen", FS, n=1)[0]
    enc = encode_example(ex)
    ignore = -100
    # prefix (bos + prompt) is masked; the tail supervises the gold identifier + eos
    assert enc.labels[: enc.prompt_token_count] == tuple(ignore for _ in range(enc.prompt_token_count))
    assert enc.labels[-1] != ignore  # eos supervised
    assert len(enc.input_ids) == len(enc.labels)


def test_encode_cohort_covers_all_examples():
    cohort = build_cohort(FS, "unseen")
    flat = [e for split in sorted(cohort) for e in cohort[split]]
    enc = encode_cohort(flat)
    assert len(enc) == len(flat)


def test_assert_frozen_recipe_accepts_the_reused_model_and_rejects_wrong_count():
    from experiments.single_hop_typed_vs_prose.model import build_model
    from experiments.unseen_identifier_copy_selection.training import assert_frozen_recipe

    model = build_model(FS)  # fixture seed, no training
    assert_frozen_recipe(model)  # 209,728 params, sole submodule 'lm'

    class _Fake:
        def parameter_count(self):
            return 123

        def named_children(self):
            return iter(())

    with pytest.raises(ValueError):
        assert_frozen_recipe(_Fake())


# ---- evaluation (injected decode; no model run) --------------------------

def test_build_trace_schema_and_classification():
    ex = generate_split("C2", "unseen", FS, n=1)[0]
    trace = build_trace(ex, ex.expected_output)
    expected_keys = {
        "example_hash", "task", "split", "cohort", "seed", "input_hash", "prompt_token_count",
        "expected_output", "raw_output", "normalized_output", "parsed_category", "exact_match",
        "token_match_fraction", "wrong_in_context", "fabricated_out_of_context", "abstention",
    }
    assert set(trace.keys()) == expected_keys
    assert trace["exact_match"] is True
    assert trace["parsed_category"] == OutputCategory.EXACT_CORRECT.value


def test_evaluate_cohort_with_injected_decode_produces_traces_and_counts():
    cohort = {"C1": generate_split("C1", "unseen", FS, n=4)}

    def stub_decode(model, prompt_ids, tokenizer, device):
        assert model is None  # injected path never builds the model
        return "ZZZZ"

    ev = evaluate_cohort("unused.pt", cohort, decode_fn=stub_decode)
    assert len(ev.traces) == 4
    assert len(ev.prediction_digest) == 64
    assert sum(ev.parser_category_counts["C1"].values()) == 4


def test_greedy_prompt_ends_at_output_marker():
    from experiments.single_hop_typed_vs_prose.config import FROZEN_TRAIN_RECIPE
    from experiments.single_hop_typed_vs_prose.tokenizer import LexicalTokenizer

    ex = generate_split("C1", "unseen", FS, n=1)[0]
    tok = LexicalTokenizer()
    ids = build_prompt_ids(ex, tok)
    assert ids[0] == tok.bos_id
    assert tok.decode(ids).endswith(FROZEN_TRAIN_RECIPE.output_marker)


# ---- replay (injected reconstruct; no retrain) ---------------------------

def test_replay_matches_identical_digests():
    original = {name: f"digest-{name}" for name in REPLAYED_DIGEST_FIELDS}

    def reconstruct(seed, cohort, token, work_dir):
        return dict(original)

    report = replay_run(FS, "unseen", original, reconstruct=reconstruct)
    assert report.matched is True


def test_replay_fails_closed_on_any_digest_mismatch():
    original = {name: f"digest-{name}" for name in REPLAYED_DIGEST_FIELDS}

    def reconstruct(seed, cohort, token, work_dir):
        drifted = dict(original)
        drifted["prediction_digest"] = "DIFFERENT"
        return drifted

    with pytest.raises(ReplayMismatch):
        replay_run(FS, "unseen", original, reconstruct=reconstruct)


# ---- evidence (atomic writes, containment, markers) ----------------------

def test_prepare_run_dir_marks_incomplete_then_finalize_clears(tmp_path):
    path = prepare_run_dir(str(tmp_path), FS, "unseen")
    assert is_incomplete(path)
    finalize_run_dir(path)
    assert not is_incomplete(path)


def test_non_empty_run_dir_refused(tmp_path):
    path = prepare_run_dir(str(tmp_path), FS, "unseen")
    atomic_write_json(path, "x.json", {"a": 1})
    with pytest.raises(EvidenceError):
        prepare_run_dir(str(tmp_path), FS, "unseen")  # now non-empty


def test_overwrite_refused(tmp_path):
    path = prepare_run_dir(str(tmp_path), FS, "unseen")
    atomic_write_json(path, "x.json", {"a": 1})
    with pytest.raises(EvidenceError):
        atomic_write_json(path, "x.json", {"a": 2})  # overwrite refused


def test_write_outside_output_dir_refused(tmp_path):
    path = prepare_run_dir(str(tmp_path), FS, "unseen")
    with pytest.raises(EvidenceError):
        atomic_write_json(path, os.path.join("..", "escape.json"), {"a": 1})


def test_write_run_evidence_emits_traces_and_manifest(tmp_path):
    written = write_run_evidence(str(tmp_path), seed=FS, cohort="unseen",
                                 traces=[{"example_hash": "h"}], manifest={"ok": True})
    names = {os.path.basename(p) for p in written.files}
    assert names == {"traces.json", "manifest.json"}
    assert not is_incomplete(written.run_directory)


# ---- manifest schema -----------------------------------------------------

def test_canonical_json_is_sorted_ascii_and_stable():
    obj = {"b": 1, "a": 2}
    assert canonical_json(obj) == '{"a":2,"b":1}'
    assert digest_json(obj) == digest_json({"a": 2, "b": 1})


def test_build_run_manifest_requires_all_digest_fields():
    digests = {name: f"d-{name}" for name in RUN_MANIFEST_DIGEST_FIELDS}
    manifest = build_run_manifest(
        seed=FS, cohort="unseen", source_commit="c", protocol_lock_commit="p",
        implementation_authorization_commit="ia", implementation_commit="i",
        digests=digests, parser_category_counts={}, per_task_metrics={},
        shortcut_results={}, resource_measurements={}, protocol_compliance={"ok": True},
    )
    assert manifest["schema_version"].startswith("unseen-id-run-manifest/")
    assert set(manifest["digests"]) == set(RUN_MANIFEST_DIGEST_FIELDS)
    assert "manifest_digest" in manifest


def test_build_run_manifest_rejects_missing_digest():
    digests = {name: "d" for name in RUN_MANIFEST_DIGEST_FIELDS[:-1]}  # drop one
    with pytest.raises(ValueError):
        build_run_manifest(
            seed=FS, cohort="unseen", source_commit="c", protocol_lock_commit="p",
            implementation_authorization_commit="ia", implementation_commit="i",
            digests=digests, parser_category_counts={}, per_task_metrics={},
            shortcut_results={}, resource_measurements={}, protocol_compliance={},
        )


# ---- frozen orchestration order + rejection list -------------------------

def test_orchestration_order_is_frozen_and_has_no_auto_transition():
    assert ORCHESTRATION_ORDER[0] == "validate_authorization_record"
    assert ORCHESTRATION_ORDER[-1] == "stop"
    assert "replay" in ORCHESTRATION_ORDER and "compare_digests" in ORCHESTRATION_ORDER
    # no automatic smoke->development transition is encoded
    assert not any("smoke" in step or "development" in step for step in ORCHESTRATION_ORDER)


def test_fail_closed_rejection_list_covers_key_conditions():
    joined = " ".join(FAIL_CLOSED_REJECTIONS)
    for needle in ("wrong seed", "wrong cohort", "final seed", "replay mismatch",
                   "wildcard/range/list", "non-empty output directory", "overwrite"):
        assert needle in joined
