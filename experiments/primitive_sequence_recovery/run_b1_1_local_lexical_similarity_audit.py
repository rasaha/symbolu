#!/usr/bin/env python3
"""B1.1 LOCAL lexical / phrase-similarity audit — interim WEAKER fallback for the blocked embedding gate.

Local, no-network, no-model, no-download. Surface-overlap screen ONLY over the 34 resolved counter-poles;
it does NOT detect deep paraphrase synonymy and does NOT count as an embedding-gate pass. Never touches
source lexicons, never generates a bridge pool, never runs a model/generation/scoring/judge.

    python3 experiments/primitive_sequence_recovery/run_b1_1_local_lexical_similarity_audit.py
"""
from __future__ import annotations

import collections
import hashlib
import itertools
import json
import pathlib
import re
import string

HERE = pathlib.Path(__file__).resolve().parent
DRAFT = HERE / "b1_1_experimental_contrastive_lexicon_draft.json"
REPORT_JSON = HERE / "B1_1_LOCAL_LEXICAL_SIMILARITY_REPORT.json"
REPORT_MD = HERE / "B1_1_LOCAL_LEXICAL_SIMILARITY_REPORT.md"

PRIMARY_FIELDS = ("liberating_expression", "functional_operation")

# ---- FROZEN thresholds ----
TJ_HARD, TJ_SOFT = 0.55, 0.40          # token Jaccard
CN_HARD, CN_SOFT = 0.70, 0.55          # char 3-gram / 4-gram Jaccard
LCS_SOFT = 0.50                        # longest-common-substring ratio
HEAD_N = 3                             # head-phrase length (tokens)
HEAD_MIN_GROUP = 3                     # repeated head phrase across >= N entries
GENERIC_DF_MIN = 6                     # report content terms appearing in >= N of 34 entries

STOPWORDS = {"the", "a", "an", "of", "to", "into", "and", "or", "by", "it", "its", "one", "without",
             "that", "would", "from", "in", "on", "as", "is", "at", "for", "not", "no", "own", "ones",
             "this", "with", "into", "onto"}
RETAIN = {"binding", "release", "ownership", "attachment", "knowledge", "action", "truth",
          "discernment", "energy", "order", "clarity"}   # never treated as stopwords


def normalize(t):
    t = (t or "").lower().replace("—", " ")
    t = t.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", t).strip()


def tokens(t):
    return [w for w in normalize(t).split() if w in RETAIN or w not in STOPWORDS]


def token_jaccard(a, b):
    sa, sb = set(tokens(a)), set(tokens(b))
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0


def char_ngrams(t, n):
    s = normalize(t).replace(" ", "")
    return {s[i:i + n] for i in range(len(s) - n + 1)} if len(s) >= n else set()


def ngram_jaccard(a, b, n):
    sa, sb = char_ngrams(a, n), char_ngrams(b, n)
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0


def lcs_ratio(a, b):
    x, y = normalize(a), normalize(b)
    if not x or not y:
        return 0.0
    prev = [0] * (len(y) + 1)
    best = 0
    for i in range(1, len(x) + 1):
        cur = [0] * (len(y) + 1)
        for j in range(1, len(y) + 1):
            if x[i - 1] == y[j - 1]:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best / min(len(x), len(y))


def draft_sha():
    return hashlib.sha256(DRAFT.read_bytes()).hexdigest()


