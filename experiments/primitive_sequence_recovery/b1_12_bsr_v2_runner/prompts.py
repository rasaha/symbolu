#!/usr/bin/env python3
"""V2 independent-judge prompt. One model, blind to any other model, produces per occurrence: supporting +
opposing evidence, relationship type, and a DBR score. Rubric text mirrors VARNA_SYMBOLIC_RESONANCE_PREREG_V2.md
(§1.2 question + scale, §1.3 supplementation firewall, §1.4 polarity-neutral opposition/resolution convention).
Frozen; not to be edited during a run."""
from __future__ import annotations
import json
from bsr_rubric import RELATIONSHIP_TYPES

_TAXO = " · ".join(RELATIONSHIP_TYPES)

_RULES = f"""FROZEN BARE-WORD SYMBOLIC RESONANCE (DBR) RULES — B1.12 V2 (VARNA_SYMBOLIC_RESONANCE_PREREG_V2.md):
- Question, per mapping: does the STABLE, ORDINARY, UNQUALIFIED bare word DIRECTLY AND NATURALLY ACCOUNT FOR the
  exact frozen mapping — through ANY of the relationship types below — WITHOUT semantic supplementation?
- "Account for" is not limited to embodiment/containment. A word may account for a mapping by embodying,
  constituting, characteristically expressing, implying, entailing as natural consequence, generating, OPPOSING,
  RESOLVING, regulating, or containing it. Opposition and resolution are LEGITIMATE, full-range relationships:
  a word that directly, conventionally, and story-free opposes/removes/resolves/neutralizes/stands in defining
  polarity to the mapping accounts for it and resonates. Polarity does NOT cap the score.
- "Direct" = available from the ordinary bare word itself without supplementation. It does NOT mean the mapped
  state must be positively contained as a dictionary feature. Antonymy is NOT evidence against resonance.
- Semantic supplementation (added actors, scenarios, metaphors, exceptional subtypes, invented narrative chains)
  is what lowers a score — for EVERY relationship type equally, never polarity.
- Relationship types (use ONLY these; do not invent): {_TAXO}.
- ONE extra value, `no_relationship`, is available for the honest case where the bare word does NOT account for the
  mapping by ANY relationship. Use `no_relationship` IF AND ONLY IF you assign dbr_score 0. Never use it with a
  non-zero score; never invent a positive relationship for something you are scoring 0.
- This is symbolic resonance ONLY — not truth, uniqueness, shuffled comparison, order, or transcendence."""

_SCALE = """DBR SCALE (use ONLY these five integers), scoring how strongly and directly the bare word accounts for
the mapping — independent of whether the accounting is by embodiment, implication, opposition, resolution, etc.:
100 = directly and characteristically accounted for by the ordinary meaning
 75 = strongly and conventionally accounted for; little interpretive work
 50 = a natural, broadly recognizable association that requires NO constructed scenario
 25 = reachable ONLY through metaphor, an external actor, contextual supplementation, an exceptional subtype, or a
      special scenario. HARD RULE: if accounting for it "requires interpretation / external context / a special
      case / an invented bridge," the score is 25, NOT 50. If your own opposing evidence names an invented bridge,
      the score may not exceed 25; if the whole link is an invented causal/narrative chain, score 0.
  0 = no defensible relationship without importing outside meaning (set relationship to `no_relationship`)
Examples (direction is irrelevant; only directness/conventionality/sufficiency/absence-of-supplementation matter):
 - love vs a "hatred" mapping: direct conventional opposition, ordinary meaning suffices -> high (75-100).
 - peace vs an "agitation" mapping: direct opposition/resolution -> high (75-100).
 - a boat vs a "despair" mapping only because a traveler USES a boat to escape despair -> supplementation -> <=25.
 - a lamp vs an "ignorance" mapping only via an added metaphor -> supplementation -> <=25."""


def build_judge_prompt(word_iast, dev, gloss, occurrences):
    """occurrences: mapped-only list of {occurrence_index, varna, mapping_gloss}. Single blind independent judgment."""
    occ = [{"occurrence_index": o["occurrence_index"], "varna": o["varna"], "mapping": o["mapping_gloss"]}
           for o in occurrences]
    sys = ("You are a careful, INDEPENDENT Sanskrit-and-symbolism analyst. You judge ONE word entirely on your own; "
           "you are NOT shown and must NOT assume any other analyst's evidence, relationship, score, or verdict. "
           "For each occurrence you give bidirectional evidence, choose the relationship type, and assign the DBR "
           "score. You do NOT compute means or the final verdict (code does that).\n\n" + _RULES + "\n\n" + _SCALE)
    user = f"""WORD: {word_iast} ({dev}) — ordinary bare-word meaning: "{gloss}"

For this bare word, produce STRICT JSON ONLY (no prose outside JSON):
{{
  "profile": "<the stable, ordinary, unqualified prototype meaning — no supplementation, no external actors>",
  "components": [
    {{
      "occurrence_index": <int>,
      "varna": "<varna>",
      "mapping": "<exact mapping text as given>",
      "supporting_evidence": "<strongest STORY-FREE reason the bare word accounts for this mapping (any relationship)>",
      "opposing_evidence": "<strongest reason it does NOT, or where supplementation would be needed>",
      "relationship": "<one of: {_TAXO}; or no_relationship IF AND ONLY IF dbr_score is 0>",
      "dbr_score": <0|25|50|75|100>,
      "adjudication": "<one concise, story-free sentence justifying the score>"
    }}
  ]
}}

The frozen mapped occurrences (do NOT change the mapping text, do NOT add/remove occurrences):
{json.dumps(occ, ensure_ascii=False, indent=2)}

Output exactly one JSON object with a "components" entry for EACH occurrence above. Scores strictly in
{{0,25,50,75,100}}. Relationship strictly from the list. Judge independently."""
    return sys, user
