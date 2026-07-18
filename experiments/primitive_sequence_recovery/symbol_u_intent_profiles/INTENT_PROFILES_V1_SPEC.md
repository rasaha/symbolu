# Symbol-U V1 Intent Profile — Specification (FROZEN)

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`
**Status: `INTENT_PROFILES_V1_FROZEN`.** Documentation/specification only. **No frozen artifact, bridge component,
mapping, ontology, parser, scenario, or utility-study preregistration was modified.**

## Objective
Define the **V1 Intent Profile** as the frozen **runtime interface** between the Symbol-U engine and the LLM. Its
purpose is **not** to generate advice or wording. It makes explicit **exactly what structured symbolic information
Arm D receives that Arm C does not**, so the preregistered **D − C** comparison stays interpretable. The intent
profile is therefore a **data contract, not a prompt**.

## What it is
For each of the 25 frozen concerns, exactly **one immutable profile** carrying **symbolic state only**:
`concern_id`, `concern_name`, `canonical_sanskrit_concept` (IAST + Devanāgarī), `pronunciation_used_iast`,
`frozen_varna_sequence`, `mapped_varnas`, `frozen_drives` (the verbatim binding-vṛtti glosses, occurrence-level, in
varṇa order), `n_drives`, `varna_multiplicity`, `mapping_coverage`, `parser_status`, `bridge_confidence`,
`abstention_status`, and `provenance`. Schema: `intent_profile.schema.json` (strict, `additionalProperties:false`).

## What it deliberately excludes
No assistant advice, stance hints, reframing suggestions, coaching language, response templates, user guidance,
inferred emotions, inferred motivations, psychological interpretation, ranking/weighting of drives, or dynamic
per-prompt analysis. Exclusion is **enforced mechanically** by the schema's `additionalProperties:false` and verified
at build (no unexpected fields present).

## Design principles (all satisfied)
Deterministic · derived only from frozen artifacts · mechanically reproducible (regeneration yields the identical
`intent_profiles_sha256`) · free of authored interpretation (drives are **verbatim** frozen glosses — verified) ·
LLM-independent · stable across runs · human-inspectable. It represents **symbolic state, not assistant behavior.**

## Universal usage rule (identical for every profile)
Held once at the artifact level and applying to all profiles verbatim:

> The profile represents possible symbolic framing pressures derived from the frozen Symbol-U mappings. These are
> auxiliary signals only. They are hypotheses, never facts. They must not override the user's explicit meaning and
> may be ignored when unsupported by the conversation.

## `bridge_confidence` (mechanical, documented — not a judgement)
A transparent function of frozen numbers only:
`HIGH` if `coverage==1.0 & n_mapped>=2 & n_b1_12_tier1>=1`; `MEDIUM` if `coverage==1.0 & n_mapped>=1`; else `LOW`.
(`n_b1_12_tier1` = how many of the word's mapped varṇas are in the B1.12 agreement-stable set d/s/v/y.) V1 result:
13 HIGH, 12 MEDIUM, 0 LOW.

## Example (illustrative — the data, not a prompt)
`C0016 money-concern → dhana`: `frozen_drives` = [`dh` → *tṛṣṇā* (limitless thirst to acquire…), `n` → *moha*
(blind attachment/infatuation…)]; `n_drives`=2; `coverage`=1.0; `bridge_confidence`=MEDIUM; `abstention`=NONE. That
verbatim payload — and nothing more — is what Arm D receives on top of Arm C.

## Scope boundary (future versions, not V1)
Dynamic per-prompt weighting, prompt-specific drive activation, symbolic interaction between multiple concerns,
generated reflection cues, balancing/liberating recommendations, and response-generation heuristics are **out of
scope**.

## Validation (all passed)
25 profiles, exactly one per frozen concern · schema-valid · reproducible from frozen inputs (identical hash) ·
drives verbatim-frozen (not authored) · no authored response content · no concern-specific advice · no frozen
artifact modified.

## Interpretation limits (explicit)
These intent profiles are **not** claims about the user, **not** psychological assessments, and are **not** generated
from the current prompt. They do **not** demonstrate utility. They only define the **deterministic symbolic payload
available to Arm D** in the preregistered four-arm utility study.

## Deliverables
`intent_profiles_v1.json`, `intent_profile.schema.json`, `intent_profile_manifest_v1.json` (hashes of all frozen
upstream artifacts + validation results), and this spec. `intent_profiles_sha256` =
`96d2512ba54a15660ce6bd028f81663aa937e968009b37bcc166aa95427b2907`.
