#!/usr/bin/env python3
"""B1.1 non-synonym embedding gate — local embedding-similarity diagnostic over the 32 non-deferred
experimental counter-poles. NOT generation, NOT scoring, NOT an LLM judge.

Frozen model + thresholds are constants below. The gate:
  1. loads the JSON draft; validates 34 total / 32 non-deferred / Ra & Śa deferred;
  2. runs the EXACT-DUPLICATE check (no model needed);
  3. loads the FROZEN embedding model — if unavailable, writes a BLOCKED availability report and stops
     (does NOT substitute a model, does NOT fabricate similarities);
  4. otherwise computes normalized embeddings + pairwise cosine, flags hard/soft pairs, writes both reports.

Never rewrites the lexicon, never generates a bridge pool, never touches source lexicons or B1 artifacts.

    python3 experiments/primitive_sequence_recovery/run_b1_1_non_synonym_embedding_gate.py
"""
from __future__ import annotations

import hashlib
import itertools
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
DRAFT = HERE / "b1_1_experimental_contrastive_lexicon_draft.json"
REPORT_JSON = HERE / "B1_1_NON_SYNONYM_EMBEDDING_REPORT.json"
REPORT_MD = HERE / "B1_1_NON_SYNONYM_EMBEDDING_REPORT.md"

# ---- FROZEN model + thresholds (do not tune after seeing scores) ----
MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_FALLBACK = "sentence-transformers/all-mpnet-base-v2"   # only with explicit approval
SIM_METRIC = "cosine_over_L2_normalized_embeddings"
TAU_HARD = 0.88     # cosine >= -> hard flag
TAU_SOFT = 0.82     # 0.82 <= cosine < 0.88 -> soft flag
DEFERRED = {"Ra", "Śa"}
PRIMARY_FIELDS = ("english_rendering", "functional_operation")


def load_entries():
    doc = json.loads(DRAFT.read_text(encoding="utf-8"))
    entries = doc["entries"]
    nondef = [e for e in entries if e["varna"] not in DEFERRED]
    defer = [e for e in entries if e["varna"] in DEFERRED]
    return doc, entries, nondef, defer


def exact_dup_check(nondef):
    out = {}
    for f in PRIMARY_FIELDS:
        vals = [e["experimental_counter_pole"][f] for e in nondef]
        dups = sorted({v for v in vals if vals.count(v) > 1})
        out[f] = dups
    return out


def draft_sha():
    return hashlib.sha256(DRAFT.read_bytes()).hexdigest()


def try_load_model():
    """Return (model, revision) or (None, reason)."""
    try:
        import importlib.util
        if importlib.util.find_spec("sentence_transformers") is None:
            return None, "sentence_transformers not installed"
        from sentence_transformers import SentenceTransformer   # noqa
        model = SentenceTransformer(MODEL_ID)                   # may need local cache / network
        rev = getattr(getattr(model, "_model_config", None), "get", lambda *_: None)("__revision__")
        return model, rev
    except Exception as e:  # noqa: BLE001 — availability guard, report and stop
        return None, f"{type(e).__name__}: {e}"


def cosine_pairs(nondef, model):
    import numpy as np
    texts = {f: [e["experimental_counter_pole"][f] for e in nondef] for f in PRIMARY_FIELDS}
    texts["combined"] = [f"{e['experimental_counter_pole']['english_rendering']} — "
                         f"{e['experimental_counter_pole']['functional_operation']}" for e in nondef]
    emb = {}
    for f, tx in texts.items():
        v = np.asarray(model.encode(tx, normalize_embeddings=True))
        emb[f] = v
    varnas = [e["varna"] for e in nondef]
    keys = [e["lexicon_key"] for e in nondef]
    flags = []
    for i, j in itertools.combinations(range(len(nondef)), 2):
        per = {f: float((emb[f][i] * emb[f][j]).sum()) for f in ("english_rendering", "functional_operation", "combined")}
        headline = max(per["english_rendering"], per["functional_operation"])
        level = "hard" if headline >= TAU_HARD else ("soft" if headline >= TAU_SOFT else None)
        if level:
            field = "english_rendering" if per["english_rendering"] >= per["functional_operation"] else "functional_operation"
            flags.append({
                "varna_a": varnas[i], "varna_b": varnas[j],
                "lexicon_key_a": keys[i], "lexicon_key_b": keys[j],
                "field_compared": field, "similarity_score": round(headline, 4),
                "per_channel": {k: round(v, 4) for k, v in per.items()},
                "text_a": nondef[i]["experimental_counter_pole"][field],
                "text_b": nondef[j]["experimental_counter_pole"][field],
                "flag_level": level,
                "suggested_adjudication": "rewrite" if level == "hard" else "accept-with-rationale",
                "rationale": "<TBD_HUMAN>"})
    flags.sort(key=lambda x: -x["similarity_score"])
    return flags


