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

# v1 (directional-axis) — SUPERSEDED before execution; preserved, accessible only if explicitly requested.
TARGETS_FILE = FROZEN / "b1_6_pilot_targets_scaffolds.json"
SCAFFOLD_MANIFEST_FILE = FROZEN / "b1_6_pilot_scaffold_manifest.json"
RANDCTL_FILE = FROZEN / "b1_6_pilot_randomized_control_manifest.json"
# v2 (named-vṛtti) — ACTIVE default representation for future runs.
V2_TARGETS_FILE = FROZEN / "b1_6_pilot_targets_scaffolds_v2_named_vritti.json"
V2_SCAFFOLD_MANIFEST_FILE = FROZEN / "b1_6_pilot_scaffold_manifest_v2_named_vritti.json"
V2_RANDCTL_FILE = FROZEN / "b1_6_pilot_randomized_control_manifest_v2_named_vritti.json"
V2_TABLE_FILE = HERE / "track_g_varna_polarity_table_v2_named_vritti.json"

REPRESENTATIONS = {
    "v2_named_vritti": {"targets": V2_TARGETS_FILE, "manifest": V2_SCAFFOLD_MANIFEST_FILE,
                        "randctl": V2_RANDCTL_FILE, "status": "ACTIVE"},
    "v1_directional": {"targets": TARGETS_FILE, "manifest": SCAFFOLD_MANIFEST_FILE,
                       "randctl": RANDCTL_FILE, "status": "SUPERSEDED_HISTORICAL"},
}
DEFAULT_REPRESENTATION = "v2_named_vritti"

PROMPT_RUBRIC_FILE = HERE / "B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md"
DECL_FILE = FROZEN / "b1_6_pilot_EVIDENCE_FREEZE_DECLARED.json"


def _repr_files(representation: str):
    if representation not in REPRESENTATIONS:
        raise ValueError(f"unknown representation {representation!r}; choices {list(REPRESENTATIONS)}")
    r = REPRESENTATIONS[representation]
    return r["targets"], r["manifest"], r["randctl"]

RUN_OUT = HERE / "run_out" / "b1_6_pilot_generation"

MODE = "pilot_generation"
EXPLORATORY_MODE = "exploratory_10_sample_generation_probe"
VALID_MODES = (MODE, EXPLORATORY_MODE)
EXPLORATORY_LABEL = "B1_6_10_SAMPLE_EXPLORATORY_GENERATION_PROBE"
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
EXPLORATORY_ATTESTATION = ("B1.6 10-sample exploratory generation probe only; no judging; "
                           "no semantic truth claim; no GENUTILITY terminal label; "
                           "B1.4b′ remains NULL_RETURN_BOTTOM.")
ATTESTATIONS = {MODE: ATTESTATION, EXPLORATORY_MODE: EXPLORATORY_ATTESTATION}

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
def verify_freeze_gate(decl_path: pathlib.Path = DECL_FILE,
                       expected_mode: str = MODE,
                       representation: str = DEFAULT_REPRESENTATION) -> Tuple[bool, List[str]]:
    """Return (ok, reasons). Refuses unless a valid operator declaration exists whose mode matches
    expected_mode and whose hashes match the REQUESTED representation's scaffold files. If the declaration
    hashes the wrong representation (e.g. v1 while v2 is requested), it is refused loudly."""
    targets_file, manifest_file, randctl_file = _repr_files(representation)
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
    if decl.get("mode") != expected_mode:
        reasons.append(f"mode != {expected_mode}")
    # representation_version, if declared, MUST match the requested representation (loud refusal on mismatch)
    decl_repr = decl.get("representation_version")
    if decl_repr is not None and decl_repr != representation:
        reasons.append(f"representation_version mismatch: declaration says {decl_repr!r} but run requested "
                       f"{representation!r} (a v1 declaration cannot authorize a v2 run, or vice versa)")
    if reasons:
        return False, reasons

    checks = [
        ("scaffold_manifest_sha256", manifest_file),
        ("target_scaffold_sha256", targets_file),
        ("randomized_control_manifest_sha256", randctl_file),
        ("prompt_rubric_sha256", PROMPT_RUBRIC_FILE),
    ]
    for field, path in checks:
        if not path.exists():
            reasons.append(f"frozen input missing: {path.name}")
            continue
        actual = _sha_file(path)
        if decl.get(field) != actual:
            reasons.append(f"{field} mismatch for representation {representation!r} "
                           f"(declared {decl.get(field)!r} != actual {actual}); "
                           f"wrong-representation declaration is refused")

    if decl.get("attestation") != ATTESTATIONS.get(expected_mode):
        reasons.append("attestation text mismatch")
    return (not reasons), reasons


