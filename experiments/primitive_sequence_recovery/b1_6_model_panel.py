"""B1.6 multi-model panel orchestration (modeled on the B1.1 dual-generator + 3-judge panel).

Iterates a panel of GENERATOR models over the frozen scaffolds via the gated driver, then RE-BLINDS the merged
pool so neither the arm nor the generator is inferable from a judge-visible id (generator identity lives ONLY in
hidden metadata). Also validates the panel and flags any generator/judge same-model or same-family conflict.

Performs NO real generation and NO judging: adapters are operator-supplied (real) or FakeAdapter (tests). Blind
judging is a separate, separately-gated step. B1.4b' remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
"""
from __future__ import annotations
import hashlib
import json
import pathlib
from typing import Callable, Dict, List, Optional, Tuple

import run_b1_6_pilot_generation as drv

B1_4B_PRIME_STATUS = "NULL_RETURN_BOTTOM"

# Panel modeled on B1.1 (values FROZEN BY OPERATOR at run time; ids here are the B1.1 reference set).
B1_1_REFERENCE_PANEL = {
    "generator_models": [
        {"id": "mistralai/Mistral-7B-Instruct-v0.3", "family": "Mistral", "revision": "<operator-frozen>"},
        {"id": "Qwen/Qwen2.5-7B-Instruct", "family": "Qwen", "revision": "<operator-frozen>"},
    ],
    "judge_models": [
        {"id": "meta-llama/Llama-3.1-8B-Instruct", "family": "Llama", "revision": "<operator-frozen>"},
        {"id": "meta-llama/Meta-Llama-3-8B-Instruct", "family": "Llama", "revision": "<operator-frozen>"},
        {"id": "google/gemma-2-9b-it", "family": "Gemma", "revision": "<operator-frozen>"},
    ],
}


def _sha_obj(o) -> str:
    return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# --------------------------------------------------------------------------------------
# Panel validation + conflict detection
# --------------------------------------------------------------------------------------
def validate_panel(panel: Dict) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    gens = panel.get("generator_models") or []
    judges = panel.get("judge_models") or []
    if not gens:
        reasons.append("no generator_models")
    if not judges:
        reasons.append("no judge_models")
    for g in gens:
        if not g.get("id") or not g.get("family"):
            reasons.append(f"generator missing id/family: {g}")
    for j in judges:
        if not j.get("id") or not j.get("family"):
            reasons.append(f"judge missing id/family: {j}")
    return (not reasons), reasons


def detect_same_model_conflicts(panel: Dict) -> List[Dict]:
    """A model must not judge its own generated outputs; judge family should differ from generator family.
    Returns a list of conflicts (empty = clean)."""
    gens = panel.get("generator_models") or []
    judges = panel.get("judge_models") or []
    gen_ids = {g.get("id") for g in gens}
    gen_fams = {g.get("family") for g in gens}
    conflicts: List[Dict] = []
    for j in judges:
        if j.get("id") in gen_ids:
            conflicts.append({"type": "SAME_MODEL", "judge": j.get("id"),
                              "detail": "judge id is also a generator id — must not judge its own outputs"})
        elif j.get("family") in gen_fams:
            conflicts.append({"type": "SAME_FAMILY", "judge": j.get("id"), "family": j.get("family"),
                              "detail": "judge family matches a generator family — record; exploratory only"})
    return conflicts


# --------------------------------------------------------------------------------------
# Shared re-blind (deterministic order by hash so neither arm nor generator is inferable)
# --------------------------------------------------------------------------------------
def _reblind(merged: List[Dict], reblind_seed: int) -> Tuple[List[Dict], List[Dict]]:
    ordered = sorted(merged, key=lambda r: hashlib.sha256(
        f"{reblind_seed}|{r['item_id']}|{r['true_arm']}|{r['generator_code']}".encode()).hexdigest())
    judge_visible: List[Dict] = []
    hidden_meta: List[Dict] = []
    for k, r in enumerate(ordered):
        fid = f"F{k+1:04d}"
        pkg = {"item_id": r["item_id"], "target_text": r["target_text"],
               "neutral_context": r["neutral_context"], "blinded_output_id": fid,
               "generation_text": r["generation_text"],
               "output_format": "Title/Interpretation(120-180w)/2 bullets/Caution"}
        drv.assert_blind(pkg)                       # raises on any arm/generator/system leak
        judge_visible.append(pkg)
        hidden_meta.append({"blinded_output_id": fid, "true_arm": r["true_arm"],
                            "generator_code": r["generator_code"], "generator_id": r["generator_id"],
                            "item_id": r["item_id"]})
    return judge_visible, hidden_meta


