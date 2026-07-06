#!/usr/bin/env python3
"""run_b1_2_g_builder.py — B1.2 dictionary-differential answer-key builder G(word).

Builds G(word) = the dictionary-derived differential answer key, DETERMINISTICALLY from WordNet (zero LLM;
R1 satisfied maximally). G is the ground truth the varṇa prediction V(word) must later align with; it is
NEVER scored as a prediction here. This script also renders V (via the real B1.1 ArmBuilder.core_A over the
byte-identical b1_2 mapping copies) ONLY to run the R3 style-tell audit — no alignment scoring, no judging.

Hard gates:
  R5  WordNet must load from a fixed offline corpus (hashed). No live web calls. Else STOP_NOW.
  R3  V and G project into ONE shared judge-facing schema; a style-tell audit must not detect source type
      above balanced-accuracy 0.55 (one auto-revision allowed). Else STOP_NOW.

Provisional target set is labelled NOT_EVIDENCE: it validates the builder only; real B1.2 evidence needs the
frozen B1.2 target set + a new joint freeze. Structure, not validated meaning. B1.1 verdict unchanged;
Track B BLOCKED; no ontology / Sanskrit / semantic-truth claim.

    python3 experiments/primitive_sequence_recovery/b1_2_mapping_fidelity/run_b1_2_g_builder.py
"""
from __future__ import annotations
import hashlib, json, os, re, sys, pathlib, statistics

HERE = pathlib.Path(__file__).resolve().parent
PSR = HERE.parent                      # experiments/primitive_sequence_recovery
sys.path.insert(0, str(PSR))           # to import the committed V machinery

# ---- rendering caps (frozen in g_function_config.json) ----
K_FEATURES, J_CONSTRAINTS, N_SUMMARY_WORDS, M_FEATURE_WORDS = 5, 3, 14, 6
STYLE_TELL_THRESHOLD = 0.55
STOPWORDS = set(("a an the of to and or in on for with without as at by from into "
                 "is are was were be been being that which who whom this these those "
                 "it its their his her they them one used use also often not no any "
                 "someone something person used-as term address given having make makes "
                 "act state quality being able having-to").split())

# provisional target set (NOT EVIDENCE) — common nouns; must exist in WordNet + cmudict
PROVISIONAL_TARGETS = ["mother", "water", "fire", "mountain", "ocean",
                       "friendship", "justice", "patience", "knowledge", "freedom"]


