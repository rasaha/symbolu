#!/usr/bin/env python3
"""Torch-free pre-registration integrity verifier for the persistence phase. Emits a machine-readable
report. Fails if any frozen definition changed, any forbidden condition holds, or any training-result
file exists. Pure stdlib."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def main() -> int:
    checks, fails = 0, []
    frozen = json.loads((HERE / "frozen_reference_config.json").read_text())
    arms = json.loads((HERE / "arm_definitions.json").read_text())
    seeds = json.loads((HERE / "seed_manifest.json").read_text())
    cls = json.loads((HERE / "classifier.json").read_text())
    h1 = json.loads((HERE / "h1_parameter_group_manifest.json").read_text())
    o1r = json.loads((HERE / "o1r_definition.json").read_text())
    h2 = json.loads((HERE / "h2_teacher_definition.json").read_text())

    def chk(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            fails.append(msg)

    # frozen source hashes (incl. interventions/stabilize swapped at runtime; O1 source)
    for rel, want in frozen["frozen_code_hashes_sha256"].items():
        checks += 1
        p = REPO / rel
        if not p.exists() or sha256(p) != want:
            fails.append(f"frozen hash mismatch/missing: {rel}")
    chk(sha256(REPO / cls["inherited_from"]["file"]) == cls["inherited_from"]["sha256"], "classify_stage_b.py changed")
    chk(sha256(REPO / "experiments/phase_lc/results/abc.json") == "b31989a3135b150ef4cf693e42f173aadb51bba876b6e956da73f022d539b482", "abc.json changed")

    # exactly six arms, exactly the right ones
    chk(arms["matrix"]["arms"] == ["A+", "R0", "O1", "O1R", "H1", "H2"], "arm set is not A+/R0/O1/O1R/H1/H2")
    chk(set(arms["arms"].keys()) == {"A+", "R0", "O1", "O1R", "H1", "H2"}, "arm definitions mismatch")
    chk(not (set(["O2", "O3", "H3", "C1"]) & set(arms["arms"].keys())), "forbidden arm present")
    chk(arms["matrix"]["planned_runs"] == 30, "planned runs != 30")

    # seeds exactly 23-27, fresh, no replacement mechanism
    chk(seeds["stage_seeds"] == [23, 24, 25, 26, 27], "seeds not 23-27")
    used = set(seeds["previously_used_bindingslots_training_seeds"])
    chk(not (used & set(seeds["stage_seeds"])), "seed overlaps a used training seed")
    chk("FORBIDDEN" in seeds["replacement_policy"], "seed replacement policy not forbidden")
    chk(seeds["planned_matrix"]["runs_started_this_phase"] == 0, "runs_started != 0")

    # O1R coefficient + schedule frozen
    chk(o1r["residual_coefficient"] == 0.01, "O1R coefficient != 0.01")
    chk(o1r["residual_start_step"] == 601 and o1r["residual_stop_step"] == 1200, "O1R residual range wrong")
    chk(o1r["evaluation_coefficient"] == 0.0, "O1R eval coefficient != 0")
    chk("no coefficient sweep on seeds 23-27" in o1r["prohibitions"], "O1R sweep not prohibited")

    # H1 param group frozen + hashed
    chk(h1["name_list_sha256"] == hashlib.sha256("\n".join(h1["ordered_names"]).encode()).hexdigest(), "H1 name-list hash mismatch")
    chk(h1["lr_multiplier"] == 0.1 and h1["active_step_range"] == [600, 900], "H1 lr/interval wrong")
    chk(h1["param_count"] == 12 and h1["element_count"] == 73728, "H1 group size wrong")
    chk(all("W_wv" not in n and "gate" not in n and "W_o" not in n and "norm" not in n for n in h1["ordered_names"]), "H1 group includes non-addressing params")

    # H2 teacher frozen + no answer label
    chk(h2["teacher_source_checkpoint"] == 600, "H2 teacher not at step 600")
    chk(h2["evaluation_coefficient"] == 0.0, "H2 present at eval")
    chk(len(h2["no_answer_label_proof"]) >= 3, "H2 missing no-answer-label proof")

    # checkpoints incl 700 diagnostic
    chk(frozen["checkpoints"]["full_cadence"] == [0, 60, 120, 300, 600, 700, 900, 1200], "checkpoint cadence wrong")

    # classifier frozen thresholds + same-seed A+
    fc = cls["frozen_constants"]
    chk(fc["FORM_MIN"] == 0.075 and fc["FORM_MARGIN"] == 0.050 and fc["CHANCE"] == 0.02, "frozen constants deviate")
    rt = cls["routing_metric_thresholds"]
    chk(rt["correct_slot_probability_min"] == 0.50 and rt["correct_slot_median_rank_max"] == 5 and rt["correct_slot_address_margin_min"] == 3.0, "routing thresholds deviate")
    chk("SAME-SEED" in cls["same_seed_aplus_threshold"].upper(), "A+ same-seed threshold not preserved")

    # schemas present
    for s in ("run_manifest", "seed_manifest", "arm_definition", "checkpoint_metrics",
              "causal_ablation_result", "routing_trajectory", "h1_parameter_group_manifest",
              "h2_teacher_definition", "integrity_report", "aggregate_classification", "selection_decision"):
        checks += 1
        if not (HERE / "schemas" / f"{s}.schema.json").exists():
            fails.append(f"missing schema {s}")

    # NO training-result files exist
    seeds_dir = HERE / "results" / "seeds"
    checks += 1
    if seeds_dir.exists() and any(seeds_dir.iterdir()):
        fails.append("training-result files exist under results/seeds")
    for banned in ("aggregate_classification.json", "selection_decision.json", "stage_aggregate.json"):
        checks += 1
        if (HERE / "results" / banned).exists():
            fails.append(f"training-outcome file exists: {banned}")

    # no forbidden architecture tokens in phase code
    checks += 1
    forbidden = ["PhaseAttentionLayer", "HybridPhaseTransformer", "MultiLatentAttention", "quadratic_attention"]
    for src in HERE.glob("*.py"):
        txt = src.read_text()
        for t in forbidden:
            if t in txt and "denylist" not in txt[max(0, txt.find(t) - 60):txt.find(t)]:
                # allow appearance only inside an explicit forbidden-token list
                if f'"{t}"' not in txt and f"'{t}'" not in txt:
                    fails.append(f"forbidden token {t} in {src.name}")

    verdict = "BINDINGSLOTS_PERSISTENCE_PREREGISTRATION_VERIFIED" if not fails else "BINDINGSLOTS_PERSISTENCE_PREREGISTRATION_FAILED"
    report = {"schema": "bindingslots_persistence/integrity_report/v1", "checks": checks,
              "failures": fails, "verdict": verdict,
              "training_started": False, "checkpoints_generated": False, "results_classified": False,
              "kda_readiness": "KDA_VALIDATION_BLOCKED"}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "integrity_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"persistence pre-registration integrity: {checks} checks, {len(fails)} failures -> {verdict}")
    for f in fails:
        print("  FAIL:", f)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
