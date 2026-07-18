"""B1.9 content-level semantic-distance runner (generation-free, judge-free; gated; mock-tested).

Tests whether a word's OWN varṇa facet aggregate is closer in embedding space to the target word/context than
preregistered control facet aggregates. NO generation, NO LLM judges, NO human judges, NO output ratings, NO
run_out/ reads. Real execution requires a B1.9 declaration and a pinned embedding model; tests use a Fake
embedding backend and never download. Emits only B1_9_CONTENT_DISTANCE_RUNNER_READY_MOCK_TESTED — never a
terminal/ontology/GENUTILITY label. B1.4b' remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import pathlib
import random
import re
from typing import Dict, List, Optional, Tuple

B1_4B_PRIME_STATUS = "NULL_RETURN_BOTTOM"
HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"

PREREG_FILE = HERE / "B1_9_CONTENT_LEVEL_SEMANTIC_DISTANCE_PREREG.md"
FACET_TABLE_FILE = HERE / "track_g_varna_polarity_table_v2_named_vritti.json"
TARGETS_FILE = FROZEN / "b1_9_targets.json"
SAMPLER_CFG_FILE = FROZEN / "b1_9_control_sampler_config.json"
PREPROC_CFG_FILE = FROZEN / "b1_9_preprocessing_config.json"
EMBED_CFG_FILE = FROZEN / "b1_9_embedding_config.json"
OUT_OF_POOL_FILE = FROZEN / "b1_9_out_of_pool_lexicon.json"

MODE = "b1_9_content_level_semantic_distance"
REPRESENTATION = "B1.9_content_distance_prereg"
PREREG_LABEL = "B1_9_CONTENT_DISTANCE_PREREG_READY"
RUNNER_LABEL = "B1_9_CONTENT_DISTANCE_RUNNER_READY_MOCK_TESTED"
ATTESTATION = ("B1.9 content-level semantic-distance test only; no generation; no judging; no GENUTILITY "
               "terminal label; no ontology claim; B1.4b′ remains NULL_RETURN_BOTTOM.")

HASH_INPUTS = {
    "prereg_sha256": PREREG_FILE, "facet_table_sha256": FACET_TABLE_FILE,
    "targets_sha256": TARGETS_FILE, "control_sampler_config_sha256": SAMPLER_CFG_FILE,
    "preprocessing_config_sha256": PREPROC_CFG_FILE, "embedding_config_sha256": EMBED_CFG_FILE,
    "out_of_pool_lexicon_sha256": OUT_OF_POOL_FILE,
}
REQUIRED_DECL_FIELDS = ("artifact", "b1_9_declared", "mode", "representation_version",
                        "declared_by", "declared_at_utc", "attestation", *HASH_INPUTS.keys())

CONTROL_FAMILIES = ("distant_source_word_mapping", "out_of_pool_lexicon_facet",
                    "same_polarity_random_varna_facet", "same_plane_random_varna_facet",
                    "frequency_length_matched_facet", "completely_random_facet",
                    "permuted_target_label", "random_word_context_decoy")
BAD_MODES = {"pilot_generation", "exploratory_10_sample_generation_probe", "pilot_judging",
             "b1_8_context_resolved_generation_probe"}


def _sha_file(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


# --------------------------------------------------------------------------------------
# Gate
# --------------------------------------------------------------------------------------
def verify_declaration(decl_path: pathlib.Path) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if not pathlib.Path(decl_path).exists():
        return False, ["no B1.9 declaration file (operator must create it)"]
    try:
        decl = json.loads(pathlib.Path(decl_path).read_text())
    except Exception as e:  # noqa: BLE001
        return False, [f"declaration not valid JSON: {e}"]
    for f in REQUIRED_DECL_FIELDS:
        if f not in decl:
            reasons.append(f"missing required field: {f}")
    if decl.get("artifact") != "b1_9_content_distance_DECLARED":
        reasons.append("artifact != b1_9_content_distance_DECLARED")
    if decl.get("b1_9_declared") is not True:
        reasons.append("b1_9_declared != true")
    if decl.get("mode") in BAD_MODES:
        reasons.append(f"refused: B1.6/B1.8 mode supplied ({decl.get('mode')!r})")
    if decl.get("mode") != MODE:
        reasons.append(f"mode != {MODE} (got {decl.get('mode')!r})")
    if decl.get("representation_version") != REPRESENTATION:
        reasons.append(f"representation_version != {REPRESENTATION} (got {decl.get('representation_version')!r})")
    if decl.get("attestation") != ATTESTATION:
        reasons.append("attestation text mismatch")
    if reasons:
        return False, reasons
    for field, path in HASH_INPUTS.items():
        if not path.exists():
            reasons.append(f"frozen input missing: {path.name}")
        elif decl.get(field) != _sha_file(path):
            reasons.append(f"{field} mismatch (wrong-track/representation declaration is refused)")
    return (not reasons), reasons


# --------------------------------------------------------------------------------------
# Frozen loading + preprocessing
# --------------------------------------------------------------------------------------
def load_frozen() -> Dict:
    return {
        "targets": json.loads(TARGETS_FILE.read_text()),
        "facets": json.loads(FACET_TABLE_FILE.read_text())["varnas"],
        "sampler": json.loads(SAMPLER_CFG_FILE.read_text()),
        "preproc": json.loads(PREPROC_CFG_FILE.read_text()),
        "embed": json.loads(EMBED_CFG_FILE.read_text()),
        "out_of_pool": json.loads(OUT_OF_POOL_FILE.read_text()),
    }


def normalize(text: str, preproc: Dict) -> str:
    s = text or ""
    if preproc.get("casing") == "lower":
        s = s.lower()
    if preproc.get("punctuation") == "strip_to_space":
        s = re.sub(r"[^\w\s'-]", " ", s)   # diacritics kept (\w is unicode-aware)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def target_rep(item: Dict, preproc: Dict) -> str:
    return normalize(item["target_text"] + ". " + item.get("context_text", ""), preproc)


def _varna_facet_text(varna: str, facets: Dict, preproc: Dict, plane: Optional[str] = None) -> str:
    e = facets.get(varna)
    if not e:
        return ""
    if plane is not None:
        return normalize((e.get("spheres") or {}).get(plane, ""), preproc)
    fields = preproc.get("facet_fields", ["named_attribute"])
    return normalize(preproc.get("facet_join", " ; ").join(str(e.get(f, "")) for f in fields), preproc)


def _supported_varnas(item: Dict, facets: Dict) -> List[str]:
    seq = item["varna_sequence"]
    out = []
    for v in seq:
        key = v.get("varna") if isinstance(v, dict) else v
        if key and key in facets and key not in out:
            out.append(key)
    return out


def facet_aggregate(varnas: List[str], facets: Dict, preproc: Dict, plane: Optional[str] = None) -> str:
    texts = [t for t in (_varna_facet_text(v, facets, preproc, plane) for v in varnas) if t]
    return preproc.get("facet_join", " ; ").join(texts)


# --------------------------------------------------------------------------------------
# Embedding backends (real placeholder + deterministic fake for tests)
# --------------------------------------------------------------------------------------
class FakeEmbedding:
    """Deterministic, NO model, NO network. Optional `mapping` fixes vectors for specific normalized texts so
    tests can control distances; otherwise a stable hash-based unit vector is used."""
    is_real = False
    backend = "fake"

    def __init__(self, mapping: Optional[Dict[str, List[float]]] = None, dim: int = 16):
        self.mapping = mapping or {}
        self.dim = dim

    def _vec(self, text: str) -> List[float]:
        if text in self.mapping:
            v = list(self.mapping[text])
        else:
            h = hashlib.sha256(text.encode()).digest()
            v = [((h[i % len(h)] / 255.0) * 2 - 1) for i in range(self.dim)]
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [self._vec(t) for t in texts]


class TransformersEmbedding:
    """REAL backend — loads the pinned model from the frozen embedding config. Never invoked in tests; fails
    LOUDLY if the model/config is missing rather than silently substituting a different model."""
    is_real = True
    backend = "transformers"

    def __init__(self, embed_cfg: Dict):
        import torch  # noqa
        from transformers import AutoTokenizer, AutoModel
        self.cfg = embed_cfg
        self.tok = AutoTokenizer.from_pretrained(embed_cfg["model"], revision=embed_cfg.get("revision"))
        self.model = AutoModel.from_pretrained(embed_cfg["model"], revision=embed_cfg.get("revision")).eval()

    def embed(self, texts: List[str]) -> List[List[float]]:
        import torch
        with torch.no_grad():
            enc = self.tok(texts, padding=True, truncation=True,
                           max_length=self.cfg.get("max_length", 256), return_tensors="pt")
            out = self.model(**enc)
            mask = enc["attention_mask"].unsqueeze(-1).float()
            v = (out.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            if self.cfg.get("normalize", True):
                v = torch.nn.functional.normalize(v, p=2, dim=1)
        return v.tolist()


def build_embedding(embed_cfg: Dict, fake: bool = False, mapping=None):
    if fake:
        return FakeEmbedding(mapping=mapping)
    return TransformersEmbedding(embed_cfg)   # loud failure if model absent


def _cos_dist(a: List[float], b: List[float]) -> float:
    return 1.0 - sum(x * y for x, y in zip(a, b))


# --------------------------------------------------------------------------------------
# Control families
# --------------------------------------------------------------------------------------
FAMILY_STATUS = {
    "distant_source_word_mapping": ("IMPLEMENTED",
        "PRIMARY (corrected control). Control = a DIFFERENT real source word W′'s OWN complete authentic "
        "varṇa-derived facet aggregate (same construction/register as authentic). W′ is frozen as the item whose "
        "target/context embedding is MOST DISTANT from W's — selected using target/context embeddings ONLY, "
        "never facet embeddings or outcome distances (anti-circular). Endpoint delta = d(target(W),facets(W′)) − "
        "d(target(W),facets(W)); positive favors W's own mapping. W′ pool = the frozen B1.9 target set."),
    "out_of_pool_lexicon_facet": ("IMPLEMENTED",
        "SECONDARY (external-register control). Control facets drawn from the frozen out-of-pool lexicon "
        "(b1_9_out_of_pool_lexicon.json), which reuses NO varṇa→meaning mapping. Carries a register caveat "
        "(concrete/sensory vs abstract-psychological); an extra control, NOT the main correction."),
    "same_polarity_random_varna_facet": ("BLOCKED_NOT_AVAILABLE",
        "polarity requires a resolver/pole selection; B1.9 is resolver-free and uses neutral named_attribute "
        "facets — no polarity dimension. Reintroducing poles would reintroduce the resolver confound."),
    "same_plane_random_varna_facet": ("IMPLEMENTED", "uses per-item plane sphere gloss for authentic and controls."),
    "frequency_length_matched_facet": ("IMPLEMENTED_LENGTH_ONLY",
        "length-matched controls implemented; word-frequency matching unavailable (no corpus frequencies)."),
    "completely_random_facet": ("IMPLEMENTED",
        "within-pool: random OTHER varṇas' facets (same 25-varṇa pool). Retained as a secondary/triangulation "
        "control; superseded as primary by out_of_pool_lexicon_facet."),
    "permuted_target_label": ("IMPLEMENTED", "authentic facet of a permuted item (null-distribution control)."),
    "random_word_context_decoy": ("IMPLEMENTED", "authentic facet vs a decoy target/context."),
}


def _rng(seed: int, *parts) -> random.Random:
    h = hashlib.sha256(("|".join([str(seed), *map(str, parts)])).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def _sample_control_varnas(item_id: str, exclude: List[str], all_varnas: List[str], k: int,
                           seed: int, family: str, length_match_to: Optional[int] = None,
                           facets=None, preproc=None) -> List[str]:
    pool = [v for v in all_varnas if v not in exclude]
    rng = _rng(seed, family, item_id)
    if length_match_to is not None and facets is not None:
        scored = sorted(pool, key=lambda v: abs(len(_varna_facet_text(v, facets, preproc)) - length_match_to))
        pool = scored[:max(k * 3, k)]                # nearest-length band, then sample
        rng.shuffle(pool)
        return pool[:k]
    rng.shuffle(pool)
    return pool[:k]


def _sample_out_of_pool(item_id: str, glosses: List[str], k: int, seed: int) -> List[str]:
    """Sample K glosses from the frozen OUT-OF-POOL lexicon (reuses NO varṇa mapping). Deterministic; never
    references d_auth or any outcome. Mirrors _sample_control_varnas so out-of-pool vs within-pool is an
    apples-to-apples swap of the content SOURCE only."""
    pool = list(glosses)
    rng = _rng(seed, "out_of_pool_lexicon_facet", item_id)
    rng.shuffle(pool)
    return pool[:k]


def _freeze_distant_source_map(items: List[Dict], preproc: Dict, backend) -> Dict[str, str]:
    """Freeze the W -> W′ assignment for the distant_source_word_mapping control, using ONLY target/context
    embeddings — never facet embeddings, never any outcome/d_auth distance (anti-circular, §6). For each target
    W, W′ is the DIFFERENT item whose target/context representation is MOST DISTANT from W's. Deterministic:
    ascending index scan, strict-greater update keeps the lowest-index winner on ties. Returns {W_id: W′_id}."""
    reps = [target_rep(it, preproc) for it in items]     # target/context representation ONLY
    embs = backend.embed(reps)
    mapping: Dict[str, str] = {}
    for i, it in enumerate(items):
        best_j, best_d = None, -1.0
        for j in range(len(items)):
            if j == i:
                continue
            d = _cos_dist(embs[i], embs[j])
            if d > best_d:
                best_d, best_j = d, j
        mapping[it["item_id"]] = items[best_j]["item_id"]
    return mapping


# --------------------------------------------------------------------------------------
# Distance computation (paired; anti-circular)
# --------------------------------------------------------------------------------------
def determine_refusals(items: List[Dict], family: str, frozen: Dict, backend,
                       constraint: Dict) -> Dict[str, str]:
    """REFUSE_UNSEPARABLE computed BEFORE any outcome (delta) analysis. Uses ONLY control-pool distance to the
    target — NEVER d_auth. Returns {item_id: reason} for refused items."""
    refusals: Dict[str, str] = {}
    if not (constraint.get("enabled") and family in constraint.get("applies_to", [])):
        return refusals
    facets, preproc = frozen["facets"], frozen["preproc"]
    all_varnas = list(facets.keys())
    tau = constraint.get("min_control_target_distance", 0.30)
    k = frozen["sampler"]["K"]; seed = frozen["sampler"]["seed"]
    for it in items:
        auth_v = _supported_varnas(it, facets)
        cand = [v for v in all_varnas if v not in auth_v]
        t_emb = backend.embed([target_rep(it, preproc)])[0]
        c_embs = backend.embed([facet_aggregate([v], facets, preproc) for v in cand])
        far = [v for v, e in zip(cand, c_embs) if _cos_dist(t_emb, e) >= tau]   # control-to-target only
        if len(far) < k:
            refusals[it["item_id"]] = "REFUSE_UNSEPARABLE"
    return refusals


def compute_family(items: List[Dict], family: str, frozen: Dict, backend) -> Dict:
    status, note = FAMILY_STATUS[family]
    if status.startswith("BLOCKED"):
        return {"family": family, "status": status, "reason": note, "deltas": [], "per_item": []}
    facets, preproc, sampler = frozen["facets"], frozen["preproc"], frozen["sampler"]
    all_varnas = list(facets.keys())
    k, seed = sampler["K"], sampler["seed"]
    constraint = sampler.get("prospective_distance_constraint", {})
    refusals = determine_refusals(items, family, frozen, backend, constraint)   # BEFORE outcomes
    # W -> W′ frozen from target/context distance ONLY, before any facet/outcome distance (anti-circular)
    distant_map = (_freeze_distant_source_map(items, preproc, backend)
                   if family == "distant_source_word_mapping" else None)

    per_item, deltas = [], []
    for i, it in enumerate(items):
        if it["item_id"] in refusals:
            per_item.append({"item_id": it["item_id"], "status": "REFUSE_UNSEPARABLE"})
            continue
        auth_v = _supported_varnas(it, facets)
        plane = it.get("plane") if family == "same_plane_random_varna_facet" else None
        t_emb = backend.embed([target_rep(it, preproc)])[0]
        a_emb = backend.embed([facet_aggregate(auth_v, facets, preproc, plane)])[0]
        d_auth = _cos_dist(t_emb, a_emb)

        if family == "distant_source_word_mapping":
            src_id = distant_map[it["item_id"]]                         # frozen W′ (target/context-distance only)
            src_it = next(x for x in items if x["item_id"] == src_id)
            src_v = _supported_varnas(src_it, facets)                   # W′'s OWN authentic varṇa mapping
            c_emb = backend.embed([facet_aggregate(src_v, facets, preproc)])[0]
            d_control = _cos_dist(t_emb, c_emb)
            delta = d_control - d_auth                                  # positive favors W's own mapping
            deltas.append(delta)
            per_item.append({"item_id": it["item_id"], "source_word_id": src_id,
                             "d_auth": round(d_auth, 4), "d_control": round(d_control, 4),
                             "delta_distance": round(delta, 4)})
            continue
        if family == "out_of_pool_lexicon_facet":
            glosses = _sample_out_of_pool(it["item_id"], frozen["out_of_pool"]["glosses"], k, seed)
            c_embs = [backend.embed([normalize(g, preproc)])[0] for g in glosses]   # content NOT from varṇa pool
        elif family == "permuted_target_label":
            j = (i + 1 + _rng(seed, family, it["item_id"]).randint(0, max(len(items) - 2, 0))) % len(items)
            if j == i:
                j = (i + 1) % len(items)
            ov = _supported_varnas(items[j], facets)
            c_embs = [backend.embed([facet_aggregate(ov, facets, preproc)])[0]]
        elif family == "random_word_context_decoy":
            rng = _rng(seed, family, it["item_id"])
            others = [x for x in items if x["item_id"] != it["item_id"]]
            rng.shuffle(others)
            d_ctrls = []
            for dec in others[:k]:
                dec_emb = backend.embed([target_rep(dec, preproc)])[0]
                d_ctrls.append(_cos_dist(dec_emb, a_emb))   # authentic facet vs decoy target
            d_control = sum(d_ctrls) / len(d_ctrls)
            delta = d_control - d_auth
            deltas.append(delta)
            per_item.append({"item_id": it["item_id"], "d_auth": round(d_auth, 4),
                             "d_control": round(d_control, 4), "delta_distance": round(delta, 4)})
            continue
        else:  # completely_random / length_matched / same_plane
            lm = len(facet_aggregate(auth_v, facets, preproc)) if family == "frequency_length_matched_facet" else None
            cv = _sample_control_varnas(it["item_id"], auth_v, all_varnas, k, seed, family,
                                        length_match_to=lm, facets=facets, preproc=preproc)
            c_embs = [backend.embed([facet_aggregate([v], facets, preproc, plane)])[0] for v in cv]

        d_control = sum(_cos_dist(t_emb, ce) for ce in c_embs) / len(c_embs)
        delta = d_control - d_auth                       # positive favors authentic
        deltas.append(delta)
        per_item.append({"item_id": it["item_id"], "d_auth": round(d_auth, 4),
                         "d_control": round(d_control, 4), "delta_distance": round(delta, 4)})

    return {"family": family, "status": status, "reason": note,
            "n_items": len(deltas), "n_refused": len(refusals),
            "deltas": deltas, "per_item": per_item, **statistics(deltas, seed)}


# --------------------------------------------------------------------------------------
# Statistics (paired item deltas; skeleton)
# --------------------------------------------------------------------------------------
def statistics(deltas: List[float], seed: int = 0, n_boot: int = 1000) -> Dict:
    n = len(deltas)
    if n == 0:
        return {"mean_delta": None, "median_delta": None, "sign_pos": 0, "sign_neg": 0,
                "bootstrap_ci95": [None, None], "sign_test_p": None, "permutation_p": None}
    mean = sum(deltas) / n
    srt = sorted(deltas)
    median = srt[n // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
    pos = sum(1 for d in deltas if d > 0); neg = sum(1 for d in deltas if d < 0)
    # bootstrap CI (fixed seed)
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(deltas) for _ in range(n)) / n for _ in range(n_boot))
    lo, hi = means[int(0.025 * n_boot)], means[min(int(0.975 * n_boot), n_boot - 1)]
    # exact two-sided sign test on decisive items
    dec = pos + neg
    def binom_p(k, m):
        from math import comb
        tail = sum(comb(m, i) for i in range(k, m + 1)) / (2 ** m)
        return min(1.0, 2 * tail)
    sign_p = binom_p(max(pos, neg), dec) if dec else None
    # permutation p: sign-flip permutation on the mean (fixed seed)
    rng2 = random.Random(seed + 1)
    obs = abs(mean); ge = 0
    for _ in range(n_boot):
        m = sum(d if rng2.random() < 0.5 else -d for d in deltas) / n
        ge += abs(m) >= obs
    perm_p = ge / n_boot
    return {"mean_delta": round(mean, 4), "median_delta": round(median, 4), "sign_pos": pos, "sign_neg": neg,
            "bootstrap_ci95": [round(lo, 4), round(hi, 4)], "sign_test_p": None if sign_p is None else round(sign_p, 4),
            "permutation_p": round(perm_p, 4)}


# --------------------------------------------------------------------------------------
# Run (all families) — mock by default; real requires declaration
# --------------------------------------------------------------------------------------
def run(mock: bool = True, decl_path: Optional[pathlib.Path] = None, backend=None,
        out_dir: Optional[pathlib.Path] = None, write: bool = False) -> Dict:
    frozen = load_frozen()
    if not mock:
        if decl_path is None:
            raise PermissionError("real B1.9 run requires a declaration path")
        ok, reasons = verify_declaration(pathlib.Path(decl_path))
        if not ok:
            raise PermissionError("B1.9 declaration refused: " + "; ".join(reasons))
        backend = backend or build_embedding(frozen["embed"], fake=False)
    else:
        backend = backend or build_embedding(frozen["embed"], fake=True)

    items = frozen["targets"]["targets"]
    families = {fam: compute_family(items, fam, frozen, backend) for fam in CONTROL_FAMILIES}
    thr = frozen["sampler"].get("success_threshold", {})
    prim = frozen["sampler"].get("primary_family")
    manifest = {
        "artifact_type": "b1_9_content_distance_manifest", "mode": "MOCK" if mock else "REAL",
        "readiness_label": RUNNER_LABEL, "representation_version": REPRESENTATION,
        "primary_family": prim, "n_targets": len(items),
        "control_family_status": {f: FAMILY_STATUS[f][0] for f in CONTROL_FAMILIES},
        "success_threshold": thr, "endpoint": "delta_distance = d_control - d_auth (positive favors authentic)",
        "backend": getattr(backend, "backend", "unknown"),
        "input_hashes": {k: _sha_file(v) for k, v in HASH_INPUTS.items()},
        "declaration_sha256": _sha_file(pathlib.Path(decl_path)) if (decl_path and not mock) else None,
        "b1_4b_prime_status": B1_4B_PRIME_STATUS, "terminal_result_label_emitted": False,
        "note": "Content-level only. No generation. No judging. No experiment-output reads. No terminal/ontology/GENUTILITY label.",
    }
    # threshold is reported as DATA only (no terminal label emitted)
    pm = families.get(prim, {})
    manifest["primary_threshold_met"] = bool(
        pm.get("mean_delta") is not None and thr.get("min_mean_delta") is not None
        and pm["mean_delta"] >= thr["min_mean_delta"])
    res = {"label": RUNNER_LABEL, "manifest": manifest, "families": families}
    if write and out_dir:
        out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "b1_9_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        (out_dir / "b1_9_family_summaries.json").write_text(json.dumps(
            {f: {k: v for k, v in d.items() if k != "deltas"} for f, d in families.items()}, ensure_ascii=False, indent=2))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.9 content-level semantic-distance runner (gated; mock-tested).")
    ap.add_argument("--mock", action="store_true", help="fake embeddings; no model, no gate")
    ap.add_argument("--decl", help="B1.9 declaration (required for real run)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    res = run(mock=args.mock, decl_path=pathlib.Path(args.decl) if args.decl else None,
              out_dir=pathlib.Path(args.out), write=True)
    print(json.dumps({"label": res["label"], "mode": res["manifest"]["mode"],
                      "family_status": res["manifest"]["control_family_status"],
                      "primary": res["manifest"]["primary_family"]}, indent=2))


if __name__ == "__main__":
    main()