def _outputs_from_run(res: Dict, code: str, gen_id: str) -> List[Dict]:
    """Join a driver run's judge_visible + hidden_meta into merge tuples (hidden side; carries generator id)."""
    jv_by_id = {p["blinded_output_id"]: p for p in res["judge_visible"]}
    out = []
    for hm in res["hidden_meta"]:
        p = jv_by_id[hm["blinded_output_id"]]
        out.append({"item_id": hm["item_id"], "target_text": p["target_text"],
                    "neutral_context": p["neutral_context"], "generation_text": p["generation_text"],
                    "true_arm": hm["true_arm"], "generator_code": code, "generator_id": gen_id})
    return out


# --------------------------------------------------------------------------------------
# Orchestrated generation across the generator panel (re-blinded)
# --------------------------------------------------------------------------------------
def run_panel(panel: Dict,
              adapter_factory: Optional[Callable[[Dict], object]] = None,
              mock: bool = False,
              mode: str = drv.EXPLORATORY_MODE,
              limit_items: Optional[int] = 10,
              decl_path: pathlib.Path = drv.DECL_FILE,
              out_dir: pathlib.Path = None,
              write: bool = False,
              reblind_seed: int = 20260708,
              representation: str = drv.DEFAULT_REPRESENTATION) -> Dict:
    """Run each generator over the (subset) scaffolds via the gated driver, then re-blind the merged pool.

    adapter_factory(generator_entry) -> adapter (FakeAdapter in tests; a real adapter on a model host).
    In mock mode the driver's deterministic placeholder is used and adapter_factory is ignored.
    """
    ok, reasons = validate_panel(panel)
    if not ok:
        raise ValueError(f"invalid panel: {reasons}")
    conflicts = detect_same_model_conflicts(panel)

    merged: List[Dict] = []      # hidden tuples across all generators (pre-re-blind)
    per_generator_counts: Dict[str, int] = {}
    for i, gen in enumerate(panel["generator_models"]):
        code = f"M{i+1}"          # opaque generator code; real id kept in the panel manifest, not judge-visible
        adapter = None
        if not mock:
            if adapter_factory is None:
                raise ValueError("real panel run requires adapter_factory(generator_entry)->adapter")
            adapter = adapter_factory(gen)
        res = drv.run(mock=mock, adapter=adapter, mode=mode, limit_items=limit_items,
                      decl_path=decl_path, out_dir=(out_dir / code) if (out_dir and write) else drv.RUN_OUT,
                      write=False, gen_code=code, representation=representation)
        part = _outputs_from_run(res, code, gen["id"])
        merged.extend(part)
        per_generator_counts[code] = len(part)

    judge_visible, hidden_meta = _reblind(merged, reblind_seed)

    panel_manifest = {
        "artifact_type": "b1_6_model_panel_manifest",
        "status": "PANEL_MANIFEST_NOT_A_FREEZE",
        "run_label": drv.EXPLORATORY_LABEL if mode == drv.EXPLORATORY_MODE else "B1_6_PILOT_FULL_GENERATION",
        "representation_version": representation,
        "mock": mock,
        "judging_performed": False,
        "generator_models": panel["generator_models"],
        "judge_models": panel["judge_models"],
        "generator_codes": {f"M{i+1}": g["id"] for i, g in enumerate(panel["generator_models"])},
        "same_model_conflicts": conflicts,
        "n_generators": len(panel["generator_models"]),
        "n_judges": len(panel["judge_models"]),
        "n_arms": len(drv.ACTIVE_ARMS),
        "n_targets": limit_items if limit_items else 24,
        "expected_outputs": (limit_items if limit_items else 24) * len(drv.ACTIVE_ARMS)
        * len(panel["generator_models"]),
        "n_outputs": len(judge_visible),
        "per_generator_counts": per_generator_counts,
        "reblind_seed": reblind_seed,
        "panel_sha256": _sha_obj({"g": panel["generator_models"], "j": panel["judge_models"]}),
        "b1_4b_prime_status": B1_4B_PRIME_STATUS,
        "note": "Generator identity lives ONLY in hidden metadata; judge-visible ids are re-blinded. No judging. "
                "No GENUTILITY_* label. Exploratory panel run cannot emit a terminal verdict.",
    }

    if write and out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "panel_judge_visible_outputs.jsonl").write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in judge_visible) + "\n")
        (out_dir / "panel_hidden_arm_generator_metadata.json").write_text(
            json.dumps(hidden_meta, ensure_ascii=False, indent=2))
        (out_dir / "panel_run_manifest.json").write_text(json.dumps(panel_manifest, ensure_ascii=False, indent=2))

    return {"label": "B1_6_MULTI_MODEL_ORCHESTRATION_CODE_READY_MOCK_TESTED",
            "panel_valid": True, "conflicts": conflicts, "panel_manifest": panel_manifest,
            "judge_visible": judge_visible, "hidden_meta": hidden_meta}


