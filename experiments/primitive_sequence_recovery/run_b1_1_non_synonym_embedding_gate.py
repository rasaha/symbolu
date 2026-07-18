#!/usr/bin/env python3
"""B1.1 non-synonym embedding gate (rerun, binding/liberating schema) — local embedding-similarity
diagnostic over ALL 34 resolved counter-poles. NOT generation, NOT scoring, NOT an LLM judge.

Frozen model + thresholds are constants below. The gate:
  1. loads the JSON draft; validates 34 entries, no deferrals;
  2. runs the EXACT-DUPLICATE check (no model needed);
  3. loads the FROZEN embedding model — if unavailable, writes a BLOCKED report and stops (no substitute,
     no fabricated scores);
  4. computes normalized embeddings + pairwise cosine on liberating_expression + functional_operation,
     flags hard/soft pairs, writes both reports.

Never rewrites the lexicon, never generates a bridge pool, never touches source lexicons or B1 artifacts.

    python3 experiments/primitive_sequence_recovery/run_b1_1_non_synonym_embedding_gate.py
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import pathlib

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

HERE = pathlib.Path(__file__).resolve().parent
DRAFT = HERE / "b1_1_experimental_contrastive_lexicon_draft.json"
REPORT_JSON = HERE / "B1_1_NON_SYNONYM_EMBEDDING_REPORT.json"
REPORT_MD = HERE / "B1_1_NON_SYNONYM_EMBEDDING_REPORT.md"

# ---- FROZEN model + thresholds (do not tune after seeing scores) ----
MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
SIM_METRIC = "cosine_over_L2_normalized_embeddings"
TAU_HARD = 0.88     # cosine >= -> hard flag
TAU_SOFT = 0.82     # 0.82 <= cosine < 0.88 -> soft flag
PRIMARY_FIELDS = ("liberating_expression", "functional_operation")


def load_entries():
    doc = json.loads(DRAFT.read_text(encoding="utf-8"))
    return doc, doc["entries"]


def exact_dup_check(entries):
    out = {}
    for f in PRIMARY_FIELDS:
        vals = [e[f] for e in entries]
        out[f] = sorted({v for v in vals if vals.count(v) > 1})
    return out


def draft_sha():
    return hashlib.sha256(DRAFT.read_bytes()).hexdigest()


def try_load_model():
    try:
        import importlib.util
        if importlib.util.find_spec("sentence_transformers") is None:
            return None, "sentence_transformers not installed"
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(MODEL_ID)
        return model, "loaded"
    except Exception as e:  # noqa: BLE001 — availability guard, report and stop
        return None, f"{type(e).__name__}: {e}"


def model_revision(model):
    try:
        import sentence_transformers as st
        rev = None
        for m in getattr(model, "_modules", {}).values():
            cfg = getattr(m, "config", None)
            rev = getattr(cfg, "_commit_hash", None) or rev
        return {"st_version": getattr(st, "__version__", "?"), "commit_hash": rev}
    except Exception:  # noqa: BLE001
        return {"st_version": "?", "commit_hash": None}


def cosine_pairs(entries, model):
    import numpy as np
    texts = {f: [e[f] for e in entries] for f in PRIMARY_FIELDS}
    texts["combined"] = [f"{e['liberating_expression']} — {e['functional_operation']}" for e in entries]
    emb = {f: np.asarray(model.encode(tx, normalize_embeddings=True)) for f, tx in texts.items()}
    flags, all_scores = [], []
    for i, j in itertools.combinations(range(len(entries)), 2):
        per = {f: float((emb[f][i] * emb[f][j]).sum())
               for f in ("liberating_expression", "functional_operation", "combined")}
        headline = max(per["liberating_expression"], per["functional_operation"])
        all_scores.append(headline)
        level = "hard" if headline >= TAU_HARD else ("soft" if headline >= TAU_SOFT else None)
        if level:
            field = ("liberating_expression"
                     if per["liberating_expression"] >= per["functional_operation"]
                     else "functional_operation")
            flags.append({
                "varna_a": entries[i]["varna"], "varna_b": entries[j]["varna"],
                "lexicon_key_a": entries[i]["lexicon_key"], "lexicon_key_b": entries[j]["lexicon_key"],
                "field_compared": field, "similarity_score": round(headline, 4),
                "per_channel": {k: round(v, 4) for k, v in per.items()},
                "text_a": entries[i][field], "text_b": entries[j][field],
                "flag_level": level,
                "suggested_adjudication": "rewrite" if level == "hard" else "accept-with-rationale",
                "rationale": "<TBD_HUMAN>"})
    flags.sort(key=lambda x: -x["similarity_score"])
    return flags, all_scores


def _pct(scores, p):
    if not scores:
        return None
    s = sorted(scores)
    return round(s[min(len(s) - 1, int(p * len(s)))], 4)


def write_md(doc, entries, dups, status, model_meta, flags, all_scores, reason=None):
    exact_ok = not any(dups.values())
    hard = [f for f in flags if f["flag_level"] == "hard"]
    soft = [f for f in flags if f["flag_level"] == "soft"]

    def flag_table(rows):
        if not rows:
            return "_none_\n"
        out = "| A | B | field | cosine | text A | text B | adjudication |\n|---|---|---|---|---|---|---|\n"
        for f in rows:
            out += (f"| {f['varna_a']} | {f['varna_b']} | {f['field_compared']} | {f['similarity_score']} "
                    f"| {f['text_a'][:60]} | {f['text_b'][:60]} | {f['suggested_adjudication']} |\n")
        return out

    blocked = status == "BLOCKED_DEPENDENCY_UNAVAILABLE"
    md = f"""# B1.1 Non-Synonym Embedding Gate — REPORT{' (BLOCKED)' if blocked else ''}

