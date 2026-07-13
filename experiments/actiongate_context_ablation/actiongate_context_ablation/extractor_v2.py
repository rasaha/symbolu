"""Multi-stage extractor (v2): Stage 1 structured + Stage 2/3 semantic with an
independent validator and fail-closed on disagreement.

Per unit:
  1. Stage 1 (structured) pins deterministic facts (HIGH confidence).
  2. For prose concepts, Stage 2 (frames) and Stage 3 (fuzzy) each vote:
       both present            -> accept  (HIGH)
       both absent             -> reject
       disagree                -> UNCERTAIN -> FAIL-CLOSED: accept the fact
     Fail-closed accepts a decision-relevant fact when only one independent method
     sees it, so a paraphrase that fools one method still surfaces the fact (the
     instability fix). It never fabricates a fact that neither method sees, and it
     only runs on the unit's own text, so a removed unit's fact correctly disappears.

Confidence per unit is exposed for the protected-span detector's features and for
audit. This module builds an ``adapter.RequestSpec`` and does NOT touch the oracle
path or ActionGate.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import adapter, concepts, semantic_extractor, structured_extractor, validator_extractor
from .extractor import _merge
from .units import Context

HIGH = "HIGH"
UNCERTAIN = "UNCERTAIN"

# Stage-3 fuzzy thresholds (calibrated on DEV/VALIDATION only — true concept sims
# cluster ~0.9, cross-concept bleed ~0.35-0.45, so these separate them cleanly).
CONFIRM_THRESHOLD = 0.50   # Stage 3 corroborates a Stage-2 finding -> HIGH confidence
RECOVER_THRESHOLD = 0.60   # Stage 3 alone recovers a concept Stage 2 missed
# mutually exclusive concept slots (an approval is single XOR dual, etc.)
_MUTEX = [{"appr_single", "appr_dual"}, {"sim_high", "sim_medium"}]


@dataclass(frozen=True)
class UnitExtraction:
    concepts: frozenset          # accepted concept keys
    structured_keys: frozenset   # facts pinned by Stage 1
    uncertain: frozenset         # concepts accepted via fail-closed (one-vote)
    structured_fragment: dict

    @property
    def confidence(self) -> str:
        return UNCERTAIN if self.uncertain else HIGH


def extract_unit(text: str) -> UnitExtraction:
    s_frag, s_keys = structured_extractor.extract(text)
    stage2 = set(semantic_extractor.detect(text))     # frames: precise + paraphrase recall
    v_sims = validator_extractor.sims(text)           # independent surface-fuzzy evidence
    stage3_confirm = {c for c, s in v_sims.items() if s >= CONFIRM_THRESHOLD}
    stage3_recover = {c for c, s in v_sims.items() if s >= RECOVER_THRESHOLD}

    accepted = set(stage2) | stage3_recover
    # mutual-exclusion resolution: keep the best-supported concept per slot
    for group in _MUTEX:
        present = [c for c in group if c in accepted]
        if len(present) > 1:
            best = max(present, key=lambda c: (c in stage2, v_sims.get(c, 0.0)))
            accepted -= (set(present) - {best})

    # UNCERTAIN (fail-closed kept): accepted but the two methods did not both agree.
    uncertain = {c for c in accepted if not (c in stage2 and c in stage3_confirm)}
    return UnitExtraction(concepts=frozenset(accepted), structured_keys=frozenset(s_keys),
                          uncertain=frozenset(uncertain), structured_fragment=s_frag)


def unit_fragment(text: str) -> dict:
    ex = extract_unit(text)
    frag = dict(ex.structured_fragment)
    concept_frag = concepts.merge_fragment(ex.concepts)
    # merge concept fragment into frag (evidence/approvals append, args/other set)
    for k, v in concept_frag.items():
        if k in ("evidence", "approvals"):
            frag.setdefault(k, []).extend(v)
        elif k == "args":
            frag.setdefault("args", {}).update(v)
        else:
            frag.setdefault(k, v)
    return frag


def realistic_spec_v2(ctx: Context, surviving_ids) -> adapter.RequestSpec:
    keep = set(surviving_ids)
    frags = [unit_fragment(u.text) for u in ctx.units if u.id in keep]
    return _merge(ctx.base, frags)