def sha256_file(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ============================================================ R5: source provisioning =============
def load_sources():
    """Load WordNet + cmudict from the offline nltk corpora; hash the zips. No web calls here."""
    import nltk.data
    from nltk.corpus import wordnet as wn
    from nltk.corpus import cmudict as cd
    src = {}
    for res in ("corpora/wordnet.zip", "corpora/omw-1.4.zip", "corpora/cmudict.zip"):
        try:
            p = str(nltk.data.find(res))
            src[res] = {"path": p, "sha256": sha256_file(p), "bytes": os.path.getsize(p)}
        except Exception as e:
            src[res] = {"error": f"{type(e).__name__}: {e}"}
    wn.ensure_loaded()
    _ = wn.synsets("mother")            # force-load; raises if corpus unusable
    cmu = cd.dict()
    return wn, cmu, {"wordnet_version": wn.get_version(), "corpora": src}


# ============================================================ G(word) deterministic builder ========
def content_lemmas(text):
    out = []
    for w in re.findall(r"[a-z]+", (text or "").lower()):
        if len(w) >= 3 and w not in STOPWORDS and w not in out:
            out.append(w)
    return out


def build_G(word, wn):
    """Deterministic dictionary differential answer key from WordNet. Word-agnostic; no varṇa, no V."""
    syns = wn.synsets(word, pos=wn.NOUN) or wn.synsets(word)
    if not syns:
        return None, "no_synset"
    target = syns[0]
    pos = target.pos()
    target_def = target.definition()

    # --- neighbor selection: same fixed rule for every word ---
    neigh = []                                    # ordered, deduped synonym/near-neighbor lemmas
    def add(lemma):
        l = lemma.replace("_", " ")
        if l and l.lower() != word.lower() and l not in neigh:
            neigh.append(l)
    for l in target.lemma_names():
        add(l)
    for hyper in target.hypernyms():              # co-hyponyms (siblings) + hypernym terms
        for sib in hyper.hyponyms():
            for l in sib.lemma_names():
                add(l)
        for l in hyper.lemma_names():
            add(l)
    for s in syns[1:]:                            # other senses' lemmas as fallback
        for l in s.lemma_names():
            add(l)
    neigh = neigh[:15]                             # cap; require >=10 (checked by caller)

    # definitions for neighbors (first matching synset, deterministic)
    ndef = {}
    for n in neigh:
        ns = wn.synsets(n.replace(" ", "_"))
        ndef[n] = ns[0].definition() if ns else ""

    # --- shared vs target-specific feature extraction (deterministic set arithmetic) ---
    tgt_feats = content_lemmas(target_def)
    neigh_feat_lists = [content_lemmas(d) for d in ndef.values() if d]
    n_nb = max(1, len(neigh_feat_lists))
    def nb_frac(feat):
        return sum(feat in fl for fl in neigh_feat_lists) / n_nb
    thr = 0.34
    shared = [f for f in tgt_feats if nb_frac(f) >= thr]
    # shared hypernym lemma names
    for hyper in target.hypernyms():
        for l in hyper.lemma_names():
            hl = l.replace("_", " ")
            if hl not in shared:
                shared.append(hl)
    target_specific = [f for f in tgt_feats if nb_frac(f) < thr]
    # excluded neighbor features: frequent in neighbors, absent from target def
    allnb = {}
    for fl in neigh_feat_lists:
        for f in fl:
            allnb[f] = allnb.get(f, 0) + 1
    excluded = [f for f, c in sorted(allnb.items(), key=lambda kv: (-kv[1], kv[0]))
                if f not in tgt_feats and c / n_nb >= thr][:6]

    ts = target_specific[:K_FEATURES] or tgt_feats[:K_FEATURES]
    sh = shared[:K_FEATURES]
    n1 = neigh[0] if neigh else "related terms"
    n2 = neigh[1] if len(neigh) > 1 else (neigh[0] if neigh else "related terms")
    a = ts[0] if ts else word
    b = ts[1] if len(ts) > 1 else (ts[0] if ts else word)
    c = sh[0] if sh else "the shared category"
    d = sh[1] if len(sh) > 1 else (sh[0] if sh else "the shared category")
    differential_summary = (f"{word} centers on {a} and {b}; unlike {n1} and {n2}, "
                            f"it is not merely {c} or {d}")

    rec = {
        "target_word": word,
        "part_of_speech": pos,
        "target_definition": target_def,
        "synonym_set": neigh,
        "synonym_definitions": ndef,
        "shared_features": sh,
        "target_specific_features": ts,
        "excluded_neighbor_features": excluded,
        "differential_summary": differential_summary,
        "provenance": {"source": "WordNet (offline)", "synset": target.name(),
                       "selection_rule": "target lemmas + co-hyponyms + hypernym terms, deterministic"},
        "extraction_method": "deterministic_wordnet",
    }
    rec["hash_inputs"] = sha256_text(json.dumps(
        {"def": target_def, "neigh": neigh, "ndef": ndef}, sort_keys=True, ensure_ascii=False))
    return rec, None


# ============================================================ shared V/G normalizer (R3) ===========
_SPLIT = re.compile(r"[;—•\n]| - ")


def _short_phrase(s, maxw=M_FEATURE_WORDS):
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()
    return " ".join(s.split()[:maxw]).strip()


def normalize_signature(raw_text, feature_list, summary_text, constraint_list, sig_id):
    """Project ANY source (V prose or G record) into the one shared judge-facing schema.
    Neutralizes source-specific punctuation (';', '—') and casing so style ≈ source-independent."""
    feats = [p for p in (_short_phrase(x) for x in feature_list) if p][:K_FEATURES]
    if len(feats) < K_FEATURES and raw_text:                    # backfill from raw text, same rule
        for chunk in _SPLIT.split(raw_text):
            p = _short_phrase(chunk)
            if p and p not in feats:
                feats.append(p)
            if len(feats) >= K_FEATURES:
                break
    summ = " ".join(_short_phrase(summary_text or raw_text or "", maxw=N_SUMMARY_WORDS).split())
    cons = [p for p in (_short_phrase(x) for x in constraint_list) if p][:J_CONSTRAINTS]
    return {"signature_id": sig_id, "features": feats, "summary": summ, "constraints": cons}


def v_to_signature(word, v_text, sig_id):
    chunks = [c for c in _SPLIT.split(v_text or "") if c.strip()]
    feats = chunks[:K_FEATURES]
    cons = chunks[K_FEATURES:K_FEATURES + J_CONSTRAINTS]
    return normalize_signature(v_text, feats, v_text, cons, sig_id)


def g_to_signature(rec, sig_id):
    return normalize_signature(rec["differential_summary"], rec["target_specific_features"],
                               rec["differential_summary"],
                               ["not " + f for f in rec["excluded_neighbor_features"]], sig_id)


# ============================================================ R3 style-tell audit =================
def style_vector(sig):
    feats, summ, cons = sig["features"], sig["summary"], sig["constraints"]
    joined = " ".join(feats + [summ] + cons)
    fw = [len(f.split()) for f in feats] or [0]
    return [
        len(feats), len(cons), len(summ.split()),
        statistics.fmean(fw), statistics.fmean([len(f) for f in feats] or [0]),
        len(joined), joined.count(","), sum(joined.count(ch) for ch in "-:/"),
    ]


def balanced_accuracy_loo(vectors, labels):
    """Leave-one-out nearest-centroid balanced accuracy on style-only features (deterministic)."""
    n = len(vectors)
    dim = len(vectors[0])
    means = [statistics.fmean(v[j] for v in vectors) for j in range(dim)]
    stds = [statistics.pstdev([v[j] for v in vectors]) or 1.0 for j in range(dim)]
    Z = [[(v[j] - means[j]) / stds[j] for j in range(dim)] for v in vectors]
    per_class = {0: [0, 0], 1: [0, 0]}             # class -> [correct, total]
    for i in range(n):
        cent = {}
        for cls in (0, 1):
            rows = [Z[k] for k in range(n) if k != i and labels[k] == cls]
            if rows:
                cent[cls] = [statistics.fmean(r[j] for r in rows) for j in range(dim)]
        if len(cent) < 2:
            continue
        d = {cls: sum((Z[i][j] - cent[cls][j]) ** 2 for j in range(dim)) for cls in cent}
        pred = min(d, key=d.get)
        per_class[labels[i]][1] += 1
        per_class[labels[i]][0] += int(pred == labels[i])
    recalls = [c / t for c, t in per_class.values() if t]
    return statistics.fmean(recalls) if recalls else float("nan"), per_class


# ============================================================ main =================================
def main():
    status = {"artifact": "b1_2_g_builder", "evidence": False,
              "note": "PROVISIONAL targets — NOT B1.2 evidence; validates the builder only."}
    stop = []

    # ---- R5 gate ----
    try:
        wn, cmu, srcmeta = load_sources()
    except Exception as e:
        write_stop(f"R5 source gate failed: {type(e).__name__}: {e}", stop=["R5_SOURCE_UNAVAILABLE"])
        return
    if any("error" in v for k, v in srcmeta["corpora"].items() if k == "corpora/wordnet.zip"):
        write_stop("R5: WordNet corpus not resolvable offline", stop=["R5_SOURCE_UNAVAILABLE"])
        return

    # ---- build G (deterministic) over provisional targets present in cmudict + wordnet ----
    g_records, syn_counts, dropped = [], {}, []
    for w in PROVISIONAL_TARGETS:
        if w not in cmu:
            dropped.append((w, "not_in_cmudict")); continue
        rec, err = build_G(w, wn)
        if err:
            dropped.append((w, err)); continue
        if len(rec["synonym_set"]) < 10:
            dropped.append((w, f"only_{len(rec['synonym_set'])}_synonyms")); continue
        g_records.append(rec)
        syn_counts[w] = len(rec["synonym_set"])

    if not g_records:
        write_stop("no G records built (targets missing from sources)", stop=["NO_G_RECORDS"])
        return

    # ---- render V via the real ArmBuilder (b1_2 byte-identical copies) — for style-tell only ----
    import run_b1_1_generation as R
    cfg = {"seeds": json.loads((HERE / "b1_2_seeds_config.reused_from_b1_1.json").read_text()),
           "arm_config": json.loads((HERE / "b1_2_arm_construction_config.reused_from_b1_1.json").read_text()),
           "bridge_pool": json.loads((HERE / "b1_2_varna_bridge_pool.json").read_text())}
    builder = R.ArmBuilder(cfg)
    v_renders = {}
    for rec in g_records:
        vt, _ = builder.core_A(rec["target_word"])
        v_renders[rec["target_word"]] = vt or ""

    # ---- shared-schema projection + style-tell audit (one auto-revision allowed) ----
    def project(sig_cap_words):
        global M_FEATURE_WORDS, N_SUMMARY_WORDS
        sigs, labels = [], []
        for rec in g_records:
            w = rec["target_word"]
            sigs.append(g_to_signature(rec, f"g_{w}")); labels.append(1)
            sigs.append(v_to_signature(w, v_renders[w], f"v_{w}")); labels.append(0)
        return sigs, labels

    revision = 0
    sigs, labels = project(None)
    ba, per_class = balanced_accuracy_loo([style_vector(s) for s in sigs], labels)
    if ba > STYLE_TELL_THRESHOLD:                      # one revision: tighten caps to equalize surface
        revision = 1
        globals()["M_FEATURE_WORDS"] = 4
        globals()["N_SUMMARY_WORDS"] = 10
        sigs, labels = project(None)
        ba, per_class = balanced_accuracy_loo([style_vector(s) for s in sigs], labels)

    style_pass = not (ba > STYLE_TELL_THRESHOLD)

    # ---- G/V independence audit ----
    banned = ("varna", "varṇa", "bridge_pool", "core_a", "phoneme", "liberating", "binding_bridge",
              "read_op", "sanskrit")
    leak_hits = []
    for rec in g_records:
        blob = json.dumps(rec, ensure_ascii=False).lower()
        for b in banned:
            if b in blob:
                leak_hits.append((rec["target_word"], b))
    v_unchanged = (sha256_file(HERE / "b1_2_varna_bridge_pool.json")
                   == "1ce2ae14b563621ac495381e8397796e6791aba740978bb817544935c6ba8c15")
    indep_ok = (not leak_hits) and v_unchanged

    # ---- write outputs ----
    (HERE / "g_outputs.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in g_records), encoding="utf-8")
    prompt_txt = ("[UNUSED IN THIS BUILD] Frozen extraction prompt placeholder. This build used "
                  "extraction_method=deterministic_wordnet (zero LLM), so no prompt was sent to any model. "
                  "If a future build enables the R1 LLM residual fallback, the exact frozen prompt goes here: "
                  "inputs = target definition + >=10 synonym definitions (dictionary only, NO varṇa, NO V, "
                  "NO B1.1 outputs, NO source labels); output = JSON {shared_features[], "
                  "target_specific_features[], excluded_neighbor_features[]}; temperature 0; JSON only.\n")
    (HERE / "g_extraction_prompt.txt").write_text(prompt_txt, encoding="utf-8")

    cfg_out = {"artifact": "g_function_config", "extraction_method": "deterministic_wordnet",
               "llm_used": False, "render_caps": {"K_features": K_FEATURES, "J_constraints": J_CONSTRAINTS,
               "N_summary_words": N_SUMMARY_WORDS, "M_feature_words": M_FEATURE_WORDS},
               "style_tell_threshold": STYLE_TELL_THRESHOLD, "neighbor_min": 10, "shared_threshold": 0.34,
               "source": "WordNet (offline, version-pinned)", "no_live_web_calls": True,
               "provisional_targets": PROVISIONAL_TARGETS, "evidence": False}
    (HERE / "g_function_config.json").write_text(json.dumps(cfg_out, indent=2, ensure_ascii=False) + "\n",
                                                 encoding="utf-8")

    style_report = {"artifact": "g_style_tell_audit", "method": "leave-one-out nearest-centroid on "
                    "style-only surface features (counts/lengths/punct; content-blind)",
                    "balanced_accuracy": round(ba, 4), "threshold": STYLE_TELL_THRESHOLD,
                    "pass": style_pass, "revision_applied": revision, "n_signatures": len(sigs),
                    "per_class_recall_counts": {"V": per_class[0], "G": per_class[1]},
                    "note": "Provisional/NOT_EVIDENCE; small-N, indicative only. Real audit runs on the "
                            "frozen B1.2 set. pass = balanced accuracy <= 0.55 (source type not detectable)."}
    (HERE / "g_style_tell_audit.json").write_text(json.dumps(style_report, indent=2) + "\n",
                                                  encoding="utf-8")
    (HERE / "g_style_tell_audit.md").write_text(
        f"# B1.2 G Style-Tell Audit (provisional; NOT_EVIDENCE)\n\n"
        f"- method: leave-one-out nearest-centroid on **style-only** surface features (content-blind)\n"
        f"- balanced accuracy (V vs G by style): **{ba:.4f}**  (threshold {STYLE_TELL_THRESHOLD})\n"
        f"- revision applied: {revision}\n- **pass: {style_pass}** "
        f"({'source type NOT detectable' if style_pass else 'STYLE-TELL DETECTED → STOP_NOW'})\n"
        f"- n signatures: {len(sigs)} ({len(g_records)} V + {len(g_records)} G)\n\n"
        f"Small-N provisional; the authoritative style-tell audit runs on the frozen B1.2 target set. "
        f"Structure, not validated meaning.\n", encoding="utf-8")

    # ---- decide status ----
    if not style_pass:
        stop.append("R3_STYLE_TELL_FAILED")
    if not indep_ok:
        stop.append("GV_INDEPENDENCE_FAILED")
    if stop:
        write_stop("hard gate(s) failed after build", stop=stop, extra={
            "style_balanced_accuracy": ba, "independence_ok": indep_ok, "leak_hits": leak_hits})
        return

    label = "PASS_G_FUNCTION_BUILD_PROVISIONAL_TARGETS_NOT_EVIDENCE"
    audit = {"artifact": "g_audit_report", "status": label, "evidence": False,
             "n_g_records": len(g_records), "synonym_counts": syn_counts, "dropped": dropped,
             "extraction_method": "deterministic_wordnet", "llm_used": False,
             "wordnet_version": srcmeta["wordnet_version"], "sources": srcmeta["corpora"],
             "style_tell": {"balanced_accuracy": round(ba, 4), "pass": style_pass, "revision": revision},
             "gv_independence": {"g_records_leak_hits": leak_hits, "v_artifact_unchanged": v_unchanged,
                                 "ok": indep_ok},
             "b1_1_verdict": "RANDOM_OR_SCRAMBLED_MATCHES (unchanged)", "track_b": "BLOCKED",
             "non_claims": ["no ontology validation", "no Sanskrit privilege", "no semantic truth",
                            "provisional targets are NOT B1.2 evidence"]}
    (HERE / "g_audit_report.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")

    manifest = {"artifact": "g_manifest", "status": label, "evidence": False,
                "wordnet_version": srcmeta["wordnet_version"],
                "source_hashes": srcmeta["corpora"],
                "config_hash": sha256_file(HERE / "g_function_config.json"),
                "prompt_hash": sha256_file(HERE / "g_extraction_prompt.txt"),
                "g_outputs_hash": sha256_file(HERE / "g_outputs.jsonl"),
                "style_audit_hash": sha256_file(HERE / "g_style_tell_audit.json"),
                "target_set_hash": sha256_text(json.dumps(PROVISIONAL_TARGETS, sort_keys=True)),
                "generation_method": "deterministic_wordnet",
                "reused_v_artifacts": {
                    "bridge_pool": sha256_file(HERE / "b1_2_varna_bridge_pool.json"),
                    "source_lexicon": sha256_file(HERE / "b1_2_varna_source_lexicon.json"),
                    "arm_construction_config": sha256_file(HERE / "b1_2_arm_construction_config.reused_from_b1_1.json"),
                    "seeds_config": sha256_file(HERE / "b1_2_seeds_config.reused_from_b1_1.json")},
                "stop_now_flags": [], "not_frozen": True, "not_run_for_evidence": True}
    (HERE / "g_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")

    (HERE / "g_audit_report.md").write_text(
        f"# B1.2 G-Function Build Audit (provisional; NOT_EVIDENCE)\n\n"
        f"**status: {label}**\n\n"
        f"- extraction method: **deterministic_wordnet** (zero LLM — R1 maximally satisfied)\n"
        f"- WordNet version: {srcmeta['wordnet_version']} (offline, hashed; no live web calls)\n"
        f"- G records built: **{len(g_records)}** ; synonyms/word: "
        f"{min(syn_counts.values())}–{max(syn_counts.values())} (>=10 required)\n"
        f"- dropped: {dropped or 'none'}\n"
        f"- style-tell balanced accuracy (V vs G): **{ba:.4f}** ≤ {STYLE_TELL_THRESHOLD} → "
        f"**{'PASS' if style_pass else 'FAIL'}** (revision {revision})\n"
        f"- G/V independence: leaks={leak_hits or 'none'}, V-artifact-unchanged={v_unchanged} → "
        f"**{'OK' if indep_ok else 'FAIL'}**\n\n"
        f"Provisional targets validate the builder only; they are **NOT B1.2 evidence**. Real evidence "
        f"requires the frozen B1.2 target set and a new joint V+G freeze.\n\n"
        f"B1.1 verdict **RANDOM_OR_SCRAMBLED_MATCHES** unchanged; Track B **BLOCKED**; no ontology / "
        f"Sanskrit / semantic-truth claim. **Structure, not validated meaning.**\n", encoding="utf-8")

    print(f"[{label}] G records={len(g_records)} synonyms={min(syn_counts.values())}-{max(syn_counts.values())} "
          f"style_tell_ba={ba:.4f} pass={style_pass} independence={indep_ok}")


def write_stop(reason, stop, extra=None):
    label = "STOP_NOW_G_IMPLEMENTATION_BLOCKED"
    rep = {"artifact": "g_audit_report", "status": label, "reason": reason, "stop_now_flags": stop,
           "evidence": False, "b1_1_verdict": "RANDOM_OR_SCRAMBLED_MATCHES (unchanged)",
           "track_b": "BLOCKED", "extra": extra or {}}
    (HERE / "g_audit_report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")
    man = {"artifact": "g_manifest", "status": label, "evidence": False, "stop_now_flags": stop,
           "reason": reason, "not_frozen": True, "not_run_for_evidence": True,
           "b1_1_verdict": "RANDOM_OR_SCRAMBLED_MATCHES (unchanged)", "track_b": "BLOCKED"}
    (HERE / "g_manifest.json").write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    (HERE / "g_audit_report.md").write_text(
        f"# B1.2 G-Function Build — {label}\n\n**reason:** {reason}\n\n**flags:** {stop}\n\n"
        f"B1.1 verdict RANDOM_OR_SCRAMBLED_MATCHES unchanged; Track B BLOCKED. Structure, not validated "
        f"meaning.\n", encoding="utf-8")
    print(f"[{label}] {reason} | flags={stop}")


if __name__ == "__main__":
    main()
