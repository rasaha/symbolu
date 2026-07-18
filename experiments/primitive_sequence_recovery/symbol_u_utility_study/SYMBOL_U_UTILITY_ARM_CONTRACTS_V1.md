# Symbol-U Assistant Utility — Four-Arm Contracts **V1** (FROZEN)

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`
**Status: `ARM_CONTRACTS_V1_FROZEN`.** Docs only. **No LLM prompts, no model calls, no judging, no implementation.**
This freezes the **interface each arm must satisfy** so the eventual utility run is attributable. Machine-readable
spec + hashes: `arm_contracts_v1.json` (`contract_sha256` = `ae72a3f2…`).

Controlling: `SYMBOL_U_ASSISTANT_UTILITY_PREREG_V1.md`. Roadmap milestone **M2**.

## The one idea this freezes
The four arms must be **identical in every way except the single reflection module that defines them.** If that holds,
each nested contrast measures exactly one added ingredient:

- **B − A** = does *any* second-pass reflection help?
- **C − B** = does *concern/concept framing* beat generic reflection?
- **D − C** = does the *varṇa (phonological) layer* add anything over the concept framing? ← the Symbol-U question.

## Model-control invariants (identical across ALL arms)
Same model, temperature (0 / deterministic), top-p/top-k, fixed seed, context window, token budget, stopping criteria,
and base system prompt — **except** the arm's reflection module. Arm labels are sealed until unblinding; response order
is randomized per scenario. The **only** thing that varies between arms is the injected reflection material.

## Shared pipeline contract
- **S1 (concern extraction)** is held **fixed** via each scenario's `frozen_concern_ids` during the primary analysis
  (arms C/D receive them; A/B ignore them). Live extraction is a *separate* secondary study.
- **S5 (reflection synthesis)** uses the **same instruction template** for arms B/C/D; only the injected material
  differs. (Prompt wording is out of scope — this fixes the *contract*, not the text.)
- **Final response** is natural language; for arm D, no Sanskrit / Symbol-U / varṇa terminology may surface unless the
  user explicitly asks.

## The four arms
| Arm | Name | Reflection passes | Injected reflection material | Purpose |
|---|---|:--:|---|---|
| **A** | base | 0 | none | baseline |
| **B** | generic_reflection | 1 | a generic second pass, **no** ontology/Sanskrit, matched to C/D in budget + length | controls for "any reflection helps" |
| **C** | concern_ontology | 1 | concern-aware reflection grounded in the routed concern + the concept's **ordinary** meaning; **no** varṇa decomposition, **no** mappings | controls for "concern/concept framing helps" |
| **D** | full_symbol_u | 1 | internal symbolic reasoning over the **varṇa-level** binding-vṛtti glosses of the concept's decomposition; output natural | adds the phonological layer (isolated by D − C) |

## Module-access matrix (what each arm may read)
| Frozen module | A | B | C | D |
|---|:--:|:--:|:--:|:--:|
| `concern_ontology_v1` | ✗ | ✗ | ✓ | ✓ |
| `concern_to_sanskrit_concept_v1` | ✗ | ✗ | ✓ | ✓ |
| `parser` (`sanskrit_stage1_parser.py`) | ✗ | ✗ | ✗ | ✓ |
| `varna_mappings_v3` | ✗ | ✗ | ✗ | ✓ |

Arm C is the load-bearing control: it gets the concept **word and its ordinary meaning** but **not** the varṇa
decomposition or the mappings — so **D − C** is the only contrast that can attribute an effect to the phonological
layer specifically.

## Frozen inputs (pinned by hash in `arm_contracts_v1.json`)
Prereg, concern ontology v1, concern→concept table v1, parser, varṇa mappings v3, scenario set v1, abstention rules.

## Out of scope (explicit)
LLM prompt wording, the actual model calls, judging, and any implementation. Those are later milestones built against
this frozen contract.

## Discipline
No prior/frozen artifact modified; no model run; no scoring. This document + `arm_contracts_v1.json` only fix the
arm interfaces and the model-control invariants.
