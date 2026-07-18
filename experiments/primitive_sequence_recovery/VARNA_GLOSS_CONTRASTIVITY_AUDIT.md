# Varṇa-Gloss Contrastivity Audit (B1.1 gate — audit only)

## 1. Scope and non-claims

Read-only audit of the current varṇa meaning lexicon, asking **one** question: *are multiple varṇas mapped
to meanings similar enough that a random draw from the same pool (control R) stays fluent, evocative, and
judge-preferred even when the mapping is wrong?* This is the mechanism candidate for the B1 result
**A ≈ R**.

**Non-claims (all hold):** this audit does **not** implement B1.1, run generation, run scoring, modify B1,
change the B1 verdict, or unblock Track B. It makes **no** claim of ontology validation, Sanskrit
privilege, semantic truth, or H2 validation. It produces **no** replacement lexicon — only *what must be
rewritten and why*. No lexicon file was modified. **Structure, not validated meaning.**

Contrastivity is **necessary but not sufficient**: even a perfectly contrastive pool with an arbitrary
word→mapping link would still yield A ≈ R (that is what the R_deranged control in the B1.1 design tests,
not this audit). This audit addresses only the *pool-overlap* hypothesis.

## 2. Input lexicon files inspected

| file | role | used by B1? | modified? |
|---|---|---|---|
| `varna_lens/lexicon_authoritative.json` | authoritative per-consonant `binding_state`/`liberating_state` (34 consonants + 12 vowels) | yes (LEX, via `varna_lens.py`) | **no** |
| `varna_lens/layer2_bridge_vocab.json` | the **64-phrase BRIDGE pool** A and R actually draw from; keyed by canonical gloss; `_meta.entries=64` | yes (BRIDGE) | **no** |
| `varna_lens/lexicon_authoritative_varna.json` | untested CANDIDATE (1ae4d4b), `CANDIDATE_UNTESTED_NOT_USED_IN_B1` | no | **no** |
| `experiments/.../B1_LEXICON_CONTRASTIVENESS_DIAGNOSTIC.md` | prior read-only inspection (4ee85ab), superseded by this scripted-grade pass | n/a | **no** |

Consonant poles were extracted verbatim from `lexicon_authoritative.json.consonants[].{binding_state,
liberating_state}.{english,sanskrit}`. Vowels carry only prose state descriptions and are not part of the
BRIDGE pool; excluded from collision scoring.

## 3. Exact duplicate findings

**Verified by script over `lexicon_authoritative.json` (34 consonants):** **4 liberated-pole Sanskrit
labels are exact-string duplicates**, each shared by exactly two varṇas (8 consonants). Two further pairs
share a Sanskrit *root* but differ in the full compound → **near**-duplicates. **No exact duplicate exists
on the blocked pole, and no exact-string English duplicate exists on either pole.**

| # | shared liberated label | severity | varṇa A (blocked → liberated) | varṇa B (blocked → liberated) | BRIDGE effect |
|---|---|---|---|---|---|
| 1 | **Viśvāsa** | **EXACT** (Sanskrit) | Kha (Worry → Trust) | Ya (Lack-of-confidence → Confidence) | collapses to **one** bridge phrase |
| 2 | **Vinaya** | **EXACT** (Sanskrit) | Ṅa (Vanity → Humility) | Ja (Ego-inflation → humility/ego-softening) | collapses to **one** bridge phrase |
| 3 | **Viveka** | **EXACT** (Sanskrit) | Ca (Aviveka → discriminative clarity) | Na (Blind-attachment → discriminative detachment) | collapses to **one** bridge phrase |
| 4 | **Jāgaraṇa** | **EXACT** (Sanskrit) | Ta (Inertia/sleep → Awakening/Alertness) | Bha (Deluded-obsession → Awareness/awakening) | collapses to **one** bridge phrase |
| 5 | **Kṣamā** (root) | near (shared root) | Ṭha (Repentance → Kṣamā/Ātmaprasāda) | Da (Peevishness → Kṣamā/Dhairya) | two **near-synonym** bridge phrases |
| 6 | **Karuṇā** (root) | near (shared root) | Ḍha (Sadistic-cruelty → Karuṇā) | La (Cruelty → Karuṇā/Sneha) | two **near-synonym** bridge phrases |

