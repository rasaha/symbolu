# B1.1 Lexicon-Rewrite Decision Memo — liberated-pole contrastive rendering

**Status:** `DECISION_MEMO_ONLY` — drafted 2026-07-04. **No lexicon modified · no model run · no generation
· no scoring.** Does **not** modify B1, change the B1 verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock
Track B. Makes **no** claim of ontology validation, Sanskrit privilege, semantic truth, or H2 validation.
**Structure, not validated meaning.**

Resolves open question **§10 Q1** of `VARNA_GLOSS_CONTRASTIVITY_AUDIT.md` (5f99b38) with a corrected,
verified framing supplied by the operator. This memo records a *decision about how a future B1.1 lexicon
would be built*; it does not build it.

---

## 1. Scope and non-claims

This memo replaces the earlier "source-fidelity vs contrastivity" tension with a precise, provenance-based
distinction, and records the decision to **rewrite only the interpretive pole** for contrastivity. It
authorizes nothing to run; the actual rewrite is a **separate, later approval**.

**On citing the classical source:** the operator supplied the primary text (P.R. Sarkar, *Acoustic Roots of
the Indo-Aryan Alphabet*, 1984–85 Calcutta; consonants only, vowels overlooked per instruction). It is
cited **solely to establish provenance** — which pole is source-original vs LLM-interpretive — **not** to
endorse the framework's metaphysics as true. Establishing "this pole is classical, that pole was added" is a
provenance fact; it is **not** a claim of Sanskrit privilege, ontology validation, or semantic truth.

## 2. Corrected framing: source-attested pole vs experimental interpretive rendering

The audit framed the choice as "source fidelity **vs** contrastivity," implying a trade-off. **That framing
is withdrawn.** The correct distinction is one of *provenance per pole*:

- **Source-attested pole** — the acoustic-root vrtti carried by the classical source (P.R. Sarkar / Varṇa
  Vijñāna), attested in the lexicon by a `source_quote` / `source_vritti`. This is the **classical side** and
  is **preserved** unless a genuine source error is found.
- **Experimental interpretive rendering** — the *counter-pole*, a derived remedial word that carries **no**
  source attestation. Per the operator, these were **LLM-created without contrastivity forethought**; the
  lexicon's own notes corroborate this ("Counter-pole Anuśāsana is the **derived** remedial restraint";
  "Negative pole Aviveka is the **derived** worldly distortion"); and the **primary classical source
  confirms it** — Sarkar attests only one acoustic-root propensity per consonant, and the liberated
  counter-poles do **not** appear there (see Appendix A). This side is **rewritable** for contrastivity
  **without claiming to rewrite classical theory.**

There is therefore **no fidelity trade-off**: rewriting the interpretive pole leaves the source-attested
pole untouched.

## 3. Why B1's collisions concentrated in the interpretive (liberated) pole

The audit found the collisions are almost entirely on the **liberated** pole — 4 exact-duplicate Sanskrit
labels (Viśvāsa, Vinaya, Viveka, Jāgaraṇa) + 2 near-duplicate roots (Kṣamā, Karuṇā) — while every **binding**
vrtti is a distinct acoustic root. The corrected framing explains *why*: the binding poles are the
source-attested classical vrttis (distinct by construction), whereas the **liberated poles were interpretive
renderings authored without a non-synonym / contrastivity audit**, so many distinct afflictions were handed
the *same* remedial word. That redundancy is what let random control **R** draw a fluent, similarly-toned
positive phrase and match **A** in B1. **The defect is in the interpretive layer, not the classical layer.**

## 4. Provenance refinement — protect the source-attested pole *wherever it sits* (primary-source confirmed)

For **27 of 34** consonants the source-attested pole is the **binding** pole, so "rewrite the liberated
pole" is correct. But a **confirmed exception set of 7** carries the source attestation on the **liberated**
pole; those liberated poles are **classical, not interpretive** — they must be **protected**, not rewritten.
Confirmed against the primary source AND the lexicon's `source_vritti` metadata (independent agreement;
verbatim attestations in **Appendix A**):

