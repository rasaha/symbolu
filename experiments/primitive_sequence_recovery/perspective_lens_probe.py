"""B1.7 Perspective-Lens Controllability probe (gated; blinded; mock-tested only).

A NEW, SEPARATE hypothesis from B1.4b'/B1.6. It does NOT claim the varna->meaning mapping is real
(B1.4b' remains NULL_RETURN_BOTTOM). It asks a repurposing question surfaced by B1.6's divergence finding:

  Can a four-plane 'sphere' scaffold act as a CONTROLLABLE reframing dial -- e.g. read 'chair' from the
  MENTAL plane, or 'grief' from the PHYSICAL plane -- and do the varna-sphere glosses add anything over a
  plain "emphasize the <plane> aspects" instruction?

Arms (per word x per target lens):
  VARNA_SPHERE_LENS         names the plane + supplies the word's varna-sphere glosses as facets
  PLAIN_SPHERE_INSTRUCTION  names the plane only (no varna content)          <- the honest control
  RANDOMIZED_VARNA_SPHERE   names the plane + SHUFFLED varna glosses (seeded) <- specificity control
  NO_LENS_BASELINE          no target plane (reference; excluded from controllability)

Measures: (1) controllability = a BLIND plane-guesser's accuracy vs the target plane (chance=0.25);
(2) quality = the existing 1-7 rubric via the B1.6 judge panel (format-compatible package);
(3) cross-plane vs native divergence (MiniLM cosine, external script).

Generation reuses b1_6_llm_adapter (transformers/openai_compat_local/fake). Blinding reuses the shared
whole-word leak matcher (+ a few Sanskrit method terms). No real generation/guessing here; FakeAdapter only.
Emits ONLY B1_7_PROBE_* plumbing labels -- never a GENUTILITY/terminal verdict. Structure, not validated meaning.
"""
from __future__ import annotations
import hashlib
import json
import pathlib
import re
from typing import Callable, Dict, List, Optional, Tuple

import run_b1_6_pilot_generation as G          # shared leak matcher + adapter-driven retry pattern
import b1_6_llm_adapter as A

B1_4B_PRIME_STATUS = "NULL_RETURN_BOTTOM"

HERE = pathlib.Path(__file__).resolve().parent
TARGETS_FILE = HERE / "frozen" / "b1_7_perspective_lens_targets_v1.json"
SPHERE_LEXICON_FILE = HERE / "track_e_varna_sphere_lexicon.json"

LENSES = ("physical", "mental", "intellectual", "spiritual")
LENS_ARMS = ("VARNA_SPHERE_LENS", "PLAIN_SPHERE_INSTRUCTION", "RANDOMIZED_VARNA_SPHERE")
ARMS = (*LENS_ARMS, "NO_LENS_BASELINE")
MODE = "exploratory_perspective_lens_probe"

ATTESTATION = ("B1.7 exploratory perspective-lens controllability probe only; tests reframing controllability, "
               "NOT varna meaning; no GENUTILITY terminal label; B1.4b′ remains NULL_RETURN_BOTTOM.")
REQUIRED_DECL_FIELDS = ("artifact", "evidence_freeze_declared", "mode",
                        "targets_sha256", "sphere_lexicon_sha256", "declared_by", "declared_at_utc", "attestation")

PLANE_DESC = {
    "physical": "physical / concrete / embodied / sensory",
    "mental": "mental / emotional / psychological / felt-experience",
    "intellectual": "intellectual / conceptual / abstract / structural",
    "spiritual": "spiritual / existential / transcendent",
}
OUTPUT_FORMAT = ("Write a short reading in EXACTLY this format:\n"
                 "Title: <a few words>\n"
                 "Interpretation: <120-180 words>\n"
                 "Practical reflection:\n- <point>\n- <point>\n"
                 "Caution: <one sentence noting this is one limited reading>")

# Sanskrit/method terms that could leak the varna arm's identity to a blind scorer (beyond the shared matcher).
_SANSKRIT_LEAK = ("tattva", "prana", "shakti", "brahma", "varuna", "agni", "vrtti", "vritti",
                  "kosha", "chakra", "sattva", "tamas", "rajas", "prakriti", "purusha")
