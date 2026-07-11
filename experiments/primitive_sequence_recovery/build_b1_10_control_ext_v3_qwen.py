"""Build the B1.10 control-extension items using the APPROVED v3 Qwen blind contexts.

Separately-labeled variant: writes `frozen/b1_10_control_ext_items_v3_qwen.json` and leaves the original
`frozen/b1_10_control_ext_items.json` (excluded development contexts), all pilot/failed-attempt/audit/manifest
artifacts, and the rejected freedom version byte-UNCHANGED. Only the context sentence at each (word, pole)
changes; the six words, three tiers, 2 poles, 72-cell design, packet definitions, and overlap/style rules are
identical (reused from `build_b1_10_control_ext.py`).

Context→pole mapping: Condition A (other-conditioned) -> `binding`; Condition B (self-grounded) -> `liberating`.
Source: `B1_10_OFFICIAL_CONTEXTS_v3_QWEN.md` (Stage-3 packet-aware audit PASS 6/6; freedom re-authored blind at
seed 20260821 after the first freedom pair was audit-REJECTED on condition-fit). Approved canonical 12-sentence
block sha256 pinned below.

Resonance / phonetic-fidelity refinement only — no GENUTILITY_*, no ONTOLOGICAL_SIGNAL, no semantic-truth /
ontology / Sanskrit-privilege claim. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b + Track B blocked.
Structure, not validated meaning. No result label produced.
"""
from __future__ import annotations
import hashlib
import pathlib
import re

import build_b1_10_control_ext as BLD

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
APPROVED_MD = HERE / "B1_10_OFFICIAL_CONTEXTS_v3_QWEN.md"
ITEMS_OUT_V3 = FROZEN / "b1_10_control_ext_items_v3_qwen.json"

# Pinned approved canonical 12-sentence block hash (from the audit; supersedes pre-audit a0abccb8...).
EXPECT_BLOCK_SHA = "e0a1477ebaaf41df95b489b7547a895369f115d5231c424fc8598d4f598c3046"
WORDS = BLD.WORDS


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def parse_approved_block(md_path: pathlib.Path):
    """Return (contexts, block_text). contexts = {word: {'binding': A, 'liberating': B}}.
    A (Condition A) -> binding pole; B (Condition B) -> liberating pole."""
    text = md_path.read_text(encoding="utf-8")
    block = text.split("```")[1].strip("\n") + "\n"     # the fenced canonical block
    contexts, cur = {}, None
    for line in block.splitlines():
        s = line.strip()
        if s in WORDS:
            cur = s
            contexts[cur] = {}
        elif cur and s.startswith("A:"):
            contexts[cur]["binding"] = s[2:].strip()
        elif cur and s.startswith("B:"):
            contexts[cur]["liberating"] = s[2:].strip()
    return contexts, block


def build_v3():
    md_bytes = APPROVED_MD.read_bytes()
    contexts, block = parse_approved_block(APPROVED_MD)

    # verify the approved block hash and completeness BEFORE building
    block_sha = _sha_bytes(block.encode("utf-8"))
    assert block_sha == EXPECT_BLOCK_SHA, f"approved block hash mismatch: {block_sha} != {EXPECT_BLOCK_SHA}"
    assert set(contexts) == set(WORDS), f"missing words: {set(WORDS) - set(contexts)}"
    for w in WORDS:
        assert "binding" in contexts[w] and "liberating" in contexts[w], f"{w}: missing A/B"
    n_sentences = sum(len(v) for v in contexts.values())
    assert n_sentences == 12, f"expected 12 sentences, parsed {n_sentences}"

    provenance = {
        "status": "APPROVED_V3_CONTROL_EXT_MOCK_ONLY",
        "contexts_source": "B1_10_OFFICIAL_CONTEXTS_v3_QWEN.md (non-Claude blind Qwen; Stage-3 audit PASS 6/6)",
        "approved_context_file_sha256": _sha_bytes(md_bytes),
        "approved_context_block_sha256": block_sha,
        "context_pole_mapping": "Condition A -> binding ; Condition B -> liberating",
        "context_provenance_note": ("Approved v3 blind contexts. freedom was audit-REJECTED (condition-fit) "
                                    "and re-authored blind at seed 20260821; the rejected version and the "
                                    "excluded development / Claude sets are preserved in their own artifacts, "
                                    "unchanged. Packets/tiers/design identical to the original items file."),
        "supersedes_context_block_pre_audit": "a0abccb89091578cc6ee81b22143bd2bcd82ee9eb8624ba6855224825a418bfc",
        "b1_4b_prime_status": "NULL_RETURN_BOTTOM",
    }

    doc = BLD.build(contexts=contexts, items_out=ITEMS_OUT_V3, provenance=provenance)

    # verify every inserted context matches the approved source exactly (requirement 5)
    for w in WORDS:
        assert doc_word(doc, w)["contexts"]["binding"] == contexts[w]["binding"]
        assert doc_word(doc, w)["contexts"]["liberating"] == contexts[w]["liberating"]
    return doc, block_sha, _sha_bytes(md_bytes)


def doc_word(doc, w):
    return next(x for x in doc["words"] if x["word"] == w)


if __name__ == "__main__":
    doc, block_sha, file_sha = build_v3()
    print(f"wrote {ITEMS_OUT_V3.name}")
    print(f"approved_context_file_sha256: {file_sha}")
    print(f"approved_context_block_sha256: {block_sha}")
    print(f"items_v3 sha256: {_sha_bytes(ITEMS_OUT_V3.read_bytes())}")
    print(f"words={doc['n_words']} status={doc['status']}")
    for w in doc["words"]:
        print(f"  {w['word']:9} N={w['facet_count']} tier2/tier3 jaccard={w['tier2_tier3_content_jaccard']}")
