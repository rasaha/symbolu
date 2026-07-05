#!/usr/bin/env python3
"""B1.1 8-ARM GENERATION RUNNER — RENDER-ONLY SAFE; real generation HARD-GATED.

Builds the 8 frozen B1.1 arms (A / D / S / R_same / R_deranged / R_domain / C / X) from the FROZEN
artifact set and renders the exact prompts a model *would* receive. In the default `--render-only`
mode it calls NO model, downloads nothing, and does NO judging/scoring — it only renders prompts,
hashes them, and leak-scans them. Real generation is gated behind THREE independent locks (all
required): `--execute-generation`, `B1_1_GENERATION_APPROVED=YES` in the environment, and a
model-access host (CUDA + transformers). In THIS environment the HuggingFace egress denial makes real
generation impossible, and the runner refuses loudly BEFORE any model is contacted.

Integrity discipline (B0/B1 style):
  * The FROZEN freeze manifest (`b1_1_freeze_manifest.json`) is verified FIRST by re-hashing every
    bound artifact. ANY hash mismatch -> INVALID_POSTHOC, refuse to run (render or generate).
  * Only the FROZEN configs are loaded for arm construction (bridge pool, arm-construction, seeds,
    generation, leak/packet). Deterministic seeds come from the frozen seeds config.
  * A uses the REAL G2P->varṇa pipeline (varna_lens.phonemes_cmudict) over the target word, then the
    FROZEN B1.1 bridge pool. No post-hoc prompt edits; no arm-specific decoding.

Non-claims: this runner does NOT authorize generation, does NOT change the B1 verdict
(RANDOM_OR_SCRAMBLED_MATCHES), does NOT unblock Track B (BLOCKED). Rendering is structural only and is
NOT evidence that B1.1 works. R_deranged remains the crux. Structure, not validated meaning.

HONEST FREEZE-COVERAGE GAPS surfaced by this build (reported, NOT silently resolved; these do NOT
block render-only validation but MUST be pinned in a frozen artifact before the real RunPod run):
  G1  A-composition policy (which pole per varṇa, cap, separator) is NOT pinned in the frozen
      arm-construction config. This runner uses the varna_lens vowel-attachment polarity rule + a
      ' ; ' separator + no cap. Deterministic, but a design choice, not a frozen one.
  G2  contrast_boundary (frozen config says "preserve") CANNOT be rendered into model-facing text: it
      names other varṇas (e.g. "not object-renunciation (Gha)") and would LEAK the mapping. It is kept
      in metadata only, never in the prompt. The config wording cannot be applied literally.
  G3  R_domain bucket maps (word->native-bucket and bridge->bucket) are NOT frozen. This runner uses a
      documented BUILD-TIME keyword heuristic so the render is fluent and leak-checkable, and flags
      R_domain as NOT_FULLY_SPECIFIED_BY_FROZEN_CONFIG.
  G4  The word/task pool lives in the committed (but NOT frozen) b1_dry_run_harness.py, and D/C/X reuse
      the committed (NOT frozen) b1_real_conditioning.py D-table / surface facts / neutral filler.

Usage:
  # default: safe render-only structural validation (no model, no network)
  python3 experiments/primitive_sequence_recovery/run_b1_1_generation.py --render-only \
      --json-out .../B1_1_GENERATION_RENDER_ONLY_REPORT.json \
      --md-out   .../B1_1_GENERATION_RENDER_ONLY_REPORT.md

  # real generation (RunPod / model-access host ONLY; refuses here):
  B1_1_GENERATION_APPROVED=YES python3 .../run_b1_1_generation.py --execute-generation --out raw.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "varna_lens"))
sys.path.insert(0, str(HERE))
import varna_lens as V                 # noqa: E402  real G2P->varṇa pipeline (committed)
import b1_dry_run_harness as B         # noqa: E402  committed word/task pool + WRAPPER (NOT frozen)
import b1_real_conditioning as RC      # noqa: E402  committed D-table / surface / neutral (NOT frozen)

MANIFEST = HERE / "b1_1_freeze_manifest.json"
ARMS = ("A", "D", "S", "R_same", "R_deranged", "R_domain", "C", "X")


# ============================================================ integrity gate ======================
def verify_frozen_or_abort():
    """Re-hash every bound artifact in the FROZEN manifest. Abort INVALID_POSTHOC on any mismatch."""
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))["B1_1_FREEZE_MANIFEST"]
    if man.get("manifest_status") != "FROZEN":
        raise SystemExit(f"ABORT: manifest_status is {man.get('manifest_status')!r}, not FROZEN.")
    bad = []
    for art in man["bound_artifacts"]:
        p = REPO / art["path"]
        if not p.exists():
            bad.append(f"missing {art['path']}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != art["sha256"]:
            bad.append(f"HASH MISMATCH {art['path']}")
    if bad:
        raise SystemExit("ABORT INVALID_POSTHOC: frozen artifact(s) changed since freeze:\n  "
                         + "\n  ".join(bad))
    if man.get("generation_authorized") is not False:
        raise SystemExit("ABORT: manifest generation_authorized is not False.")
    print(f"[ok] frozen manifest verified: all {len(man['bound_artifacts'])} bound artifacts match "
          f"(freeze base {man['finalization']['finalized_commit_base'][:10]}).")
    return man


def load_frozen_configs(man):
    """Load ONLY the frozen artifacts (paths taken from the verified manifest)."""
    by_name = {pathlib.Path(a["path"]).name: REPO / a["path"] for a in man["bound_artifacts"]}

    def _load(name):
        if name not in by_name:
            raise SystemExit(f"ABORT: frozen artifact {name} not in the manifest bound set.")
        return json.loads(by_name[name].read_text(encoding="utf-8"))

    return {
        "bridge_pool": _load("b1_1_bridge_pool_draft.json"),
        "arm_config": _load("b1_1_arm_construction_config.json"),
        "seeds": _load("b1_1_seeds_config.json"),
        "generation": _load("b1_1_generation_config.json"),
        "leak_packet": _load("b1_1_leak_and_packet_config.json"),
        "lexicon": _load("b1_1_experimental_contrastive_lexicon_draft.json"),
    }


# ============================================================ arm construction ====================
class ArmBuilder:
    """Deterministic 8-arm builder over the FROZEN bridge pool + FROZEN seeds. No model, no network."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.seeds = cfg["seeds"]
        pool = cfg["bridge_pool"]["entries"]
        # lexicon_key -> {varna, binding_bridge, liberating_bridge}
        self.pool = {e["lexicon_key"]: {"varna": e["varna"],
                                        "binding": e["binding_bridge"],
                                        "liberating": e["liberating_bridge"]}
                     for e in pool}
        self.all_bridges = []            # (lexicon_key, pole, text) over all 34x2 = 68 phrases
        for e in pool:
            self.all_bridges.append((e["lexicon_key"], "binding", e["binding_bridge"]))
            self.all_bridges.append((e["lexicon_key"], "liberating", e["liberating_bridge"]))
        self.words = list(B.PRIMARY_WORDS) + list(B.PRIVATIVE_WORDS)
        self._derangement = self._build_derangement()
        self._bridge_bucket = self._bucket_bridges()          # G3 build-time heuristic (flagged)

    # -- real G2P->varṇa + vowel-attachment polarity (varna_lens rule) --------------------------
    def varna_poles(self, word):
        """Return [(lexicon_key, pole, surface)] for the word's CONSONANT varṇas via real G2P.

        Polarity is the varna_lens.read_op vowel-attachment rule (structural, referent-blind):
          * the word's FIRST consonant -> binding (worldly seed)
          * a consonant with a vowel immediately after (onset) -> liberating
          * a bare consonant (word-final / pre-consonant) -> binding
          * doubled consonant: 1st occurrence -> liberating, 2nd -> binding
        """
        ph, warn = V.phonemes_cmudict(word)
        n = len(ph)
        out = []
        for i, (typ, key, surf) in enumerate(ph):
            if typ != "C" or key not in self.pool:
                continue
            prev = ph[i - 1] if i > 0 else None
            nxt = ph[i + 1] if i + 1 < n else None
            if prev and prev[0] == "C" and prev[1] == key:
                pole = "binding"                      # 2nd of a doubled pair
            elif nxt and nxt[0] == "C" and nxt[1] == key and i != 0:
                pole = "liberating"                   # 1st of a doubled pair
            elif i == 0:
                pole = "binding"                      # word's first consonant -> worldly seed
            elif nxt and nxt[0] == "V":
                pole = "liberating"                   # onset (vowel follows)
            else:
                pole = "binding"                      # bare
            out.append((key, pole, surf))
        return out, warn

    def _compose(self, items):
        """items: [(lexicon_key, pole)] -> ' ; '-joined bridge text (G1 separator/no-cap policy)."""
        return " ; ".join(self.pool[k][pole] for k, pole in items)

    # -- A: word's own real varṇa-derived bridge ------------------------------------------------
    def core_A(self, word):
        poles, warn = self.varna_poles(word)
        if not poles:
            return None, {"warn": warn, "empty": True}
        text = self._compose([(k, p) for k, p, _ in poles])
        meta = {"varna_sequence": [(self.pool[k]["varna"], p) for k, p, _ in poles],
                "n_varnas": len(poles), "warn": warn,
                "contrast_boundary_excluded": True}      # G2: never rendered (leaks varṇa names)
        return text, meta

    # -- S: word's varṇa set, seeded scramble of bridge->position -------------------------------
    def core_S(self, word):
        poles, warn = self.varna_poles(word)
        if not poles:
            return None, {"warn": warn, "empty": True}
        bridges = [self.pool[k][p] for k, p, _ in poles]
        rng = random.Random(f"{self.seeds['arm_construction_seed']}:S:{word}")
        scrambled = bridges[:]
        rng.shuffle(scrambled)
        if len(scrambled) > 1 and scrambled == bridges:      # force a real derangement of order
            scrambled = scrambled[1:] + scrambled[:1]
        return " ; ".join(scrambled), {"n_varnas": len(poles), "warn": warn}

    # -- R_same: seeded sample from the 68-pool, excluding the word's own varṇas ----------------
    def core_R_same(self, word, n):
        own = {k for k, _, _ in self.varna_poles(word)[0]}
        candidates = [b for b in self.all_bridges if b[0] not in own]
        rng = random.Random(f"{self.seeds['r_same_sample_seed']}:{word}")
        k = max(1, min(n, len(candidates)))
        picks = rng.sample(candidates, k)
        return " ; ".join(t for _, _, t in picks), {"n_picked": k, "excluded_own": sorted(own)}

    # -- R_deranged: another word's REAL A mapping (seeded derangement pi, pi(w)!=w) -------------
    def _build_derangement(self):
        rng = random.Random(self.seeds["r_deranged_assignment_seed"])
        words = self.words[:]
        for _ in range(10000):
            perm = words[:]
            rng.shuffle(perm)
            if all(perm[i] != words[i] for i in range(len(words))):
                return dict(zip(words, perm))
        raise SystemExit("ABORT: could not build a derangement (should not happen).")

    def core_R_deranged(self, word):
        other = self._derangement[word]
        text, meta = self.core_A(other)
        return text, {"source_word": other, "source_meta": meta}

    # -- R_domain: fluent bridge from a deterministically MISMATCHED bucket (G3, build-time) -----
    _BUCKET_KEYWORDS = {
        "body/health": ["sensory", "body", "sleep", "torpor", "physical", "desire", "craving"],
        "social/relation": ["another", "others", "social", "regard", "shame", "malign", "maligned"],
        "cognition/knowledge": ["knowledge", "discern", "insight", "clarity", "knowing", "sense", "common sense"],
        "motion/action": ["action", "act", "effort", "striving", "commit", "energy", "force"],
        "material/object": ["accumulation", "hoard", "possession", "acquire", "surplus", "object", "own"],
        "ethical/order": ["order", "truth", "dharma", "conduct", "value", "worth", "warranted"],
        "emotion/affect": ["remorse", "dejection", "melancholy", "grief", "envy", "sting", "gladness", "buoyancy"],
        "cosmic/abstract": ["identity", "ego", "spell", "entrancement", "dissolution", "collapse", "bondage"],
        "speech/communication": ["speech", "exaggeration", "overstat", "display", "performance", "transparency"],
        "protection/harm": ["harm", "cruelty", "protect", "shield", "compassion", "goodwill", "vulnerable"],
    }
    _BUCKETS = tuple(_BUCKET_KEYWORDS)

    def _bucket_of_text(self, text):
        low = text.lower()
        best, score = self._BUCKETS[0], -1
        for b, kws in self._BUCKET_KEYWORDS.items():
            s = sum(low.count(k) for k in kws)
            if s > score:
                best, score = b, s
        return best

    def _bucket_bridges(self):
        m = {b: [] for b in self._BUCKETS}
        for key, pole, text in self.all_bridges:
            m[self._bucket_of_text(text)].append((key, pole, text))
        return m

    def _native_bucket(self, word):
        text, _ = self.core_A(word)
        return self._bucket_of_text(text or "")

    def core_R_domain(self, word, n):
        native = self._native_bucket(word)
        rng = random.Random(f"{self.seeds['r_domain_assignment_seed']}:{word}")
        candidate_buckets = [b for b in self._BUCKETS if b != native and self._bridge_bucket[b]]
        if not candidate_buckets:
            return None, {"note": "no mismatched bucket available", "native_bucket": native}
        mism = rng.choice(candidate_buckets)
        pool = self._bridge_bucket[mism]
        k = max(1, min(n, len(pool)))
        picks = rng.sample(pool, k)
        return " ; ".join(t for _, _, t in picks), {
            "native_bucket": native, "mismatched_bucket": mism, "n_picked": k,
            "policy_status": "NOT_FULLY_SPECIFIED_BY_FROZEN_CONFIG (G3: build-time heuristic bucketing)"}

    # -- D / C / X : lexicon-independent controls reused from committed B1 (NOT frozen; G4) ------
    def core_D(self, word):
        try:
            return RC._core_D(word), {"source": "b1_real_conditioning D-table (committed, NOT frozen)"}
        except RC.ConditioningUnavailable as e:
            return None, {"error": str(e)}

    def core_C(self, word):
        return RC._core_C(word, RC._profile(word)), {"source": "b1_real_conditioning surface facts"}

    def core_X(self, word):
        return RC.X_CORE, {"source": "b1_real_conditioning neutral filler"}

    # -- dispatcher -----------------------------------------------------------------------------
    def core(self, word, arm):
        if arm == "A":
            return self.core_A(word)
        if arm == "S":
            return self.core_S(word)
        if arm == "R_deranged":
            return self.core_R_deranged(word)
        if arm in ("R_same", "R_domain"):
            a_text, _ = self.core_A(word)
            n = len((a_text or "").split(" ; ")) if a_text else 1
            return self.core_R_same(word, n) if arm == "R_same" else self.core_R_domain(word, n)
        if arm == "D":
            return self.core_D(word)
        if arm == "C":
            return self.core_C(word)
        if arm == "X":
            return self.core_X(word)
        raise ValueError(f"unknown arm {arm!r}")

    def build_prompt(self, word, task_id, arm):
        core, meta = self.core(word, arm)
        if core is None:
            return None, None, meta
        task = B.TASKS[task_id].format(w=word)
        prompt = B.WRAPPER.format(conditioning=core, task=task)
        return core, prompt, meta


