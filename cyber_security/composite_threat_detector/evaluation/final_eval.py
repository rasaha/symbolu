"""Guarded official final evaluator + immutable evaluation record (§5).

Access controls that make the replacement (holdout) final split hard to inspect
casually and impossible to run "officially" in development mode or against modified
inputs. The development and calibration commands (``story_corpus_v2.evaluate_corpus``
/ ``check_gates``) operate on the exposed development corpus only and cannot reach
the holdout by construction — the holdout is a disjoint generation and only this
module evaluates it.
"""

from __future__ import annotations

import json
import os

from composite_threat_detector.canonical import digest

from . import freeze as F
from . import story_corpus_v2 as S

DEFAULT_RECORD = os.path.join(os.path.dirname(__file__), "results",
                              "story_final_eval_record.json")


class FinalEvalError(Exception):
    pass


def run_official_final(frozen: dict, *, commit: str, now: str,
                       record_path: str = DEFAULT_RECORD,
                       development_mode: bool = False,
                       allow_new_generation: bool = False) -> dict:
    """Run the holdout final split exactly once under a frozen configuration.

    Refuses when: development mode is set; the freeze is not an official 'final'
    profile or drifted from the current inputs; or an immutable record already
    exists for a different freeze/generation (unless a NEW evaluation generation is
    explicitly requested). Emits one immutable evaluation record.
    """
    if development_mode:
        raise FinalEvalError("official final evaluation refuses development mode")
    # refuses modified graph/provider/policy/corpus/matcher inputs + dev profile
    F.require_frozen(frozen, official=True)

    holdout = S.holdout_hashes()
    if holdout != frozen.get("story_corpus_holdout"):
        raise FinalEvalError("holdout corpus differs from the frozen holdout hash")

    prior = _read_record(record_path)
    if prior is not None and not allow_new_generation:
        same = (prior.get("freeze_digest") == frozen.get("freeze_digest")
                and prior.get("holdout", {}).get("holdout_id_hash")
                == holdout["holdout_id_hash"])
        raise FinalEvalError(
            "an immutable final-evaluation record already exists"
            + ("" if same else " (for a different freeze/generation)")
            + "; pass allow_new_generation=True to record a NEW evaluation generation")

    cases = S.holdout_final_cases()
    metrics = S.evaluate_corpus(cases)
    metrics["split"] = "final_holdout"
    gates = S.check_gates(metrics)

    record = {
        "record_kind": "immutable_final_evaluation",
        "generation": (prior.get("generation", 0) + 1) if prior else 1,
        "commit": commit, "invoked_at": now,
        "freeze_digest": frozen.get("freeze_digest"),
        "matcher_semantics": frozen.get("matcher_semantics"),
        "witness_tiebreak_version": frozen.get("witness_tiebreak_version"),
        "story_corpus_generator": frozen.get("story_corpus_generator"),
        "holdout": holdout,
        "gates_all_pass": gates["all_pass"],
        "metrics": {k: v for k, v in metrics.items() if k != "per_case"},
        "gate_checks": gates["checks"],
    }
    record["record_digest"] = digest(record, domain="CTD-FINAL-RECORD")
    _write_record(record_path, record, overwrite=allow_new_generation)
    return {"metrics": metrics, "gates": gates, "record": record,
            "record_path": record_path}


def _read_record(path):
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def _write_record(path, record, *, overwrite):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and not overwrite:
        raise FinalEvalError("refusing to overwrite an existing immutable record")
    with open(path, "w") as fh:
        json.dump(record, fh, indent=1, sort_keys=True)


def dev_corpus_excludes_holdout() -> bool:
    """Structural guarantee: no development-corpus case id is a holdout case id."""
    dev_ids = {c.case_id for c in S.CORPUS}
    holdout_ids = {c.case_id for c in S.holdout_final_cases()}
    return dev_ids.isdisjoint(holdout_ids)