# --------------------------------------------------------------------------------------
# Sequential single-GPU path: run one generator part at a time, then merge + re-blind.
# --------------------------------------------------------------------------------------
def run_single_generator_panel_part(panel: Dict, gen_index: int,
                                    adapter_factory: Optional[Callable[[Dict], object]] = None,
                                    mock: bool = False, mode: str = drv.EXPLORATORY_MODE,
                                    limit_items: Optional[int] = 10, decl_path: pathlib.Path = drv.DECL_FILE,
                                    out_dir: pathlib.Path = None, write: bool = False,
                                    representation: str = drv.DEFAULT_REPRESENTATION) -> Dict:
    """Run ONE generator (panel.generator_models[gen_index]) over the subset via the gated driver, and emit a
    partial package (hidden side; carries generator identity) for a later merge. No re-blinding yet."""
    ok, reasons = validate_panel(panel)
    if not ok:
        raise ValueError(f"invalid panel: {reasons}")
    if gen_index < 0 or gen_index >= len(panel["generator_models"]):
        raise IndexError(f"gen_index {gen_index} out of range for {len(panel['generator_models'])} generators")
    gen = panel["generator_models"][gen_index]
    code = f"M{gen_index + 1}"
    adapter = None
    settings = None
    if not mock:
        if adapter_factory is None:
            raise ValueError("real part run requires adapter_factory(generator_entry)->adapter")
        adapter = adapter_factory(gen)
        # Thread the panel's real generation params into the driver: adapter.generate() uses the settings
        # the driver passes, so without this the panel's max_tokens/temperature/seed are silently ignored.
        from b1_6_llm_adapter import GenerationSettings
        settings = GenerationSettings(
            model_id=gen["id"], backend=panel.get("backend", "transformers"),
            revision=gen.get("revision") if panel.get("backend") == "transformers" else None,
            base_url=gen.get("endpoint"),
            temperature=panel.get("temperature", 0.7), max_tokens=panel.get("max_tokens", 600),
            seed=panel.get("seed", 1101))
    res = drv.run(mock=mock, adapter=adapter, settings=settings, mode=mode, limit_items=limit_items,
                  decl_path=decl_path, write=False, gen_code=code, representation=representation)
    m = res["manifest"]
    part = {
        "artifact_type": "b1_6_panel_part",
        "generator_code": code, "generator_id": gen["id"],
        "mode": m["declared_freeze_mode"], "representation_version": m["representation_version"],
        "item_ids": m["item_ids"], "arms": m["arms"],
        "scaffold_input_hashes": m["frozen_input_hashes"], "declaration_sha256": m["declaration_sha256"],
        "n_outputs": m["n_success"], "judging_performed": False,
        "b1_4b_prime_status": B1_4B_PRIME_STATUS,
        "outputs": _outputs_from_run(res, code, gen["id"]),   # hidden side (generator identity present)
    }
    if write and out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "panel_part.json").write_text(json.dumps(part, ensure_ascii=False, indent=2))
    return part


def load_part(path: pathlib.Path) -> Dict:
    p = pathlib.Path(path)
    if p.is_dir():
        p = p / "panel_part.json"
    return json.loads(p.read_text())


