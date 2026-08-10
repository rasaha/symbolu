# MIRROR_CASE_ANALYSIS — Do Deterministic Resolvers Generalise?

Hidden mirror cases (AUDIT ONLY — never scored in the benchmark). Each preserves
a capability but alters the surface. Two families per capability:
- **entity mirror** — changes entities, order, section numbers; KEEPS the cue phrase.
- **wording mirror** — KEEPS entities; changes only the relationship cue phrase.

Scored on **edge detection** (relationship discovery) to isolate generalisation
from packet construction. Run via `run_audit.mirror_audit`.

## Cue substitutions in the wording mirrors
| Capability | Entity mirror keeps | Wording mirror changes cue to |
|---|---|---|
| supersede | "deleted and replaced" | "struck out and substituted" |
| governs_over | "governs over the X" | "shall control against the X" |
| override | "notwithstanding … / policy prohibits" | "regardless of any contract clause" |
| exception | "except that" | "save where" |

## Results (edge detected?)

| Resolver | entity mirrors | wording mirrors |
|---|---|---|
| FrozenResolver | 1/4 | 1/4 |
| RuleResolver | **4/4** | **1/4** |
| GraphTraversalResolver | **4/4** | **1/4** |

Per-mirror (Rule / Graph):
- supersede_entity ✅  supersede_wording ❌
- governs_entity ✅  governs_wording ❌
- override_entity ✅  override_wording ✅ (only because the "policy prohibits" cue survived)
- exception_entity ✅  exception_wording ❌

## Interpretation
- **Generalise across entity / order / number:** 4/4. The resolvers do not depend
  on specific parties, document order, or section numbers — good.
- **Brittle to relationship wording:** 1/4. Changing the cue phrase (without
  changing the relationship) breaks detection. The one wording mirror that passed
  did so only because a second cue ("policy prohibits") happened to survive.

This confirms the methodological leakage (LEAKAGE_ANALYSIS.md): the deterministic
resolvers detect relationships by matching a **fixed cue vocabulary shared with
the gold**. On SEEB v1's exact phrasings they look strong (Graph 13/16), but a
small paraphrase of the relationship language collapses discovery.

## Consequence for trust
As frozen today the benchmark cannot distinguish a resolver that *understands*
relationships from one that *memorises SEEB's cue phrases*. Before freeze it needs
a **hidden, wording-varied** set (rotating cue phrasings) so that high scores
require robustness to relationship language, not cue lookup. Mirror cases here are
audit-only and are NOT added to benchmark scores.
