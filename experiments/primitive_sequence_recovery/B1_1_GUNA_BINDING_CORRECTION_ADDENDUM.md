# B1.1 Guṇa-Binding Correction — Addendum (Sa / Ra / Śa)

## Scope and non-claims

**Addendum only.** Corrects the B1.1 review framing for **Sa, Ra, Śa** so a *positive/sattvic/energetic*
pole is not mislabeled as *liberated*. Modifies **no** JSON, runs **no** model, generation, or scoring. Does
**not** modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). This
reasons **within the framework's own internal logic** (to label provenance/handling correctly) and makes
**no** claim of ontology validation, Sanskrit privilege, or semantic truth. **Structure, not validated
meaning.**

## Why sattva and rajas can still bind

In the source's own Sāṅkhya/Tantra frame, **guṇa** literally means *strand / rope*: the three guṇas —
**sattva** (clarity/harmony), **rajas** (activity/desire), **tamas** (inertia/ignorance) — are the *binding*
principles of prakṛti. **Liberation (mokṣa) is guṇātīta — beyond all three guṇas.** So:

- **sattva binds by attachment to clarity, knowledge, purity, and happiness** — the classic **"golden
  chain"**;
- **rajas binds by activity, desire, ambition, projection, and compulsion** — a **"fiery chain"**;
- tamas binds by inertia/ignorance — a dark chain.

**A "positive" or "sattvic" pole is therefore NOT automatically liberated.** Only what is *trans-guṇa* is
release. The earlier B1.1 draft over-credited the sattvic/energetic poles by treating them as clean
"liberated" endpoints. The layman framing we use internally:

> **Sa = a golden chain · Ra = a fiery chain · Śa = a worldly-purpose chain.** All can be useful; all can
> bind unless transcended.

## Sa correction

- **Do not** treat Sa as a simple positive/liberated endpoint. The current draft's source pole conflates two
  distinct things — **Mokṣa** (trans-guṇa, genuinely liberating) **and Sattvaguṇa** (still a guṇa, still
  binding).
- Treat Sa as **source-attested sattvic / release-oriented clarity that may still be guṇa-bound.**
- B1.1 handling must **distinguish**:
  - **(a) sattvic order / clarity / harmony *within* bondage** — the golden chain; and
  - **(b) trans-guṇa release *from attachment to* purity / knowledge / harmony** — mokṣa proper.
- **Require human review before freezing Sa's counter-pole.** (Consequence: Sa moves out of `ready_draft`
  into the human-review set — see below.)

## Ra correction

- Treat Ra as **source-complex rajasic activation / vitality / destructive force.** Rajas binds through
  **motion, desire, ambition, compulsion, and projection** (fiery chain).
- The counter-pole must **not** be "more vitality" (that only tightens the chain).
- **Candidate direction (human-review, not frozen):** *non-compulsive directed energy / action without
  bondage / transmuted rajas* — energy that acts without attachment to its fruit.
- **Keep the human-review flag** (`source_complex_human_review`).

## Śa correction

- Treat Śa as the **source-attested rajas / artha / worldly-directed principle** (worldly-purpose chain).
- **Do not** force it into a simple vice/virtue pair (neither "directed accomplishment = good" nor "material
  greed = bad").
- **Candidate direction (human-review, not frozen):** *purposeful worldly action without possessive bondage.*
- **Keep the neutral-principle human-review flag** (`neutral_principle_human_review`).

## Framing to avoid going forward

Future B1.1 decision notes must **not** assert:
- ✗ Sa = automatically liberated
- ✗ Ra = simply positive vitality
- ✗ Śa = simply greed / material vice

## Consequences for the JSON draft and future bridge pool

*(Documented here; the JSON is changed only at a separate, approved JSON-update gate.)*

1. **Sa reclassified** from `exception_protected` / `ready_draft` → **human-review** (deferred), joining Ra
   and Śa. The **deferred set grows `{Ra, Śa}` → `{Ra, Sa, Śa}`**; **non-deferred drops 32 → 31.**
2. **Sa's source pole must be corrected** at the JSON-update gate: split/clarify "Mokṣa / Sattvaguṇa —
   liberation / clarity" so sattva (guṇa-bound) is not presented as liberation; its counter-pole is authored
   only after the (a)-vs-(b) human decision above.
3. **Embedding gate scope updates:** when re-run, the non-synonym check covers **31** non-deferred
   counter-poles (Sa excluded until resolved); the committed gate is already `BLOCKED` and must be re-run
   regardless.
4. **Bridge pool must not include Ra / Sa / Śa counter-poles** until each is resolved or explicitly
   pre-registered as excluded from B1.1 generation.
5. **Related caution (OPEN, not decided here):** the same "positive ≠ liberated" logic may warrant reviewing
   the other knowledge/order poles — **Ha (parā-vidyā), Kṣa (aparā-vidyā)**, and even **Ca (viveka) / Va
   (dharma)** — since knowledge and order can also bind. Flagged for the freeze review; **not** changed by
   this addendum.

## Human-review decisions required before freeze

1. **Sa:** decide whether Sa's protected pole should represent **(a) sattvic-within-bondage** or **(b)
   trans-guṇa mokṣa**, then author its counter-pole accordingly (do not conflate the two).
2. **Ra:** approve a **transmuted-rajas / action-without-bondage** counter-pole (explicitly *not* "more
   vitality").
3. **Śa:** approve **purposeful worldly action without possessive bondage** (not a vice/virtue pair).
4. **Open:** decide whether Ha / Kṣa (and the framing of Ca / Va) also need the guṇa-binding review at
   freeze.
5. Only after 1–4 may the embedding gate re-run over the final non-deferred set and the bridge pool be
   generated and frozen.

## Final status block

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             ADDENDUM ONLY
JSON modified:         NO (Sa reclassification documented, applied at a later approved gate)
Model run:             NO
Generation run:        NO
Scoring run:           NO
Ontology validation:   NO
Sanskrit privilege:    NO
Semantic truth:        NO
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` · Track F `CORRECTNESS_DEGRADED`. Contrastivity /
non-synonymy repair remains **necessary but not sufficient**; `R_deranged` remains the crux.

**Structure, not validated meaning.** Addendum only; the B1 verdict stands and Track B remains BLOCKED.