def merge_panel_parts(parts: List[Dict], out_dir: pathlib.Path = None, write: bool = False,
                      reblind_seed: int = 20260708) -> Dict:
    """Merge >=2 generator parts and re-blind exactly like run_panel. Refuses on any cross-part mismatch
    (mode / representation / arms / scaffold hashes / declaration hash / target subset / duplicate generator)."""
    parts = [load_part(p) if isinstance(p, (str, pathlib.Path)) else p for p in parts]
    reasons: List[str] = []
    if len(parts) < 2:
        return {"label": "B1_6_V2_SEQUENTIAL_PANEL_GENERATION_BLOCKED_MERGE",
                "reasons": ["need >= 2 generator parts to merge"]}
    ref = parts[0]
    for p in parts[1:]:
        for k in ("mode", "representation_version", "arms", "scaffold_input_hashes", "declaration_sha256"):
            if p.get(k) != ref.get(k):
                reasons.append(f"{k} mismatch across parts: {ref.get(k)!r} != {p.get(k)!r}")
        if sorted(p.get("item_ids", [])) != sorted(ref.get("item_ids", [])):
            reasons.append("target subset (item_ids) mismatch across parts")
    codes = [p["generator_code"] for p in parts]
    if len(set(codes)) != len(codes):
        reasons.append(f"duplicate generator_code across parts: {codes}")
    if reasons:
        return {"label": "B1_6_V2_SEQUENTIAL_PANEL_GENERATION_BLOCKED_MERGE", "reasons": reasons}

    merged: List[Dict] = []
    per_generator_counts: Dict[str, int] = {}
    for p in parts:
        merged.extend(p["outputs"])
        per_generator_counts[p["generator_code"]] = len(p["outputs"])
    judge_visible, hidden_meta = _reblind(merged, reblind_seed)

    manifest = {
        "artifact_type": "b1_6_model_panel_manifest",
        "status": "PANEL_MANIFEST_NOT_A_FREEZE",
        "orchestration": "SEQUENTIAL_MERGE",
        "run_label": drv.EXPLORATORY_LABEL if ref["mode"] == drv.EXPLORATORY_MODE else "B1_6_PILOT_FULL_GENERATION",
        "representation_version": ref["representation_version"],
        "mode": ref["mode"], "judging_performed": False,
        "generator_codes": {p["generator_code"]: p["generator_id"] for p in parts},
        "n_generators": len(parts), "n_arms": len(ref.get("arms", [])),
        "n_targets": len(ref.get("item_ids", [])),
        "expected_outputs": len(ref.get("item_ids", [])) * len(ref.get("arms", [])) * len(parts),
        "n_outputs": len(judge_visible), "per_generator_counts": per_generator_counts,
        "reblind_seed": reblind_seed,
        "scaffold_input_hashes": ref["scaffold_input_hashes"], "declaration_sha256": ref["declaration_sha256"],
        "b1_4b_prime_status": B1_4B_PRIME_STATUS,
        "note": "Sequential single-GPU merge; identical re-blind to the simultaneous panel (same seed => same "
                "final ids). Generator identity ONLY in hidden metadata. No judging. No GENUTILITY_* label.",
    }
    if write and out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "panel_judge_visible_outputs.jsonl").write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in judge_visible) + "\n")
        (out_dir / "panel_hidden_arm_generator_metadata.json").write_text(
            json.dumps(hidden_meta, ensure_ascii=False, indent=2))
        (out_dir / "panel_run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

    return {"label": "B1_6_V2_SEQUENTIAL_PANEL_GENERATION_READY_MOCK_TESTED",
            "panel_manifest": manifest, "judge_visible": judge_visible, "hidden_meta": hidden_meta}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="B1.6 multi-model panel orchestration (gated; mock-tested).")
    ap.add_argument("--model-panel-manifest", dest="panel", help="path to a JSON panel manifest")
    ap.add_argument("--mock", action="store_true", help="deterministic placeholder text (plumbing only)")
    ap.add_argument("--mode", default=drv.EXPLORATORY_MODE, choices=list(drv.VALID_MODES))
    ap.add_argument("--limit-items", type=int, default=10)
    ap.add_argument("--representation-version", default=drv.DEFAULT_REPRESENTATION,
                    choices=list(drv.REPRESENTATIONS))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    panel = json.loads(pathlib.Path(args.panel).read_text()) if args.panel else B1_1_REFERENCE_PANEL
    if not args.mock:
        raise SystemExit("Real panel generation requires per-generator model adapters on a model-access host "
                         "(adapter_factory) + a matching operator declaration; not runnable from CLI. "
                         "Use --mock for plumbing.")
    res = run_panel(panel, mock=True, mode=args.mode, limit_items=args.limit_items,
                    representation=args.representation_version,
                    out_dir=pathlib.Path(args.out) if args.out else None, write=bool(args.out))
    print(json.dumps(res["panel_manifest"], indent=2))


if __name__ == "__main__":
    main()
