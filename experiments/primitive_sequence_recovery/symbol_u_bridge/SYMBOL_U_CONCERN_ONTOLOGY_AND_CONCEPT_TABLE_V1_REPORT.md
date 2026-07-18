# Symbol-U Seed Concern Ontology & Concept Bridge — V1 Report

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`
**Status: `BRIDGE_SEED_V1_FROZEN`.** Docs/data only. No experiment, no resonance scoring, no B1.12 modification, no
change to the frozen parser or varṇa mappings/glosses, no prompts, no user-facing responses.

Controlling architecture: `SYMBOL_U_CONCERN_TO_CONCEPT_BRIDGE_SPEC_V1.md` and the schemas under `symbol_u_bridge/`.
This delivers the first usable, versioned **data layer** for the bridge: a bounded seed concern ontology, a
deterministic concern→Sanskrit-concept table, full provenance/ambiguity/exclusion audits, and frozen hashes.

- **Final ontology SHA-256:** `39de5d4d2f0252634948b4f15e6486494094479dfe013131aa17807207cfe168`
- **Final concept-table SHA-256:** `04e8c4e4ffd48b364b8efeae407070c14c9f332b9f1c6b772a19e3f827103e4d`

## Result summary
- **25 canonical concerns** (from a 45-candidate pool; 20 excluded), **closed vocabulary**, ids `C0001…C0025`.
- **One primary Sanskrit concept per concern**, all **distinct → 0 many-to-one mappings** in V1.
- All 25 concepts **attested** (MW headwords); alternatives + ambiguity + confidence documented per concern.
- **Abstention representable** at every stage (`NO_APPLICABLE_CONCERN` / `NO_APPLICABLE_CONCEPT` / `NO_MAPPED_VARNA`).
- Both schema-bound artifacts **validate** against the frozen schemas.
- Post-freeze audit: **25/25 parse, 100% mapped coverage, 0 zero-mapped** — and no concept was chosen or changed
  because of coverage.

## Category distribution (25 concerns)
| Category | n | concerns |
|---|--:|---|
| fear_and_insecurity | 2 | fear (bhaya), anxiety (cintā) |
| anger_and_conflict | 2 | anger (krodha), resentment (dveṣa) |
| attachment_and_loss | 2 | attachment (āsakti), grief (śoka) |
| desire_and_ambition | 2 | craving (kāma), greed (lobha) |
| confusion_and_uncertainty | 2 | confusion (moha), doubt (saṃśaya) |
| self_worth_and_identity | 2 | pride (garva), shame (lajjā) |
| loneliness_and_relationship_needs | 1 | separation-longing (viraha) |
| responsibility_and_duty | 2 | duty (kartavya), burden (bhāra) |
| money_and_material_concerns | 2 | money-concern (dhana), poverty (dāridrya) |
| work_and_purpose | 3 | diligence (udyoga), laziness (ālasya), purpose (lakṣya) |
| learning_and_understanding | 2 | curiosity (jijñāsā), knowledge (jñāna) |
| calm_patience_and_regulation | 3 | patience (kṣamā), contentment (santoṣa), calm (śānti) |

Counts are intentionally not forced equal: **loneliness_and_relationship_needs has only 1** because the modern
emotional sense of "loneliness" has **no clear ordinary single Sanskrit lexeme** (excluded, see below); only
`viraha` (separation from a beloved) is lexically clean. work/purpose and calm each carry 3 where clear lexemes were
available.

## Complete concern → Sanskrit-concept table
| id | concern | concept (IAST) | Devanāgarī | ordinary gloss | conf. |
|---|---|---|---|---|---|
| C0001 | fear | bhaya | भय | fear | HIGH |
| C0002 | anxiety | cintā | चिन्ता | anxious thought, worry | HIGH |
| C0003 | anger | krodha | क्रोध | anger, wrath | HIGH |
| C0004 | resentment | dveṣa | द्वेष | aversion, hatred | HIGH |
| C0005 | attachment | āsakti | आसक्ति | attachment, clinging | HIGH |
| C0006 | grief | śoka | शोक | grief, sorrow | HIGH |
| C0007 | craving | kāma | काम | desire, longing | HIGH |
| C0008 | greed | lobha | लोभ | greed, covetousness | HIGH |
| C0009 | confusion | moha | मोह | delusion, confusion | HIGH |
| C0010 | doubt | saṃśaya | संशय | doubt, uncertainty | HIGH |
| C0011 | pride | garva | गर्व | pride, arrogance | MEDIUM |
| C0012 | shame | lajjā | लज्जा | shame, modesty | HIGH |
| C0013 | separation-longing | viraha | विरह | separation (from a beloved) | MEDIUM |
| C0014 | duty | kartavya | कर्तव्य | duty (what ought to be done) | HIGH |
| C0015 | burden | bhāra | भार | burden, load | MEDIUM |
| C0016 | money-concern | dhana | धन | wealth, money | HIGH |
| C0017 | poverty | dāridrya | दारिद्र्य | poverty, indigence | HIGH |
| C0018 | diligence | udyoga | उद्योग | effort, industry | MEDIUM |
| C0019 | laziness | ālasya | आलस्य | sloth, laziness | HIGH |
| C0020 | purpose | lakṣya | लक्ष्य | aim, goal, target | MEDIUM |
| C0021 | curiosity | jijñāsā | जिज्ञासा | desire to know | HIGH |
| C0022 | knowledge | jñāna | ज्ञान | knowledge, understanding | MEDIUM |
| C0023 | patience | kṣamā | क्षमा | patience, forbearance | MEDIUM |
| C0024 | contentment | santoṣa | सन्तोष | contentment | HIGH |
| C0025 | calm | śānti | शान्ति | peace, tranquility | HIGH |

## Excluded candidates (20)
| candidate | proposed as | reason |
|---|---|---|
| dharma | duty | EXCESSIVE_POLYSEMY (kartavya chosen) |
| karma | work/action | EXCESSIVE_POLYSEMY / doctrinal |
| ahaṃkāra | ego | TECHNICAL_OR_DOCTRINAL (garva chosen) |
| ātman | self/identity | TECHNICAL_OR_DOCTRINAL |
| loneliness | loneliness | NO_CLEAR_SANSKRIT_CONCEPT |
| validation | need for recognition | TOO_CONTEXT_DEPENDENT |
| mamatā | possessiveness | OVERLAPPING_DEFINITION (āsakti) |
| rāga | passion/attachment | OVERLAPPING_DEFINITION (āsakti); polysemous |
| icchā | wish | OVERLAPPING_DEFINITION (kāma) |
| māna | pride/honor | OVERLAPPING_DEFINITION (garva); polysemous |
| saṃyama | restraint | TECHNICAL_OR_DOCTRINAL |
| vairāgya | dispassion | TECHNICAL_OR_DOCTRINAL |
| duḥkha | suffering | TOO_CONTEXT_DEPENDENT (umbrella) |
| īrṣyā | jealousy | NOT_SUITABLE_FOR_SEED_SCOPE (deferred) |
| bhrama | confusion | DUPLICATE_CONCERN (moha) |
| aniścaya | indecision | OVERLAPPING_DEFINITION (saṃśaya) |
| spṛhā | ambition/longing | OVERLAPPING_DEFINITION (kāma) |
| prayatna | effort | DUPLICATE_CONCERN (udyoga) |
| vidyā | knowledge | DUPLICATE_CONCERN (jñāna) |
| utkaṇṭhā | longing | OVERLAPPING_DEFINITION (viraha) |

None was excluded because of downstream varṇa mappings.

## Ambiguity & confusable concerns
Confusable concern pairs (distinguished by inclusion/exclusion criteria + clarification cues; if still unclear,
extraction returns both — processed independently — or abstains): fear↔anxiety, anger↔resentment,
attachment↔craving, craving↔greed, confusion↔doubt, pride↔shame, grief↔separation-longing, duty↔burden,
money-concern↔poverty, diligence↔purpose, diligence↔laziness, curiosity↔knowledge, patience↔calm,
contentment↔calm. Full detail + concept-level alternatives in `concern_concept_ambiguity_audit_v1.json`. Concept
ambiguity resolution is deterministic: primary = rank-1 by semantic fit; alternatives are documented but never used
at runtime; if two concepts were genuinely indistinguishable by ordinary meaning, the bridge emits
`NO_APPLICABLE_CONCEPT` rather than guessing.

## Many-to-one policy
**No many-to-one mappings in V1** — all 25 concerns map to distinct Sanskrit concepts. No materially different
concerns were silently collapsed.

## Multi-concern utterances (frozen runtime rules)
One utterance may yield multiple concern IDs, each processed independently (e.g. "I'm afraid I'll lose my job and
disappoint my family" → money-concern/poverty + fear + duty). Frozen: **max 3 concerns/utterance**; **ordering** by
extraction confidence desc then ascending id; **dedup** identical ids (keep the specific concern over its parent
category); **confidence threshold** floor with `NO_APPLICABLE_CONCERN` fallback; **tie-break** ascending id; **no
hybrid** concerns invented.

## Abstention coverage
Representable at every stage: `NO_APPLICABLE_CONCERN` (extraction), `NO_APPLICABLE_CONCEPT` (table miss),
`NO_MAPPED_VARNA` (engine), `LOW_CONFIDENCE_SUPPRESS` (synthesis). See `abstention_rules.json`. This mirrors B1.12's
most reliable signal (`no_relationship`).

## Parser & technical coverage (computed AFTER freeze; membership only)
25/25 parse successfully; **all 25 have 100% mapped-consonant coverage**; 0 zero-mapped; 0 unsupported units; 0
concepts flagged `BRIDGE_SUPPORTED_SYMBOLIC_LAYER_UNAVAILABLE`. Parser SHA `d885391f…`, mapping table SHA
`65116f37…`. **Mapping gloss text was not read, summarized, ranked, or used** to alter any selection; no concept was
replaced on account of its varṇa decomposition. Full table: `concern_concept_parser_coverage_v1.json`.

## Interpretation limits (explicit)
This table does **not** prove: that the selected Sanskrit concept is the *only* valid representation; that the varṇa
mappings are objectively true; that concern extraction is solved; or that the symbolic layer improves assistant
behavior. It **only** defines a reproducible input bridge for later testing.

## Selection-firewall attestation
Concept selection used **only** ordinary concern meaning, lexical clarity, attestation, practical personal-assistant
relevance, and concern↔concept semantic fit. **Not consulted for selection:** varṇa glosses, B1.12 resonance scores,
mapping-stability rankings, expected symbolic output, Tier-1 varṇa membership, or anticipated product benefit. Some
chosen concepts coincide with words used in B1.12 (they are simply the ordinary lexemes for these concerns); their
B1.12 scores were not consulted. The parser/coverage audit ran only after the table was frozen and altered nothing.

## Artifacts
`concern_ontology_v1.json`, `concern_to_sanskrit_concept_v1.json`, `concern_candidate_pool_v1.json`,
`concern_exclusions_v1.json`, `concern_concept_ambiguity_audit_v1.json`, `concern_bridge_manifest_v1.json`, this
report, plus companions `concern_extraction_aids_v1.json` (per-concern confusable/cues/abstention/utterance
examples — held outside the `additionalProperties:false` core ontology schema) and `concern_concept_provenance_v1.json`
(grammatical category, lexical source/citation, attestation, reason-for-fit, alternatives, ambiguity, confidence),
and the post-freeze `concern_concept_parser_coverage_v1.json`.

## Repository discipline
No B1.12 artifact, frozen parser, or varṇa mapping/gloss was modified. The frozen bridge schemas were left unchanged;
task-required fields that the minimal schemas cannot hold live in clearly-labelled companion files. No resonance
scoring, no product evaluation, no assistant prompts.
