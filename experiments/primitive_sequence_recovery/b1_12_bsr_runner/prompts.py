#!/usr/bin/env python3
"""Author and scorer prompt builders. Strict-JSON contracts; taxonomy and scale embedded verbatim."""
from __future__ import annotations
import json
from bsr_rubric import RELATIONSHIP_TYPES

_TAXO = " · ".join(RELATIONSHIP_TYPES)

_RULES = f"""FROZEN BARE-WORD SYMBOLIC RESONANCE (BSR) RULES — B1.12 (VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md + freeze amendment):
- Question, per mapping: does the STABLE, ORDINARY, UNQUALIFIED meaning of the bare word naturally ACCOUNT FOR this
  frozen mapping, WITHOUT semantic supplementation?
- A mapping does NOT resonate if accounting for it requires: added adjectives, extra nouns, external actors,
  exceptional subtypes, invented stories, post-hoc lexical-sense switching, or speculative rescue.
- Relationship types (use ONLY these; do not invent): {_TAXO}.
- Embodiment is NOT failure. Resolution is NOT mandatory. Record whichever relationship naturally holds.
- This is symbolic resonance ONLY — not truth, uniqueness, shuffled comparison, causation, order, or transcendence."""

_SCALE = """BSR SCALE (use ONLY these five integers):
100 = directly and characteristically accounted for by the bare word
 75 = strongly implied by the ordinary meaning
 50 = plausible but requires interpretation
 25 = requires substantial qualification, an exceptional case, or an external actor
  0 = cannot be supported without adding external meaning"""

def build_author_prompt(word_iast, dev, gloss, occurrences):
    """occurrences: mapped-only list of {occurrence_index, varna, mapping_gloss}."""
    occ = [{"occurrence_index": o["occurrence_index"], "varna": o["varna"], "mapping": o["mapping_gloss"]}
           for o in occurrences]
    sys = ("You are a careful Sanskrit-and-symbolism analyst. You AUTHOR a locked bare-word profile and "
           "bidirectional evidence. You DO NOT assign any score, combined score, or verdict.\n\n" + _RULES)
    user = f"""WORD: {word_iast} ({dev}) — ordinary bare-word meaning: "{gloss}"

For this bare word, produce STRICT JSON ONLY (no prose outside JSON):
{{
  "profile": "<the stable, ordinary, unqualified prototype meaning — no supplementation, no external actors>",
  "components": [
    {{
      "occurrence_index": <int>,
      "varna": "<varna>",
      "mapping": "<exact mapping text as given>",
      "supporting_evidence": "<strongest STORY-FREE reason the bare word accounts for this mapping>",
      "opposing_evidence": "<strongest reason it does NOT, or where supplementation would be needed>",
      "proposed_relationship": "<one of: {_TAXO}>"
    }}
  ]
}}

The frozen mapped occurrences (do NOT change the mapping text, do NOT add/remove occurrences):
{json.dumps(occ, ensure_ascii=False, indent=2)}

Output exactly one JSON object with a "components" entry for EACH occurrence above. No score. No verdict."""
    return sys, user

def build_scorer_prompt(word_iast, gloss, profile, author_components):
    """author_components: list from the author output (occurrence_index, varna, mapping, supporting/opposing, proposed_relationship)."""
    sys = ("You are an INDEPENDENT scorer. You receive a locked profile, the exact frozen mappings, and another "
           "analyst's supporting/opposing evidence. You assign the final relationship and BSR score per occurrence "
           "and a holistic combined-reconciliation score. You MUST NOT alter the profile, mappings, or evidence "
           "text. You do NOT compute means or the final verdict (code does that).\n\n" + _RULES + "\n\n" + _SCALE)
    user = f"""WORD: {word_iast} — ordinary meaning: "{gloss}"
LOCKED PROFILE: {profile}

For each occurrence below, decide the FINAL relationship type and the BSR score (0/25/50/75/100) for how naturally
the bare word accounts for the mapping, using the author's evidence and your own judgment. Output STRICT JSON ONLY:
{{
  "components": [
    {{
      "occurrence_index": <int>,
      "final_relationship": "<one of: {_TAXO}>",
      "bsr_score": <0|25|50|75|100>,
      "adjudication": "<one concise sentence justifying the score, story-free>"
    }}
  ],
  "combined_reconciliation": <0-100 holistic: do the component accounts cohere into ONE symbolic reading? explanatory only>,
  "combined_note": "<one sentence; must NOT be used to repair weak components>"
}}

Occurrences with the author's evidence:
{json.dumps(author_components, ensure_ascii=False, indent=2)}

One "components" entry per occurrence. Scores strictly in {{0,25,50,75,100}}. Relationship strictly from the list."""
    return sys, user