**8 of 34 consonants (24%) share an *exact* liberated Sanskrit pole; 12 of 34 (35%) collide exactly-or-near
on the liberated pole.** The English poles are *never* exact-string duplicates (e.g. "humility" vs
"humility/ego-softening"; "awareness/awakening" vs "awakening/alertness"), so the collisions live at the
Sanskrit/affect layer, not the raw English string.

**Mechanistic confirmation of pool redundancy:** 34 consonants × 2 poles = 68 candidate glosses, but the
frozen BRIDGE pool has **`_meta.entries = 64`**. The missing 4 are *exactly* the four EXACT liberated
duplicates above — the BRIDGE keys by canonical gloss, so each exact pair **collapses to a single shared
phrase**. Two varṇas therefore point at the *identical* conditioning phrase; the two near-duplicates
(#5, #6) remain as separate but near-synonymous entries (`karuṇā` vs `karuṇā/sneha`; `kṣamā/ātmaprasāda`
vs `kṣamā/dhairya`). Either way the pool carries **redundant positive entries a random draw hits
interchangeably.**

**No exact duplicate on the blocked pole.** Every binding vrtti is a *distinct acoustic root* (Āśā, Cintā,
Ceṣṭā, Mamatā, Dambha, Aviveka, Vikalatā, Ahaṁkāra, Lobha, Kapaṭatā, Vitarka, Anutāpa, Lajjā, Piśunatā,
Īrṣyā, Jāḍya, Viṣāda, Krodha, Tṛṣṇā, Moha, Ghṛṇā, Bhaya, Avajñā, Mūrcchā, Praśraya, Aviśvāsa, Sarvanāśa,
Krūratā, Adharma, …). **This asymmetry is the single most important finding of the audit (see §7, §10).**

## 4. Near-duplicate liberated-pole clusters

| cluster (liberated) | varṇas | Sanskrit | severity |
|---|---|---|---|
| **Fearlessness** | Ḍa (Nirbhayatā/Svīkāra), Pha (Abhaya) | different Sanskrit, same English | near (English-exact) |
| **Contentment** | Jha (Santoṣa/Aparigraha), Dha (Nivṛtti/Tuṣṭi) | Santoṣa vs Tuṣṭi (synonyms) | near |
| **Detachment / non-attachment / renunciation** | Ka (Nirāśā), Gha (Anāsakti), Dha (Nivṛtti), Na (discriminative detachment) | distinct Sanskrit, one affect | broad-valence |
| **Joy / affection / friendliness / sympathetic-joy** | Tha (Harṣa/Prīti), Pa (Maitrī/Sneha), Ṇa (Muditā) | distinct Sanskrit, one warm-affect basin | broad-valence |
| **Knowledge / clarity** | Ca (Viveka), Na (Viveka), Sa (Mokṣa→"liberation/clarity"), Ha (Parā-vidyā), Kṣa (Aparā-vidyā) | mixed | near→broad |
| **Silence / stillness / objectivity** | Ga (Sthiti "stillness"), Ṭa (Maunam "silence/objectivity") | distinct Sanskrit | broad-valence |

## 5. Near-duplicate blocked-pole clusters

Blocked poles are far more distinct (§3), but their **English renderings** cluster into a few basins:

