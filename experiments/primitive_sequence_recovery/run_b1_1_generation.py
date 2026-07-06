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

FREEZE-COVERAGE GAPS (surfaced by the first render; PINNED in the re-freeze — see
B1_1_POSTFREEZE_LEAK_FIX_AND_REFREEZE):
  G1  A-composition policy (pole rule, no cap, separator) is pinned in the frozen arm config
      arms.A.composition_policy; the runner reads the separator from it.
  G2  contrast_boundary is pinned METADATA_ONLY in the arm/leak configs and is never rendered; the
      runner composes A/S from binding_bridge/liberating_bridge only.
  G3  R_domain bucket_keyword_map + bucket order + derivation rules + seed are pinned in the frozen arm
      config; the runner LOADS them from config and persists b1_1_r_domain_assignments.json.
  G4  The word/task pool + D/C/X + G2P-routing source paths are recorded in the generation config and
      hash-bound in the freeze manifest referenced_source_hashes.

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
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "varna_lens"))
sys.path.insert(0, str(HERE))
import varna_lens as V                 # noqa: E402  real G2P->varṇa pipeline (committed)
import b1_dry_run_harness as B         # noqa: E402  committed word/task pool + WRAPPER (NOT frozen)
import b1_real_conditioning as RC      # noqa: E402  committed D-table / surface / neutral (NOT frozen)

# Performance only (no behavior change): nltk cmudict.dict() rebuilds the whole dict on every call, and
# the G2P routing is invoked hundreds of times. Cache it once so render-only/dry-run/audit stay fast.
try:
    import nltk.corpus as _nc
    _CMU_CACHE = _nc.cmudict.dict()
    _nc.cmudict.dict = lambda: _CMU_CACHE          # noqa: E731  identical data, memoized
except Exception:                                   # noqa: BLE001  (fall back to per-call load)
    pass

MANIFEST = HERE / "b1_1_freeze_manifest.json"
ARMS = ("A", "D", "S", "R_same", "R_deranged", "R_domain", "C", "X")


