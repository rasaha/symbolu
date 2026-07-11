#!/usr/bin/env python3
"""B1.10 — deterministic Tier-3 echo + convergence Jaccard (packet-aware audit, Stage 3).

Implements EXACTLY the frozen method in `B1_10_PACKET_AWARE_AUDIT_PREREG.md` §3 (committed BEFORE any
overlap was computed):

- tokenize: lowercase; strip punctuation (non a-z -> space); split on whitespace;
- remove a FIXED English stopword list (embedded below);
- remove the TARGET WORD's stem from both sides (shared by construction; not evidence of echo);
- Porter stemming (nltk.PorterStemmer — the canonical deterministic Porter algorithm);
- context set(word) = stems(A) ∪ stems(B)  (self-check lines excluded);
- tier3 set(word)   = stems(∪ all Tier-3 'specific' facet texts, both poles);
- Jaccard = |context ∩ tier3| / |context ∪ tier3|;  cap = 0.20 (frozen).

Also (advisory only) the convergence diagnostic: Jaccard(context, excluded-context) against the excluded
development set (frozen items-file contexts) and the excluded Claude v2 set; flag if > 0.50.

The script computes the QUANTITATIVE numbers only. Naturalness / condition-fit / fairness are auditor
judgements recorded in the audit report, not here. NO packet, context, or item is modified.

Guardrails: resonance / phonetic-fidelity refinement only. No GENUTILITY_*; no ONTOLOGICAL_SIGNAL; no
semantic-truth / ontology / Sanskrit-privilege claim. B1.4b' NULL_RETURN_BOTTOM; original B1.4b blocked;
Track B blocked. Structure, not validated meaning.
"""

import json
import pathlib
import re

from nltk.stem import PorterStemmer

HERE = pathlib.Path(__file__).resolve().parent
WORDS = ["pride", "freedom", "patience", "courage", "control", "doubt"]
JACCARD_CAP = 0.20            # frozen (pre-reg §3)
CONVERGENCE_FLAG = 0.50      # advisory (pre-reg §3)

# Fixed English stopword list (embedded; NOT nltk-data, to avoid any network/download dependency).
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "as", "of", "at", "by", "for", "with",
    "about", "against", "between", "into", "through", "during", "before", "after", "above", "below",
    "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", "again", "further", "once",
    "is", "am", "are", "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does",
    "did", "doing", "would", "should", "could", "ought", "will", "shall", "can", "may", "might", "must",
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", "yourself",
    "yourselves", "he", "him", "his", "himself", "she", "her", "hers", "herself", "it", "its", "itself",
    "they", "them", "their", "theirs", "themselves", "what", "which", "who", "whom", "this", "that",
    "these", "those", "here", "there", "when", "where", "why", "how", "all", "any", "both", "each",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "than",
    "too", "very", "just", "now", "also", "whether", "into", "onto", "upon", "without", "within",
    "whatever", "whenever", "wherever", "one", "ones",
}

_stemmer = PorterStemmer()


def stem_set(text, target_word):
    """Frozen tokenize→stopword→Porter→drop-target pipeline; returns a set of stems."""
    tokens = re.sub(r"[^a-z]+", " ", text.lower()).split()
    target_stem = _stemmer.stem(target_word.lower())
    out = set()
    for t in tokens:
        if t in STOPWORDS:
            continue
        s = _stemmer.stem(t)
        if not s or s == target_stem:
            continue
        out.add(s)
    return out


def jaccard(a, b):
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------- parsers (read committed files)
def parse_ab_context_md(md_path):
    """Parse a context .md with `word` headers followed by `A:`/`B:` lines. Returns {word:{'A':..,'B':..}}.
    Works for both the v3 official file (inside its fenced block) and the v2 file."""
    text = pathlib.Path(md_path).read_text(encoding="utf-8")
    # if there's a fenced block, restrict to its contents (v3); else use whole file (v2)
    fences = text.split("```")
    body = fences[1] if len(fences) >= 3 else text
    out, cur = {}, None
    for line in body.splitlines():
        s = line.strip()
        if s in WORDS:
            cur = s
            out[cur] = {}
        elif cur and s.startswith("A:"):
            out[cur]["A"] = s[2:].strip()
        elif cur and s.startswith("B:"):
            out[cur]["B"] = s[2:].strip()
    return out


def load_tier3(items_path):
    """{word: [facet texts (both poles)]} and excluded dev contexts {word:{'A':binding,'B':liberating}}."""
    d = json.load(open(items_path))
    tier3, dev = {}, {}
    for w in d["words"]:
        facets = []
        for pole in ("binding", "liberating"):
            facets += [f["text"] for f in w["packets"]["specific"][pole]]
        tier3[w["word"]] = facets
        dev[w["word"]] = {"A": w["contexts"]["binding"], "B": w["contexts"]["liberating"]}
    return tier3, dev


def main():
    v3 = parse_ab_context_md(HERE / "B1_10_OFFICIAL_CONTEXTS_v3_QWEN.md")
    v2 = parse_ab_context_md(HERE / "B1_10_OFFICIAL_CONTEXTS_v2_FROZEN.md")
    tier3, dev = load_tier3(HERE / "frozen" / "b1_10_control_ext_items.json")

    results = {}
    for w in WORDS:
        ctx = stem_set(v3[w]["A"], w) | stem_set(v3[w]["B"], w)
        t3 = set()
        for facet in tier3[w]:
            t3 |= stem_set(facet, w)
        echo_j = jaccard(ctx, t3)

        # convergence (advisory): vs excluded dev set and excluded Claude v2 set
        conv = {}
        dev_ctx = stem_set(dev[w]["A"], w) | stem_set(dev[w]["B"], w)
        conv["excluded_dev"] = jaccard(ctx, dev_ctx)
        if w in v2:
            v2_ctx = stem_set(v2[w]["A"], w) | stem_set(v2[w]["B"], w)
            conv["excluded_claude_v2"] = jaccard(ctx, v2_ctx)
        conv_max = max(conv.values())

        results[w] = {
            "tier3_echo_jaccard": round(echo_j, 4),
            "tier3_echo_shared_stems": sorted(ctx & t3),
            "echo_within_cap": echo_j <= JACCARD_CAP,
            "convergence_jaccard": {k: round(v, 4) for k, v in conv.items()},
            "convergence_max": round(conv_max, 4),
            "convergence_flag_gt_0_50": conv_max > CONVERGENCE_FLAG,
        }

    summary = {
        "artifact": "b1_10_packet_aware_echo_audit",
        "method": "frozen pre-reg §3 (lowercase/strip-punct/stopword/drop-target/Porter Jaccard)",
        "stemmer": "nltk.PorterStemmer",
        "jaccard_cap": JACCARD_CAP,
        "convergence_flag_threshold": CONVERGENCE_FLAG,
        "v3_block_source": "B1_10_OFFICIAL_CONTEXTS_v3_QWEN.md (canonical block a0abccb8...)",
        "results": results,
        "all_within_cap": all(r["echo_within_cap"] for r in results.values()),
        "any_convergence_flag": any(r["convergence_flag_gt_0_50"] for r in results.values()),
        "guardrails": "no GENUTILITY_*; no ONTOLOGICAL_SIGNAL; B1.4b' NULL_RETURN_BOTTOM; structure, not validated meaning",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    main()
