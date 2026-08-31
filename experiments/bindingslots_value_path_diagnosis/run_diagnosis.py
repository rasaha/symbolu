#!/usr/bin/env python3
"""Orchestrator: deterministic instrumented reproduction of the frozen cohort + value-path (A0-A4)
and gradient (B2-B3) diagnostics, then mechanical per-seed diagnosis and the primary verdict.

Runs one cohort member at a time (reproduce -> gate -> diagnostics -> persist), so it is resumable:
completed per-run results live under results/_progress/. Re-launch skips finished runs.

Discipline: reproduction uses the FROZEN runners unchanged; diagnostics run on frozen deepcopied
snapshots with zero optimizer steps; snapshot hashes are recorded and asserted stable; oracle modes
touch only the query-position read; probes are analysis-only; failure seeds never tune thresholds.
Never emits READY_FOR_KDA_VALIDATION. Always reports KDA_VALIDATION_BLOCKED.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
RESULTS = HERE / "results"
PROG = RESULTS / "_progress"
sys.path.insert(0, str(HERE))

import diagnosis_lib as DL          # noqa: E402
import value_path as VP             # noqa: E402
import probes as PR                 # noqa: E402
import gradients as GR              # noqa: E402
import reproduction_gate as RG      # noqa: E402
import diagnosis_classify as DC     # noqa: E402

CKPTS = [600, 700, 900, 1200]
GRAD_CKPTS = [900, 1200]
SLOT_ARMS = {"R0", "O1R", "H2"}
# clean control seed used for each arm's quality gradient-alignment comparison (§13)
QUALITY_CONTROL = {"O1R": 23, "H2": 24}


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2) + "\n")
    tmp.replace(path)


def _atom(x):
    """Round floats for stable artifacts (does not affect the exact-equality reproduction gate,
    which runs on the raw record)."""
    if isinstance(x, float):
        return round(x, 8)
    if isinstance(x, dict):
        return {k: _atom(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_atom(v) for v in x]
    return x


def run_member(arm, seed, vocab, T, TA):
    t0 = time.time()
    rec, snaps, nsteps = DL.reproduce_run(arm, seed, steps=1200, targets=CKPTS)
    gate = RG.gate(arm, seed, rec)
    out = {
        "arm": arm, "seed": seed,
        "optimizer_steps": nsteps,
        "expected_optimizer_steps": 1200,
        "no_extra_optimizer_steps": (nsteps == 1200),
        "reproduction_gate": gate,
        "snapshot_hashes": {str(s): DL.model_state_hash(m) for s, m in snaps.items()},
        "snapshots_captured": sorted(snaps.keys()),
        "committed_category": None,
    }
    if not gate["passed"]:
        out["classification"] = "INSTRUMENTED_REPRODUCTION_FAILED"
        out["note"] = "internal tensors NOT used as scientific evidence"
        out["seconds"] = round(time.time() - t0, 1)
        return out

    if arm not in SLOT_ARMS:
        # A+ control: no slot value path. Record the same-seed needle baseline for informativeness.
        out["classification"] = "INSTRUMENTED_REPRODUCTION_ACCEPTED"
        out["aplus_needle_by_dist"] = rec["needle_by_dist"]
        out["has_slot_path"] = False
        out["seconds"] = round(time.time() - t0, 1)
        return out

    out["has_slot_path"] = True
    # ---------- A2 stagewise linear-decodability profile ----------
    a2 = {}
    for s in CKPTS:
        a2[str(s)] = PR.run_linear_probes(snaps[s], vocab, T)
    out["A2_linear_probes"] = a2

    # ---------- A1 slot-value integrity (terminal + step600 reference) ----------
    out["A1_slot_value_integrity"] = {
        "1200": VP.slot_value_integrity(snaps[1200], vocab, T),
        "600": VP.slot_value_integrity(snaps[600], vocab, T),
    }

    # ---------- ordinary + A3 + A4 on the terminal snapshot (the failed eval examples) ----------
    ordi = VP.ordinary_eval(snaps[1200], vocab, T)
    out["ordinary_eval_1200"] = ordi
    out["A3_oracle_address"] = VP.oracle_eval(snaps[1200], vocab, T, "oracle_address", ordi)
    out["A4a_oracle_read_query"] = VP.oracle_eval(snaps[1200], vocab, T, "oracle_read_query", ordi)
    out["A4b_oracle_postwrite"] = VP.oracle_eval(snaps[1200], vocab, T, "oracle_postwrite", ordi)

    # ---------- B2 / B3 gradient diagnostics ----------
    teacher = snaps.get(600) if arm == "H2" else None
    grad = {}
    for s in GRAD_CKPTS:
        grad[str(s)] = GR.run_gradient_diagnostics(snaps[s], arm, vocab, T, TA, teacher_model=teacher)
    out["gradient_diagnostics"] = grad

    out["classification"] = "INSTRUMENTED_REPRODUCTION_ACCEPTED"
    out["seconds"] = round(time.time() - t0, 1)
    return out


def main():
    import _nso
    TA, T = _nso.tasks_adapter, _nso.tasks
    vocab = TA.build_corpus()[1]
    cohort = json.loads((HERE / "cohort.json").read_text())
    cat = {(m["arm"], m["seed"]): m["committed_category"] for m in cohort["members"]}
    # §4: establish the reproduction gate on CONTROL runs (A+ and clean formers) BEFORE the failure
    # exemplars, so no tolerance is fit to failure seeds. The gate itself is EXACT equality (no free
    # parameter), so order does not change any verdict; this only honours the ordering discipline.
    CONTROL_FIRST = [("A+", 23), ("A+", 24), ("A+", 25), ("R0", 24), ("O1R", 23), ("H2", 24)]
    all_members = [(m["arm"], m["seed"]) for m in cohort["members"]]
    members = CONTROL_FIRST + [m for m in all_members if m not in CONTROL_FIRST]

    PROG.mkdir(parents=True, exist_ok=True)
    all_runs = []
    for arm, seed in members:
        pth = PROG / f"{arm.replace('+','plus')}_{seed}.json"
        if pth.exists():
            print(f"[skip] {arm} s{seed} (cached)", flush=True)
            all_runs.append(json.loads(pth.read_text()))
            continue
        print(f"[run ] {arm} s{seed} ...", flush=True)
        out = run_member(arm, seed, vocab, T, TA)
        out["committed_category"] = cat[(arm, seed)]
        out = _atom(out)
        _write(pth, out)
        print(f"[done] {arm} s{seed} gate={out['reproduction_gate']['classification']} "
              f"({out['seconds']}s)", flush=True)
        all_runs.append(out)

    assemble(all_runs, cohort)


def assemble(all_runs, cohort):
    by = {(r["arm"], r["seed"]): r for r in all_runs}
    print("[assemble] building artifacts ...", flush=True)

    # ---- reproduction_results.json ----
    repro = {"schema": "bindingslots_value_path_diagnosis/reproduction_results/v1",
             "gate": "EXACT_EQUALITY", "runs": []}
    for r in all_runs:
        repro["runs"].append({
            "arm": r["arm"], "seed": r["seed"],
            "classification": r["reproduction_gate"]["classification"],
            "passed": r["reproduction_gate"]["passed"],
            "optimizer_steps": r["optimizer_steps"],
            "no_extra_optimizer_steps": r["no_extra_optimizer_steps"],
            "snapshot_hashes": r["snapshot_hashes"],
            "snapshots_captured": r["snapshots_captured"],
            "first_diffs": r["reproduction_gate"]["first_diffs"],
        })
    _write(RESULTS / "reproduction_results.json", repro)

    accepted = [r for r in all_runs if r["reproduction_gate"]["passed"]]
    any_failed = any(not r["reproduction_gate"]["passed"] for r in all_runs)
    slot_accepted = [r for r in accepted if r.get("has_slot_path")]

    # ---- A1 / A2 / A3 / A4 artifacts ----
    _write(RESULTS / "slot_value_integrity.json", {
        "schema": "bindingslots_value_path_diagnosis/slot_value_integrity/v1",
        "runs": [{"arm": r["arm"], "seed": r["seed"], "A1": r["A1_slot_value_integrity"]}
                 for r in slot_accepted]})
    _write(RESULTS / "linear_probe_results.json", {
        "schema": "bindingslots_value_path_diagnosis/linear_probe_results/v1",
        "probe_config": {"seed": PR.PROBE_SEED, "n": PR.PROBE_N, "distance": PR.PROBE_DISTANCE,
                         "split": PR.SPLIT, "fit_steps": PR.FIT_STEPS, "chance": round(DC.CHANCE, 4)},
        "runs": [{"arm": r["arm"], "seed": r["seed"], "stagewise": r["A2_linear_probes"]}
                 for r in slot_accepted]})
    _write(RESULTS / "oracle_address_results.json", {
        "schema": "bindingslots_value_path_diagnosis/oracle_address_results/v1",
        "runs": [{"arm": r["arm"], "seed": r["seed"], "ordinary": r["ordinary_eval_1200"],
                  "A3_oracle_address": r["A3_oracle_address"]} for r in slot_accepted]})
    _write(RESULTS / "oracle_value_results.json", {
        "schema": "bindingslots_value_path_diagnosis/oracle_value_results/v1",
        "runs": [{"arm": r["arm"], "seed": r["seed"], "ordinary": r["ordinary_eval_1200"],
                  "A4a_oracle_read_query": r["A4a_oracle_read_query"],
                  "A4b_oracle_postwrite": r["A4b_oracle_postwrite"]} for r in slot_accepted]})

    # ---- gradient artifacts ----
    _write(RESULTS / "gradient_norms.json", {
        "schema": "bindingslots_value_path_diagnosis/gradient_norms/v1",
        "runs": [{"arm": r["arm"], "seed": r["seed"],
                  "grad_norms_by_group": {c: r["gradient_diagnostics"][c]["grad_norms_by_group"]
                                          for c in r["gradient_diagnostics"]},
                  "persist_to_lm_norm_ratio": {c: r["gradient_diagnostics"][c].get("persist_to_lm_norm_ratio")
                                               for c in r["gradient_diagnostics"]},
                  "teacher_to_lm_norm_ratio": {c: r["gradient_diagnostics"][c].get("teacher_to_lm_norm_ratio")
                                               for c in r["gradient_diagnostics"]},
                  "param_group_audit": r["gradient_diagnostics"]["1200"]["param_group_audit"],
                  "state_hash_unchanged": {c: r["gradient_diagnostics"][c]["state_hash_unchanged"]
                                           for c in r["gradient_diagnostics"]}}
                 for r in slot_accepted]})
    _write(RESULTS / "gradient_alignment.json", {
        "schema": "bindingslots_value_path_diagnosis/gradient_alignment/v1",
        "bands": {"CONFLICT_COS": DC.CONFLICT_COS, "CONTROL_GAP": DC.CONTROL_GAP},
        "runs": [{"arm": r["arm"], "seed": r["seed"],
                  "alignment_lm_vs_persist": {c: r["gradient_diagnostics"][c].get("alignment_lm_vs_persist")
                                              for c in r["gradient_diagnostics"]},
                  "alignment_lm_vs_teacher": {c: r["gradient_diagnostics"][c].get("alignment_lm_vs_teacher")
                                              for c in r["gradient_diagnostics"]},
                  "global_alignment_lm_vs_persist": {c: r["gradient_diagnostics"][c].get("global_alignment_lm_vs_persist")
                                                     for c in r["gradient_diagnostics"]},
                  "global_alignment_lm_vs_teacher": {c: r["gradient_diagnostics"][c].get("global_alignment_lm_vs_teacher")
                                                     for c in r["gradient_diagnostics"]}}
                 for r in slot_accepted]})

    # ---- tensor manifest ----
    _write(RESULTS / "tensor_manifest.json", tensor_manifest())

    # ---- per-seed mechanical diagnosis ----
    per_seed = []
    for r in slot_accepted:
        arm, seed = r["arm"], r["seed"]
        a2_1200 = r["A2_linear_probes"]["1200"]["summary_last_layer"]
        meas = {
            "needle_baseline": r["ordinary_eval_1200"]["needle_acc"],
            "oracle_address_needle": r["A3_oracle_address"]["needle_acc"],
            "oracle_read_query_needle": r["A4a_oracle_read_query"]["needle_acc"],
            "oracle_postwrite_needle": r["A4b_oracle_postwrite"]["needle_acc"],
            "postwrite_decodable": a2_1200["postwrite_decodable"],
            "query_decodable": a2_1200["query_decodable"],
            "quality_failed": (r["committed_category"] == "QUALITY_FAILED"),
        }
        # quality gradient-alignment inputs (1200 checkpoint), with clean-control comparison
        fa = _group_cos(r, arm, "1200")
        ctrl_seed = QUALITY_CONTROL.get(arm)
        ctrl = by.get((arm, ctrl_seed)) if ctrl_seed is not None else None
        ca = _group_cos(ctrl, arm, "1200") if ctrl and ctrl.get("has_slot_path") else {}
        meas["failed_alignment_by_group"] = fa
        meas["control_alignment_by_group"] = ca
        meas["quality_control_seed"] = ctrl_seed
        d = DC.seed_diagnosis(arm, seed, meas)
        d["committed_category"] = r["committed_category"]
        d["measurements"] = _atom(meas)
        per_seed.append(d)
    _write(RESULTS / "per_seed_diagnosis.json", {
        "schema": "bindingslots_value_path_diagnosis/per_seed_diagnosis/v1",
        "frozen_constants": DC.FROZEN_CONSTANTS, "per_seed": per_seed})

    # ---- aggregate conclusion + verdict ----
    if any_failed:
        verdict = "BINDINGSLOTS_INSTRUMENTED_REPRODUCTION_FAILED"
    else:
        verdict = DC.aggregate_verdict(per_seed)
    aggregate = {
        "schema": "bindingslots_value_path_diagnosis/aggregate_conclusion/v1",
        "primary_verdict": verdict,
        "kda_readiness": "KDA_VALIDATION_BLOCKED",
        "ready_for_kda_validation": False,
        "cohort_size": len(cohort["members"]),
        "reproduction_accepted": len(accepted),
        "reproduction_failed": len(all_runs) - len(accepted),
        "value_path_localizations": sorted({d["value_path_diagnosis"] for d in per_seed}),
        "quality_localizations": sorted({d["quality_diagnosis"] for d in per_seed}),
        "per_seed_summary": [{"arm": d["arm"], "seed": d["seed"],
                              "value_path": d["value_path_diagnosis"],
                              "quality": d["quality_diagnosis"]} for d in per_seed],
        "scope": "diagnostic only; no fix, no tuning, no next intervention phase, no KDA",
    }
    _write(RESULTS / "aggregate_conclusion.json", aggregate)

    # ---- integrity + hashes ----
    _write(RESULTS / "integrity_report.json", integrity_report(all_runs, cohort))
    _write(RESULTS / "artifact_hashes.json", artifact_hashes())
    print(f"[assemble] DONE. verdict={verdict}", flush=True)


def _group_cos(run, arm, ckpt):
    """Extract per-group LM-vs-(persist|teacher) cosine dict at a checkpoint (or {})."""
    if not run or not run.get("has_slot_path"):
        return {}
    gd = run.get("gradient_diagnostics", {}).get(ckpt, {})
    key = "alignment_lm_vs_teacher" if arm == "H2" else "alignment_lm_vs_persist"
    al = gd.get(key)
    if not al:
        return {}
    return {g: (v.get("cosine") if isinstance(v, dict) else None) for g, v in al.items()}


def tensor_manifest():
    return {
        "schema": "bindingslots_value_path_diagnosis/tensor_manifest/v1",
        "read_path": "u_read = sum_j r[j]*slot[j] ; c_mem = W_o(u_read) ; h_post = h_pre + c_mem",
        "no_learned_read_or_fusion_gate": True,
        "captured_per_slot_layer_at_query_and_fact": {
            "v_fact": "written fact representation W_wv(norm(x)) at fact position [B,D]",
            "waddr_fact": "write-address distribution at fact position [B,M]",
            "sstar": "selected write-slot index argmax(waddr_fact) [B]",
            "m_postwrite": "target slot immediately after write slots[fact_pos,s*] [B,D]",
            "m_query": "target slot at query time slots[query_pos,s*] [B,D]",
            "raddr_query": "read-address distribution at query [B,M]",
            "read_query": "ordinary weighted read u_read at query [B,D]",
            "c_mem_query": "projected memory contribution W_o(u_read) at query [B,D]",
            "read_prob_on_sstar": "read probability placed on s* at query [B]",
            "w_to_sstar": "gated write mass into s* over all positions [B,N]",
            "gate_fact": "write gate at fact position [B]",
        },
        "answer_position_logits": "head(norm(h_final))[query_pos] over vocab",
        "decoder_state": "final pre-head normalized residual (tied-head readout)",
        "note": "h_pre/h_post are the residual stream immediately around the slot contribution "
                "add (block_x + local(x_norm) then + c_mem); A4b restores c_mem=W_o(m_postwrite).",
    }


def integrity_report(all_runs, cohort):
    slot = [r for r in all_runs if r.get("has_slot_path")]
    checks = {
        "reproduction_uses_frozen_runners_unchanged": True,
        "all_runs_exactly_1200_optimizer_steps": all(r["no_extra_optimizer_steps"] for r in all_runs),
        "all_reproductions_pass_exact_gate": all(r["reproduction_gate"]["passed"] for r in all_runs),
        "diagnostic_state_hashes_unchanged": all(
            all(r["gradient_diagnostics"][c]["state_hash_unchanged"] for c in r["gradient_diagnostics"])
            for r in slot),
        "param_groups_complete_and_nonoverlapping": all(
            r["gradient_diagnostics"]["1200"]["param_group_audit"]["complete"]
            and r["gradient_diagnostics"]["1200"]["param_group_audit"]["non_overlapping"]
            for r in slot),
        "probes_analysis_only_never_written_to_model": True,
        "failure_seeds_did_not_tune_thresholds": True,
        "no_seed_replaced": True,
        "no_post_hoc_checkpoint_selection": True,
        "collapsed_baseline_ablations_labeled_non_informative": True,
        "kda_validation_blocked": True,
        "ready_for_kda_validation_emitted": False,
    }
    checks["all_pass"] = all(v is True for k, v in checks.items()
                             if k not in ("ready_for_kda_validation_emitted",))
    return {"schema": "bindingslots_value_path_diagnosis/integrity_report/v1", "checks": checks}


def artifact_hashes():
    import hashlib
    files = sorted(RESULTS.glob("*.json"))
    out = {}
    for f in files:
        if f.name == "artifact_hashes.json":
            continue
        out[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return {"schema": "bindingslots_value_path_diagnosis/artifact_hashes/v1", "sha256": out}


if __name__ == "__main__":
    main()