# --------------------------------------------------------------------------------------
# Prompt rendering (uses the frozen scaffold data; no CSR/STL, no Kosha)
# --------------------------------------------------------------------------------------
def _render_kcpr_dual_pole(kcpr_frame: Dict) -> str:
    """Render both poles per varṇa. Handles v1 (directional-axis: list of axis dicts) and
    v2 (named-vṛtti: dict with worldly_binding_pole / spiritual_liberating_pole / named_attribute)."""
    lines = []
    for varna, val in kcpr_frame.items():
        if isinstance(val, list):                       # v1 directional-axis
            for ax in val:
                lines.append(
                    f"{varna}: axis = {ax['axis']}; worldly/binding pole = {ax['worldly_binding_pole']}; "
                    f"liberating/counter pole = {ax['liberating_counter_pole']}; table_lean = {ax['table_lean']}"
                )
        elif isinstance(val, dict):                     # v2 named-vṛtti
            named = val.get("named_attribute", "")
            lines.append(
                f"{varna}: named = {named}; worldly/binding pole = {val.get('worldly_binding_pole')}; "
                f"liberating/counter pole = {val.get('spiritual_liberating_pole')}"
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


def select_balanced_subset(targets: List[Dict], n: int) -> List[Dict]:
    """Deterministic balanced subset: round-robin across strata (category), file order within stratum."""
    strata: Dict[str, List[Dict]] = {}
    for t in targets:
        strata.setdefault(t["category"], []).append(t)
    picked: List[Dict] = []
    p = 0
    while len(picked) < n and any(p < len(v) for v in strata.values()):
        for items in strata.values():
            if p < len(items) and len(picked) < n:
                picked.append(items[p])
        p += 1
    return picked


def select_items(targets_doc: Dict, item_ids=None, limit_items=None) -> List[Dict]:
    targets = targets_doc["targets"]
    if item_ids:
        want = list(item_ids)
        order = {i: k for k, i in enumerate(want)}
        chosen = [t for t in targets if t["item_id"] in set(want)]
        chosen.sort(key=lambda t: order.get(t["item_id"], 10 ** 9))
        return chosen
    if limit_items:
        return select_balanced_subset(targets, limit_items)
    return list(targets)


def build_records(targets: List[Dict], randctl_doc: Dict) -> List[Dict]:
    """Cross the (possibly-subset) target list with the active arms; render every prompt."""
    rand_by_id = {r["item_id"]: r for r in randctl_doc["randomized_scaffolds"]}
    out: List[Dict] = []
    blind_n = 0
    for rec in targets:
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


def make_hidden_meta(record: Dict, seed: int, gen_code: Optional[str] = None) -> Dict:
    return {
        "blinded_output_id": record["blinded_output_id"],
        "true_arm": record["arm"],
        "item_id": record["item_id"],
        "generator_code": gen_code,          # opaque generator code (panel); HIDDEN side only
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


def _make_emit(mock, adapter, generator, settings, validate_real):
    """Return (emit(record)->(text|None,status,reasons), gen_meta)."""
    if mock:
        return (lambda rec: (mock_generator(rec), "mock", [])), {"backend": "mock", "model_id": "MOCK_ONLY"}
    from b1_6_llm_adapter import generate_with_retry, validate_output_format  # lazy; no torch at import
    if adapter is not None:
        def emit(rec):
            return generate_with_retry(adapter, rec["prompt"], settings, validate=validate_real)
        return emit, {**settings.metadata(), "backend": getattr(adapter, "backend", "custom")}
    if generator is not None:
        def emit(rec):
            txt = generator(rec)
            if not validate_real:
                return txt, "ok", []
            okv, rs = validate_output_format(txt)
            return (txt, "ok", []) if okv else (None, "format_invalid", rs)
        return emit, {"backend": "custom_generator", **settings.metadata()}
    raise ValueError("real mode requires an operator-supplied adapter or generator callable; none provided")


def run(mock: bool = False,
        generator: Optional[Callable[[Dict], str]] = None,
        adapter=None,
        settings=None,
        mode: str = MODE,
        item_ids=None,
        limit_items: Optional[int] = None,
        out_dir: pathlib.Path = RUN_OUT,
        decl_path: pathlib.Path = DECL_FILE,
        write: bool = True,
        validate_real: bool = True,
        gen_code: Optional[str] = None,
        representation: str = DEFAULT_REPRESENTATION) -> Dict:
    """Gated run. Refuses without a valid operator declaration whose mode matches `mode` and whose hashes
    match the requested `representation` (default v2_named_vritti; v1_directional is superseded/historical).
    Real generation uses `adapter` or a bare `generator`, with output-format validation + retry. `mock` is
    unchanged deterministic placeholder text. No judging."""
    if mode not in VALID_MODES:
        raise ValueError(f"unknown mode {mode!r}")
    targets_file, manifest_file, randctl_file = _repr_files(representation)
    ok, reasons = verify_freeze_gate(decl_path, expected_mode=mode, representation=representation)
    if not ok:
        raise PermissionError("EVIDENCE_FREEZE gate refused: " + "; ".join(reasons))

    from b1_6_llm_adapter import GenerationSettings
    settings = settings or GenerationSettings()
    emit, gen_meta = _make_emit(mock, adapter, generator, settings, validate_real)

    targets_doc = json.loads(targets_file.read_text())
    randctl_doc = json.loads(randctl_file.read_text())
    seed = randctl_doc.get("seed")
    # normalize v2 named-vṛtti frame key -> the common render key (handles both representations)
    for t in targets_doc["targets"]:
        if "KCPR_NAMED_DUAL_POLE_FRAME" in t and "KCPR_DUAL_POLE_FRAME" not in t:
            t["KCPR_DUAL_POLE_FRAME"] = t["KCPR_NAMED_DUAL_POLE_FRAME"]
    for r in randctl_doc.get("randomized_scaffolds", []):
        if "KCPR_NAMED_DUAL_POLE_FRAME" in r and "KCPR_DUAL_POLE_FRAME" not in r:
            r["KCPR_DUAL_POLE_FRAME"] = r["KCPR_NAMED_DUAL_POLE_FRAME"]
    chosen = select_items(targets_doc, item_ids=item_ids, limit_items=limit_items)
    records = build_records(chosen, randctl_doc)

    judge_visible, hidden_meta, rendered_hidden, failures = [], [], [], []
    for rec in records:
        text, status, rs = emit(rec)
        if status in ("ok", "mock") and text is not None:
            judge_visible.append(make_judge_visible(rec, text))
            hidden_meta.append(make_hidden_meta(rec, seed, gen_code))
            rendered_hidden.append({"blinded_output_id": rec["blinded_output_id"],
                                    "arm": rec["arm"], "prompt": rec["prompt"]})
        else:
            failures.append({"blinded_output_id": rec["blinded_output_id"], "item_id": rec["item_id"],
                             "status": status, "reasons": rs})

    subset = bool(item_ids) or bool(limit_items)
    run_label = EXPLORATORY_LABEL if mode == EXPLORATORY_MODE else "B1_6_PILOT_FULL_GENERATION"
    manifest = {
        "artifact_type": "b1_6_pilot_generation_run_manifest",
        "mode": "MOCK" if mock else "REAL",
        "representation_version": representation,
        "representation_status": REPRESENTATIONS[representation]["status"],
        "declared_freeze_mode": mode,
        "run_label": run_label,
        "subset": subset,
        "judging_performed": False,
        "generator_meta": gen_meta,
        "n_targets": len(chosen),
        "n_arms": len(ACTIVE_ARMS),
        "n_prompts": len(records),
        "n_success": len(judge_visible),
        "n_failures": len(failures),
        "failures": failures,
        "arms": ACTIVE_ARMS,
        "seed": seed,
        "item_ids": [t["item_id"] for t in chosen],
        "frozen_input_hashes": {
            "target_scaffolds": _sha_file(targets_file),
            "scaffold_manifest": _sha_file(manifest_file),
            "randomized_control": _sha_file(randctl_file),
            "prompt_rubric": _sha_file(PROMPT_RUBRIC_FILE),
        },
        "scaffold_files": {"targets": str(targets_file.name), "manifest": str(manifest_file.name),
                           "randomized_control": str(randctl_file.name)},
        "declaration_sha256": _sha_file(decl_path) if decl_path.exists() else None,
        "b1_4b_prime_status": B1_4B_PRIME_STATUS,
        "note": "No judging performed by this driver. Blinded outputs and hidden metadata are NOT committed. "
                "No GENUTILITY_* label is emitted by generation.",
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
            "hidden_meta": hidden_meta, "records": records, "failures": failures}


def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.6 pilot generation driver (gated; mock-tested).")
    ap.add_argument("--mock", action="store_true", help="deterministic placeholder text (tests/plumbing only)")
    ap.add_argument("--local-model", help="HF model path/id for a real transformers run (model-access host)")
    ap.add_argument("--base-url", help="LOCAL OpenAI-compatible server (e.g. vLLM) for a real run")
    ap.add_argument("--adapter-config", help="path to a JSON GenerationSettings config for a real run")
    ap.add_argument("--mode", default=MODE, choices=list(VALID_MODES),
                    help="freeze mode: full pilot_generation or exploratory_10_sample_generation_probe")
    ap.add_argument("--limit-items", type=int, default=None, help="e.g. 10 for the exploratory probe")
    ap.add_argument("--item-ids", nargs="*", default=None, help="explicit deterministic subset of item ids")
    ap.add_argument("--representation-version", default=DEFAULT_REPRESENTATION, choices=list(REPRESENTATIONS),
                    help="active scaffold representation (default v2_named_vritti; v1_directional is "
                         "superseded/historical and must be requested explicitly)")
    ap.add_argument("--out", default=str(RUN_OUT))
    args = ap.parse_args(argv)

    if args.mock:
        res = run(mock=True, mode=args.mode, limit_items=args.limit_items, item_ids=args.item_ids,
                  representation=args.representation_version, out_dir=pathlib.Path(args.out))
        print(json.dumps(res["manifest"], indent=2))
        return

    # REAL: build an adapter (only on a model-access host); still gated by the freeze declaration.
    from b1_6_llm_adapter import GenerationSettings, build_adapter, model_backend_readiness
    if args.adapter_config:
        cfg = json.loads(pathlib.Path(args.adapter_config).read_text())
        settings = GenerationSettings(**cfg)
    elif args.base_url:
        settings = GenerationSettings(model_id=args.local_model or "local", backend="openai_compat_local",
                                      base_url=args.base_url)
    elif args.local_model:
        settings = GenerationSettings(model_id=args.local_model, backend="transformers")
    else:
        raise SystemExit("Real generation needs --local-model, --base-url, or --adapter-config "
                         "(and a matching operator evidence-freeze declaration). Use --mock for plumbing.")
    ready = model_backend_readiness()
    if settings.backend == "transformers" and not ready.get("cuda_available"):
        raise SystemExit(f"REFUSED: no CUDA/transformers backend on this host. readiness={ready}")
    adapter = build_adapter(settings)
    res = run(mock=False, adapter=adapter, settings=settings, mode=args.mode,
              limit_items=args.limit_items, item_ids=args.item_ids,
              representation=args.representation_version, out_dir=pathlib.Path(args.out))
    print(json.dumps(res["manifest"], indent=2))


if __name__ == "__main__":
    main()