def audit():
    doc = json.loads(DRAFT.read_text(encoding="utf-8"))
    entries = doc["entries"]
    assert len(entries) == 34, f"expected 34, got {len(entries)}"

    # exact-duplicate
    dups = {}
    for f in PRIMARY_FIELDS:
        vals = [e[f] for e in entries]
        dups[f] = sorted({v for v in vals if vals.count(v) > 1})
    exact_ok = not any(dups.values())

    flags = []
    for f in PRIMARY_FIELDS:
        for i, j in itertools.combinations(range(len(entries)), 2):
            a, b = entries[i][f], entries[j][f]
            tj = token_jaccard(a, b)
            c3 = ngram_jaccard(a, b, 3)
            c4 = ngram_jaccard(a, b, 4)
            lc = lcs_ratio(a, b)
            metrics = [("token_jaccard", tj, TJ_HARD, TJ_SOFT),
                       ("char_3gram", c3, CN_HARD, CN_SOFT),
                       ("char_4gram", c4, CN_HARD, CN_SOFT),
                       ("lcs_ratio", lc, 2.0, LCS_SOFT)]   # lcs has no hard cut
            level, metric, score = None, None, None
            # hard wins over soft; pick strongest
            for name, val, hard, soft in metrics:
                if val >= hard:
                    level, metric, score = "hard", name, round(val, 4)
                    break
            if level is None:
                for name, val, hard, soft in metrics:
                    if val >= soft:
                        if level is None or val > score:
                            level, metric, score = "soft", name, round(val, 4)
            if level:
                flags.append({
                    "varna_a": entries[i]["varna"], "varna_b": entries[j]["varna"],
                    "lexicon_key_a": entries[i]["lexicon_key"], "lexicon_key_b": entries[j]["lexicon_key"],
                    "field_compared": f, "metric": metric, "score": score,
                    "all_metrics": {"token_jaccard": round(tj, 4), "char_3gram": round(c3, 4),
                                    "char_4gram": round(c4, 4), "lcs_ratio": round(lc, 4)},
                    "text_a": a, "text_b": b, "flag_level": level,
                    "suggested_action": "rewrite" if level == "hard" else "accept-with-rationale-or-leave-for-embedding-gate",
                    "rationale": "<TBD_HUMAN>"})
    flags.sort(key=lambda x: (x["flag_level"] != "hard", -x["score"]))

    # repeated head phrases (per field)
    head_groups = []
    for f in PRIMARY_FIELDS:
        heads = collections.defaultdict(list)
        for e in entries:
            tk = normalize(e[f]).split()
            if len(tk) >= HEAD_N:
                heads[" ".join(tk[:HEAD_N])].append(e["varna"])
        for h, vs in heads.items():
            if len(vs) >= HEAD_MIN_GROUP:
                head_groups.append({"field": f, "head_phrase": h, "varnas": vs, "flag_level": "soft"})

    # repeated generic terms (document frequency over combined text)
    df = collections.Counter()
    for e in entries:
        combined = f"{e['liberating_expression']} {e['functional_operation']}"
        df.update(set(tokens(combined)))
    generic = sorted([(w, c) for w, c in df.items() if c >= GENERIC_DF_MIN], key=lambda x: -x[1])

    hard = [f for f in flags if f["flag_level"] == "hard"]
    soft = [f for f in flags if f["flag_level"] == "soft"] + head_groups
    status = ("FAIL_EXACT_DUPLICATE" if not exact_ok else
              "HARD_REVIEW_REQUIRED" if hard else
              "SOFT_REVIEW_REQUIRED" if soft else "PASS_LOCAL_SURFACE_ONLY")
    return doc, entries, dups, exact_ok, flags, hard, soft, head_groups, generic, status