| source-attested pole = LIBERATED (protect this liberated pole) | classical liberated meaning |
|---|---|
| **Ca** | Viveka (discrimination) — Ca *is* the acoustic root of viveka |
| **Va** | Dharma / Jalatattva |
| **Sa** | Mokṣa / Sattvaguṇa (liberation) |
| **Ha** | Parā-vidyā (spiritual knowledge) |
| **Kṣa** | Aparā-vidyā (mundane knowledge) |
| **Ra** | Prāṇaśakti / Agnitattva (vitality/fire) |
| **Śa** | directed energy / purposeful pursuit (rajoguṇa/artha) |

So the operative rule is **not** "binding stable, liberated rewrite" verbatim — it is:

> **Preserve the source-attested pole (whichever side it sits on); rewrite only the derived interpretive
> counter-pole.**

For 33 of 34 consonants this leaves the binding pole classical and the liberated pole rewritable. **In the
six collision families it changes exactly one case:** in the **Viveka** collision, **Ca's Viveka is
classical → protect it**, and only its interpretive twin **Na's Viveka** (Na's source vrtti is Moha, a
binding pole) is rewritten. All other collision members have interpretive liberated poles and are freely
rewritable.

## 5. Decision / recommendations

1. **Keep source-attested poles stable** (binding poles for most; the §4 liberated exceptions for Ca, Va,
   Sa, Ha, Kṣa, Ra, Śa) unless a genuine source error is found and separately documented.
2. **Rewrite the interpretive liberated poles into distinct *functional operations*** — not synonyms, not a
   tidier basin. Each becomes a verb-like operation that separates it from its neighbors.
3. **Regenerate the BRIDGE pool from the rewritten liberated operations** (do not hand-edit the pool; it is
   derived from the lexicon).
4. **Require one-to-one bridge phrases: no two liberated poles may collapse to the same or a near-duplicate
   bridge phrase.** (This directly kills the 4 exact collapses that reduced 68 glosses to 64.)

## 6. Four-field future-lexicon format (preserved)

Every consonant entry will carry:

- **binding / blocked impulse** — the source-attested affliction (preserved).
- **liberated impulse** — the freed state (interpretive rendering, rewritten for contrast; or preserved if
  it is the §4 source-attested pole).
- **functional operation** — what the varṇa *does* (a verb, the discriminating field).
- **contrast boundary** — what this varṇa is **not** (names the specific siblings it must be told apart
  from).

## 7. Liberated-rendering construction rule (mandatory)

Every **rewritten** liberated rendering MUST include, and pass, all four:

1. **liberated impulse** — the freed state, in plain words.
2. **functional operation** — the distinct operation it performs.
3. **contrast boundary** — explicit "not X, not Y" naming its nearest siblings.
4. **non-synonym check against all other liberated poles** — the new rendering must be *non-synonymous*
   with every other liberated pole (verified by an embedding-distance gate: pairwise cosine-distance ≥
   τ_min, pre-registered), and must not reintroduce a shared Sanskrit label or a collapsed bridge phrase.

A rendering that fails the non-synonym check is rejected and re-authored.

## 8. Per-collision resolution direction (from the audit; direction only, not final meanings)