# ============================================================ leak scan ============================
_VARNA_NAMES = ("Ka", "Kha", "Ga", "Gha", "Ṅa", "Ca", "Cha", "Ja", "Jha", "Ña", "Ṭa", "Ṭha", "Ḍa",
                "Ḍha", "Ṇa", "Ta", "Tha", "Da", "Dha", "Na", "Pa", "Pha", "Ba", "Bha", "Ma", "Ya",
                "Ra", "La", "Va", "Śa", "Ṣa", "Sa", "Ha", "Kṣa")
_ARM_LABELS = ("R_same", "R_deranged", "R_domain", "control_arm")   # multi-char, low false-positive


def leak_scan(text, lexicon):
    """Flag varṇa-name / Sanskrit-label / IAST-diacritic / arm-label leakage in model-facing text."""
    hits = {"iast_diacritics": [], "sanskrit_labels": [], "varna_names": [], "arm_labels": []}
    for ch in text:
        if ch in V._IAST_CHARS and ch not in hits["iast_diacritics"]:
            hits["iast_diacritics"].append(ch)
    for e in lexicon["entries"]:
        for part in str(e["source_attested_pole"]["sanskrit_label"]).replace("/", " ").split():
            p = part.strip()
            if len(p) > 2 and p in text and p not in hits["sanskrit_labels"]:
                hits["sanskrit_labels"].append(p)
    for name in _VARNA_NAMES:
        if f" {name} " in f" {text} " or f"({name})" in text or f"«{name}»" in text:
            hits["varna_names"].append(name)
    for lab in _ARM_LABELS:
        if lab in text:
            hits["arm_labels"].append(lab)
    total = sum(len(v) for v in hits.values())
    return total, hits


