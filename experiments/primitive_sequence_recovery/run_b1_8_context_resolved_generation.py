"""B1.8 context-resolved KCPR Layer-1 generation driver + freeze gate (gated; blinded; mock-tested).

Renders the 7 B1.8 arms from the frozen selected-pole scaffolds, gates real generation behind a B1.8
evidence-freeze declaration, blinds outputs, and (via part/merge) re-blinds a two-generator package. Reuses the
B1.6 adapter (`b1_6_llm_adapter`) and the shared whole-word leak matcher. NO real generation here (FakeAdapter
only in tests); real generation runs on an operator model host. No judging, no ratings freeze, no unblinding, no
`GENUTILITY_*`. B1.4b' remains NULL_RETURN_BOTTOM. Structure, not validated meaning.

Arms: KCPR_SELECTED_POLE, SCRAMBLED_SELECTED_POLE, UNRESOLVED_BOTH_POLES, SCRAMBLED_UNRESOLVED,
PLAIN_PROMPT_BASELINE, GENERIC_STRUCTURED_PROMPT_BASELINE, SEMANTIC_LLM_BASELINE.
Primary contrast: KCPR_SELECTED_POLE vs SCRAMBLED_SELECTED_POLE.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
from typing import Dict, List, Optional, Tuple

import run_b1_6_pilot_generation as G          # shared whole-word method/arm leak matcher
import b1_6_llm_adapter as A

B1_4B_PRIME_STATUS = "NULL_RETURN_BOTTOM"
HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"

TARGETS_FILE = FROZEN / "b1_8_context_resolved_targets_scaffolds.json"
RANDOMIZED_FILE = FROZEN / "b1_8_context_resolved_randomized_control_manifest.json"
SCAFFOLD_MANIFEST_FILE = FROZEN / "b1_8_context_resolved_scaffold_manifest.json"
PREREG_FILE = HERE / "B1_8_CONTEXT_RESOLVED_KCPR_LAYER1_PREREG.md"
RULEBOOK_FILE = HERE / "B1_8_KCPR_LAYER1_RESOLVER_RULEBOOK.md"
RUNBOOK_FILE = HERE / "B1_8_CONTEXT_RESOLVED_GENERATION_RUNBOOK.md"
V2_TABLE_FILE = HERE / "track_g_varna_polarity_table_v2_named_vritti.json"
PROMPT_RUBRIC_FILE = HERE / "B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md"

MODE = "b1_8_context_resolved_generation_probe"
REPRESENTATION = "B1.8_context_resolved_layer1"
ATTESTATION = ("B1.8 context-resolved KCPR Layer-1 generation probe only; no judging; no semantic truth claim; "
               "no GENUTILITY terminal label; B1.4b′ remains NULL_RETURN_BOTTOM.")

ARMS = ("KCPR_SELECTED_POLE", "SCRAMBLED_SELECTED_POLE", "UNRESOLVED_BOTH_POLES", "SCRAMBLED_UNRESOLVED",
        "PLAIN_PROMPT_BASELINE", "GENERIC_STRUCTURED_PROMPT_BASELINE", "SEMANTIC_LLM_BASELINE")

# hash field -> frozen input file (gate verifies each; a B1.6-v2 declaration fails on these B1.8-specific hashes)
HASH_INPUTS = {
    "prereg_sha256": PREREG_FILE, "resolver_rulebook_sha256": RULEBOOK_FILE,
    "target_scaffolds_sha256": TARGETS_FILE, "randomized_control_sha256": RANDOMIZED_FILE,
    "scaffold_manifest_sha256": SCAFFOLD_MANIFEST_FILE, "generation_runbook_sha256": RUNBOOK_FILE,
    "v2_named_vritti_table_sha256": V2_TABLE_FILE, "prompt_rubric_sha256": PROMPT_RUBRIC_FILE,
}
REQUIRED_DECL_FIELDS = ("artifact", "evidence_freeze_declared", "mode", "representation_version",
                        "declared_by", "declared_at_utc", "attestation", *HASH_INPUTS.keys())

HEADER = ("You are an interpreter using a structural lens as a heuristic scaffold - NOT as truth. Read the item "
          "in the given context. Do NOT claim this proves meaning, is true, ancient, or authoritative. Do NOT "
          "mention any system name.")
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
    """Blinding filter: ONLY hard method/arm identifiers (varna/varṇa/KCPR/SYMBOLU/arm labels), whole-word.
    Deliberately does NOT filter general Sanskrit content words (dharma/sattva/mokṣa): those occur in the
    authentic pole texts but not the scrambled ones, so filtering them would cause differential attrition and
    bias the KCPR_SELECTED_POLE vs SCRAMBLED_SELECTED_POLE contrast."""
    return list(G.leaked_tokens(text))


# --------------------------------------------------------------------------------------
# Freeze gate
# --------------------------------------------------------------------------------------
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
    if decl.get("artifact") != "b1_8_context_resolved_EVIDENCE_FREEZE_DECLARED":
        reasons.append("artifact != b1_8_context_resolved_EVIDENCE_FREEZE_DECLARED")
    if decl.get("evidence_freeze_declared") is not True:
        reasons.append("evidence_freeze_declared != true")
    if decl.get("mode") != expected_mode:
        reasons.append(f"mode != {expected_mode} (got {decl.get('mode')!r})")
    if decl.get("representation_version") != REPRESENTATION:
        reasons.append(f"representation_version != {REPRESENTATION} (got {decl.get('representation_version')!r}); "
                       "a v1 / B1.6-v2 declaration cannot authorize a B1.8 run")
    if decl.get("attestation") != ATTESTATION:
        reasons.append("attestation text mismatch")
    if reasons:
        return False, reasons
    for field, path in HASH_INPUTS.items():
        if not path.exists():
            reasons.append(f"frozen input missing: {path.name}")
            continue
        if decl.get(field) != _sha_file(path):
            reasons.append(f"{field} mismatch (declared {decl.get(field)!r} != actual {_sha_file(path)}); "
                           "wrong-track/representation declaration is refused")
    if panel_manifest_path is not None:
        if "model_panel_manifest_sha256" not in decl:
            reasons.append("panel mode: missing model_panel_manifest_sha256")
        elif not pathlib.Path(panel_manifest_path).exists():
            reasons.append("panel manifest file missing")
        elif decl.get("model_panel_manifest_sha256") != _sha_file(pathlib.Path(panel_manifest_path)):
            reasons.append("model_panel_manifest_sha256 mismatch")
    return (not reasons), reasons


# --------------------------------------------------------------------------------------
# Prompt rendering (facets rendered WITHOUT varṇa keys to limit echo of method tokens)
# --------------------------------------------------------------------------------------
def _selected_bullets(frame: Dict) -> str:
    out, seen = [], set()
    for f in frame.values():
        t = f["text"]
        if t not in seen:
            seen.add(t); out.append(f"- {t}")
    return "\n".join(out) or "- (no facet)"


def _both_bullets(frame: Dict) -> str:
    out, seen = [], set()
    for f in frame.values():
        pair = (f["worldly_binding_distortion"], f["spiritual_liberating_reading"])
        if pair not in seen:
            seen.add(pair); out.append(f"- {pair[0]}  /  {pair[1]}")
    return "\n".join(out) or "- (no facet)"


def render_prompt(arm: str, t: Dict, r: Optional[Dict]) -> str:
    plane = t["SELECTED_PLANE"]
    base = f"{HEADER}\nItem: {t['TARGET_TEXT']}\nContext: {t['CONTEXT_TEXT']}\n"
    if arm == "PLAIN_PROMPT_BASELINE":
        body = "Interpret the item in this context.\n"
    elif arm == "GENERIC_STRUCTURED_PROMPT_BASELINE":
        body = "Consider opposing tensions and several facets of the item; weigh them, then synthesize a specific reading.\n"
    elif arm == "SEMANTIC_LLM_BASELINE":
        body = "Interpret the item using its ordinary dictionary and connotative meaning in this context.\n"
    elif arm == "KCPR_SELECTED_POLE":
        body = (f"Emphasize the {plane} plane. Read each element through the single facet below (a lens only):\n"
                f"{_selected_bullets(t['KCPR_LAYER1_SELECTED_FRAME'])}\n")
    elif arm == "SCRAMBLED_SELECTED_POLE":
        body = (f"Emphasize the {plane} plane. Read each element through the single facet below (a lens only):\n"
                f"{_selected_bullets(r['SCRAMBLED_SELECTED_POLE_FRAME'])}\n")
    elif arm == "UNRESOLVED_BOTH_POLES":
        body = (f"Emphasize the {plane} plane. Both poles are shown; do not treat either as correct; let each "
                f"pole-pair color the reading as a tension field:\n{_both_bullets(t['UNRESOLVED_BOTH_POLES_FRAME'])}\n")
    elif arm == "SCRAMBLED_UNRESOLVED":
        body = (f"Emphasize the {plane} plane. Both poles are shown; do not treat either as correct; let each "
                f"pole-pair color the reading as a tension field:\n{_both_bullets(r['SCRAMBLED_UNRESOLVED_BOTH_POLES_FRAME'])}\n")
    else:
        raise ValueError(f"unknown arm {arm!r}")
    return base + body + "\n" + OUTPUT_FORMAT


# --------------------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------------------
def load_frozen() -> Tuple[Dict, Dict]:
    return json.loads(TARGETS_FILE.read_text()), json.loads(RANDOMIZED_FILE.read_text())


def build_records(targets_doc: Dict, rand_doc: Dict, limit_items: Optional[int] = None) -> List[Dict]:
    rand_by = {x["item_id"]: x for x in rand_doc["items"]}
    targets = targets_doc["targets"][:limit_items] if limit_items else targets_doc["targets"]
    recs, n = [], 0
    for t in targets:
        r = rand_by.get(t["item_id"])
        for arm in ARMS:
            n += 1
            recs.append({
                "item_id": t["item_id"], "target_text": t["TARGET_TEXT"], "context_text": t["CONTEXT_TEXT"],
                "stratum": t["STRATUM"], "arm": arm, "selected_plane": t["SELECTED_PLANE"],
                "resolver_decision": t["RESOLVER_DECISION"], "blinded_output_id": f"G{n:04d}",
                "prompt": render_prompt(arm, t, r),
            })
    return recs


# --------------------------------------------------------------------------------------
# Blinding
# --------------------------------------------------------------------------------------
def make_judge_visible(rec: Dict, text: str) -> Dict:
    pkg = {"item_id": rec["item_id"], "target_text": rec["target_text"],
           "neutral_context": rec["context_text"], "blinded_output_id": rec["blinded_output_id"],
           "generation_text": text, "output_format": "Title/Interpretation(120-180w)/2 bullets/Caution"}
    bad = {"arm", "true_arm", "resolver_decision", "selected_plane", "stratum"} & set(pkg.keys())
    if bad:
        raise ValueError(f"INVALID_BLINDING: leaked keys {sorted(bad)}")
    lk = leaked(text)
    if lk:
        raise ValueError(f"INVALID_LEAKAGE: method/arm tokens {lk} in generation_text")
    return pkg


def make_hidden(rec: Dict, gen_code: Optional[str], gen_id: Optional[str]) -> Dict:
    return {"blinded_output_id": rec["blinded_output_id"], "true_arm": rec["arm"],
            "generator_code": gen_code, "generator_id": gen_id, "item_id": rec["item_id"],
            "stratum": rec["stratum"], "resolver_decision": rec["resolver_decision"],
            "selected_plane": rec["selected_plane"], "representation_version": REPRESENTATION}


def assert_blind(judge_visible: List[Dict]) -> None:
    for i, pkg in enumerate(judge_visible):
        extra = set(pkg.keys()) - ALLOWED_JV_KEYS
        if extra:
            raise ValueError(f"INVALID_BLINDING [{i}]: unexpected keys {sorted(extra)}")
        lk = leaked(str(pkg.get("generation_text", "")))
        if lk:
            raise ValueError(f"INVALID_LEAKAGE [{i}]: {lk}")


# --------------------------------------------------------------------------------------
# Run one generator -> a part (hidden side; carries generator identity)
# --------------------------------------------------------------------------------------
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
    """Run ONE generator over all (target x arm) records. Gated unless mock. Returns a part (hidden side)."""
    if not mock:
        if decl_path is None:
            raise PermissionError("real run requires a B1.8 evidence-freeze declaration path")
        ok, reasons = verify_freeze_gate(pathlib.Path(decl_path), panel_manifest_path=panel_manifest_path)
        if not ok:
            raise PermissionError("EVIDENCE_FREEZE gate refused: " + "; ".join(reasons))
    settings = settings or A.GenerationSettings()
    gen_id = gen_id or getattr(settings, "model_id", "MOCK_ONLY")
    targets_doc, rand_doc = load_frozen()
    records = build_records(targets_doc, rand_doc, limit_items=limit_items)
    emit, gen_meta = _emit(mock, adapter, settings, validate_real)

    outputs, failures = [], []
    for rec in records:
        text, status, rs = emit(rec)
        lk = leaked(text) if (status in ("ok", "mock") and text is not None) else []
        if lk:
            status, rs = "blindness_leak", [f"tokens: {lk}"]
        if status in ("ok", "mock") and text is not None and not lk:
            outputs.append({**rec, "generation_text": text, "generator_code": gen_code, "generator_id": gen_id})
        else:
            failures.append({"blinded_output_id": rec["blinded_output_id"], "item_id": rec["item_id"],
                             "status": status, "reasons": rs})
    part = {
        "artifact_type": "b1_8_context_resolved_part", "mode": "MOCK" if mock else "REAL",
        "representation_version": REPRESENTATION, "generator_code": gen_code, "generator_id": gen_id,
        "arms": list(ARMS), "n_records": len(records), "n_outputs": len(outputs), "n_failures": len(failures),
        "failures": failures, "generator_meta": gen_meta, "b1_4b_prime_status": B1_4B_PRIME_STATUS,
        "input_hashes": {k: _sha_file(v) for k, v in HASH_INPUTS.items()},
        "declaration_sha256": _sha_file(pathlib.Path(decl_path)) if (decl_path and not mock) else None,
        "outputs": outputs,
    }
    if write and out_dir:
        out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "b1_8_part.json").write_text(json.dumps(part, ensure_ascii=False, indent=2))
    return part


def load_part(path: pathlib.Path) -> Dict:
    p = pathlib.Path(path)
    if p.is_dir():
        p = p / "b1_8_part.json"
    return json.loads(p.read_text())


# --------------------------------------------------------------------------------------
# Merge + re-blind one or more parts into the final blind package
# --------------------------------------------------------------------------------------
def merge_parts(parts: List[Dict], out_dir: Optional[pathlib.Path] = None, write: bool = False,
                reblind_seed: int = 20260709) -> Dict:
    reasons = []
    reprs = {p.get("representation_version") for p in parts}
    if reprs != {REPRESENTATION}:
        reasons.append(f"representation mismatch across parts: {reprs}")
    codes = [p.get("generator_code") for p in parts]
    if len(set(codes)) != len(codes):
        reasons.append(f"duplicate generator_code across parts: {codes}")
    hsets = {json.dumps(p.get("input_hashes"), sort_keys=True) for p in parts}
    if len(hsets) != 1:
        reasons.append("parts disagree on frozen input hashes")
    if reasons:
        return {"label": "B1_8_GENERATION_BLOCKED_ARM_RENDERING", "reasons": reasons}

    merged = [o for p in parts for o in p["outputs"]]
    merged.sort(key=lambda o: hashlib.sha256(
        f"{reblind_seed}|{o['item_id']}|{o['arm']}|{o['generator_code']}".encode()).hexdigest())
    judge_visible, hidden = [], []
    for i, o in enumerate(merged, 1):
        fid = f"F{i:04d}"
        rec = {**o, "blinded_output_id": fid}
        judge_visible.append(make_judge_visible(rec, o["generation_text"]))
        hidden.append(make_hidden(rec, o["generator_code"], o["generator_id"]))
    assert_blind(judge_visible)

    manifest = {
        "artifact_type": "b1_8_context_resolved_run_manifest", "mode": parts[0].get("mode"),
        "representation_version": REPRESENTATION, "run_label": "B1_8_CONTEXT_RESOLVED_GENERATION_PROBE",
        "arms": list(ARMS), "n_generators": len(parts),
        "generator_codes": {p["generator_code"]: p["generator_id"] for p in parts},
        "n_targets": len({o["item_id"] for o in merged}), "n_outputs": len(merged),
        "expected_full": 12 * len(ARMS) * len(parts),
        "per_generator_counts": {p["generator_code"]: p["n_outputs"] for p in parts},
        "reblind_seed": reblind_seed, "input_hashes": parts[0].get("input_hashes"),
        "declaration_sha256": parts[0].get("declaration_sha256"),
        "judging_performed": False, "unblinded": False, "b1_4b_prime_status": B1_4B_PRIME_STATUS,
        "note": "Generator identity ONLY in hidden metadata; judge-visible re-blinded. No judging. No GENUTILITY_*.",
    }
    if write and out_dir:
        out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "panel_judge_visible_outputs.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in judge_visible) + "\n")
        (out_dir / "panel_hidden_arm_generator_metadata.json").write_text(json.dumps(hidden, ensure_ascii=False, indent=2))
        (out_dir / "panel_run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return {"label": "B1_8_GENERATION_DRIVER_READY_MOCK_TESTED", "manifest": manifest,
            "judge_visible": judge_visible, "hidden": hidden}


# --------------------------------------------------------------------------------------
# CLI (mock plumbing + gated real run via operator-supplied adapter args)
# --------------------------------------------------------------------------------------
def _adapter_from_args(args):
    return A.build_adapter(A.GenerationSettings(
        model_id=args.model_id, backend=args.backend, base_url=args.base_url,
        revision=args.revision, temperature=args.temperature, max_tokens=args.max_tokens))


def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.8 context-resolved generation driver (gated; mock-tested).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("part", help="run one generator over all (target x arm) records")
    rp.add_argument("--mock", action="store_true")
    rp.add_argument("--decl"); rp.add_argument("--panel-manifest")
    rp.add_argument("--gen-code", default="M1"); rp.add_argument("--limit-items", type=int)
    rp.add_argument("--backend", default="transformers"); rp.add_argument("--model-id", default="MOCK_ONLY")
    rp.add_argument("--base-url"); rp.add_argument("--revision")
    rp.add_argument("--temperature", type=float, default=0.7); rp.add_argument("--max-tokens", type=int, default=600)
    rp.add_argument("--out", required=True)

    mp = sub.add_parser("merge", help="merge + re-blind parts into the final blind package")
    mp.add_argument("--parts", nargs="+", required=True); mp.add_argument("--out", required=True)
    mp.add_argument("--reblind-seed", type=int, default=20260709)

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
                          "n_failures": part["n_failures"], "representation_version": part["representation_version"]},
                         indent=2))
        return
    if args.cmd == "merge":
        parts = [load_part(pathlib.Path(p)) for p in args.parts]
        res = merge_parts(parts, out_dir=pathlib.Path(args.out), write=True, reblind_seed=args.reblind_seed)
        if res["label"] != "B1_8_GENERATION_DRIVER_READY_MOCK_TESTED":
            raise SystemExit(f"MERGE REFUSED ({res['label']}): {res.get('reasons')}")
        print(json.dumps(res["manifest"], indent=2))


if __name__ == "__main__":
    main()