def write_blocked_md(dups, reason, defer):
    exact_ok = not any(dups.values())
    md = f"""# B1.1 Non-Synonym Embedding Gate — REPORT (BLOCKED: dependency unavailable)

## 1. Scope and non-claims
Embedding-similarity diagnostic over the 32 non-deferred experimental counter-poles. NOT generation, NOT
scoring, NOT an LLM judge. Does not modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock
Track B (**BLOCKED**). No ontology / Sanskrit privilege / semantic-truth claim. **Structure, not validated
meaning.**

## 2. Frozen model and thresholds
- model_id (frozen): `{MODEL_ID}` · fallback (approval-only): `{MODEL_FALLBACK}`
- metric: {SIM_METRIC} · thresholds: hard ≥ {TAU_HARD}, soft {TAU_SOFT}–{TAU_HARD}, pass < {TAU_SOFT}
- **STATUS: model NOT loaded** — {reason}

## 3. Inputs and exclusions
- input: `b1_1_experimental_contrastive_lexicon_draft.json` (sha256 `{draft_sha()}`)
- evaluated scope: 32 non-deferred entries · excluded (deferred): {sorted(e['varna'] for e in defer)} · vowels excluded

## 4. Exact duplicate check (no model needed — RAN)
- english_rendering duplicates: {dups['english_rendering'] or 'NONE'}
- functional_operation duplicates: {dups['functional_operation'] or 'NONE'}
- exact-duplicate result: **{'PASS (no exact duplicates)' if exact_ok else 'FAIL'}**

## 5. Pairwise similarity summary
**NOT COMPUTED** — embedding dependency unavailable (no fabricated scores).

## 6. Hard flags
NOT COMPUTED (dependency unavailable).

## 7. Soft flags
NOT COMPUTED (dependency unavailable).

## 8. Ra/Śa exclusion note
Ra (source_complex) and Śa (neutral_principle) carry deferred null counter-poles and are excluded from this
check. Before B1.1 freeze: either resolve their counter-poles and re-run over 34, or pre-register exclusion.

## 9. Human adjudication requirements
None yet — no flags computed. Adjudication applies once the embedding run completes.

## 10. Pass/fail gate status
**`BLOCKED_DEPENDENCY_UNAVAILABLE`** — the exact-duplicate sub-check passed
({'no dups' if exact_ok else 'DUPS FOUND'}), but the embedding portion could not run. The gate is **not
PASS**; the lexicon may **not** proceed to bridge generation.

**To unblock (requires approval):** install `sentence-transformers` (pulls `torch`) and cache `{MODEL_ID}`,
then re-run this script; OR approve switching to a different available embedding model. Do not substitute a
model silently.

## 11. Next recommended gate
Resolve dependency/model availability (with approval), then re-run this gate to completion; only then
`B1_1_BRIDGE_POOL_GENERATION`.

## Final status
```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             EMBEDDING DIAGNOSTIC — BLOCKED (dependency unavailable)
Bridge pool generated: NO
Generation run:        NO
Scoring run:           NO
LLM judge run:         NO
Source lexicon:        NOT modified
Exact-duplicate check: {'PASS' if exact_ok else 'FAIL'}
```
**Structure, not validated meaning.** Embedding diagnostic blocked; verdict stands, Track B BLOCKED.
"""
    REPORT_MD.write_text(md, encoding="utf-8")


def main():
    doc, entries, nondef, defer = load_entries()
    assert len(entries) == 34, f"expected 34 consonants, got {len(entries)}"
    assert len(nondef) == 32, f"expected 32 non-deferred, got {len(nondef)}"
    assert {e["varna"] for e in defer} == DEFERRED, "Ra/Śa must be the deferred entries"
    dups = exact_dup_check(nondef)
    print(f"[ok] loaded draft: 34 total, 32 non-deferred, deferred={sorted(e['varna'] for e in defer)}")
    print(f"[{'ok' if not any(dups.values()) else 'FAIL'}] exact-duplicate check: "
          f"english={dups['english_rendering'] or 'none'} operation={dups['functional_operation'] or 'none'}")

    model, info = try_load_model()
    if model is None:
        write_blocked_md(dups, info, defer)
        print(f"[BLOCKED] embedding model unavailable: {info}")
        print(f"[BLOCKED] wrote availability report -> {REPORT_MD.name} (no JSON report; no fabricated scores)")
        print("gate_status = BLOCKED_DEPENDENCY_UNAVAILABLE (NOT pass; bridge generation NOT unblocked)")
        return

    # --- embeddings available: full run ---
    flags = cosine_pairs(nondef, model)
    hard = [f for f in flags if f["flag_level"] == "hard"]
    soft = [f for f in flags if f["flag_level"] == "soft"]
    exact_ok = not any(dups.values())
    status = ("HARD_REVIEW_REQUIRED" if hard else
              "SOFT_REVIEW_REQUIRED" if soft else
              ("PASS" if exact_ok else "FAIL_EXACT_DUPLICATE"))
    report = {
        "artifact": "b1_1_non_synonym_embedding_report",
        "b1_verdict_unchanged": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b_status": "BLOCKED",
        "frozen_model": MODEL_ID, "model_info": str(info),
        "embedding_dim": int(model.get_sentence_embedding_dimension()),
        "similarity_metric": SIM_METRIC,
        "thresholds": {"hard_ge": TAU_HARD, "soft_ge": TAU_SOFT},
        "input_sha256": draft_sha(),
        "n_evaluated": len(nondef), "excluded_deferred": sorted(e["varna"] for e in defer),
        "exact_duplicates": dups, "n_hard": len(hard), "n_soft": len(soft),
        "gate_status": status, "flags": flags,
        "non_claims": ["no ontology validation", "no Sanskrit privilege", "no semantic truth",
                       "necessary but not sufficient; R_deranged remains the crux"]}
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[ok] model={MODEL_ID} dim={report['embedding_dim']} pairs=496 "
          f"hard={len(hard)} soft={len(soft)} status={status}")
    print(f"[ok] wrote {REPORT_JSON.name} (+ .md to be rendered)")
    # (md rendering for the completed case is added when the model is actually available)


if __name__ == "__main__":
    main()
