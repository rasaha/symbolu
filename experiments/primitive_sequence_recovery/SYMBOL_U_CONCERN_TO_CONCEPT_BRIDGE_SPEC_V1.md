# Symbol-U Concern → Concept Bridge — Architectural Specification **V1**

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`
**Documentation only.** No experiment, no scoring, no change to any B1.12 artifact, mapping, parser, or frozen
preregistration. This freezes the **architecture** of the deterministic bridge from natural-language conversation to
canonical Symbol-U concepts. Populated data (the concern ontology, the concern→concept table) are separate versioned
artifacts authored against the schemas here (see roadmap). Out of scope: LLM prompts, evaluation, utility testing,
and any redesign of Symbol-U.

## Objective

Define a **deterministic, reproducible** bridge between conversation and the Symbol-U varṇa engine that **removes
evaluator freedom at the concern-selection stage** and is implementable **without changing the varṇa mappings**.

The design rationale is the B1.12 synthesis result: the varṇa mappings are internally patterned, but *free choice*
(of scores in B1.12; of concepts here) is where evaluator-dependence enters. The bridge therefore pushes all
free-text judgment into a **bounded selection over frozen, versioned vocabularies**, and makes everything downstream
of the canonical concern **fully deterministic**.

## Frozen pipeline

```
            ┌───────────────────────── model (bounded) ─────────────────────────┐
User Conversation
      │  STAGE 1  Concern Extraction        in: turn(s)         out: ranked concern IDs (frozen ontology only)
      ▼
Canonical Concern                            ← deterministic selection + threshold (ties → ascending ID)
      │  STAGE 2  Canonical Concern Dictionary   frozen, versioned ontology (schema: concern_ontology.schema.json)
      ▼
      │  STAGE 3  Concern → Sanskrit Concept   in: concern ID   out: 1 canonical concept  (frozen TABLE lookup)
      ▼
Canonical Sanskrit Concept                   ← deterministic; no free generation
      │  STAGE 4  Concept Validation          abstain (NO_APPLICABLE_CONCEPT) rather than force
      ▼
      │  STAGE 5  Varṇa Engine                frozen parser + frozen v3 lexicon — UNCHANGED
      ▼
Frozen Symbol-U Mapping (varṇa → binding-vṛtti glosses)
      │  STAGE 6  Reflective Synthesis        in: gloss set + confidence   out: bounded reflection
            └───────────────────────── model (bounded) ─────────────────────────┘
      ▼