## 1. Scope and non-claims
Embedding-similarity diagnostic over all **34 resolved** binding/liberating counter-poles. NOT generation,
NOT scoring, NOT an LLM judge. Does not modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or
unblock Track B (**BLOCKED**). No ontology / Sanskrit privilege / semantic-truth claim. Necessary but not
sufficient; `R_deranged` remains the crux. **Structure, not validated meaning.**

## 2. Frozen model and thresholds
- model_id (frozen): `{MODEL_ID}`
- model_meta: {json.dumps(model_meta)}
- metric: {SIM_METRIC} · thresholds: hard ≥ {TAU_HARD}, soft {TAU_SOFT}–{TAU_HARD}, pass < {TAU_SOFT}
- fields (primary): liberating_expression, functional_operation · combined = diagnostic · contrast_boundary NOT a primary target
{f'- **STATUS: model NOT loaded** — {reason}' if blocked else '- status: model loaded, run complete'}

## 3. Inputs and exclusions
- input: `b1_1_experimental_contrastive_lexicon_draft.json` (sha256 `{draft_sha()}`)
- evaluated: **{len(entries)}** entries · no deferrals · vowels excluded

## 4. Exact duplicate check
- liberating_expression duplicates: {dups['liberating_expression'] or 'NONE'}
- functional_operation duplicates: {dups['functional_operation'] or 'NONE'}
- exact-duplicate result: **{'PASS (no exact duplicates)' if exact_ok else 'FAIL'}**

## 5. Pairwise similarity summary
"""
    if blocked:
        md += "**NOT COMPUTED** — embedding dependency unavailable (no fabricated scores).\n"
    else:
        md += (f"- pairs evaluated: {len(all_scores)} (C(34,2)=561)\n"
               f"- headline cosine — max {round(max(all_scores),4)} · 95th pct {_pct(all_scores,0.95)} "
               f"· median {_pct(all_scores,0.5)} · min {round(min(all_scores),4)}\n"
               f"- hard flags (≥{TAU_HARD}): {len(hard)} · soft flags ({TAU_SOFT}–{TAU_HARD}): {len(soft)}\n")

    md += f"""
## 6. Hard flags
{('NOT COMPUTED (dependency unavailable).' if blocked else flag_table(hard))}
## 7. Soft flags
{('NOT COMPUTED (dependency unavailable).' if blocked else flag_table(soft))}
## 8. Human adjudication requirements
Every flagged pair requires one of: rewrite · accept-with-rationale (operationally distinct) · defer.
Rationale placeholders (`<TBD_HUMAN>`) are in the JSON report; no flag passes by synonym substitution.
Deliberate contrast-pairs (e.g. Ha↔Kṣa knowing-by-intuition vs -inference; Ḍha↔La shield-maligned vs
protect-weak) are expected soft flags and are candidates for accept-with-rationale.