_SANSKRIT_RE = re.compile(r"(?<![\w-])(?:" + "|".join(_SANSKRIT_LEAK) + r")(?![\w-])", re.IGNORECASE)


def _sha_file(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def leaked(text: str) -> List[str]:
    """Method/arm-identifying tokens in an output (shared whole-word matcher + Sanskrit method terms)."""
    out = list(G.leaked_tokens(text))
    seen = {t.lower() for t in out}
    for m in _SANSKRIT_RE.finditer(text or ""):
        if m.group(0).lower() not in seen:
            seen.add(m.group(0).lower()); out.append(m.group(0))
    return out


# --------------------------------------------------------------------------------------
# Sphere lexicon + facets
# --------------------------------------------------------------------------------------
def load_sphere_varnas(path: pathlib.Path = SPHERE_LEXICON_FILE) -> Dict[str, Dict[str, str]]:
    return json.loads(pathlib.Path(path).read_text())["varnas"]


def varna_sphere_facets(varnas: List[str], sphere: str, lex: Dict[str, Dict[str, str]]) -> List[str]:
    """Ordered, de-duplicated target-plane glosses for a word's varna sequence (unknown varnas skipped)."""
    out, seen = [], set()
    for v in varnas:
        g = (lex.get(v) or {}).get(sphere)
        if g and g not in seen:
            seen.add(g); out.append(g)
    return out


def _derangement(keys: List[str], seed: int) -> Dict[str, str]:
    """Deterministic derangement (no fixed points) of `keys` via a seeded LCG shuffle + rotation fallback."""
    ks = list(keys)
    state = seed + 1
    for i in range(len(ks) - 1, 0, -1):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        j = state % (i + 1)
        ks[i], ks[j] = ks[j], ks[i]
    mapping = {k: ks[i] for i, k in enumerate(keys)}
    for k in list(mapping):                    # remove any fixed points by rotating with the next key
        if mapping[k] == k:
            order = list(keys); idx = order.index(k)
            mapping[k] = order[(idx + 1) % len(order)]
    return mapping


# --------------------------------------------------------------------------------------
# Prompt rendering
# --------------------------------------------------------------------------------------
def render_prompt(arm: str, word: str, varnas: List[str], target_sphere: Optional[str],
                  lex: Dict[str, Dict[str, str]], rand_map: Optional[Dict[str, str]] = None) -> str:
    if arm == "NO_LENS_BASELINE":
        return f"Interpret the word '{word}'.\n\n{OUTPUT_FORMAT}"
    if target_sphere not in PLANE_DESC:
        raise ValueError(f"lens arm {arm} needs a valid target_sphere, got {target_sphere!r}")
    head = (f"Interpret the word '{word}', emphasizing its {PLANE_DESC[target_sphere]} aspects above all "
            f"others. Even if this is not the word's most obvious dimension, commit to the {target_sphere} plane.")
    if arm == "PLAIN_SPHERE_INSTRUCTION":
        return f"{head}\n\n{OUTPUT_FORMAT}"
    if arm == "VARNA_SPHERE_LENS":
        facets = varna_sphere_facets(varnas, target_sphere, lex)
    elif arm == "RANDOMIZED_VARNA_SPHERE":
        rm = rand_map or {}
        facets = varna_sphere_facets([rm.get(v, v) for v in varnas], target_sphere, lex)
    else:
        raise ValueError(f"unknown arm {arm!r}")
    bullets = "\n".join(f"- {f}" for f in facets) or "- (no facets available)"
    return f"{head}\nDraw on these facets of experience:\n{bullets}\n\n{OUTPUT_FORMAT}"


# --------------------------------------------------------------------------------------
# Records + blinding
# --------------------------------------------------------------------------------------
def build_records(targets_doc: Dict, lex: Dict[str, Dict[str, str]], seed: int) -> List[Dict]:
    """One record per (word, arm, lens). NO_LENS has no lens (one per word). Blinded ids assigned in order."""
    rand_map = _derangement(sorted(lex.keys()), seed)
    recs: List[Dict] = []
    n = 0
    for t in targets_doc["targets"]:
        word, varnas = t["TARGET_TEXT"], t["supported_varna_sequence"]
        for arm in LENS_ARMS:
            for lens in LENSES:
                n += 1
                recs.append({
                    "item_id": t["item_id"], "target_text": word, "neutral_context": t.get("neutral_context", ""),
                    "arm": arm, "target_sphere": lens, "native_plane": t["native_plane"],
                    "blinded_output_id": f"L{n:04d}",
                    "prompt": render_prompt(arm, word, varnas, lens, lex, rand_map),
                })
        n += 1
        recs.append({
            "item_id": t["item_id"], "target_text": word, "neutral_context": t.get("neutral_context", ""),
            "arm": "NO_LENS_BASELINE", "target_sphere": None, "native_plane": t["native_plane"],
            "blinded_output_id": f"L{n:04d}", "prompt": render_prompt("NO_LENS_BASELINE", word, varnas, None, lex),
        })
    return recs


ALLOWED_JV_KEYS = {"item_id", "target_text", "neutral_context", "blinded_output_id",
                   "generation_text", "output_format"}


def make_judge_visible(rec: Dict, text: str) -> Dict:
    """B1.6-judge-compatible blind package: word + text only; NO arm, NO target plane, NO varna."""
    pkg = {
        "item_id": rec["item_id"], "target_text": rec["target_text"],
        "neutral_context": rec["neutral_context"], "blinded_output_id": rec["blinded_output_id"],
        "generation_text": text, "output_format": "Title/Interpretation(120-180w)/2 bullets/Caution",
    }
    bad = {"arm", "target_sphere", "native_plane"} & set(pkg.keys())
    if bad:
        raise ValueError(f"INVALID_BLINDING: leaked keys {sorted(bad)}")
    lk = leaked(text)
    if lk:
        raise ValueError(f"INVALID_LEAKAGE: method/varna tokens {lk} in generation_text")
    return pkg


def make_hidden(rec: Dict, gen_code: Optional[str]) -> Dict:
    return {"blinded_output_id": rec["blinded_output_id"], "true_arm": rec["arm"],
            "target_sphere": rec["target_sphere"], "native_plane": rec["native_plane"],
            "item_id": rec["item_id"], "generator_code": gen_code}


# --------------------------------------------------------------------------------------
# Gate
# --------------------------------------------------------------------------------------
def verify_freeze_gate(decl_path: pathlib.Path, expected_mode: str = MODE) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if not decl_path.exists():
        return False, ["no EVIDENCE_FREEZE_DECLARED file (operator must create it)"]
    decl = json.loads(decl_path.read_text())
    for f in REQUIRED_DECL_FIELDS:
        if f not in decl:
            reasons.append(f"missing field: {f}")
    if decl.get("artifact") != "b1_7_perspective_lens_EVIDENCE_FREEZE_DECLARED":
        reasons.append("artifact mismatch")
    if decl.get("evidence_freeze_declared") is not True:
        reasons.append("evidence_freeze_declared != true")
    if decl.get("mode") != expected_mode:
        reasons.append(f"mode != {expected_mode}")
    if decl.get("attestation") != ATTESTATION:
        reasons.append("attestation text mismatch")
    if reasons:
        return False, reasons
    if decl.get("targets_sha256") != _sha_file(TARGETS_FILE):
        reasons.append("targets_sha256 mismatch")
    if decl.get("sphere_lexicon_sha256") != _sha_file(SPHERE_LEXICON_FILE):
        reasons.append("sphere_lexicon_sha256 mismatch")
    return (not reasons), reasons


# --------------------------------------------------------------------------------------
# Generation run (gated, blinded)
# --------------------------------------------------------------------------------------
def _emit(mock, adapter, settings, validate_real):
    if mock:
        def emit(rec):
            h = hashlib.sha256(rec["prompt"].encode()).hexdigest()[:8]
            filler = " ".join(["a measured reading unfolds here plainly"] * 18)
            txt = (f"Title: reading {h}\nInterpretation: {filler} and closes.\n"
                   f"Practical reflection:\n- consider slowly\n- hold lightly\n"
                   f"Caution: one limited, non-authoritative reading.")
            return txt, "mock", []
        return emit, {"backend": "mock", "model_id": "MOCK_ONLY"}
    from b1_6_llm_adapter import generate_with_retry, validate_output_format  # noqa
    def emit(rec):
        return generate_with_retry(adapter, rec["prompt"], settings, validate=validate_real)
    return emit, {**settings.metadata(), "backend": getattr(adapter, "backend", "custom")}


def run(mock: bool = False, adapter=None, settings=None, decl_path: pathlib.Path = None,
        gen_code: Optional[str] = None, out_dir: pathlib.Path = None, write: bool = False,
        limit_items: Optional[int] = None, validate_real: bool = True) -> Dict:
    """Gated blinded generation over all (word x arm x lens) records. Refuses without a valid declaration."""
    if not mock:
        if decl_path is None:
            raise PermissionError("real run requires an evidence-freeze declaration path")
        ok, reasons = verify_freeze_gate(pathlib.Path(decl_path))
        if not ok:
            raise PermissionError("EVIDENCE_FREEZE gate refused: " + "; ".join(reasons))
    settings = settings or A.GenerationSettings()
    targets_doc = json.loads(TARGETS_FILE.read_text())
    if limit_items:
        targets_doc = {**targets_doc, "targets": targets_doc["targets"][:limit_items]}
    lex = load_sphere_varnas()
    records = build_records(targets_doc, lex, targets_doc.get("randomization_seed", 20260709))

    emit, gen_meta = _emit(mock, adapter, settings, validate_real)
    judge_visible, hidden, failures = [], [], []
    for rec in records:
        text, status, rs = emit(rec)
        lk = leaked(text) if (status in ("ok", "mock") and text is not None) else []
        if lk:
            status, rs = "blindness_leak", [f"tokens: {lk}"]
        if status in ("ok", "mock") and text is not None and not lk:
            judge_visible.append(make_judge_visible(rec, text))
            hidden.append(make_hidden(rec, gen_code))
        else:
            failures.append({"blinded_output_id": rec["blinded_output_id"], "status": status, "reasons": rs})

    manifest = {
        "artifact_type": "b1_7_perspective_lens_run_manifest",
        "mode": "MOCK" if mock else "REAL", "run_label": "B1_7_PERSPECTIVE_LENS_PROBE",
        "arms": list(ARMS), "lenses": list(LENSES),
        "n_records": len(records), "n_success": len(judge_visible), "n_failures": len(failures),
        "failures": failures, "generator_meta": gen_meta, "generator_code": gen_code,
        "judging_performed": False, "unblinded": False, "b1_4b_prime_status": B1_4B_PRIME_STATUS,
        "targets_sha256": _sha_file(TARGETS_FILE), "sphere_lexicon_sha256": _sha_file(SPHERE_LEXICON_FILE),
        "note": "Perspective-lens probe. Blind package is B1.6-judge compatible. No GENUTILITY_* label.",
    }
    if write and out_dir:
        out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "panel_judge_visible_outputs.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in judge_visible) + "\n")
        (out_dir / "panel_hidden_lens_metadata.json").write_text(json.dumps(hidden, ensure_ascii=False, indent=2))
        (out_dir / "perspective_lens_run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return {"manifest": manifest, "judge_visible": judge_visible, "hidden": hidden}


# --------------------------------------------------------------------------------------
# Controllability: a BLIND plane-guesser
# --------------------------------------------------------------------------------------
def build_guess_prompt(item: Dict) -> str:
    return (f"Read this interpretation of the word '{item['target_text']}'. Which SINGLE plane of experience "
            f"does it most emphasize? Choose exactly one of: physical, mental, intellectual, spiritual.\n\n"
            f"Interpretation:\n{item['generation_text']}\n\n"
            f"Answer with ONLY one word: physical, mental, intellectual, or spiritual.")


def parse_guess(text: str) -> Optional[str]:
    t = (text or "").lower()
    for p in LENSES:                    # first plane word that appears
        if re.search(rf"(?<![a-z]){p}(?![a-z])", t):
            return p
    return None


class FakeGuesser:
    """Deterministic test guesser. NO model, NO network. Returns a plane keyed on the prompt hash; if the
    interpretation text carries a '[[plane:X]]' marker it reads X (lets a mock simulate a controllable dial)."""
    is_real = False
    backend = "fake"

    def __init__(self, malformed: bool = False):
        self.malformed = malformed

    def generate(self, prompt: str, settings=None) -> str:
        if self.malformed:
            return "unsure"
        m = re.search(r"\[\[plane:(physical|mental|intellectual|spiritual)\]\]", prompt)
        if m:
            return m.group(1)
        h = int(hashlib.sha256(prompt.encode()).hexdigest(), 16)
        return LENSES[h % 4]


def run_guesser(judge_visible_file: pathlib.Path, adapter, settings=None,
                limit: Optional[int] = None, out_dir: pathlib.Path = None, write: bool = False) -> Dict:
    """One blind guesser over the blind package. Reads ONLY blind fields; retries unparseable guesses."""
    items = [json.loads(l) for l in pathlib.Path(judge_visible_file).read_text().splitlines() if l.strip()]
    ok, reasons = G_check_blind(items)
    if not ok:
        raise ValueError(f"INVALID_BLINDING: {reasons[:3]}")
    items = sorted(items, key=lambda r: r["blinded_output_id"])
    if limit:
        items = items[:limit]
    settings = settings or A.GenerationSettings(max_tokens=16, temperature=0.0, max_attempts=5)

    def _guess_ok(t):
        return parse_guess(t) is not None, ([] if parse_guess(t) else ["no plane word"])
    guesses, errors = [], []
    for it in items:
        text, status, rs = A.generate_with_retry(adapter, build_guess_prompt(it), settings,
                                                  validate=True, validator=_guess_ok)
        g = parse_guess(text) if text is not None else None
        if g is None:
            errors.append({"blinded_output_id": it["blinded_output_id"], "reasons": rs or ["unparseable"]})
        else:
            guesses.append({"blinded_output_id": it["blinded_output_id"], "guess": g})
    part = {"artifact_type": "b1_7_controllability_part", "n_guesses": len(guesses),
            "n_errors": len(errors), "guesses": guesses, "errors": errors,
            "reads_hidden_metadata": False, "unblinded": False, "b1_4b_prime_status": B1_4B_PRIME_STATUS}
    if write and out_dir:
        out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "controllability_part.json").write_text(json.dumps(part, ensure_ascii=False, indent=2))
    return part


def G_check_blind(items: List[Dict]) -> Tuple[bool, List[str]]:
    reasons = []
    for i, pkg in enumerate(items):
        extra = set(pkg.keys()) - ALLOWED_JV_KEYS
        if extra:
            reasons.append(f"[{i}] unexpected key(s): {sorted(extra)}")
        for tok in leaked(str(pkg.get("generation_text", ""))):
            reasons.append(f"[{i}] forbidden token {tok!r}")
    return (not reasons), reasons


def aggregate_controllability(guesses: List[Dict], hidden: List[Dict]) -> Dict:
    """Unblind ONLY here. Per lens-arm: accuracy of the blind guess vs the true target plane (chance 0.25)."""
    tgt = {m["blinded_output_id"]: m["target_sphere"] for m in hidden}
    arm = {m["blinded_output_id"]: m["true_arm"] for m in hidden}
    per_arm: Dict[str, Dict] = {a: {"n": 0, "correct": 0, "confusion": {}} for a in LENS_ARMS}
    for g in guesses:
        bid = g["blinded_output_id"]; a = arm.get(bid); t = tgt.get(bid)
        if a not in per_arm or t is None:            # skip NO_LENS (no target) / unknown
            continue
        d = per_arm[a]; d["n"] += 1
        d["correct"] += int(g["guess"] == t)
        d["confusion"].setdefault(t, {}).setdefault(g["guess"], 0)
        d["confusion"][t][g["guess"]] += 1
    summary = {}
    for a, d in per_arm.items():
        summary[a] = {"n": d["n"], "accuracy": round(d["correct"] / d["n"], 4) if d["n"] else None,
                      "chance": 0.25, "confusion": d["confusion"]}
    return {"label": "B1_7_PROBE_CONTROLLABILITY_READY_MOCK_TESTED",
            "controllability_by_arm": summary, "unblinded": True,
            "b1_4b_prime_status": B1_4B_PRIME_STATUS,
            "note": "Controllability is descriptive plumbing; NOT a terminal verdict; varna meaning NOT validated."}