# ============================================================ integrity gate ======================
def verify_frozen_or_abort(manifest_path=MANIFEST, require_frozen=True):
    """Re-hash every bound artifact in the manifest. Abort INVALID_POSTHOC on any mismatch.

    require_frozen=True (generation path): manifest_status MUST be FROZEN.
    require_frozen=False (render-only bootstrap): a DRAFT_READY_FOR_FREEZE_REVIEW manifest is accepted so
    candidate artifacts can be leak-validated BEFORE the final freeze is signed. Rendering is structural
    and authorizes nothing; the generation path still demands the FROZEN manifest.
    """
    man = json.loads(pathlib.Path(manifest_path).read_text(encoding="utf-8"))["B1_1_FREEZE_MANIFEST"]
    status = man.get("manifest_status")
    ok_status = {"FROZEN"} if require_frozen else {"FROZEN", "DRAFT_READY_FOR_FREEZE_REVIEW"}
    if status not in ok_status:
        raise SystemExit(f"ABORT: manifest_status {status!r} not in {sorted(ok_status)}.")
    bad = []
    for art in man["bound_artifacts"]:
        p = REPO / art["path"]
        if not p.exists():
            bad.append(f"missing {art['path']}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != art["sha256"]:
            bad.append(f"HASH MISMATCH {art['path']}")
    if bad:
        raise SystemExit("ABORT INVALID_POSTHOC: bound artifact(s) changed vs manifest:\n  "
                         + "\n  ".join(bad))
    if man.get("generation_authorized") is not False:
        raise SystemExit("ABORT: manifest generation_authorized is not False.")
    print(f"[ok] manifest verified ({status}): all {len(man['bound_artifacts'])} bound artifacts match.")
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
        arm = cfg["arm_config"]
        # G1: separator is pinned in the frozen arm config's A composition_policy.
        self.sep = arm["arms"]["A"].get("composition_policy", {}).get("separator", " ; ")
        # G3: bucket keyword map + bucket order are pinned in the frozen arm config (authoritative).
        rdp = arm.get("r_domain_policy", {})
        self._bucket_keywords = rdp.get("bucket_keyword_map") or dict(self._BUCKET_KEYWORDS_FALLBACK)
        self._buckets = tuple(self._bucket_keywords)
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
        self._poles_cache = {}                                # memo: word -> (poles, warn)
        self._a_cache = {}                                    # memo: word -> (A_text, meta)
        self._derangement = self._build_derangement()
        self._bridge_bucket = self._bucket_bridges()          # G3 buckets from frozen config map

    # -- real G2P->varṇa + vowel-attachment polarity (varna_lens rule) --------------------------
    def varna_poles(self, word):
        """Return [(lexicon_key, pole, surface)] for the word's CONSONANT varṇas via real G2P.

        Polarity is the varna_lens.read_op vowel-attachment rule (structural, referent-blind):
          * the word's FIRST consonant -> binding (worldly seed)
          * a consonant with a vowel immediately after (onset) -> liberating
          * a bare consonant (word-final / pre-consonant) -> binding
          * doubled consonant: 1st occurrence -> liberating, 2nd -> binding
        """
        if word in self._poles_cache:
            return self._poles_cache[word]
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
        self._poles_cache[word] = (out, warn)
        return out, warn

    def _compose(self, items):
        """items: [(lexicon_key, pole)] -> separator-joined bridge text (G1 policy; separator from config)."""
        return self.sep.join(self.pool[k][pole] for k, pole in items)

    # -- A: word's own real varṇa-derived bridge ------------------------------------------------
    def core_A(self, word):
        if word in self._a_cache:
            return self._a_cache[word]
        poles, warn = self.varna_poles(word)
        if not poles:
            res = (None, {"warn": warn, "empty": True})
        else:
            text = self._compose([(k, p) for k, p, _ in poles])
            meta = {"varna_sequence": [(self.pool[k]["varna"], p) for k, p, _ in poles],
                    "n_varnas": len(poles), "warn": warn,
                    "contrast_boundary_excluded": True}  # G2: never rendered (leaks varṇa names)
            res = (text, meta)
        self._a_cache[word] = res
        return res

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
        return self.sep.join(scrambled), {"n_varnas": len(poles), "warn": warn}

    # -- R_same: seeded sample from the 68-pool, excluding the word's own varṇas ----------------
    def core_R_same(self, word, n):
        own = {k for k, _, _ in self.varna_poles(word)[0]}
        candidates = [b for b in self.all_bridges if b[0] not in own]
        rng = random.Random(f"{self.seeds['r_same_sample_seed']}:{word}")
        k = max(1, min(n, len(candidates)))
        picks = rng.sample(candidates, k)
        return self.sep.join(t for _, _, t in picks), {"n_picked": k, "excluded_own": sorted(own)}

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

    # -- R_domain: fluent bridge from a deterministically MISMATCHED bucket -----------------------
    # G3: the authoritative bucket_keyword_map is loaded from the FROZEN arm config in __init__.
    # This fallback is used only if the config lacks the map (should not happen post-refreeze).
    _BUCKET_KEYWORDS_FALLBACK = {
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

    def _bucket_of_text(self, text):
        low = text.lower()
        best, score = self._buckets[0], -1
        for b in self._buckets:                       # fixed bucket order for deterministic ties
            s = sum(low.count(k) for k in self._bucket_keywords[b])
            if s > score:
                best, score = b, s
        return best

    def _bucket_bridges(self):
        m = {b: [] for b in self._buckets}
        for key, pole, text in self.all_bridges:
            m[self._bucket_of_text(text)].append((key, pole, text))
        return m

    def _native_bucket(self, word):
        text, _ = self.core_A(word)
        return self._bucket_of_text(text or "")

    def core_R_domain(self, word, n):
        # style_parity (pinned): R_domain must be a MISMATCHED-domain bridge that is length-comparable to
        # A (never obviously weaker). Accumulate distinct phrases from one mismatched bucket until we have
        # >= n phrases AND >= 0.6x A's length; prefer buckets that can reach that length.
        a_text, _ = self.core_A(word)
        target = len(a_text or "")
        native = self._native_bucket(word)
        rng = random.Random(f"{self.seeds['r_domain_assignment_seed']}:{word}")
        nonempty = [b for b in self._buckets if b != native and self._bridge_bucket[b]]
        if not nonempty:
            return None, {"note": "no mismatched bucket available", "native_bucket": native}
        able = [b for b in nonempty
                if sum(len(t) for _, _, t in self._bridge_bucket[b]) >= 0.6 * target]
        candidate_buckets = able or nonempty          # fall back to any non-native bucket if none suffice
        mism = rng.choice(candidate_buckets)
        order = self._bridge_bucket[mism][:]
        rng.shuffle(order)
        picks, total = [], 0
        for cand in order:
            picks.append(cand)
            total += len(cand[2]) + len(self.sep)
            if len(picks) >= n and total >= 0.6 * target:
                break
        return self.sep.join(t for _, _, t in picks), {
            "native_bucket": native, "mismatched_bucket": mism, "n_picked": len(picks),
            "target_len": target, "achieved_len": len(self.sep.join(t for _, _, t in picks)),
            "policy_status": "PINNED_BY_FROZEN_CONFIG (G3: bucket_keyword_map in b1_1_arm_construction_config.json)"}

    def r_domain_assignments(self):
        """Deterministic per-word native/mismatched R_domain buckets (G3 persisted artifact)."""
        out = {}
        for w in self.words:
            a_text, _ = self.core_A(w)
            n = len((a_text or "").split(self.sep)) if a_text else 1
            _, meta = self.core_R_domain(w, n)
            out[w] = {"native_bucket": meta.get("native_bucket"),
                      "mismatched_bucket": meta.get("mismatched_bucket"), "n_picked": meta.get("n_picked")}
        return out

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


# ============================================================ model adapters ======================
class TransformersAdapter:
    """REAL model adapter — loads a FROZEN model at its FROZEN revision and generates with the FROZEN
    decode policy. Reuses B1's committed pattern (run_b1_generation.TransformersAdapter): user-turn only,
    NO system prompt, apply_chat_template(return_dict=True), set_seed per row. Instantiated ONLY inside the
    execute-generation loop on a model-access host — never in render-only or mock mode, and never reached in
    this egress-denied environment (the CUDA/transformers gate refuses first)."""
    is_real = True

    def __init__(self, model_id, revision, decode):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.model_id, self.revision, self.decode = model_id, revision, decode
        self.tok = AutoTokenizer.from_pretrained(model_id, revision=revision)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, revision=revision, torch_dtype=torch.float16, device_map="auto")
        self.model.eval()

    def generate(self, prompt, seed):
        import torch
        from transformers import set_seed
        set_seed(seed)                       # deterministic per (row, seed)
        msgs = [{"role": "user", "content": prompt}]   # NO system prompt (frozen decode.system_prompt=none)
        enc = self.tok.apply_chat_template(
            msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True).to(self.model.device)
        in_len = enc["input_ids"].shape[1]
        with torch.no_grad():
            out = self.model.generate(
                **enc, do_sample=True, temperature=self.decode["temperature"],
                top_p=self.decode["top_p"], max_new_tokens=self.decode["max_tokens"],
                pad_token_id=self.tok.eos_token_id)
        return self.tok.decode(out[0][in_len:], skip_special_tokens=True).strip()


class MockAdapter:
    """MOCK_ONLY adapter — deterministic non-model placeholder for LOCAL CI of the loop mechanics
    (JSONL schema, resume, incremental write, error handling). Calls NO model and touches NO network. Its
    output is NEVER B1.1 evidence; every row is stamped mock=true / status MOCK_ONLY and written to a
    mock-marked path."""
    is_real = False
    name = "MOCK_ONLY"

    def __init__(self, model_id, revision, decode):
        self.model_id, self.revision, self.decode = model_id, revision, decode

    def generate(self, prompt, seed):
        h = hashlib.sha256(f"{self.model_id}|{self.revision}|{seed}|{prompt}".encode()).hexdigest()
        return f"[MOCK_ONLY — deterministic non-model placeholder, NOT B1.1 evidence — {h[:24]}]"


# ============================================================ generation rows + loop ==============
def build_generation_prompt(cfg, core, word, task_id):
    """Build the model-facing prompt from the FROZEN generation config ONLY (prompt_template +
    task_templates). No post-hoc edits. core = the arm's conditioning (from the frozen bridge pool)."""
    gen = cfg["generation"]
    task = gen["task_templates"][task_id]["exact_prompt"].format(target_word=word)
    return gen["prompt_template"].format(arm_bridge_text=core, task=task)


def expand_generation_rows(builder, cfg):
    """Full frozen generation matrix: word × arm × task × model × seed. Prompts + conditioning are built
    from the frozen configs; nothing is invented. Returns a list of row dicts (no model called)."""
    gen = cfg["generation"]
    models = gen["generation_models"]                 # [{id, revision, ...}]
    seeds = gen["decoding"]["generation_seeds"]
    task_ids = list(gen["task_templates"].keys())     # T1..T6 (frozen order)
    rows = []
    for word in builder.words:
        for arm in ARMS:
            core, cmeta = builder.core(word, arm)
            if core is None:
                continue
            for task_id in task_ids:
                prompt = build_generation_prompt(cfg, core, word, task_id)
                prompt_id = hashlib.sha256(prompt.encode()).hexdigest()[:16]
                for m in models:
                    for seed in seeds:
                        rows.append({
                            "key": f"{word}|{task_id}|{arm}|{m['id']}|{seed}",
                            "target_word": word, "arm": arm, "task_id": task_id,
                            "model_id": m["id"], "model_revision": m.get("revision"),
                            "seed": seed, "prompt_id": prompt_id, "prompt_text": prompt,
                            "conditioning_text": core})
    return rows


def _git_head():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO), capture_output=True,
                              text=True, timeout=10).stdout.strip() or None
    except Exception:                                   # noqa: BLE001
        return None


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _gen_with_retry(adapter, prompt, seed, max_attempts, mock):
    """Frozen retry policy: retry up to max_attempts on transient error with backoff; then record an error
    row (never silently skip). Mock never sleeps and never errors."""
    last_err = None
    for attempt in range(max_attempts):
        try:
            text = adapter.generate(prompt, seed)
            return text, ("MOCK_ONLY" if mock else "ok"), None
        except Exception as e:                          # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            if not mock and attempt < max_attempts - 1:
                time.sleep(min(2 ** attempt, 8))
    return None, "error", last_err