| cluster (blocked) | varṇas | notes | severity |
|---|---|---|---|
| **Cruelty / harshness** | Ḍha (Piśunatā "sadistic cruelty"), La (Krūratā "cruelty"; BRIDGE softens to "separative harshness") | two "cruelty" entries | near |
| **Attachment / craving / greed / desire** | Gha (Mamatā), Na (Moha "blind attachment"), Dha (Tṛṣṇā "craving"), Jha (Lobha "greed"), Ṣa (Kāma "desire"), Śa ("material greed") | six-way clinging/acquisition basin | broad-valence |
| **Vanity / ego / hypocrisy** | Ṅa (Dambha), Ja (Ahaṁkāra), Ña (Kapaṭatā) | ego-display basin; note Ṅa & Ja both remediate to **Vinaya** (see §3 #2) | near→broad |
| **Inertia / darkness / delusion / dogma** | Ta (Jāḍya), Bha (Mūrcchā), Ha (Avidyā/Rātri), Ṣa (Tamoguṇa "confusion"), Sa ("escapism"), Kṣa (Mithyā-jñāna "dogma"), Na (Moha) | tamas/ignorance basin | broad-valence |
| **Fear / shyness** | Pha (Bhaya), Ḍa (Lajjā "shyness") | overlapping | near |
| **Worry / melancholy / hatred** | Kha (Cintā), Tha (Viṣāda), Pa (Ghṛṇā) | negative-affect basin | broad-valence |

## 6. Broad-valence clusters (summary)

Collapsing all 34 consonants by affect, the pool concentrates into a small number of basins on each side:

- **Positive basins (liberated pole — where the exact duplicates live):** *release* (detach/renounce/
  non-attach), *warmth* (compassion/friendliness/joy), *steadiness* (trust/confidence/firmness/patience/
  forgiveness), *clarity* (discernment/awakening/knowledge), *humility*, *restraint*.
- **Negative basins (blocked pole — more distinct, but English-clustered):** *clinging/greed*,
  *aversion/cruelty/hatred*, *ego-display*, *tamas/ignorance/inertia*, *anxiety/melancholy*, *fear*.

The **positive side is the contrastivity problem**: many distinct afflictions were assigned the *same
remedial counter-state*, so aspirational conditioning draws from ~6 repeated states plus a few basins.

## 7. Why these collisions make R strong

A and R draw from the **same frozen 64-phrase BRIDGE pool**. Given the §3–§6 structure:

1. **Redundant positive entries.** Four liberated Sanskrit labels collapse two varṇas onto a *single*
   shared bridge phrase (Viśvāsa, Vinaya, Viveka, Jāgaraṇa), and two more (Kṣamā, Karuṇā) produce
   near-synonym phrase pairs (forgiveness-self-acceptance / patience-forgiveness; compassion /
   compassion-gentleness). A random draw has a high chance of landing on the same positive state as the
   "correct" draw.
2. **Basin redundancy.** Even off the exact duplicates, most positive entries fall into ~6 affect basins.
   A random pick lands in the *same affective neighborhood* as the resonance pick → similar evocative tone.
3. **Aspirational lean.** Generation conditioning that leans on the liberated/aspirational pole is drawing
   from the *most collapsed* part of the pool, maximizing R's chance of reading as coherent.
4. **Judge can't separate.** A blind judge scoring "which is better" sees two fluent, similarly-toned
   evocative conditionings and splits ≈ 50/50 → **A ≈ R** (observed: A_vs_R 0.5135, CI straddles 0.5).
   Meanwhile **S (scrambled) breaks intra-word order**, which *is* detectable → A beat S (0.5615). This
   audit is consistent with the exact B1 signature: **fail R, pass S.**

**Crucial caveat (honest):** the *blocked* poles are distinct (§3). So one plausible contributor to R's
strength is specifically that conditioning used the **collapsed positive pole**. This is a *hypothesis the
audit surfaces*, not a proven cause, and it is a design lever (§10), not a rescue.

## 8. Recommended rewrite principles

Per the B1.1 four-field format — **blocked impulse · liberated impulse · functional operation · contrast
boundary** — with the *contrast boundary naming the specific colliding sibling(s)*. Principles only; **no
final meanings asserted.**

| collision | rewrite principle (what must separate them) |
|---|---|
| **Viśvāsa** (Kha, Ya) | split by *object of trust*: Kha = remaining open under **impersonal uncertainty/open space**; Ya = **self-efficacy/confidence to act**. Boundaries: Kha "not self-confidence (Ya)"; Ya "not open-space tolerance (Kha)". |
| **Vinaya** (Ṅa, Ja) | split by *what deflates*: Ṅa = dropping **outward pretense/display**; Ja = dissolving **inflated I-centeredness**. Boundaries name each other. |
| **Viveka** (Ca, Na) | split by *operation*: Ca = **analytic discrimination** (right/wrong, real/unreal); Na = **detachment from infatuation/delusion**. Boundaries name each other. |
| **Kṣamā** (Ṭha, Da) | split by *direction*: Ṭha = **self-directed** release of remorse (self-acceptance); Da = **other-directed** forbearance under provocation. Boundaries name each other. |
| **Karuṇā** (Ḍha, La) | split by *object*: Ḍha = compassion countering **malice/slander** (social); La = compassion countering **physical cruelty** to the weak. Boundaries name each other. |
| **Jāgaraṇa** (Ta, Bha) | split by *what is dispelled*: Ta = lifting **inertia/dullness/sleep**; Bha = breaking **hypnotic delusion/obsession**. Boundaries name each other. |
| **Fearlessness** (Ḍa, Pha) | split by *what fear dissolves*: Ḍa = **social shame** (Lajjā); Pha = **threat/danger** (Bhaya). |
| **Detach/renounce/non-attach** (Ka, Gha, Dha, Na) | split by *what is released*: Ka = **outcome/hope**; Gha = **the loved object**; Dha = **craving/acquisition**; Na = **delusive infatuation**. |
| **Cruelty** (Ḍha, La) blocked | keep distinct objects (malice vs physical harm); do not co-render both as "cruelty". |
| **Attachment/greed basin** (Gha/Na/Dha/Jha/Ṣa/Śa) | distinguish *love-bond* (Gha) · *infatuation* (Na) · *thirst-to-acquire* (Dha) · *avarice-hoarding* (Jha) · *sensory desire* (Ṣa) · *rajasic material drive* (Śa). |

General principle (all rewrites): **no synonym swap**; the contrast-boundary field must name the sibling it
separates from, and that separation must later be *verified by an embedding-distance gate* (§9). Sanskrit
labels and phoneme→varṇa assignments are **not** changed by a gloss rewrite; changing assignments would be
a separate, larger, separately-approved study.

## 9. Proposed freeze-gate for future B1.1 lexicon

A revised pool must clear a **pre-registered** gate *before* any B1.1 generation, and then be **frozen and
hash-bound inside the B1.1 freeze set** (closing the B1 gap where the lexicon JSONs sat outside the frozen
11):

1. `exact_duplicate_liberated_sanskrit == 0` and `exact_duplicate_english_pole == 0` (kills all six §3 cases).
2. Each of the six §3 families carries a `functional_operation` **and** a `contrast_boundary` that names its
   sibling(s).
3. **Embedding-distance gate:** median pairwise gloss cosine-distance ≥ τ_min; no affect basin (cluster at
   τ_broad) larger than K_max; count of pairs below τ_near ≤ P_max. τ_min, τ_broad, τ_near, K_max, P_max
   and the embedding model are pre-registered constants, frozen, hash-bound.
4. The BRIDGE pool is **regenerated** from the revised lexicon and re-checked (it must not silently re-collapse
   duplicates via its alphabetical tie-break).
5. Gate report (`varna_contrastivity_report.json`) committed alongside; the gate is **not** tunable after
   seeing any B1.1 outcome.

Passing the gate removes the *pool-overlap* confound only. It is **not** evidence for H2 and does **not**
predict A will beat R_deranged.

## 10. Open questions requiring human decision

1. **Source-fidelity vs contrastivity (the core tension).** The shared liberated poles are not accidental:
   the source genuinely assigns e.g. **Vinaya** as the counter to *both* Dambha (Ṅa) and Ahaṁkāra (Ja), and
   **Kṣamā** to *both* Anutāpa (Ṭha) and Krodha (Da). Splitting them for experimental separability may
   **depart from the source doctrine**. Decision needed: prioritize source fidelity or experimental
   contrastivity? (This audit does not decide it.)
2. **Condition on the blocked pole instead?** The blocked poles are already distinct (§3). Conditioning
   generation on the *distinct binding vrtti* rather than the *collapsed liberated pole* might reduce R's
   strength **without any rewrite** — a cheaper design lever. Should B1.1 test blocked-pole conditioning as
   an arm/ablation? (Design question, not decided here.)
3. **Base file for rewrite:** start from `lexicon_authoritative.json` or from the untested candidate
   `lexicon_authoritative_varna.json` (1ae4d4b)?
4. **English-only vs deeper edit:** is rewriting English glosses + adding the two new fields sufficient, or
   must Sanskrit labels also be disambiguated (larger, separate approval)?
5. **Gate thresholds & embedding model** (τ values, model) — must be chosen and pre-registered before running.
6. **Vowels:** left out of collision scoring (prose-only). Include them in B1.1 or keep consonant-only?

## 11. Final status block

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Culprit:               R (random), not S             (A_vs_R 0.5135 fail · A_vs_S 0.5615 pass)
Track B:               BLOCKED
This step:             AUDIT ONLY
Lexicon modified:      NO
Model run:             NO
Scoring run:           NO
Ontology validation:   NO
Sanskrit privilege:    NO
Semantic truth:        NO
H2 validation:         NO
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (A_vs_R −0.1917, A_vs_X −0.075) · Track F
`CORRECTNESS_DEGRADED`. Contrastivity repair is **necessary but not sufficient**; a contrastive pool with an
arbitrary word→mapping link still yields A ≈ R (tested by R_deranged, not by this audit).

**Structure, not validated meaning.** Audit only; the B1 verdict stands and Track B remains BLOCKED.
