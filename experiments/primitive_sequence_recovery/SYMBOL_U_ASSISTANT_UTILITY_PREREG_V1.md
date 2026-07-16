# Symbol-U Assistant Utility — Preregistration **V1**

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`
**Documentation only.** This preregistration authorizes **no** runs. No assistant is implemented, no models run, no
conversations are scored, and no existing bridge / ontology / parser / mapping / B1.12 artifact is modified. Prompts
and implementation are **out of scope** and are built later against the frozen contracts here.

This is **not** a resonance study and **not** a mapping-validation study. It is an **assistant-utility** study.

## Objective
Determine whether the Symbol-U reasoning layer **improves assistant usefulness beyond ordinary reflective
reasoning.** The study does **not** attempt to prove Symbol-U; it only evaluates whether the architecture produces
better assistant responses.

## Architecture under test (frozen)
```
Conversation → frozen concern extraction → frozen concern ontology → frozen concern→concept bridge
            → frozen parser → frozen varṇa mappings → reflective synthesis → assistant response
```
No stage may change during the experiment. Frozen inputs are pinned by hash:

| Component | Path | SHA-256 (prefix) |
|---|---|---|
| Bridge spec | `SYMBOL_U_CONCERN_TO_CONCEPT_BRIDGE_SPEC_V1.md` | `4cf3c7f5…` |
| Concern ontology v1 | `symbol_u_bridge/concern_ontology_v1.json` | `39de5d4d…` |
| Concern→concept table v1 | `symbol_u_bridge/concern_to_sanskrit_concept_v1.json` | `04e8c4e4…` |
| Abstention rules | `symbol_u_bridge/abstention_rules.json` | `90dca16b…` |
| Parser | `sanskrit_stage1_parser.py` | `d885391f…` |
| Varṇa mappings (v3) | `frozen/varna_native_stage1_merged_v3.json` | `65116f37…` |

## Four experimental arms
Every arm receives **only** the user message and is otherwise identical (see Model control). The arms differ **only**
in the injected reasoning module — this is what makes each nested contrast attributable.

- **Arm A — Base.** The assistant alone. No second-pass reasoning, no symbolic module.
- **Arm B — Generic reflective.** A generic second-pass reflection matched to the symbolic arms in reasoning budget,
  response length, and model. **No** ontology, **no** Sanskrit, **no** Symbol-U. (Controls for "any reflection helps.")
- **Arm C — Concern ontology.** Uses the frozen concern ontology + frozen concern→concept bridge to reflect in a
  **concern-aware** way (grounded in the routed concern and its canonical concept's ordinary meaning). **No** varṇa
  decomposition, **no** varṇa mappings, **no** phonological reasoning. (Controls for "affliction/concept framing helps.")
- **Arm D — Full Symbol-U.** Uses the frozen concern ontology + concern→concept bridge + frozen parser + frozen varṇa
  mappings, with internal symbolic reasoning over the varṇa-level glosses. The final response must remain **natural**;
  **no Sanskrit terminology may appear unless the user explicitly asks.**

**Why four, not three:** the only contrast that isolates the *phonological* varṇa layer — Symbol-U's actual core —
is **D − C**. A base/reflection/full triad cannot separate "the affliction ontology helped" from "the varṇa mappings
helped." Arm C is the load-bearing control.

## Scenarios
Approximately **50** realistic user conversations, **balanced across the frozen concern ontology** (≈2 per concern
over the 25 v1 concerns, including some multi-concern and some deliberate `NO_APPLICABLE_CONCERN` scenarios). Each
scenario (schema: `symbol_u_utility_study/scenario.schema.json`) has: `scenario_id`, `user_message`,
`frozen_concern_ids`, `rationale`, `expected_bridge_output`, `category`. **The scenario set is authored and
hash-frozen BEFORE any arm runs** (roadmap M1); concern IDs and expected bridge output may **not** change during the
primary analysis.

*Illustrative only (not the frozen set):*
- `S001` "I keep telling myself I'll be fine once I've saved more, but I never feel safe." → concerns `C0002` (anxiety),
  `C0016` (money-concern) → bridge OK.
- `S002` "I'm afraid I'll lose my job and disappoint my family." → `C0001` (fear), `C0014` (duty), `C0017` (poverty) —
  processed independently, never merged.
- `S003` "What's the capital of France?" → `[]` → `NO_APPLICABLE_CONCERN` (symbolic layer abstains; arms C/D must add nothing).

## Model control
All four arms use the **same** LLM, temperature, context, token budget, stopping criteria, and system prompt —
**except** for the symbolic modules that define each arm. Decoding is deterministic; responses are logged verbatim;
arm labels are sealed until unblinding.

## Primary outcome
**Overall assistant usefulness** (integer 1–5). Definitions frozen in `symbol_u_utility_study/metrics.schema.json`.

## Secondary outcomes (rated independently)
clarity · understanding · relevance · emotional attunement · depth · actionability · reframing quality · user
alignment · avoidance of unsupported interpretation. (Each 1–5, higher better.)

## Overinterpretation (explicit penalty)
Unsupported symbolic claims are flagged per response with a severity (`minor`=0.5, `major`=1.0) in categories:
invented unconscious motive · asserted hidden cause · symbolic hypothesis stated as fact · excessive philosophical
elaboration · unnecessary Sanskrit discussion. Preregistered composite: **`net_usefulness = overall_usefulness −
Σ(penalty weights)`, floored at 1, reported alongside (never replacing) raw usefulness.** This guards against the
symbolic arm "winning" by sounding deep.

## Judging
**Blind** (arm labels hidden; `response_key` maps to arm only in a sealed key), **randomized arm order** per
scenario, **separate LLM judges** (multiple, for agreement) and **optional human judges**. Judges may optionally
guess the arm so **blinding integrity** can be checked; if arm D is identifiable above chance, affected contrasts are
flagged blinding-compromised. **Inter-rater agreement is reported** per metric (exact + within-one-step on the 1–5
scale, plus a chance-corrected coefficient), separately for LLM and human judges. Schemas:
`symbol_u_utility_study/judge.schema.json`, `metrics.schema.json`.

## Hypotheses
- **H1** — generic reflection improves over baseline (B > A).
- **H2** — concern ontology improves over generic reflection (C > B).
- **H3** — full Symbol-U improves over ontology (D > C).
- **H4** — full Symbol-U does **not** increase unsupported interpretation (overinterpretation at D ≤ at C).

## Analysis
Compare the **nested contrasts**: **B − A**, **C − B**, **D − C** (and D − C on overinterpretation for H4), per
metric, per scenario, per judge. **Do not** rely on **D − A** alone — it confounds reflection + ontology + phonology
and cannot isolate the varṇa layer. Primary analysis holds concern extraction **fixed** via the frozen concern IDs;
live-extraction robustness is a **separate, secondary** analysis. Full plan: `symbol_u_utility_study/analysis_plan.json`.

## Success criteria (engineering, not statistical — deferred by instruction)
- **D − C** shows a **consistent** positive usefulness delta across a majority of judges **and** scenarios;
- the usefulness gain at D comes **without** an increase in overinterpretation vs C (H4 holds);
- reframing quality improves at D **without** increased overinterpretation;
- gains are consistent, not driven by a few scenarios or a single judge.

## Failure criteria
- ontology alone (C) explains all gains → **D − C ≈ 0**;
- the symbolic layer adds no measurable usefulness benefit;
- the symbolic layer improves depth but **harms** understanding/relevance/factual grounding;
- the symbolic layer **increases** unsupported interpretation (H4 violated).

Failure outcomes are reported as prominently as success; no post-hoc arm redefinition.

## Limitations (explicit)
Success would demonstrate **engineering utility** — that the architecture yields better assistant responses — **not**
proof that Symbol-U is objectively correct, that the chosen Sanskrit concept is the only valid representation, that
the varṇa mappings are true, or that concern extraction is solved. It defines and evaluates a reproducible pipeline;
it is not a truth claim about the symbolic system.

## Deliverables (produced by this preregistration)
- `SYMBOL_U_ASSISTANT_UTILITY_PREREG_V1.md` (this document)
- `symbol_u_utility_study/scenario.schema.json`
- `symbol_u_utility_study/judge.schema.json`
- `symbol_u_utility_study/metrics.schema.json`
- `symbol_u_utility_study/analysis_plan.json`
- `symbol_u_utility_study/execution_roadmap.json`

## Discipline
No experiment, no prompts, no implementation, no scoring. No modification of any bridge, ontology, parser, mapping,
or B1.12 artifact. Preregistration only; execution is gated on the roadmap milestones and this frozen design.