def run_generation_loop(builder, cfg, man, manifest_path, out_path, resume, mock):
    """Frozen generation loop. Verifies leakage over every prompt FIRST, then writes one JSONL row per
    (word,task,arm,model,seed). Incremental append + flush; structured error rows on failure; resume skips
    completed keys. Real adapter loads models (HF) — reached only on a model-access host."""
    lex = cfg["lexicon"]
    decode = cfg["generation"]["decoding"]
    max_attempts = 3                                    # frozen retry_policy: "retry up to 3x"
    rows = expand_generation_rows(builder, cfg)

    # requirement #6: leakage validation BEFORE any model call. Scan every unique conditioning + prompt.
    leaks = []
    seen_core = {}
    for r in rows:
        c = r["conditioning_text"]
        if c not in seen_core:
            seen_core[c] = leak_scan(c, lex)[0]
        p_leak = leak_scan(r["prompt_text"], lex)[0] if r["arm"] == "X" else seen_core[c]
        if p_leak:
            leaks.append(r["key"])
    if leaks:
        raise SystemExit(f"ABORT: {len(leaks)} prompt(s) contain leakage; refusing to generate. "
                         f"e.g. {leaks[:3]}. (Structure, not validated meaning.)")

    manifest_sha = hashlib.sha256(pathlib.Path(manifest_path).read_bytes()).hexdigest()
    run_id = f"b1_1_gen_{'mock_' if mock else ''}{_now().replace(':', '').replace('-', '')}"
    freeze_commit = _git_head()

    done = set()
    if resume and out_path.exists():
        for ln in out_path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(ln)
                if rec.get("status") in ("ok", "MOCK_ONLY"):
                    done.add(rec["key"])
            except Exception:                           # noqa: BLE001
                pass

    Adapter = MockAdapter if mock else TransformersAdapter
    adapters, written, errors = {}, 0, 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as fh:
        for i, r in enumerate(rows, 1):
            if r["key"] in done:
                continue
            mid = r["model_id"]
            if mid not in adapters:
                print(f"[load] adapter for {mid} @ {str(r['model_revision'])[:10]} "
                      f"({'MOCK' if mock else 'REAL'}) …")
                adapters[mid] = Adapter(mid, r["model_revision"], decode)  # real: loads model (HF)
            text, status, err = _gen_with_retry(adapters[mid], r["prompt_text"], r["seed"],
                                                max_attempts, mock)
            rec = {
                "run_id": run_id, "manifest_sha256": manifest_sha,
                "manifest_path": str(pathlib.Path(manifest_path).name), "freeze_commit": freeze_commit,
                "model_id": r["model_id"], "model_revision": r["model_revision"],
                "task_id": r["task_id"], "target_word": r["target_word"], "arm": r["arm"],
                "prompt_id": r["prompt_id"], "prompt_text": r["prompt_text"],
                "conditioning_text": r["conditioning_text"], "generation_text": text,
                "decoding": {"temperature": decode["temperature"], "top_p": decode["top_p"],
                             "max_tokens": decode["max_tokens"]},
                "seed": r["seed"], "timestamp": _now(), "status": status, "error": err,
                "key": r["key"], "mock": bool(mock),
                "b1_verdict_anchor": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b_anchor": "BLOCKED",
                "is_b1_1_evidence": (False if mock else True),
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            written += 1
            if status not in ("ok", "MOCK_ONLY"):
                errors += 1
            if i % 500 == 0 or i == len(rows):
                print(f"  … {i}/{len(rows)} (written {written}, errors {errors})")
    return {"total_rows": len(rows), "written": written, "errors": errors, "skipped_resume": len(done),
            "run_id": run_id, "manifest_sha256": manifest_sha, "mock": bool(mock)}


# ============================================================ main =================================
def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.1 8-arm generation runner (render-only safe).")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--render-only", action="store_true",
                      help="DEFAULT-SAFE: render + hash + leak-scan prompts; no model, no network.")
    mode.add_argument("--execute-generation", action="store_true",
                      help="Real generation. Requires B1_1_GENERATION_APPROVED=YES + a model-access host.")
    mode.add_argument("--mock-generation", action="store_true",
                      help="MOCK_ONLY loop for local CI: exercises the JSONL/resume/error mechanics with a "
                           "deterministic non-model placeholder. NO model, NO network, NOT B1.1 evidence. "
                           "Requires --out with a 'mock' filename.")
    ap.add_argument("--json-out", default=str(HERE / "B1_1_GENERATION_RENDER_ONLY_REPORT.json"))
    ap.add_argument("--md-out", default=str(HERE / "B1_1_GENERATION_RENDER_ONLY_REPORT.md"))
    ap.add_argument("--out", default=None,
                    help="(execute/mock mode) raw-output JSONL path (required for those modes)")
    ap.add_argument("--resume", action="store_true", help="(execute/mock mode) resume into an existing --out")
    ap.add_argument("--manifest", default=None,
                    help="manifest to verify (default: final b1_1_freeze_manifest.json; falls back to the "
                         "draft for render-only bootstrap before the final freeze is signed).")
    args = ap.parse_args(argv)

    mpath = pathlib.Path(args.manifest) if args.manifest else MANIFEST
    if not args.manifest and not mpath.exists():
        mpath = HERE / "b1_1_freeze_manifest.draft.json"   # render-only bootstrap fallback
    man = verify_frozen_or_abort(mpath, require_frozen=bool(args.execute_generation))
    cfg = load_frozen_configs(man)
    builder = ArmBuilder(cfg)

    # ----- real generation path: hard-gated; refuses in this egress-denied environment -------------
    if args.execute_generation:
        if os.environ.get("B1_1_GENERATION_APPROVED") != "YES":
            raise SystemExit("REFUSED: --execute-generation requires B1_1_GENERATION_APPROVED=YES in "
                             "the environment. Real generation is not authorized without it.")
        if not args.out:
            raise SystemExit("REFUSED: --execute-generation requires an explicit --out <path.jsonl>.")
        out_path = pathlib.Path(args.out)
        if out_path.exists() and not args.resume:
            raise SystemExit(f"REFUSED: output path {out_path} already exists; pass --resume to append, "
                             "or move it. Never silently overwrite raw outputs.")
        # requirement #6: render/leak validation BEFORE any model call.
        pre = render_only(builder, cfg["lexicon"])
        if pre["leak_total"] != 0 or pre["empty_arms"]:
            raise SystemExit(f"REFUSED: render/leak validation failed (leak_total={pre['leak_total']}, "
                             f"empty_arms={len(pre['empty_arms'])}); refusing to generate.")
        print(f"[pre-run] render/leak validation OK (leak_total=0, {pre['n_conditioning_cores']} cores).")
        ready = model_access_readiness()
        print("[model-access readiness]", json.dumps(ready, indent=2))
        if not ready["cuda_available"] or ready["transformers_version"] is None:
            # THIS environment: no CUDA / egress-denied -> refuse BEFORE any model is contacted.
            raise SystemExit("REFUSED: no CUDA / transformers backend on this host (and huggingface.co "
                             "egress is denied here). Real generation must run on the model-access host "
                             "(RunPod), not this prep environment. No model call attempted.")
        # --- model-access host only (never reached here): run the frozen generation loop ---
        try:
            summary = run_generation_loop(builder, cfg, man, mpath, out_path, args.resume, mock=False)
        except SystemExit:
            raise
        except Exception as e:                          # noqa: BLE001  (clear HF/load failure)
            raise SystemExit(f"ABORT: generation loop failed (model load/egress or runtime error): {e}. "
                             "No partial result is treated as evidence.")
        print(f"[done] {summary['written']} rows -> {out_path} (errors {summary['errors']})")
        print("RAW GENERATION ONLY. Not scored, not judged, no packets, no verdict. Track B BLOCKED.")
        print("Next gate: B1_1_POST_GENERATION_LEAK_SCAN (separately approved).")
        return

    # ----- MOCK generation path (local CI only; no model, no network, NOT evidence) ----------------
    if args.mock_generation:
        if not args.out or "mock" not in pathlib.Path(args.out).name.lower():
            raise SystemExit("REFUSED: --mock-generation requires --out with a 'mock' filename (so mock "
                             "output is never confused with real B1.1 evidence).")
        out_path = pathlib.Path(args.out)
        if out_path.exists() and not args.resume:
            raise SystemExit(f"REFUSED: mock output {out_path} exists; pass --resume or move it.")
        pre = render_only(builder, cfg["lexicon"])
        if pre["leak_total"] != 0 or pre["empty_arms"]:
            raise SystemExit(f"REFUSED: render/leak validation failed (leak_total={pre['leak_total']}).")
        print("[mock] MOCK_ONLY loop — deterministic placeholder, NO model, NO network. NOT B1.1 evidence.")
        summary = run_generation_loop(builder, cfg, man, mpath, out_path, args.resume, mock=True)
        print(f"[mock] {summary['written']} MOCK_ONLY rows -> {out_path} "
              f"(errors {summary['errors']}, skipped {summary['skipped_resume']})")
        return

    # ----- render-only path (default) ---------------------------------------------------------
    print("[render-only] building 8 arms from the frozen set — NO model, NO network.")
    result = render_only(builder, cfg["lexicon"])
    # G3: persist the deterministic per-word R_domain assignments artifact.
    rda = {"artifact": "b1_1_r_domain_assignments", "status": "candidate_deterministic",
           "policy": "pinned in b1_1_arm_construction_config.json r_domain_policy (bucket_keyword_map + seed)",
           "seed_ref": "r_domain_assignment_seed", "assignments": builder.r_domain_assignments(),
           "b1_verdict_anchor": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b_anchor": "BLOCKED",
           "generation_authorized": False}
    (HERE / "b1_1_r_domain_assignments.json").write_text(
        json.dumps(rda, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gaps = [
        "G1 (RESOLVED): A-composition policy (pole rule, no cap, separator) is now pinned in "
        "b1_1_arm_construction_config.json arms.A.composition_policy; the runner reads the separator from it.",
        "G2 (RESOLVED): contrast_boundary is pinned METADATA_ONLY in arm/leak configs and is never rendered; "
        "the runner composes A/S from binding_bridge/liberating_bridge only.",
        "G3 (RESOLVED): R_domain bucket_keyword_map + bucket order + derivation rules + seed are pinned in "
        "the frozen arm config; the runner loads them from config and persists b1_1_r_domain_assignments.json.",
        "G4 (RESOLVED): word/task pool + D/C/X + G2P-routing source paths are recorded in the generation "
        "config and hash-bound in the freeze manifest referenced_source_hashes.",
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
            "freeze_base": man.get("finalization", {}).get("finalized_commit_base", man.get("created_at", "draft")),
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