## 9. Gate status
**`{status}`**"""
    if not blocked:
        md += (f" — exact-dup {'PASS' if exact_ok else 'FAIL'}, hard={len(hard)}, soft={len(soft)}. "
               f"{'May proceed to bridge-pool spec.' if status=='PASS' else 'Adjudication required before bridge generation.'}")
    else:
        md += (" — the exact-duplicate sub-check "
               f"{'passed' if exact_ok else 'FAILED'}, but the embedding portion could not run. "
               "To unblock: install sentence-transformers + torch and cache the model, then re-run (approval-gated).")
    md += f"""

## 10/11. Next gate
{'`B1_1_BRIDGE_POOL_GENERATION_SPEC` (if PASS)' if status=='PASS' else '`B1_1_EMBEDDING_FLAG_ADJUDICATION` (flags to resolve)' if status in ('SOFT_REVIEW_REQUIRED','HARD_REVIEW_REQUIRED') else 'resolve dependency (approval), then re-run'}

## Final status
```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             EMBEDDING DIAGNOSTIC{' — BLOCKED' if blocked else ''}
Entries evaluated:     {len(entries)}
Bridge pool generated: NO
Generation/scoring/judge: NO
Source lexicon:        NOT modified
Gate status:           {status}
```
**Structure, not validated meaning.**
"""
    REPORT_MD.write_text(md, encoding="utf-8")


def main():
    doc, entries = load_entries()
    assert len(entries) == 34, f"expected 34 consonants, got {len(entries)}"
    assert doc.get("deferred_count") == 0, "expected deferred_count=0"
    dups = exact_dup_check(entries)
    exact_ok = not any(dups.values())
    print(f"[ok] loaded draft: 34 resolved entries, deferred_count=0")
    print(f"[{'ok' if exact_ok else 'FAIL'}] exact-duplicate check: "
          f"lib={dups['liberating_expression'] or 'none'} op={dups['functional_operation'] or 'none'}")

    model, info = try_load_model()
    if model is None:
        write_md(doc, entries, dups, "BLOCKED_DEPENDENCY_UNAVAILABLE", {"reason": info}, [], [], reason=info)
        print(f"[BLOCKED] embedding model unavailable: {info}")
        print(f"[BLOCKED] wrote {REPORT_MD.name} (no JSON; no fabricated scores)")
        print("gate_status = BLOCKED_DEPENDENCY_UNAVAILABLE")
        return

    meta = model_revision(model)
    meta["embedding_dim"] = int(model.get_sentence_embedding_dimension())
    flags, all_scores = cosine_pairs(entries, model)
    hard = [f for f in flags if f["flag_level"] == "hard"]
    soft = [f for f in flags if f["flag_level"] == "soft"]
    status = ("FAIL_EXACT_DUPLICATE" if not exact_ok else
              "HARD_REVIEW_REQUIRED" if hard else
              "SOFT_REVIEW_REQUIRED" if soft else "PASS")
    report = {
        "artifact": "b1_1_non_synonym_embedding_report",
        "b1_verdict_unchanged": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b_status": "BLOCKED",
        "frozen_model": MODEL_ID, "model_meta": meta, "similarity_metric": SIM_METRIC,
        "thresholds": {"hard_ge": TAU_HARD, "soft_ge": TAU_SOFT},
        "input_sha256": draft_sha(), "n_evaluated": len(entries), "n_pairs": len(all_scores),
        "exact_duplicates": dups, "n_hard": len(hard), "n_soft": len(soft),
        "gate_status": status, "flags": flags,
        "non_claims": ["no ontology validation", "no Sanskrit privilege", "no semantic truth",
                       "necessary but not sufficient; R_deranged remains the crux"]}
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_md(doc, entries, dups, status, meta, flags, all_scores)
    print(f"[ok] model={MODEL_ID} dim={meta['embedding_dim']} pairs={len(all_scores)} "
          f"hard={len(hard)} soft={len(soft)} status={status}")
    print(f"[ok] wrote {REPORT_JSON.name} + {REPORT_MD.name}")


if __name__ == "__main__":
    main()