| collision | provenance | resolution direction |
|---|---|---|
| **Viśvāsa** (Kha, Ya) | both liberated interpretive | Kha = remaining open under impersonal uncertainty; Ya = self-efficacy to act. Boundaries name each other. |
| **Vinaya** (Ṅa, Ja) | both liberated interpretive | Ṅa = dropping outward pretense; Ja = dissolving inflated I-centeredness. |
| **Viveka** (Ca, **Na**) | **Ca classical — PROTECT**; Na interpretive | Keep Ca = Viveka (discrimination). Rewrite **Na only** → release from delusive infatuation (Moha's counter). |
| **Jāgaraṇa** (Ta, Bha) | both liberated interpretive | Ta = lifting inertia/dullness; Bha = breaking hypnotic delusion. |
| **Kṣamā** (Ṭha, Da) | both liberated interpretive | Ṭha = self-directed release of remorse; Da = other-directed forbearance under provocation. |
| **Karuṇā** (Ḍha, La) | both liberated interpretive | Ḍha = compassion countering malice/slander; La = compassion countering physical cruelty. |

## 9. Bridge regeneration & one-to-one gate

After rewrite, the BRIDGE pool is **regenerated from the lexicon** and must satisfy:

- **68 → 68** (no collapse): with duplicate liberated labels removed, all 34 blocked + 34 liberated glosses
  yield **distinct** bridge phrases (the B1 pool collapsed to 64 because 4 liberated pairs were identical).
- **No near-duplicate phrases:** pairwise phrase distance ≥ τ_near (pre-registered).
- The regenerated pool + its distance report are **frozen and hash-bound inside the B1.1 freeze set**
  (closing the B1 gap where the lexicon/pool sat outside the frozen 11).

## 10. Integrity language (must appear on any rewritten lexicon)

- The rewritten liberated poles are **experimental interpretive renderings.**
- They are **not** claimed as classical Sanskrit meanings, and carry no source attestation.
- They exist **only** to test whether a *contrastive symbolic channel* can beat random control **R** in a
  future B1.1 — nothing more. A pass would be `LIMITED_GENERATION_UTILITY` for the revised pipeline only;
  it would **not** validate the ontology, privilege Sanskrit, or assert semantic truth.
- The source-attested poles (binding for most; the §4 liberated exceptions) remain labeled as the classical
  side and are unchanged.

## 11. Still open / NOT decided by this memo

- **Blocked-pole conditioning ablation** (audit §10 Q2): conditioning generation on the *distinct* binding
  pole instead of the collapsed liberated pole might weaken R **without any rewrite** — still an open design
  lever for the B1.1 arm set, not decided here.
- **Base file, τ thresholds, embedding model, vowel inclusion** (audit §10 Q3–Q6): to be fixed at B1.1
  pre-registration.
- **The actual rewrite** is a separate, later approval (`B1_1_LEXICON_REWRITE_EXECUTION` or similar). This
  memo only records the *decision framing*.

## Appendix A — Classical source attestation (consonants only)

Source: P.R. Sarkar, *Acoustic Roots of the Indo-Aryan Alphabet* (1984–85, Calcutta; reproduced text
supplied by operator). Vowels overlooked per instruction. Cited for **provenance only** (classical vs
interpretive), not as a truth claim. OCR-normalized; propensity names verbatim where legible.

**Rule read off the table:** the classical source attests **one** acoustic-root propensity per consonant.
Where that propensity is the *worldly* vrtti (27 consonants), it equals our `binding_state` → **binding pole
is classical, liberated pole is interpretive (rewritable)**. Where the source attests the *positive*
pole/principle (7 consonants), **that liberated pole is classical (protect); the binding side is the
interpretive counter-pole**.

| Varṇa | classical acoustic-root (verbatim source) | matches our pole | source-attested (protect) | interpretive (rewritable) |
|---|---|---|---|---|
| Ka | "acoustic root of the abhīpsātmaka **āśā** vrtti" (hope) | binding | binding | liberated |
| Kha | "**cintā** vrtti [worry]" | binding | binding | liberated |
| Ga | "**ceṣṭā** vrtti" (effort/striving) | binding | binding | liberated |
| Gha | "**mamatā** … love and attachment" | binding | binding | liberated |
| Ṅa | "**dambha** vrtti [vanity]" | binding | binding | liberated |
| **Ca** | "**viveka** [conscience]" | **liberated** | **liberated** | binding |
| Cha | "**vikalatā** vrtti [nervous breakdown]" | binding | binding | liberated |
| Ja | "**ahaṁkāra** vrtti (ego)" | binding | binding | liberated |
| Jha | "**lolupatā, lobha** [greed] and lolatā" | binding | binding | liberated |
| Ña | "**kapaṭatā** vrtti [hypocrisy]" | binding | binding | liberated |
| Ṭa | "**vitarka** vrtti [overstating one's case]" | binding | binding | liberated |
| Ṭha | "**anutāpa** vrtti [repentance]" | binding | binding | liberated |
| Ḍa | "**lajjā** vrtti [shyness]" | binding | binding | liberated |
| Ḍha | "**piśunatā** … sadistic cruelty" | binding | binding | liberated |
| Ṇa | "**īrṣyā** vrtti [envy]" | binding | binding | liberated |
| Ta | "**staticity, long sleep and deep sleep**" (jāḍya/nidrā) | binding | binding | liberated |
| Tha | "**viṣāda** vrtti, of melancholy" | binding | binding | liberated |
| Da | "acoustic root of **peevishness**" (krodha/karkaśatā) | binding | binding | liberated |
| Dha | "**thirst for acquisition**" (tṛṣṇā) | binding | binding | liberated |
| Na | "**moha** vrtti [blind attachment / infatuation]" | binding | binding | liberated |
| Pa | "**ghṛṇā** vrtti [hatred or revulsion]" | binding | binding | liberated |
| Pha | "**bhaya** vrtti [fear]" | binding | binding | liberated |
| Ba | "**avajñā** vrtti [indifference]" | binding | binding | liberated |
| Bha | "the **mūrcchā** vrtti" (deluded obsession) | binding | binding | liberated |
| Ma | "**praṇāśa** [annihilation] … **praśraya** [indulgence]" | binding | binding | liberated |
| Ya | "**aviśvāsa** vrtti [lack of confidence]" | binding | binding | liberated |
| **Ra** | "**agnitattva/prāṇaśakti – vitality**" (also sarvanāśa) | **liberated** (+binding) | **liberated** (both attested) | — (both classical) |
| La | "**krūratā** vrtti [cruelty]" | binding | binding | liberated |
| **Va** | "acoustic root of **dharma**" (+ jalatattva) | **liberated** | **liberated** | binding |
| **Śa** | "**rajoguṇa** [mutative] … **artha** [psychic longing]" | (principle) | **principle attested** | both pole-assignments interpretive |
| Ṣa | "**tamoguṇa** [static] … **kāma** [worldly desire]" | binding | binding | liberated |
| **Sa** | "**mokṣa** [liberation] … **sattvaguṇa**" | **liberated** | **liberated** | binding |
| **Ha** | "ethereal factor … **parā-vidyā** [intuitional science]" | **liberated** | **liberated** | binding |
| **Kṣa** | "**mundane knowledge** … material science" (aparā-vidyā) | **liberated** | **liberated** | binding |

**Exception set (protect the liberated pole): Ca, Va, Sa, Ha, Kṣa** (clear positive) **+ Ra** (both poles
attested) **+ Śa** (neutral principle; both pole-assignments interpretive). Matches the `source_vritti`
metadata finding independently. **Within the six B1 collision families, only Ca falls in this set** →
protect Ca's Viveka, rewrite Na's Viveka.

*Caveat:* OCR of the reproduced text is imperfect (retroflex/nasal headers garbled); propensity identities
were cross-checked against the lexicon's `source_quote` fields, which quote the same Sarkar text. No pole
assignment in this table depends on a garbled token.

## 12. Final status block

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             DECISION MEMO ONLY
Lexicon modified:      NO (no lexicon modified unless separately approved)
Model run:             NO
Generation run:        NO
Scoring run:           NO
Ontology validation:   NO
Sanskrit privilege:    NO
Semantic truth:        NO
H2 validation:         NO
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (A_vs_R −0.1917, A_vs_X −0.075) · Track F
`CORRECTNESS_DEGRADED`. Contrastivity repair remains **necessary but not sufficient**; a contrastive pool
with an arbitrary word→mapping link still yields A ≈ R (tested by R_deranged, not by any lexicon rewrite).

**Structure, not validated meaning.** Decision memo only; the B1 verdict stands and Track B remains BLOCKED.
