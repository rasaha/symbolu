"""B1.6 pilot generation-run driver (GATED; mock-tested only).

Renders generation prompts for the five active B1.6 arms over the frozen pilot
target set, writes BLINDED output packages + a HIDDEN arm-metadata file, and NEVER
judges. It REFUSES to run unless an operator-created evidence-freeze declaration
(`frozen/b1_6_pilot_EVIDENCE_FREEZE_DECLARED.json`) exists with matching hashes.

The assistant NEVER creates that declaration; the operator does.

This module performs NO real LLM generation and makes NO external API call.
`--mock` produces deterministic placeholder text ("MOCK_GENERATION_ONLY_DO_NOT_SCORE")
for plumbing/tests only. Real mode requires an explicit model-adapter callable passed
in by an operator; none is implemented here.

No judging. No evidence freeze created here. B1.4b' remains NULL_RETURN_BOTTOM.
Structure, not validated meaning.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
from typing import Callable, Dict, List, Optional, Tuple

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"

TARGETS_FILE = FROZEN / "b1_6_pilot_targets_scaffolds.json"
SCAFFOLD_MANIFEST_FILE = FROZEN / "b1_6_pilot_scaffold_manifest.json"
RANDCTL_FILE = FROZEN / "b1_6_pilot_randomized_control_manifest.json"
PROMPT_RUBRIC_FILE = HERE / "B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md"
DECL_FILE = FROZEN / "b1_6_pilot_EVIDENCE_FREEZE_DECLARED.json"

RUN_OUT = HERE / "run_out" / "b1_6_pilot_generation"

MODE = "pilot_generation"
ACTIVE_ARMS = [
    "SYMBOLU_SCAFFOLD",
    "PLAIN_PROMPT_BASELINE",
    "GENERIC_STRUCTURED_PROMPT_BASELINE",
    "RANDOMIZED_SYMBOLU_CONTROL",
    "SEMANTIC_LLM_BASELINE",
]
# F. SYMBOLIC_SYSTEM_BASELINE stays DISABLED.

MOCK_TEXT = "MOCK_GENERATION_ONLY_DO_NOT_SCORE"
B1_4B_PRIME_STATUS = "NULL_RETURN_BOTTOM"

REQUIRED_DECL_FIELDS = (
    "artifact",
    "evidence_freeze_declared",
    "mode",
    "scaffold_manifest_sha256",
    "target_scaffold_sha256",
    "randomized_control_manifest_sha256",
    "prompt_rubric_sha256",
    "declared_by",
    "declared_at_utc",
    "attestation",
)
ATTESTATION = ("B1.6 pilot generation only; no judging; no semantic truth claim; "
               "Symbol-U utility test only; B1.4b′ remains NULL_RETURN_BOTTOM.")

OUTPUT_FORMAT_SPEC = (
    "Title: <one short phrase>\n"
    "Interpretation: <120-180 words>\n"
    "Practical reflection:\n- <bullet 1>\n- <bullet 2>\n"
    "Caution: <one sentence stating the limits/uncertainty of this interpretation>"
)

# words/markers that must NEVER appear in judge-visible outputs
FORBIDDEN_IN_JUDGE_VIEW = ("SYMBOLU", "Symbol-U", "varṇa", "varna", "KCPR", "scaffold",
                           "RANDOMIZED", "arm", "polarity")


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha_file(p: pathlib.Path) -> str:
    return _sha_bytes(p.read_bytes())


def _sha_text(s: str) -> str:
    return _sha_bytes(s.encode("utf-8"))


# --------------------------------------------------------------------------------------
# Evidence-freeze gate
# --------------------------------------------------------------------------------------
def verify_freeze_gate(decl_path: pathlib.Path = DECL_FILE) -> Tuple[bool, List[str]]:
    """Return (ok, reasons). Refuses unless a valid operator declaration exists."""
    reasons: List[str] = []
    if not decl_path.exists():
        return False, ["no EVIDENCE_FREEZE_DECLARED file (operator must create it)"]
    try:
        decl = json.loads(decl_path.read_text())
    except Exception as e:  # pragma: no cover - defensive
        return False, [f"declaration not valid JSON: {e}"]

    for f in REQUIRED_DECL_FIELDS:
        if f not in decl:
            reasons.append(f"missing required field: {f}")
    if decl.get("artifact") != "b1_6_pilot_EVIDENCE_FREEZE_DECLARED":
        reasons.append("artifact != b1_6_pilot_EVIDENCE_FREEZE_DECLARED")
    if decl.get("evidence_freeze_declared") is not True:
        reasons.append("evidence_freeze_declared != true")
    if decl.get("mode") != MODE:
        reasons.append(f"mode != {MODE}")
    if reasons:
        return False, reasons

    checks = [
        ("scaffold_manifest_sha256", SCAFFOLD_MANIFEST_FILE),
        ("target_scaffold_sha256", TARGETS_FILE),
        ("randomized_control_manifest_sha256", RANDCTL_FILE),
        ("prompt_rubric_sha256", PROMPT_RUBRIC_FILE),
    ]
    for field, path in checks:
        if not path.exists():
            reasons.append(f"frozen input missing: {path.name}")
            continue
        actual = _sha_file(path)
        if decl.get(field) != actual:
            reasons.append(f"{field} mismatch (declared {decl.get(field)!r} != actual {actual})")

    if decl.get("attestation") != ATTESTATION:
        reasons.append("attestation text mismatch")
    return (not reasons), reasons


# --------------------------------------------------------------------------------------
# Prompt rendering (uses the frozen scaffold data; no CSR/STL, no Kosha)
# --------------------------------------------------------------------------------------
def _render_kcpr_dual_pole(kcpr_frame: Dict) -> str:
    lines = []
    for varna, axlist in kcpr_frame.items():
        for ax in axlist:
            lines.append(
                f"{varna}: axis = {ax['axis']}; worldly/binding pole = {ax['worldly_binding_pole']}; "
                f"liberating/counter pole = {ax['liberating_counter_pole']}; table_lean = {ax['table_lean']}"
            )
    return "\n".join(lines) if lines else "(no supported varṇa profiles)"


def _render_varna_sequence(seq: List[Dict]) -> str:
    parts = []
    for u in seq:
        if u["status"] == "SUPPORTED":
            parts.append(f"{u['phoneme']}->{u['varna']}")
        else:
            parts.append(f"{u['phoneme']}[{u['status']}]")
    return " ".join(parts)


def render_prompt(arm: str, rec: Dict, rand_rec: Optional[Dict]) -> str:
    """Render the generation prompt for one arm + one target from frozen data."""
    target = rec["TARGET_TEXT"]
    ctx = rec["neutral_context"]
    if arm == "PLAIN_PROMPT_BASELINE":
        return (
            "You are a thoughtful interpreter. Give a thoughtful, grounded interpretation of the "
            "following item. Do not use any special framework, system, or lens.\n"
            f"Item: {target}\n{ctx}\n\nRespond in EXACTLY this format:\n{OUTPUT_FORMAT_SPEC}\n"
            "Do not claim your reading is objectively true, ancient, or authoritative. Do not name any system."
        )
    if arm == "GENERIC_STRUCTURED_PROMPT_BASELINE":
        return (
            "You are a thoughtful interpreter. Interpret the following item using this general interpretive "
            "structure (an ordinary organizing structure, not a special system).\n"
            f"Item: {target}\n{ctx}\n\n"
            "Work through these lenses internally, then synthesize:\n"
            "- surface meaning; - emotional tone; - metaphorical associations; - a practical reflection; "
            "- a note of caution.\n\n"
            f"Respond in EXACTLY this format:\n{OUTPUT_FORMAT_SPEC}\n"
            "Do not claim your reading is objectively true, ancient, or authoritative. Do not name any system."
        )
    if arm == "SEMANTIC_LLM_BASELINE":
        return (
            "You are a knowledgeable interpreter. Give a strong, conventional interpretation of the following "
            "item, drawing on ordinary semantic and conceptual analysis and common cultural associations "
            "(etymology only if you actually know it; do NOT invent facts).\n"
            f"Item: {target}\n{ctx}\n\n"
            f"Respond in EXACTLY this format:\n{OUTPUT_FORMAT_SPEC}\n"
            "Do not use any esoteric framework. Do not name any system. If unsure of a fact, say so."
        )
    if arm == "SYMBOLU_SCAFFOLD":
        frame = _render_kcpr_dual_pole(rec["KCPR_DUAL_POLE_FRAME"])
        return (
            "You are an interpreter using a structural lens as a heuristic scaffold - NOT as truth. Use the "
            "pre-computed structural profile below to shape an interpretation. Treat it as one possible lens, "
            "never as proof that sound carries meaning.\n"
            f"Item: {target}\n{ctx}\n\n"
            f"Structural scaffold (use as a lens only):\n"
            f"- sequence: {_render_varna_sequence(rec['VARNA_SEQUENCE'])}\n"
            f"- pole frame (both poles shown; do not treat either as correct):\n{frame}\n"
            "- transformation: read in order; let each element's pole-pair color the reading as a tension "
            "field; synthesize a specific reading of THIS item.\n\n"
            "Build the reading from the scaffold, not from the dictionary definition. Do NOT claim this proves "
            "meaning, is true, ancient, or authoritative. Do NOT mention any system name.\n\n"
            f"Respond in EXACTLY this format:\n{OUTPUT_FORMAT_SPEC}"
        )
    if arm == "RANDOMIZED_SYMBOLU_CONTROL":
        assert rand_rec is not None, "randomized control record required"
        frame = _render_kcpr_dual_pole(rand_rec["KCPR_DUAL_POLE_FRAME"])
        # presented EXACTLY like the scaffold arm; no hint of randomization
        seq_str = " ".join(f"{m['varna_position_key']}" for m in rand_rec["randomized_profile_map"])
        return (
            "You are an interpreter using a structural lens as a heuristic scaffold - NOT as truth. Use the "
            "pre-computed structural profile below to shape an interpretation. Treat it as one possible lens, "
            "never as proof that sound carries meaning.\n"
            f"Item: {target}\n{ctx}\n\n"
            f"Structural scaffold (use as a lens only):\n"
            f"- sequence: {seq_str}\n"
            f"- pole frame (both poles shown; do not treat either as correct):\n{frame}\n"
            "- transformation: read in order; let each element's pole-pair color the reading as a tension "
            "field; synthesize a specific reading of THIS item.\n\n"
            "Build the reading from the scaffold, not from the dictionary definition. Do NOT claim this proves "
            "meaning, is true, ancient, or authoritative. Do NOT mention any system name.\n\n"
            f"Respond in EXACTLY this format:\n{OUTPUT_FORMAT_SPEC}"
        )
    raise ValueError(f"unknown arm {arm!r}")


def build_records(targets_doc: Dict, randctl_doc: Dict) -> List[Dict]:
    """Cross the frozen targets with the active arms; render every prompt."""
    rand_by_id = {r["item_id"]: r for r in randctl_doc["randomized_scaffolds"]}
    out: List[Dict] = []
    blind_n = 0
    for rec in targets_doc["targets"]:
        rand_rec = rand_by_id.get(rec["item_id"])
        for arm in ACTIVE_ARMS:
            prompt = render_prompt(arm, rec, rand_rec)
            blind_n += 1
            out.append({
                "item_id": rec["item_id"],
                "target_text": rec["TARGET_TEXT"],
                "neutral_context": rec["neutral_context"],
                "arm": arm,                                   # HIDDEN side only
                "blinded_output_id": f"G{blind_n:04d}",
                "prompt": prompt,
                "prompt_sha256": _sha_text(prompt),
            })
    return out


# --------------------------------------------------------------------------------------
# Blinding / packaging
# --------------------------------------------------------------------------------------
def make_judge_visible(record: Dict, generation_text: str) -> Dict:
    """Blinded package - NO arm name, NO scaffold metadata, NO system label."""
    pkg = {
        "item_id": record["item_id"],
        "target_text": record["target_text"],
        "neutral_context": record["neutral_context"],
        "blinded_output_id": record["blinded_output_id"],
        "generation_text": generation_text,
        "output_format": "Title/Interpretation(120-180w)/2 bullets/Caution",
    }
    assert_blind(pkg)
    return pkg


def make_hidden_meta(record: Dict, seed: int) -> Dict:
    return {
        "blinded_output_id": record["blinded_output_id"],
        "true_arm": record["arm"],
        "item_id": record["item_id"],
        "prompt_sha256": record["prompt_sha256"],
        "scaffold_hash": record.get("prompt_sha256") if record["arm"] in
        ("SYMBOLU_SCAFFOLD", "RANDOMIZED_SYMBOLU_CONTROL") else None,
        "randomization_seed": seed if record["arm"] == "RANDOMIZED_SYMBOLU_CONTROL" else None,
    }


def assert_blind(pkg: Dict) -> None:
    """Raise if any arm-identifying token leaks into a judge-visible package."""
    forbidden_keys = {"arm", "true_arm", "scaffold", "prompt", "KCPR_DUAL_POLE_FRAME",
                      "VARNA_PROFILE_TABLE", "VARNA_SEQUENCE"}
    bad = forbidden_keys & set(pkg.keys())
    if bad:
        raise ValueError(f"INVALID_BLINDING: forbidden keys in judge-visible package: {sorted(bad)}")
    gen = pkg.get("generation_text", "")
    for tok in FORBIDDEN_IN_JUDGE_VIEW:
        if tok in gen:
            raise ValueError(f"INVALID_LEAKAGE: forbidden token {tok!r} in generation_text")


# --------------------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------------------
def mock_generator(record: Dict) -> str:
    return f"{MOCK_TEXT} [{record['blinded_output_id']}]"


def run(mock: bool,
        generator: Optional[Callable[[Dict], str]] = None,
        out_dir: pathlib.Path = RUN_OUT,
        decl_path: pathlib.Path = DECL_FILE,
        write: bool = True) -> Dict:
    """Gated run. Refuses without a valid operator declaration."""
    ok, reasons = verify_freeze_gate(decl_path)
    if not ok:
        raise PermissionError("EVIDENCE_FREEZE gate refused: " + "; ".join(reasons))

    if not mock and generator is None:
        raise ValueError("real mode requires an explicit operator-supplied model adapter "
                         "(generator callable); none is implemented in this module")
    gen: Callable[[Dict], str] = mock_generator if mock else generator  # type: ignore

    targets_doc = json.loads(TARGETS_FILE.read_text())
    randctl_doc = json.loads(RANDCTL_FILE.read_text())
    seed = randctl_doc.get("seed")
    records = build_records(targets_doc, randctl_doc)

    judge_visible = []
    hidden_meta = []
    rendered_hidden = []
    for rec in records:
        text = gen(rec)
        judge_visible.append(make_judge_visible(rec, text))
        hidden_meta.append(make_hidden_meta(rec, seed))
        rendered_hidden.append({"blinded_output_id": rec["blinded_output_id"],
                                "arm": rec["arm"], "prompt": rec["prompt"]})

    manifest = {
        "artifact_type": "b1_6_pilot_generation_run_manifest",
        "mode": "MOCK" if mock else "REAL",
        "judging_performed": False,
        "n_targets": len(targets_doc["targets"]),
        "n_arms": len(ACTIVE_ARMS),
        "n_prompts": len(records),
        "arms": ACTIVE_ARMS,
        "seed": seed,
        "b1_4b_prime_status": B1_4B_PRIME_STATUS,
        "note": "No judging performed by this driver. Blinded outputs and hidden metadata are NOT committed.",
    }

    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "judge_visible_outputs.jsonl").write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in judge_visible) + "\n")
        (out_dir / "hidden_arm_metadata.json").write_text(
            json.dumps(hidden_meta, ensure_ascii=False, indent=2))
        (out_dir / "rendered_prompts_hidden.jsonl").write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in rendered_hidden) + "\n")
        (out_dir / "generation_run_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2))

    return {"manifest": manifest, "judge_visible": judge_visible,
            "hidden_meta": hidden_meta, "records": records}


def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.6 pilot generation driver (gated; mock-tested).")
    ap.add_argument("--mock", action="store_true", help="deterministic placeholder text (tests/plumbing only)")
    ap.add_argument("--out", default=str(RUN_OUT))
    args = ap.parse_args(argv)
    if not args.mock:
        raise SystemExit("Real generation requires an operator-supplied model adapter; not runnable from CLI. "
                         "Use --mock for plumbing only.")
    res = run(mock=True, out_dir=pathlib.Path(args.out))
    print(json.dumps(res["manifest"], indent=2))


if __name__ == "__main__":
    main()