def write_reports(doc, entries, dups, exact_ok, flags, hard, soft, head_groups, generic, status):
    report = {
        "artifact": "b1_1_local_lexical_similarity_report",
        "note": "INTERIM WEAKER fallback for the blocked embedding gate; surface overlap only, NOT semantic. "
                "PASS_LOCAL_SURFACE_ONLY does NOT mean the embedding gate passed.",
        "b1_verdict_unchanged": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b_status": "BLOCKED",
        "input_sha256": draft_sha(), "n_evaluated": len(entries),
        "thresholds": {"token_jaccard_hard": TJ_HARD, "token_jaccard_soft": TJ_SOFT,
                       "char_ngram_hard": CN_HARD, "char_ngram_soft": CN_SOFT, "lcs_soft": LCS_SOFT,
                       "head_phrase_len": HEAD_N, "head_min_group": HEAD_MIN_GROUP,
                       "generic_df_min": GENERIC_DF_MIN},
        "exact_duplicates": dups, "n_hard": len(hard), "n_soft_pairs": len([f for f in flags if f["flag_level"] == "soft"]),
        "repeated_head_phrases": head_groups, "repeated_generic_terms": generic,
        "gate_status": status, "flags": flags,
        "non_claims": ["weaker than embedding gate", "no semantic synonymy detection",
                       "does not replace B1_1_NON_SYNONYM_EMBEDDING_GATE", "no ontology/Sanskrit/semantic claim"]}
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def tbl(rows):
        if not rows:
            return "_none_\n"
        out = "| A | B | field | metric | score | text A | text B | action |\n|---|---|---|---|---|---|---|---|\n"
        for f in rows:
            out += (f"| {f['varna_a']} | {f['varna_b']} | {f['field_compared']} | {f['metric']} | {f['score']} "
                    f"| {f['text_a'][:48]} | {f['text_b'][:48]} | {f['suggested_action']} |\n")
        return out
    soft_pairs = [f for f in flags if f["flag_level"] == "soft"]
    md = f"""# B1.1 Local Lexical / Phrase-Similarity Audit — REPORT (interim fallback)

## 1. Scope and non-claims
Local surface-overlap screen over all **34** resolved counter-poles. **Interim WEAKER fallback** for the
blocked embedding gate — detects shared tokens / character n-grams / templates, **NOT** deep paraphrase
synonymy. Does not modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B
(**BLOCKED**). No ontology / Sanskrit privilege / semantic-truth claim. **Structure, not validated meaning.**

## 2. Why this is weaker than the embedding gate
The real embedding gate (`all-MiniLM-L6-v2` cosine) is `BLOCKED_DEPENDENCY_UNAVAILABLE` (huggingface.co
egress-denied). This lexical audit sees **surface form only**: two operations can share almost no words yet
mean nearly the same thing — this screen is blind to that. **`PASS_LOCAL_SURFACE_ONLY` does NOT mean the
embedding gate passed.**

## 3. Inputs
- `b1_1_experimental_contrastive_lexicon_draft.json` (sha256 `{draft_sha()}`)
- fields: liberating_expression, functional_operation (primary) · combined (diagnostic) · contrast_boundary NOT a target
- entries: {len(entries)} · no deferrals · vowels excluded

## 4. Methods and thresholds
exact-dup · token Jaccard (hard ≥{TJ_HARD}, soft ≥{TJ_SOFT}) · char 3-gram & 4-gram Jaccard (hard ≥{CN_HARD},
soft ≥{CN_SOFT}) · LCS ratio (soft ≥{LCS_SOFT}) · repeated head phrase (first {HEAD_N} tokens across ≥{HEAD_MIN_GROUP}) ·
generic-term df (report ≥{GENERIC_DF_MIN}). Normalization: lowercase, strip punctuation, collapse whitespace;
stopwords removed for token-overlap (content/retain terms kept). Thresholds frozen before running.

## 5. Exact duplicate results
- liberating_expression: {dups['liberating_expression'] or 'NONE'}
- functional_operation: {dups['functional_operation'] or 'NONE'}
- result: **{'PASS (no exact duplicates)' if exact_ok else 'FAIL'}**

## 6. Pairwise flag summary
- pairs evaluated: {len(list(itertools.combinations(range(len(entries)),2)))*2} (561 pairs × 2 primary fields)
- **hard flags: {len(hard)}** · **soft pair-flags: {len(soft_pairs)}** · repeated-head groups: {len(head_groups)}

## 7. Hard flags
{tbl(hard)}
## 8. Soft flags
{tbl(soft_pairs)}
## 9. Repeated head phrases / repeated generic terms
Repeated head phrases (≥{HEAD_MIN_GROUP} entries): {head_groups or '_none_'}

Repeated generic terms (df ≥ {GENERIC_DF_MIN}, report-only): {', '.join(f'{w}×{c}' for w,c in generic) or '_none_'}

## 10. Gate status
**`{status}`** — {'no exact dups, no hard flags' if status=='PASS_LOCAL_SURFACE_ONLY' else 'review required'}.
Even PASS_LOCAL_SURFACE_ONLY is a **surface** pass only, NOT a contrastivity/embedding pass.

## 11. Relationship to the blocked embedding gate
The real embedding gate remains **owed**. Before B1.1 freeze: either (A) run the real embedding gate and
pass, or (B) the prereg explicitly records that the embedding gate was unavailable (egress-denied) and this
weaker lexical audit was used as fallback, with the elevated risk documented.

## 12. Bridge-generation warning
**Bridge-pool generation remains BLOCKED by default** until the real embedding gate runs. If the owner
proceeds on the local fallback only, the **B1.1 prereg MUST explicitly state** the weaker fallback and the
**elevated risk that R remains strong due to deep synonymy** this audit cannot detect.

## 13. Next recommended gate
{'`B1_1_LOCAL_LEXICAL_FLAG_ADJUDICATION` (flags to resolve)' if status in ('HARD_REVIEW_REQUIRED','SOFT_REVIEW_REQUIRED') else '`B1_1_BRIDGE_POOL_GENERATION_SPEC_DECISION` (surface-clean; owner decides embedding-gate path)'}

## Final status
```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             LOCAL LEXICAL AUDIT (interim, weaker)
Embedding run:         NO (still BLOCKED: model-host egress denial)
Model run:             NO
Bridge pool generated: NO
Generation/scoring/judging: NO
Gate status:           {status}
```
**Structure, not validated meaning.** Weaker surface screen; the embedding gate is still owed.
"""
    REPORT_MD.write_text(md, encoding="utf-8")


def main():
    doc, entries, dups, exact_ok, flags, hard, soft, head_groups, generic, status = audit()
    write_reports(doc, entries, dups, exact_ok, flags, hard, soft, head_groups, generic, status)
    print(f"[ok] entries=34 exact_dup={'none' if exact_ok else dups} hard={len(hard)} "
          f"soft_pairs={len([f for f in flags if f['flag_level']=='soft'])} head_groups={len(head_groups)}")
    print(f"[ok] generic terms (df>={GENERIC_DF_MIN}): {[f'{w}x{c}' for w,c in generic] or 'none'}")
    print(f"[ok] gate_status = {status}")
    print(f"[ok] wrote {REPORT_JSON.name} + {REPORT_MD.name}")


if __name__ == "__main__":
    main()
