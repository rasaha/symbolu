"""Frozen-invariance regression: prove the benchmark surface is unchanged since the
Qwen2.5-7B primary run — only the model may change across the cross-model study."""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

_RUNPOD = pathlib.Path(__file__).resolve().parents[1] / "runpod"
if str(_RUNPOD) not in sys.path:
    sys.path.insert(0, str(_RUNPOD))

import runpod_common as RC          # noqa: E402
from actiongate_context_ablation import real_llm_bench as R, llm_tasks  # noqa: E402
from actiongate_context_ablation.corpus import manifest as CM  # noqa: E402

# Values recorded by the frozen Qwen2.5-7B primary run (results/qwen7b_primary_real_llm).
QWEN_FROZEN_FINGERPRINT = "sha256:ac4e069262ec663de0983c5461c64ad57bb8d62db326e6a6f1701f0628381eac"
QWEN_SYSTEM_HASH = "sha256:0131598f9a531c02e142a8cc2ad178a82f5c0472963059d2a18fa9f72499a564"
QWEN_POLICY = "0.1.0-ref:b93b95d182bf796c"


def test_frozen_fingerprint_matches_qwen_run():
    assert RC.frozen_fingerprint()["fingerprint"] == QWEN_FROZEN_FINGERPRINT


def test_actiongate_policy_unchanged():
    assert RC.frozen_fingerprint()["policy"] == QWEN_POLICY


def test_system_prompt_unchanged():
    got = "sha256:" + hashlib.sha256(R._SYSTEM.encode()).hexdigest()
    assert got == QWEN_SYSTEM_HASH


def test_methods_and_budgets_unchanged():
    assert R.METHODS == ["original", "structural_only", "protected", "protection_unaware"]
    assert R.BUDGETS == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]


def test_task_types_unchanged():
    assert llm_tasks.TASK_TYPES == [
        "tool_selection", "tool_argument_generation", "factual_qa", "reasoning",
        "instruction_following", "extraction", "summarization",
        "actiongate_envelope_extraction"]


def test_corpus_unchanged_vs_committed_manifest():
    committed = json.loads((RC.PKG_DIR / "corpus" / "manifest.json").read_text())
    assert CM.build_manifest()["manifest_hash"] == committed["manifest_hash"]


def test_qwen_committed_result_is_frozen_and_consistent():
    d = RC.EXPERIMENT_DIR / "results" / "qwen7b_primary_real_llm"
    man = json.loads((d / "run_manifest.json").read_text())
    res = json.loads((d / "results.json").read_text())
    assert man["frozen_fingerprint"] == QWEN_FROZEN_FINGERPRINT
    assert man["run_config"]["system_hash"] == QWEN_SYSTEM_HASH
    assert man["model_id"] == "Qwen/Qwen2.5-7B-Instruct"
    assert res["is_real_llm"] is True and res["recommendation"] == "GO"
