"""Build the FROZEN items for the B1.10 pole-context sanity MICRO-TEST (mock-only; 3 words).

Reads the active fidelity_bundle_v1 mapping (v3 table + combined bridge) and writes a small frozen items file
holding, for each of {happy, peace, love}: the varṇa sequence, a binding/other-conditioned context, a
liberating/self-grounded context, and the two CONTEXT-INVARIANT packets (binding + liberating), each a list of
{varna, text} facets read verbatim from the frozen v3 table (deduped, order-preserved — the same dedup the
scaffolds use). Contexts are the operator-approved sentences from the approval table (3632c92) / prereg (95d08dc).

This does NOT re-derive any existing frozen bundle artifact; it creates one NEW micro-test items file and pins the
source hashes. Packets are copied from the frozen v3 table so a test can assert byte-equality to the live lookup.

Resonance / phonetic-fidelity refinement only — no GENUTILITY_*, no ONTOLOGICAL_SIGNAL, no semantic-truth /
ontology / Sanskrit-privilege claim. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b + Track B remain blocked.
Structure, not validated meaning. No result label is produced here.
"""
from __future__ import annotations
import hashlib
import json
import pathlib
from typing import Dict, List

import varna_bridge_active as AB
import build_b1_9_pole_did_scaffold as B0   # BINDING / LIBERATING field-name constants

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
V3_TABLE = FROZEN / "varna_polarity_table_v3.json"
BRIDGE_MANIFEST = FROZEN / "varna_polarity_bridge_v3.json"
DECOMPOSER = HERE / "stage_a_prime_coverage.py"
ITEMS_OUT = FROZEN / "b1_10_pole_context_microtest_items.json"

WORDS = ("happy", "peace", "love")   # clean/usable subset only — longing + devotion deliberately excluded

# Operator-approved contexts (approval table 3632c92 / prereg 95d08dc). Same word appears in BOTH contexts.
CONTEXTS = {
    "happy": {
        "binding":    "He was happy only because he had beaten his rival and could watch the man's face fall.",
        "liberating": "She was happy sitting alone at dawn, wanting nothing and comparing herself to no one.",
    },
    "peace": {
        "binding":    "He felt peace only once his opponents were silenced and no one could challenge him.",
        "liberating": "Peace settled in her on its own, needing no victory and no one's permission.",
    },
    "love": {
        "binding":    "His love demanded she prove it daily, and curdled into jealousy whenever she looked away.",
        "liberating": "Her love asked for nothing back; it simply wished the other well and let him go.",
    },
}

JUDGE_QUESTION = ("How well does this packet describe the inner experiential weather or source-condition "
                  "underlying this word in this context?")


def _sha(p) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _packet(seq: List[str], pole: str, table: Dict) -> List[Dict]:
    """Deduped, order-preserved facets for a sequence at one pole (the scaffolds' dedup rule)."""
    seen, out = set(), []
    for v in seq:
        txt = table[v][pole]
        if txt in seen:
            continue
        seen.add(txt)
        out.append({"varna": v, "text": txt})
    return out


def build() -> Dict:
    table = json.loads(V3_TABLE.read_text())["varnas"]
    labels = AB.labels()
    words = []
    for w in WORDS:
        seq = AB.word_to_varnas(w)
        assert all(v in table for v in seq), f"{w}: out-of-table varṇa {seq}"
        words.append({
            "word": w,
            "varna_sequence": seq,
            "contexts": {"binding": CONTEXTS[w]["binding"], "liberating": CONTEXTS[w]["liberating"]},
            "packets": {
                "binding": _packet(seq, B0.BINDING, table),
                "liberating": _packet(seq, B0.LIBERATING, table),
            },
        })

    doc = {
        "artifact_type": "b1_10_pole_context_microtest_items",
        "mapping_era": labels["mapping_era"], "table": labels["table"], "bridge": labels["bridge"],
        "aspiration_applied": labels["aspiration_applied"],
        "status": "FROZEN_MICROTEST_MOCK_ONLY",
        "representation_version": "B1.10_pole_context",
        "words_included": list(WORDS),
        "excluded_words": ["longing", "devotion"],
        "excluded_reason": "longing: asymmetric discriminating power; devotion: too many off-axis facets "
                           "(approval table 3632c92).",
        "judge_question": JUDGE_QUESTION,
        "rating_scale": {"min": 0, "max": 6, "meaning": "0 = not at all, 6 = extremely well"},
        "packet_invariance_note": "Each word's binding/liberating packets are fixed by its varṇas and are "
                                  "context-invariant; only the context changes and sets which pole SHOULD fit. "
                                  "Packet text is copied verbatim from the frozen v3 table.",
        "source_hashes": {
            "varna_polarity_table_v3.json": _sha(V3_TABLE),
            "varna_polarity_bridge_v3.json": _sha(BRIDGE_MANIFEST),
            "stage_a_prime_coverage.py": _sha(DECOMPOSER),
        },
        "interpretation_note": "No result label is emitted by this test. A positive context_pole_margin would show "
                               "only source-condition / resonance legibility to judges — NOT ontology, semantic "
                               "truth, Sanskrit privilege, generation utility, or word-specific varṇa mapping. A "
                               "null means the pole-context distinction is not legible under this rating design.",
        "b1_4b_prime_status": "NULL_RETURN_BOTTOM", "track_b_status": "BLOCKED",
        "n_words": len(words), "words": words,
    }
    ITEMS_OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
    return doc


if __name__ == "__main__":
    d = build()
    print(f"wrote {ITEMS_OUT.name} | words={d['n_words']} ({', '.join(d['words_included'])}) "
          f"era={d['mapping_era']}")
    for w in d["words"]:
        print(f"  {w['word']:6} seq={','.join(w['varna_sequence'])} "
              f"| binding facets={len(w['packets']['binding'])} liberating facets={len(w['packets']['liberating'])}")
    print(f"items sha: {_sha(ITEMS_OUT)}")
