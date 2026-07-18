"""B1.9 POLE DIFF-IN-DIFF driver + freeze gate (gated; blinded; mock-tested).

4 arms, pole is the manipulated variable and W′ (a distant word) is the valence control:
  OWN_CORRECT_POLE      = W's own varṇas at W's referent-correct pole
  OWN_FLIPPED_POLE      = W's own varṇas at the OPPOSITE pole
  CONTROL_CORRECT_POLE  = distant word W′'s varṇas at W's correct pole
  CONTROL_FLIPPED_POLE  = W′'s varṇas at the OPPOSITE pole
Primary statistic (at aggregation): DiD = (OWN_CORRECT - OWN_FLIPPED) - (CONTROL_CORRECT - CONTROL_FLIPPED).
Only an EXCESS own-mapping correct-vs-flipped margin beyond the generic pole-valence effect (the control diff)
supports pole-specific varṇa resolution. A null is informative. A positive is low-level only: no ontology, no
semantic truth, no Sanskrit privilege, no GENUTILITY.

Rendering rule (corrected): each facet is rendered as the word's DIRECT inner meaning; contrastive/opposite
framing is prohibited (closes the leakage that made the first, permissive run inconclusive — see
B1_9_POLE_DID_RESULTS.md). Same experiment/representation; only the render instruction changed. A per-arm
contrastive-marker audit is reported (diagnostic only: never drops or penalizes an output).

Consonant-only canonical varṇas (Stage A′ + bridge; vowels dropped — see prereg §Vowel-omission limitation).
Anti-circularity: correct pole fixed by the frozen referent classification, which must be operator-APPROVED
(classification_approved==true) before any real run — the gate refuses otherwise. Reuses the B1.6 adapter + shared
leak matcher. NO real generation here (FakeAdapter only in tests). B1.4b′ remains NULL_RETURN_BOTTOM.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import re
from typing import Dict, List, Optional, Tuple

import run_b1_6_pilot_generation as G
import b1_6_llm_adapter as A

B1_4B_PRIME_STATUS = "NULL_RETURN_BOTTOM"
HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"

SCAFFOLD_FILE = FROZEN / "b1_9_pole_did_scaffold.json"
ITEMS_FILE = FROZEN / "b1_9_pole_did_items.json"
V2_TABLE_FILE = HERE / "track_g_varna_polarity_table_v2_named_vritti.json"
BRIDGE_FILE = FROZEN / "b1_6_phoneme_to_varna_bridge_manifest.json"
DECOMPOSER_FILE = HERE / "stage_a_prime_coverage.py"
PREREG_FILE = HERE / "B1_9_POLE_DID_PREREG.md"
PROMPT_RUBRIC_FILE = HERE / "B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md"

MODE = "b1_9_pole_did_probe"
REPRESENTATION = "B1.9_pole_did"
ATTESTATION = ("B1.9 pole diff-in-diff probe only; own vs control (distant word) varṇas at correct vs flipped "
               "pole; correct pole from the frozen referent-ontology classification; consonant-only canonical "
               "varṇas; no semantic-truth claim; no GENUTILITY terminal label; B1.4b′ remains NULL_RETURN_BOTTOM.")

ARMS = ("OWN_CORRECT_POLE", "OWN_FLIPPED_POLE", "CONTROL_CORRECT_POLE", "CONTROL_FLIPPED_POLE")
FACET_ARMS = ARMS
DID = "DiD = (OWN_CORRECT_POLE - OWN_FLIPPED_POLE) - (CONTROL_CORRECT_POLE - CONTROL_FLIPPED_POLE)"

HASH_INPUTS = {
    "prereg_sha256": PREREG_FILE, "items_sha256": ITEMS_FILE, "scaffold_sha256": SCAFFOLD_FILE,
    "v2_named_vritti_table_sha256": V2_TABLE_FILE, "bridge_manifest_sha256": BRIDGE_FILE,
    "decomposer_sha256": DECOMPOSER_FILE, "prompt_rubric_sha256": PROMPT_RUBRIC_FILE,
}
REQUIRED_DECL_FIELDS = ("artifact", "evidence_freeze_declared", "mode", "representation_version",
                        "declared_by", "declared_at_utc", "attestation", *HASH_INPUTS.keys())
BAD_MODES = {"pilot_generation", "b1_8_context_resolved_generation_probe",
             "b1_9_content_level_semantic_distance", "b1_9_generation_corrected_control_probe",
             "b1_9_pole_sensitivity_probe"}

HEADER = ("You are an interpreter using a structural lens as a heuristic scaffold - NOT as truth. Read the item "
          "in the given context. Do NOT claim this proves meaning, is true, ancient, or authoritative. Do NOT "
          "mention any system name.")
# Corrected render rule (closes the contrastive-framing leakage found in the permissive run;
# see B1_9_POLE_DID_RESULTS.md). Same experiment/representation — only the rendering instruction changed.
DIRECT_RULE = ("Render each facet as the word's direct inner meaning in this context. Do not frame any facet as "
               "the word's obstacle, opposite, contrast, antidote, what it resists, what it overcomes, what it "
               "is free from, or what it protects against.")
# Output-side contrastive-marker audit (diagnostic ONLY: never drops or penalizes an output).
CONTRASTIVE = re.compile(
    r"\b(shield(s|ed)? against|against|overcome(s|n)?|resist(s|ed|ing)?|free from|freedom from|"
    r"not\s+\w+\s+but|protect(s|ed)? against|transcend(s|ing)?|counter(s|balance|ing)?|rather than|"
    r"instead of|guard(s|ed)? against|antidote|opposite of|release from|letting go of|escape from)\b", re.I)
OUTPUT_FORMAT = ("Respond in EXACTLY this format:\n"
                 "Title: <one short phrase>\n"
                 "Interpretation: <120-180 words>\n"
                 "Practical reflection:\n- <bullet 1>\n- <bullet 2>\n"
                 "Caution: <one sentence stating the limits/uncertainty of this interpretation>")

ALLOWED_JV_KEYS = {"item_id", "target_text", "neutral_context", "blinded_output_id",
                   "generation_text", "output_format"}


def _sha_file(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def leaked(text: str) -> List[str]:
    return list(G.leaked_tokens(text))


def contrastive_markers(text: str) -> List[str]:
    """Diagnostic scan for contrastive/opposite framing. AUDIT ONLY — never used to drop or penalize an output."""
    return [m.group(0) for m in CONTRASTIVE.finditer(text or "")]


def classification_approved() -> bool:
    try:
        return json.loads(ITEMS_FILE.read_text()).get("classification_approved") is True
    except Exception:  # noqa: BLE001
        return False


def verify_freeze_gate(decl_path: pathlib.Path, expected_mode: str = MODE,
                       panel_manifest_path: Optional[pathlib.Path] = None) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if not pathlib.Path(decl_path).exists():
        return False, ["no EVIDENCE_FREEZE_DECLARED file (operator must create it)"]
    try:
        decl = json.loads(pathlib.Path(decl_path).read_text())
    except Exception as e:  # noqa: BLE001
        return False, [f"declaration not valid JSON: {e}"]
    for f in REQUIRED_DECL_FIELDS:
        if f not in decl:
            reasons.append(f"missing required field: {f}")
    if decl.get("artifact") != "b1_9_pole_did_EVIDENCE_FREEZE_DECLARED":
        reasons.append("artifact != b1_9_pole_did_EVIDENCE_FREEZE_DECLARED")
    if decl.get("evidence_freeze_declared") is not True:
        reasons.append("evidence_freeze_declared != true")
    if decl.get("mode") in BAD_MODES:
        reasons.append(f"refused: other-track mode supplied ({decl.get('mode')!r})")
    if decl.get("mode") != expected_mode:
        reasons.append(f"mode != {expected_mode} (got {decl.get('mode')!r})")
    if decl.get("representation_version") != REPRESENTATION:
        reasons.append(f"representation_version != {REPRESENTATION} (got {decl.get('representation_version')!r})")
    if decl.get("attestation") != ATTESTATION:
        reasons.append("attestation text mismatch")
    if not classification_approved():
        reasons.append("referent classification NOT approved (set classification_approved=true after sign-off "
                       "BEFORE any generation — anti-circularity requirement)")
    if reasons:
        return False, reasons
    for field, path in HASH_INPUTS.items():
        if not path.exists():
            reasons.append(f"frozen input missing: {path.name}")
            continue
        if decl.get(field) != _sha_file(path):
            reasons.append(f"{field} mismatch (wrong-track/representation declaration is refused)")
    if panel_manifest_path is not None:
        if "model_panel_manifest_sha256" not in decl:
            reasons.append("panel mode: missing model_panel_manifest_sha256")
        elif not pathlib.Path(panel_manifest_path).exists():
            reasons.append("panel manifest file missing")
        elif decl.get("model_panel_manifest_sha256") != _sha_file(pathlib.Path(panel_manifest_path)):
            reasons.append("model_panel_manifest_sha256 mismatch")
    return (not reasons), reasons


def _facet_bullets(facets: List[Dict]) -> str:
    out, seen = [], set()
    for f in facets:
        t = f["text"]
        if t not in seen:
            seen.add(t); out.append(f"- {t}")
    return "\n".join(out) or "- (no facet)"


def render_prompt(arm: str, item: Dict) -> str:
    if arm not in FACET_ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    return (f"{HEADER}\nItem: {item['TARGET_TEXT']}\nContext: {item['CONTEXT_TEXT']}\n"
            f"Emphasize the {item['PLANE']} plane. {DIRECT_RULE}\n"
            f"{_facet_bullets(item['ARM_FACETS'][arm])}\n\n{OUTPUT_FORMAT}")


def load_scaffold() -> Dict:
    return json.loads(SCAFFOLD_FILE.read_text())


def build_records(scaffold: Dict, limit_items: Optional[int] = None) -> List[Dict]:
    items = scaffold["items"][:limit_items] if limit_items else scaffold["items"]
    recs, n = [], 0
    for it in items:
        for arm in ARMS:
            n += 1
            recs.append({
                "item_id": it["item_id"], "target_text": it["TARGET_TEXT"], "context_text": it["CONTEXT_TEXT"],
                "referent_type": it["REFERENT_TYPE"], "arm": arm, "plane": it["PLANE"],
                "correct_pole": it["CORRECT_POLE"], "flipped_pole": it["FLIPPED_POLE"],
                "wprime_item_id": it["wprime_item_id"], "blinded_output_id": f"G{n:04d}",
                "prompt": render_prompt(arm, it),
            })
    return recs


def make_judge_visible(rec: Dict, text: str) -> Dict:
    pkg = {"item_id": rec["item_id"], "target_text": rec["target_text"],
           "neutral_context": rec["context_text"], "blinded_output_id": rec["blinded_output_id"],
           "generation_text": text, "output_format": "Title/Interpretation(120-180w)/2 bullets/Caution"}
    bad = {"arm", "true_arm", "correct_pole", "flipped_pole", "wprime_item_id"} & set(pkg.keys())
    if bad:
        raise ValueError(f"INVALID_BLINDING: leaked keys {sorted(bad)}")
    lk = leaked(text)
    if lk:
        raise ValueError(f"INVALID_LEAKAGE: method/arm tokens {lk} in generation_text")
    return pkg


def make_hidden(rec: Dict, gen_code: Optional[str], gen_id: Optional[str]) -> Dict:
    return {"blinded_output_id": rec["blinded_output_id"], "true_arm": rec["arm"],
            "generator_code": gen_code, "generator_id": gen_id, "item_id": rec["item_id"],
            "referent_type": rec["referent_type"], "plane": rec["plane"], "correct_pole": rec["correct_pole"],
            "flipped_pole": rec["flipped_pole"], "wprime_item_id": rec["wprime_item_id"],
            "contrastive_markers": rec.get("contrastive_markers", []),
            "representation_version": REPRESENTATION}


def assert_blind(judge_visible: List[Dict]) -> None:
    for i, pkg in enumerate(judge_visible):
        extra = set(pkg.keys()) - ALLOWED_JV_KEYS
        if extra:
            raise ValueError(f"INVALID_BLINDING [{i}]: unexpected keys {sorted(extra)}")
        lk = leaked(str(pkg.get("generation_text", "")))
        if lk:
            raise ValueError(f"INVALID_LEAKAGE [{i}]: {lk}")


def _mock_text(rec: Dict) -> str:
    h = hashlib.sha256(rec["prompt"].encode()).hexdigest()[:8]
    filler = " ".join(["a measured reading unfolds here in plain words"] * 16)
    return (f"Title: reading {h}\nInterpretation: {filler} and it settles into a calm close.\n"
            f"Practical reflection:\n- consider it slowly\n- hold it lightly\n"
            f"Caution: This is one limited, non-authoritative reading and may not fit every context.")


def _emit(mock, adapter, settings, validate_real):
    if mock:
        return lambda rec: (_mock_text(rec), "mock", []), {"backend": "mock", "model_id": "MOCK_ONLY"}
    from b1_6_llm_adapter import generate_with_retry
    def emit(rec):
        return generate_with_retry(adapter, rec["prompt"], settings, validate=validate_real)
    return emit, {**settings.metadata(), "backend": getattr(adapter, "backend", "custom")}


def run_part(mock: bool = False, adapter=None, settings=None, decl_path: Optional[pathlib.Path] = None,
             panel_manifest_path: Optional[pathlib.Path] = None, gen_code: Optional[str] = None,
             gen_id: Optional[str] = None, limit_items: Optional[int] = None, validate_real: bool = True,
             out_dir: Optional[pathlib.Path] = None, write: bool = False) -> Dict:
    if not mock:
        if decl_path is None:
            raise PermissionError("real run requires a B1.9 pole-DiD evidence-freeze declaration path")
        ok, reasons = verify_freeze_gate(pathlib.Path(decl_path), panel_manifest_path=panel_manifest_path)
        if not ok:
            raise PermissionError("EVIDENCE_FREEZE gate refused: " + "; ".join(reasons))
    settings = settings or A.GenerationSettings()
    gen_id = gen_id or getattr(settings, "model_id", "MOCK_ONLY")
    records = build_records(load_scaffold(), limit_items=limit_items)
    emit, gen_meta = _emit(mock, adapter, settings, validate_real)

    outputs, failures = [], []
    for rec in records:
        text, status, rs = emit(rec)
        lk = leaked(text) if (status in ("ok", "mock") and text is not None) else []
        if lk:
            status, rs = "blindness_leak", [f"tokens: {lk}"]
        if status in ("ok", "mock") and text is not None and not lk:
            outputs.append({**rec, "generation_text": text, "generator_code": gen_code, "generator_id": gen_id,
                            "contrastive_markers": contrastive_markers(text)})   # AUDIT only; never dropped
        else:
            failures.append({"blinded_output_id": rec["blinded_output_id"], "item_id": rec["item_id"],
                             "arm": rec["arm"], "status": status, "reasons": rs})
    part = {
        "artifact_type": "b1_9_pole_did_part", "mode": "MOCK" if mock else "REAL",
        "representation_version": REPRESENTATION, "generator_code": gen_code, "generator_id": gen_id,
        "arms": list(ARMS), "primary_statistic": DID, "n_records": len(records),
        "n_outputs": len(outputs), "n_failures": len(failures), "failures": failures, "generator_meta": gen_meta,
        "b1_4b_prime_status": B1_4B_PRIME_STATUS, "classification_approved": classification_approved(),
        "input_hashes": {k: _sha_file(v) for k, v in HASH_INPUTS.items()},
        "declaration_sha256": _sha_file(pathlib.Path(decl_path)) if (decl_path and not mock) else None,
        "outputs": outputs,
    }
    if write and out_dir:
        out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "b1_9_pole_did_part.json").write_text(json.dumps(part, ensure_ascii=False, indent=2))
    return part


def load_part(path: pathlib.Path) -> Dict:
    p = pathlib.Path(path)
    if p.is_dir():
        p = p / "b1_9_pole_did_part.json"
    return json.loads(p.read_text())


def _contrastive_audit(outputs: List[Dict]) -> Dict:
    """Per-arm contrastive-framing rate. Diagnostic ONLY — no output dropped, no score penalized."""
    by = {a: [0, 0] for a in ARMS}
    for o in outputs:
        c = by.get(o["arm"])
        if c is None:
            continue
        c[1] += 1; c[0] += 1 if o.get("contrastive_markers") else 0
    return {a: {"contrastive": n, "total": t, "rate": (round(n / t, 3) if t else None)} for a, (n, t) in by.items()}


def merge_parts(parts: List[Dict], out_dir: Optional[pathlib.Path] = None, write: bool = False,
                reblind_seed: int = 20260712) -> Dict:
    reasons = []
    if {p.get("representation_version") for p in parts} != {REPRESENTATION}:
        reasons.append("representation mismatch across parts")
    codes = [p.get("generator_code") for p in parts]
    if len(set(codes)) != len(codes):
        reasons.append(f"duplicate generator_code across parts: {codes}")
    if len({json.dumps(p.get("input_hashes"), sort_keys=True) for p in parts}) != 1:
        reasons.append("parts disagree on frozen input hashes")
    if reasons:
        return {"label": "B1_9_POLE_DID_BLOCKED_ARM_RENDERING", "reasons": reasons}

    merged = [o for p in parts for o in p["outputs"]]
    merged.sort(key=lambda o: hashlib.sha256(
        f"{reblind_seed}|{o['item_id']}|{o['arm']}|{o['generator_code']}".encode()).hexdigest())
    judge_visible, hidden = [], []
    for i, o in enumerate(merged, 1):
        rec = {**o, "blinded_output_id": f"F{i:04d}"}
        judge_visible.append(make_judge_visible(rec, o["generation_text"]))
        hidden.append(make_hidden(rec, o["generator_code"], o["generator_id"]))
    assert_blind(judge_visible)

    manifest = {
        "artifact_type": "b1_9_pole_did_run_manifest", "mode": parts[0].get("mode"),
        "representation_version": REPRESENTATION, "run_label": "B1_9_POLE_DID_PROBE",
        "arms": list(ARMS), "primary_statistic": DID, "n_generators": len(parts),
        "generator_codes": {p["generator_code"]: p["generator_id"] for p in parts},
        "n_targets": len({o["item_id"] for o in merged}), "n_outputs": len(merged),
        "expected_full": 24 * len(ARMS) * len(parts),
        "per_generator_counts": {p["generator_code"]: p["n_outputs"] for p in parts},
        "contrastive_audit": _contrastive_audit(merged),            # diagnostic only; no drop / no penalty
        "reblind_seed": reblind_seed, "input_hashes": parts[0].get("input_hashes"),
        "classification_approved": parts[0].get("classification_approved"),
        "declaration_sha256": parts[0].get("declaration_sha256"),
        "judging_performed": False, "unblinded": False, "b1_4b_prime_status": B1_4B_PRIME_STATUS,
        "note": "4-arm diff-in-diff; pole is the manipulated variable, W′ (distant word) is the valence control. "
                "Corrected direct-meaning render rule (no contrastive framing); contrastive audit is diagnostic "
                "only (no drop/penalty). Judge-visible re-blinded. No judging. No GENUTILITY_*.",
    }
    if write and out_dir:
        out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "panel_judge_visible_outputs.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in judge_visible) + "\n")
        (out_dir / "panel_hidden_arm_generator_metadata.json").write_text(json.dumps(hidden, ensure_ascii=False, indent=2))
        (out_dir / "panel_run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return {"label": "B1_9_POLE_DID_DRIVER_READY_MOCK_TESTED", "manifest": manifest,
            "judge_visible": judge_visible, "hidden": hidden}


def _adapter_from_args(args):
    return A.build_adapter(A.GenerationSettings(
        model_id=args.model_id, backend=args.backend, base_url=args.base_url,
        revision=args.revision, temperature=args.temperature, max_tokens=args.max_tokens))


def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.9 pole diff-in-diff driver (gated; mock-tested).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("part")
    rp.add_argument("--mock", action="store_true")
    rp.add_argument("--decl"); rp.add_argument("--panel-manifest")
    rp.add_argument("--gen-code", default="M1"); rp.add_argument("--limit-items", type=int)
    rp.add_argument("--backend", default="transformers"); rp.add_argument("--model-id", default="MOCK_ONLY")
    rp.add_argument("--base-url"); rp.add_argument("--revision")
    rp.add_argument("--temperature", type=float, default=0.7); rp.add_argument("--max-tokens", type=int, default=600)
    rp.add_argument("--out", required=True)
    mp = sub.add_parser("merge")
    mp.add_argument("--parts", nargs="+", required=True); mp.add_argument("--out", required=True)
    mp.add_argument("--reblind-seed", type=int, default=20260712)

    args = ap.parse_args(argv)
    if args.cmd == "part":
        adapter = None if args.mock else _adapter_from_args(args)
        settings = None if args.mock else adapter.s
        part = run_part(mock=args.mock, adapter=adapter, settings=settings,
                        decl_path=pathlib.Path(args.decl) if args.decl else None,
                        panel_manifest_path=pathlib.Path(args.panel_manifest) if args.panel_manifest else None,
                        gen_code=args.gen_code, gen_id=args.model_id, limit_items=args.limit_items,
                        out_dir=pathlib.Path(args.out), write=True)
        print(json.dumps({"generator_code": part["generator_code"], "n_outputs": part["n_outputs"],
                          "n_failures": part["n_failures"], "classification_approved": part["classification_approved"]},
                         indent=2))
        return
    if args.cmd == "merge":
        parts = [load_part(pathlib.Path(p)) for p in args.parts]
        res = merge_parts(parts, out_dir=pathlib.Path(args.out), write=True, reblind_seed=args.reblind_seed)
        if res["label"] != "B1_9_POLE_DID_DRIVER_READY_MOCK_TESTED":
            raise SystemExit(f"MERGE REFUSED ({res['label']}): {res.get('reasons')}")
        print(json.dumps(res["manifest"], indent=2))


if __name__ == "__main__":
    main()