# ============================================================ render-only =========================
def render_only(builder, lexicon, tasks=("T1", "T3", "T4", "T6")):
    words = builder.words
    cores, full_examples, leak_total, per_arm_leak = [], [], 0, {a: 0 for a in ARMS}
    empty_arms = []
    leak_findings = {}          # token -> {category, arms:set, words:set, count}
    for w in words:
        for arm in ARMS:
            core, meta = builder.core(w, arm)
            if core is None:
                empty_arms.append({"word": w, "arm": arm, "meta": meta})
                continue
            t, hits = leak_scan(core, lexicon)
            leak_total += t
            per_arm_leak[arm] += t
            for cat, toks in hits.items():
                for tok in toks:
                    f = leak_findings.setdefault(tok, {"category": cat, "arms": set(),
                                                        "words": set(), "count": 0})
                    f["arms"].add(arm)
                    f["words"].add(w)
                    f["count"] += 1
            cores.append({"word": w, "arm": arm, "core_sha256": hashlib.sha256(core.encode()).hexdigest(),
                          "n_chars": len(core), "leak_hits": t, "leak_detail": hits if t else None,
                          "meta": meta})
    # a full-prompt example per arm for one representative word
    ex_word = "justice"
    for arm in ARMS:
        core, prompt, meta = builder.build_prompt(ex_word, "T1", arm)
        if prompt:
            full_examples.append({"word": ex_word, "task": "T1", "arm": arm, "prompt": prompt,
                                  "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()})
    n_full = len(words) * len(tasks) * len(ARMS)
    findings = [{"token": tok, "category": f["category"], "count": f["count"],
                 "arms": sorted(f["arms"]), "words": sorted(f["words"]),
                 "varna_source": _varna_for_token(tok, builder),
                 "blocker": "FROZEN_ARTIFACT_LEAK — requires re-freeze (bridge pool is frozen; "
                            "cannot be edited without INVALID_POSTHOC and a new manifest)"}
                for tok, f in sorted(leak_findings.items())]
    return {
        "n_words": len(words), "n_tasks_rendered": len(tasks), "n_arms": len(ARMS),
        "n_conditioning_cores": len(cores), "n_full_prompts_would_render": n_full,
        "leak_total": leak_total, "per_arm_leak": per_arm_leak, "leak_findings": findings,
        "empty_arms": empty_arms, "cores": cores, "full_prompt_examples": full_examples,
    }


def _varna_for_token(tok, builder):
    """Best-effort: which frozen bridge phrase(s) carry the leaking token (for traceability)."""
    out = []
    for key, pole, text in builder.all_bridges:
        if tok in text:
            out.append(f"{builder.pool[key]['varna']}/{pole}")
    return sorted(set(out))


# ============================================================ model-access readiness ==============
def model_access_readiness():
    checks = {}
    try:
        import torch
        checks["torch_importable"] = True
        checks["cuda_available"] = bool(torch.cuda.is_available())
    except Exception as e:                                   # noqa: BLE001
        checks["torch_importable"] = False
        checks["cuda_available"] = False
        checks["torch_error"] = str(e)
    try:
        import transformers
        checks["transformers_version"] = transformers.__version__
    except Exception as e:                                   # noqa: BLE001
        checks["transformers_version"] = None
        checks["transformers_error"] = str(e)
    # DO NOT touch the network. Report the known, policy-level HuggingFace egress denial.
    checks["huggingface_egress"] = ("DENIED_BY_ENV_POLICY (huggingface.co 403 CONNECT). No download "
                                    "attempted. Real generation must run on a model-access host (RunPod).")
    return checks


# ============================================================ main =================================
def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.1 8-arm generation runner (render-only safe).")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--render-only", action="store_true",
                      help="DEFAULT-SAFE: render + hash + leak-scan prompts; no model, no network.")
    mode.add_argument("--execute-generation", action="store_true",
                      help="Real generation. Requires B1_1_GENERATION_APPROVED=YES + a model-access host.")
    ap.add_argument("--json-out", default=str(HERE / "B1_1_GENERATION_RENDER_ONLY_REPORT.json"))
    ap.add_argument("--md-out", default=str(HERE / "B1_1_GENERATION_RENDER_ONLY_REPORT.md"))
    ap.add_argument("--out", default=str(HERE / "b1_1_raw_outputs.jsonl"),
                    help="(execute mode) raw-output JSONL path")
    ap.add_argument("--resume", action="store_true", help="(execute mode) resume into an existing --out")
    args = ap.parse_args(argv)

    man = verify_frozen_or_abort()
    cfg = load_frozen_configs(man)
    builder = ArmBuilder(cfg)

    # ----- real generation path: hard-gated, refuses in this environment ----------------------
    if args.execute_generation:
        if os.environ.get("B1_1_GENERATION_APPROVED") != "YES":
            raise SystemExit("REFUSED: --execute-generation requires B1_1_GENERATION_APPROVED=YES in "
                             "the environment. Real generation is not authorized without it.")
        ready = model_access_readiness()
        print("[model-access readiness]", json.dumps(ready, indent=2))
        out_path = pathlib.Path(args.out)
        if out_path.exists() and not args.resume:
            raise SystemExit(f"REFUSED: output path {out_path} already exists; pass --resume to append, "
                             "or move it. Never silently overwrite raw outputs.")
        if not ready["cuda_available"] or ready["transformers_version"] is None:
            raise SystemExit("REFUSED: no CUDA / transformers backend on this host. Real generation must "
                             "run on the model-access host (RunPod), not this prep environment.")
        # Model-access host would proceed below; in THIS env HF egress is denied, so refuse loudly
        # BEFORE any model is contacted (no download, no call).
        raise SystemExit("REFUSED_HF_EGRESS: this environment denies huggingface.co egress (same denial "
                         "that blocks the embedding gate); the frozen generation models "
                         "(mistralai/Mistral-7B-Instruct-v0.3, Qwen/Qwen2.5-7B-Instruct) cannot be "
                         "fetched here. No model call attempted. Run on a model-access host and author "
                         "the RunPod execution plan (B1_1_RUNPOD_GENERATION_EXECUTION_PLAN) first.")

    # ----- render-only path (default) ---------------------------------------------------------
    print("[render-only] building 8 arms from the frozen set — NO model, NO network.")
    result = render_only(builder, cfg["lexicon"])
    gaps = [
        "G1: A-composition pole/cap/separator NOT pinned in the frozen arm-construction config "
        "(runner uses varna_lens vowel-attachment polarity + ' ; ' + no cap).",
        "G2: contrast_boundary cannot be rendered (it names other varṇas -> would leak); kept in "
        "metadata only. The frozen config's 'preserve contrast_boundary' cannot apply to prompt text.",
        "G3: R_domain word->bucket and bridge->bucket maps NOT frozen; runner uses a build-time keyword "
        "heuristic and flags R_domain NOT_FULLY_SPECIFIED_BY_FROZEN_CONFIG.",
        "G4: word/task pool (b1_dry_run_harness.py) and D/C/X sources (b1_real_conditioning.py) are "
        "committed but NOT in the frozen artifact set.",
    ]
    passed = result["leak_total"] == 0 and not result["empty_arms"]
    report = {
        "B1_1_GENERATION_RENDER_ONLY_REPORT": {
            "status": "PASS_RENDER_ONLY" if passed else "REVIEW_REQUIRED_BLOCKER",
            "runner_mechanics": "PASS (8 arms built, seeded, deterministic, manifest-verified)",
            "blockers": [] if passed else [
                "FROZEN_ARTIFACT_LEAK: model-facing leak(s) originate in the FROZEN bridge pool and "
                "cannot be repaired post-hoc without editing a frozen artifact (INVALID_POSTHOC). "
                "Generation must NOT proceed until a re-freeze removes the leak. See leak_findings."],
            "mode": "render-only (no model, no network, no judging, no scoring)",
            "manifest_status": man["manifest_status"],
            "generation_authorized": man["generation_authorized"],
            "freeze_base": man["finalization"]["finalized_commit_base"],
            "arms": list(ARMS),
            "render": {k: v for k, v in result.items() if k != "cores"},
            "cores": result["cores"],
            "freeze_coverage_gaps": gaps,
            "model_access": model_access_readiness(),
            "anchors": {
                "b1_verdict": "RANDOM_OR_SCRAMBLED_MATCHES",
                "track_b": "BLOCKED",
                "track_g": man["track_g_anchor"],
                "positive_cap": man["positive_label_limit"],
                "crux": "R_deranged",
                "fallback_qualification": man["fallback_qualification"],
            },
            "non_claims": ["structure not validated meaning", "render is not evidence B1.1 works",
                           "does not authorize generation", "does not unblock Track B"],
        }
    }
    pathlib.Path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    _write_md(args.md_out, report["B1_1_GENERATION_RENDER_ONLY_REPORT"], result)
    r = report["B1_1_GENERATION_RENDER_ONLY_REPORT"]
    print(f"[render-only] status={r['status']} | cores={result['n_conditioning_cores']} | "
          f"leak_total={result['leak_total']} | empty_arms={len(result['empty_arms'])}")
    print(f"[render-only] wrote {args.json_out}")
    print(f"[render-only] wrote {args.md_out}")
    print("RENDER ONLY. No model, no judging, no scoring. B1 verdict stands; Track B BLOCKED.")


def _write_md(path, r, result):
    per_arm = result["per_arm_leak"]
    lines = [
        "# B1.1 Generation Render-Only Report (structural; no model, no network)",
        "",
        f"## Status: `{r['status']}`",
        "",
        "Render-only structural validation of the 8-arm B1.1 runner against the **frozen** artifact set. "
        "**No model call, no download, no judging, no scoring.** This is **not** evidence that B1.1 works "
        "or outperforms B1/H2. `R_deranged` remains the crux. **Structure, not validated meaning.**",
        "",
        "## Frozen integrity",
        f"- manifest_status: **{r['manifest_status']}** · generation_authorized: **{r['generation_authorized']}** "
        f"· freeze base `{r['freeze_base'][:10]}`",
        "- The runner **re-hashes every bound artifact first** and aborts `INVALID_POSTHOC` on any mismatch.",
        "",
        "## Arms rendered",
        f"- Arms (exactly 8): {', '.join('`'+a+'`' for a in r['arms'])}",
        f"- Conditioning cores rendered: **{result['n_conditioning_cores']}** "
        f"({result['n_words']} words × {result['n_arms']} arms)",
        f"- Full prompts that would render (word × task × arm): **{result['n_full_prompts_would_render']}**",
        "",
        "## Runner mechanics",
        f"- **{r['runner_mechanics']}** — all 8 arms built deterministically from the frozen set with "
        "frozen seeds; A uses real G2P→varṇa; R_deranged uses a seeded derangement; controls are "
        "length-matched.",
        "",
        "## Leakage scan (model-facing text)",
        f"- **Total leak hits: {result['leak_total']}** across "
        f"{result['n_conditioning_cores']} cores.",
        "- Per-arm: " + ", ".join(f"{a}={per_arm[a]}" for a in r["arms"]),
        "- Scanned for: IAST diacritics, Sanskrit labels, varṇa names, multi-char arm labels. "
        "`contrast_boundary` is **excluded** from prompts (it names varṇas → would leak).",
        "",
    ]
    if result["leak_findings"]:
        lines += ["### Leak findings (BLOCKER — originate in the FROZEN bridge pool)"]
        for f in result["leak_findings"]:
            lines.append(
                f"- token **`{f['token']}`** ({f['category']}) — source {', '.join(f['varna_source'])}; "
                f"appears in {f['count']} core(s), arms {f['arms']}, words {f['words']}. "
                f"**{f['blocker']}**")
        lines += [
            "",
            "> **Why the pre-freeze dry run missed this:** the sample-word dry run used **illustrative "
            "spelling-based** varṇa decomposition, which never routed these words to the leaking varṇa. "
            "Real G2P→varṇa (used here) does. The leak is in the **frozen** bridge pool, so it is a "
            "`FROZEN_ARTIFACT_LEAK`: generation must not run until a re-freeze removes it.",
            "",
        ]
    lines += [
        "## A construction (real pipeline)",
        "- A uses **real G2P→varṇa** (`varna_lens.phonemes_cmudict`) over the target word, then the "
        "**frozen** B1.1 bridge pool; per-varṇa pole via the vowel-attachment rule; composed in order.",
        "",
        "## Freeze-coverage gaps (honest; do NOT block render-only, MUST be pinned before the real run)",
    ]
    lines += [f"- **{g.split(':',1)[0]}**:{g.split(':',1)[1]}" for g in r["freeze_coverage_gaps"]]
    lines += [
        "",
        "## Model access in this environment",
        f"- torch importable: {r['model_access'].get('torch_importable')} · "
        f"cuda: {r['model_access'].get('cuda_available')} · "
        f"transformers: {r['model_access'].get('transformers_version')}",
        f"- HuggingFace egress: {r['model_access']['huggingface_egress']}",
        "- Real generation is **hard-gated** (`--execute-generation` + `B1_1_GENERATION_APPROVED=YES` + "
        "model-access host) and **refuses here** before any model is contacted.",
        "",
        "## Anchors preserved",
        f"- B1 verdict: **{r['anchors']['b1_verdict']}** · Track B: **{r['anchors']['track_b']}** · "
        f"positive cap: **{r['anchors']['positive_cap']}** · crux: **{r['anchors']['crux']}**",
        f"- Track G: `{r['anchors']['track_g']['label']}` (`{r['anchors']['track_g']['commit']}`; "
        f"A_vs_R {r['anchors']['track_g']['A_vs_R']}, A_vs_X {r['anchors']['track_g']['A_vs_X']}) · "
        f"fallback: **{r['anchors']['fallback_qualification']}**",
        "",
        "## Next gate",
        "- **BLOCKER FIRST:** the `FROZEN_ARTIFACT_LEAK` (see leak findings) must be resolved by a "
        "**re-freeze** (edit the source lexicon/bridge under a new manifest — the current freeze cannot "
        "be edited without `INVALID_POSTHOC`). The pre-freeze audit/dry-run should be re-run with **real "
        "G2P** (not illustrative spelling) so latent varṇa-routing leaks are caught."
        if r["status"] != "PASS_RENDER_ONLY" else
        "- **`B1_1_RUNPOD_GENERATION_EXECUTION_PLAN`** — plan the real run on a model-access host.",
        "- Then **`B1_1_RUNPOD_GENERATION_EXECUTION_PLAN`** — plan the real run on a model-access host; "
        "resolve gaps G1–G4 into frozen artifacts before generating. Generation remains **unauthorized "
        "here**.",
        "",
        "**Structure, not validated meaning.** Render only; the B1 verdict stands and Track B remains BLOCKED.",
    ]
    pathlib.Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