Assistant Response (reflection injected as auxiliary, non-authoritative)
```

Determinism boundary: **Stages 2–5 are fully deterministic and inspectable.** The only two model-touched stages are
1 (extraction) and 6 (synthesis), and both are **bounded** — extraction may only *select* from the frozen ontology;
synthesis may only produce contributions from a fixed allowed-list (Stage 6). Evaluator freedom at concern selection
is removed by making Stage 1 a classification into a closed set with a deterministic tie-break, not a free naming.

---

## STAGE 1 — Concern Extraction
- **Input:** the user conversation (one or more turns).
- **Output:** a ranked list of **concern IDs drawn only from the frozen ontology** (Stage 2), each with a score; then
  a deterministic selection picks the canonical concern(s): keep IDs at/above the confidence threshold, cap at top-k,
  break ties by ascending concern ID. Below threshold → **`NO_APPLICABLE_CONCERN`**.
- **Output is NOT Sanskrit.** It is a canonical concern list. Symbol-U is **not** invoked here.
- **Constraint:** the extractor never invents concern names; it maps text onto existing IDs (a bounded classification).
  Worked illustrations (canonical concern in **bold**):
  - "I'm worried about money." → **financial insecurity**
  - "My son won't stop watching YouTube." → **compulsion**, attention, rumination
  - "I feel nobody understands me." → **loneliness**, validation, identity

## STAGE 2 — Canonical Concern Dictionary
A **frozen, versioned** ontology. Every concern carries: unique **id**, English **label**, **description**,
**inclusion_criteria**, **exclusion_criteria**, **parent**, **children**, **synonyms**. Schema:
`symbol_u_bridge/concern_ontology.schema.json`. **LLMs never invent concern names — they only select from this set.**
The populated ontology is authored and hashed separately (roadmap M1); the inclusion/exclusion criteria are what make
extraction reproducible rather than free-associative.

## STAGE 3 — Concern → Sanskrit Concept
A **table-driven, deterministic** mapping from each concern ID to exactly **one canonical Sanskrit concept**. Schema:
`symbol_u_bridge/concept_mapping.schema.json`. Illustrative entries:

| concern | → | concept (IAST / Devanāgarī) |
|---|---|---|
| financial insecurity | → | **artha** / अर्थ |
| anger | → | **krodha** / क्रोध |
| attachment | → | **mamatā** / ममता |
| hope | → | **āśā** / आशा |

Where multiple attested candidates exist, the frozen `selection_rule` chooses deterministically (rank → highest
Tier-1 varṇa coverage → ascending IAST codepoint). **No free generation** at any point.

## STAGE 4 — Concept Validation (abstention)
If no suitable concept exists for the selected concern, emit **`NO_APPLICABLE_CONCEPT`** rather than forcing one. This
mirrors B1.12's most reliable signal (`no_relationship`): honestly declining to map beats fabricating a link. Full
rules and precedence: `symbol_u_bridge/abstention_rules.json`.

## STAGE 5 — Varṇa Engine
Reference the **frozen** `sanskrit_stage1_parser.py` (SHA `d885391f…`) and **frozen** mapping table
`frozen/varna_native_stage1_merged_v3.json` (SHA `65116f37…`). **No changes, no new mappings, no reinterpretation.**
The concept word is parsed to varṇas; each mapped consonant yields its frozen binding-vṛtti gloss.

## STAGE 6 — Reflective Synthesis (bounded contribution)
Turns the gloss set + confidence into an auxiliary reflection. **Allowed / forbidden contributions are fixed:**

| The symbolic layer MAY | The symbolic layer MAY NOT |
|---|---|
| suggest hidden framing | diagnose |
| suggest reflective questions | predict the future |
| suggest alternate perspectives | claim causal certainty |
| identify possible unconscious emphasis | override explicit user intent |
| recommend alternative conceptual anchors | contradict known facts |
| | fabricate symbolic meaning |

The reflection is **auxiliary and non-authoritative**. (This spec fixes *what may be contributed*; it does **not**
specify prompts — out of scope.)

---

## Confidence model
Every symbolic contribution carries a confidence assembled from:
- **bridge confidence** — Stage-1 extraction score for the selected concern;
- **mapping coverage** — fraction of the concept's consonants that are mapped;
- **relationship family** — B1.12 stability of the families involved (`opposition`/`no_relationship` high; `implication` weak; others low);
- **historical stability** — B1.12 per-varṇa cross-evaluator agreement (Tier-1 varṇas **d, s, v, y** preferred; evaluator-sensitive **t, k, n, r** downweighted);
- **`NO_APPLICABLE_CONCEPT` / `NO_MAPPED_VARNA`** — hard abstentions that zero the contribution.

**Tier-1 mappings from B1.12 are preferred**; a reflection resting only on low-power or evaluator-sensitive varṇas is
surfaced (if at all) as an explicitly hedged, low-confidence aside.

---

## Worked examples
*(Varṇa decompositions and glosses below are read verbatim from the frozen v3 lexicon — faithful, not invented. The
"reflection" lines illustrate the Stage-6 output **contract**, not any prompt.)*

### Example 1 — Money anxiety
1. **Conversation:** "I keep telling myself I'll be fine once I have more saved, but I never feel safe."
2. **Concern extraction →** `financial insecurity`
3. **Canonical concern →** financial insecurity (C-id)
4. **Concern → concept →** **artha** (अर्थ, "wealth / aim")
5. **Varṇa decomposition →** `r` → *sarvanāśa* (the defeatist "I have nothing / all is lost" annihilation-thought); `th` → *viśāda* (melancholy, dejection that sinks one's mood)
6. **Confidence →** MIXED (`r` Tier-2 evaluator-sensitive; `th` low-power) — surface hedged.
7. **Reflection (contract illustration):** *hidden framing* — the worry may be less about the number than about a
   background dread of total loss (*sarvanāśa*) and the low mood it feeds; *reflective question* — "what would 'safe
   enough' actually feel like, independent of the balance?" No diagnosis, no prediction.

### Example 2 — Relationship conflict
1. **Conversation:** "Every time my partner cancels plans I just seethe about it for days."
2. **Concern extraction →** `resentment` (aversion)
3. **Canonical concern →** resentment
4. **Concern → concept →** **dveṣa** (द्वेष, "aversion / hatred")
5. **Varṇa decomposition →** `d` → *peevishness / reactive irritability* (perverse contrary reactivity); `v` → *rigid
   over-holding, clinging to one's own position*; `ṣ` → *kāma* (grasping worldly desire)
6. **Confidence →** HIGHER (two **Tier-1** varṇas: `d`, `v`).
7. **Reflection (contract illustration):** *unconscious emphasis* — the sting may be sustained by reactive
   irritability (*d*) plus a rigid holding-on to how things "should" go (*v*); *alternate perspective* — "is the anger
   protecting an expectation you're gripping?" No claim about the partner, no causal certainty.

### Example 3 — Creative block
1. **Conversation:** "I sit down to write and just freeze — I keep second-guessing every sentence."
2. **Concern extraction →** `self-doubt`
3. **Canonical concern →** self-doubt
4. **Concern → concept →** **saṃśaya** (संशय, "doubt")
5. **Varṇa decomposition →** `s` → *the sattvic / clarity impulse clung to*; `ś` → *artha as possessive acquisition*;
   `y` → *aviśvāsa* (self-doubt that cannot commit; lack of confidence)
6. **Confidence →** HIGHER (`s` and `y` are **Tier-1**; `y`→*aviśvāsa* fits directly).
7. **Reflection (contract illustration):** *hidden framing* — the freeze looks like a commitment problem
   (*aviśvāsa*), possibly from gripping an idealized standard of clarity (*s*); *reflective question* — "what would a
   deliberately rough first sentence cost you?" No prediction of success/failure.

### Example 4 — Fear of failure
1. **Conversation:** "I'm not even applying — if I try and don't get it, I don't know how I'd recover."
2. **Concern extraction →** `fear`
3. **Canonical concern →** fear
4. **Concern → concept →** **bhaya** (भय, "fear")
5. **Varṇa decomposition →** `bh` → *mūrcchā* (entrancement; loss of common sense/discernment under a spell); `y` →
   *aviśvāsa* (self-doubt that cannot commit)
6. **Confidence →** MIXED (`bh` low-power; `y` Tier-1).
7. **Reflection (contract illustration):** *alternate anchor* — the block may be a kind of entrancement (*mūrcchā*)
   where one imagined outcome eclipses discernment, held in place by a stalled self-trust (*aviśvāsa*); *reflective
   question* — "what does 'recover' concretely require — and is it as unavailable as it feels?" No fatalistic claim.

---

## Deliverables produced by this spec
- **`SYMBOL_U_CONCERN_TO_CONCEPT_BRIDGE_SPEC_V1.md`** (this document — architecture, stage contracts, confidence model, worked examples, diagram).
- **`symbol_u_bridge/concern_ontology.schema.json`** — concern ontology schema.
- **`symbol_u_bridge/concept_mapping.schema.json`** — concern→Sanskrit-concept mapping schema.
- **`symbol_u_bridge/abstention_rules.json`** — abstention rules + precedence.
- **`symbol_u_bridge/implementation_roadmap.json`** — implementation roadmap (deterministic bridge only).
- Architecture diagram — the frozen pipeline block above.

## Out of scope (explicitly)
No LLM prompts specified; no evaluation designed; no utility testing designed; no redesign of Symbol-U; no
modification of the mappings, parser, glosses, scale, taxonomy, preregistrations, or any B1.12 artifact. This document
specifies **only the deterministic bridge**.

## Honest note
The load-bearing new degree of freedom is the **concern ontology + concern→concept table** (roadmap M1–M2). Freezing
both as versioned, criteria-bearing artifacts is what actually removes evaluator freedom at concern selection — the
schemas here define their shape; authoring and hashing their contents is the next step. Downstream of the canonical
concern, the bridge is fully deterministic and reuses the frozen varṇa engine untouched.
