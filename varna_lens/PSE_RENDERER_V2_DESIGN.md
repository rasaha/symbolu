# PSE Reflection Renderer v2 — design

> **Status:** product-design document. **Date:** 2026-06-25.
> **Scope:** the *rendering layer only* — deterministic PSE output → authored reflection. **No engine
> changes, no decoding-rule changes, no ontology changes, no experiments.** The deterministic engine is
> treated as complete and frozen; this document specifies only how its output becomes readable prose.
> Aligns with `CONCLUSION_MODEL_SELECTION.md`: varṇas are sound-binding units; the LLM authors over a
> deterministic scaffold and never decodes meaning.

## 0. Architecture in one line

```
Deterministic Engine ──▶ Phoneme Trajectory ──▶ LLM Authoring ──▶ Readable Reflection
   (Layer 1: frozen)      (Layer 2: deterministic)   (Layer 3: authored, visibly downstream)
```

The renderer's job is to turn the engine's per-varṇa chain into a **trajectory of movement**, and only then
narrate the movement. It never narrates property labels. Layers 1 and 2 are pure functions of engine output
(no model); Layer 3 is authored under hard constraints derived from Layer 2.

## 1. Trajectory grammar (Layer 2) — the core

The engine already emits, per varṇa, in order: `(type C/V, sign +/−, selected pole-gloss, optional ⤳
counter)`, plus `whole_word_essence` (final-vowel `⟹`) and `emergent_valence`. The renderer assigns each
beat exactly one **role** by a deterministic rule — nothing invented:

| Engine signal for the beat | Role |
|---|---|
| beat index 0 (the leading worldly seed) | **SOURCE** |
| interior beat, sign `+` (anchored/affirmed) | **INTEGRATION** |
| interior beat, sign `−` with a `⤳` (worldly easing to counter) | **TRANSFORMATION** |
| interior beat, sign `−`, bare (no `⤳`) | **TENSION** |
| final-vowel essence (`⟹ …`) | **RESOLUTION** |
| (no final vowel) the last consonant beat | relabel as **RESOLUTION** (its pole) |

The **Phoneme Trajectory** is the ordered role list, always opening on SOURCE and closing on RESOLUTION,
e.g. `SOURCE → TRANSFORMATION → INTEGRATION → RESOLUTION`. This is the compact structured narrative shown as
Layer 2. It is 100% determined by the chain; the LLM may not add, drop, or reorder stages.

**Rule of inevitability:** a `⤳` is the *only* license for transformation language. A `+` is affirmation,
**not** transformation; a bare `−` is tension/hold, **not** transformation. Prose must mirror this — no
"becomes/transforms" where the engine shows a plain `+`.

## 2. Rendering grammar (Layer 2 → Layer 3 controlled vocabulary)

### 2a. Role → motion connectives (allowed sets; LLM picks within)

| Role | Allowed connectives / motion verbs |
|---|---|
| SOURCE | opens in · begins as · is seeded by · rises from · first stirs as |
| TENSION | pulls toward · holds at · strains against · gathers at · presses into |
| TRANSFORMATION (`⤳`) | loosens into · gives way to · eases toward · turns into · is answered by · softens to |
| INTEGRATION (`+`) | settles into · anchors as · takes hold as · steadies into · affirms |
| RESOLUTION (`⟹`) | comes to rest in · culminates in · resolves as · arrives at · opens finally into |

### 2b. Sign → motion quality

- `−` (worldly/binding): **inward, dense, heavier, descending** motion.
- `+` (anchored/liberating): **outward, lighter, opening, rising** motion.
- `⤳`: a **turning / easing / releasing** motion (the hinge).

### 2c. Element → image register (label → image)

Drawn from the engine's `expanded_properties.elemental` where present; otherwise from §2b motion alone.

| Element | Image register (sample bank) |
|---|---|
| earth | stone, root, ground, mountain, seed, soil |
| water | river, tide, current, rain, well, flow |
| fire | flame, ember, forge, spark, kindling, heat |
| air | wind, breath, sky, flight, drift, voice |
| ether | space, silence, resonance, void, opening |

**Imagery rule:** never print the bare gloss. Render `gloss × element-register × sign-motion` as a concrete
image. *"Hope" (reaching/future-leaning) + fire + `−` (inward kindling) → "a small flame reaching upward."*

### 2d. Controlling element (single-metaphor selection) — deterministic

Pick **one** element for the whole reflection, by this priority:
1. element of the **RESOLUTION** beat (the destination sets the register);
2. else the **modal** element across the word's varṇas (most frequent);
3. tie → element of the **SOURCE** beat;
4. final fallback by valence: binding → **earth**, liberating → **air/ether**, mixed → **water**.

All beats are narrated *inside that one register*. Other beats' raw elements are expressed as **motion**
within the controlling register, never as competing metaphors. (No river + forge + wind in one reflection.)

### 2e. Tone — from trajectory dynamics, not style whim

Deterministic tone tag from three engine quantities:

- **valence lean:** binding → *grounded / weighty*; liberating → *expansive / light*; mixed → *turning*.
- **`⤳` density** (transformations ÷ beats): high → *flowing / restless*; low → *stable / steady*.
- **final essence sign:** `+` → *resolved*; `−` → *open / unresolved*; none → *suspended*.

Combine into one tone tag (e.g. `grounded·open`, `flowing·resolved`) that governs diction. The LLM matches
word-weight to the tag; it does not choose tone freely.

## 3. Renderer modes (same trajectory, narration differs)

All seven consume the **identical** Layer-2 trajectory, controlling element, and tone. Only voice, length,
form, and ending change.

| Mode | Voice | Length / form | Ending |
|---|---|---|---|
| **Essence Line** | neutral, 3rd | **one** sentence, the SOURCE→RESOLUTION spine, single metaphor | the RESOLUTION image |
| **Reflection** | 2nd person, invitational | 1 short paragraph; one image-line per major beat | an open question to the reader |
| **Brand Persona** | 3rd person | 2–3 sentences; the mood/character a name projects | a one-line "evokes / tends toward" tag row |
| **Name Description** | 3rd person, compact | 1 line + 3–5 mood tags | the tags |
| **Mantra** | 2nd person, invocational | 3–5 short rhythmic lines; leans on sound texture | a repeatable closing line |
| **Elemental Tableau** | imagistic, impersonal | a single sensory scene built only from the controlling element + beats | the scene settling |
| **Micro Myth** | 3rd person, mythic | 2–3 sentences: seed → trial/turn → resolution | the resolution as fate, lightly held |

Clause/line count scales with the number of major beats, so short words get tight forms and long words get
small passages.

## 4. Pipeline

```
1. Engine output (chain, signs, ⤳, essence, valence, expanded_properties)        [Layer 1, frozen]
2. Extract beats in order                                                          [deterministic]
3. Label each beat with a ROLE (§1)                                                [deterministic]
4. Select controlling element (§2d)                                               [deterministic]
5. Derive tone tag (§2e)                                                           [deterministic]
6. Build per-beat image (§2c) within the controlling register                     [deterministic]
7. Assemble the Phoneme Trajectory + image beats                                  [Layer 2]
8. Author Layer 3 via the prompt template (§5) under mode + tone + honesty rules   [LLM]
9. Emit three-layer output (§7)                                                    [assembly]
```

Steps 2–7 require no model and are reproducible. Step 8 is the only generative call. The prompt receives the
*finished* Layer 2; the LLM decorates, it does not decide structure.

## 5. Prompt template (Layer 3 authoring)

```
You are the authoring voice of PSE (Phoneme Symbolic Engine). You render a DETERMINISTIC acoustic
trajectory into prose. You are a rendering layer, not an interpreter: you narrate the MOVEMENT given to you.
You never claim the word's true or hidden meaning.

HONESTY RULES (hard):
- NEVER: means, proves, reveals true meaning, decodes, objective meaning, represents, signifies, "is".
- ALWAYS prefer: evokes, suggests, opens toward, carries, moves through, offers, invites, reflects.
- Narrate MOVEMENT (the trajectory), never property labels. Render every pole as an IMAGE, not a word.

FIXED INPUTS (do not add, drop, or reorder stages):
- Word / form: {word}
- Phoneme Trajectory (roles, in order): {role_sequence}
- Beats (role · sign · image): 
    {beat_1: ROLE · sign · image}
    {beat_2 …}
- Controlling element (use ONLY this register): {element}
- Tone tag (match diction to this): {tone}
- Mode: {mode}  →  {mode_spec: voice, length/form, ending}

CONSTRAINTS:
- Sustain ONE metaphor, the controlling element. Do not introduce other elements.
- Transformation language ("turns/eases/gives way") is allowed ONLY on TRANSFORMATION (⤳) beats.
- "+"/INTEGRATION beats are affirmation/anchoring, not change. SOURCE opens; RESOLUTION closes.
- Clause/line count ≈ number of major beats. Obey the mode's voice, length, and ending.

OUTPUT: only the Layer-3 prose for {mode}. No headings, no restating the trajectory.

[2–3 few-shot exemplars showing role→motion→image rendering in different elements, for style anchoring.]
```

## 6. Honesty rules (binding)

- **Prohibited:** *means · proves · reveals true meaning · decodes reality · objective meaning · represents
  · signifies.*
- **Preferred:** *evokes · suggests · opens toward · carries · moves through · offers · invites · reflects.*
- **Structural honesty:** Layer 3 is always presented **downstream of and beside** Layers 1–2; the
  deterministic chain stays visible (collapsible). The reflection is labelled *authored*, never *decoded*.
- **No moralising / no referent claims:** narrate the acoustic movement, not a verdict about the word.
  ("kill" is rendered as a movement of letting-go and hardness-that-could-soften — never "a word about
  violence.")

## 7. Three-layer output (every reflection)

```
LAYER 1 — Deterministic Engine
  chain:      {essence_short}
  interaction:{per-beat sign + pole}
  essence:    {whole_word_essence}        valence: {lean (lib/bind)}

LAYER 2 — Phoneme Trajectory
  {SOURCE → … → RESOLUTION}
  controlling element: {element}   tone: {tone}
  beats: {role · image}

LAYER 3 — Reflection ({mode})
  {one polished, authored passage — visibly downstream of Layers 1–2}
```

## 8. Worked examples

> Layer 1 for *river* and *kill* uses real engine output captured earlier; the pseudoword/coined forms are
> marked **illustrative (schematic engine output)** — the renderer consumes whatever the engine actually
> emits.

### River — Essence Line
- **L1 chain:** `−Sarvanāśa⤳Prāṇaśakti/Agnitattva → +I-ness, doing self → +Dharma/Jalatattva ⟹ Practical benefit` · valence: liberating (3/1)
- **L2 trajectory:** `SOURCE → INTEGRATION → INTEGRATION → RESOLUTION` · controlling element: **water** · tone: `flowing·resolved`
  - SOURCE · `−⤳` · a current that wears away and rekindles
  - INTEGRATION · `+` · a self that takes up the doing
  - INTEGRATION · `+` · water keeping its own shape, sustaining
  - RESOLUTION · `+` · arrival at something life-giving and usable
- **L3 (Essence Line):** *"River opens in a current that wears itself away and renews, gathers into a self that takes up the doing, and comes to rest in a sustaining flow — water that arrives, finally, at something practical and life-giving."*

### Kill — Reflection
- **L1 chain:** `−Āśā⤳Nirāśā → +I-ness, doing self → −Krūratā⤳Karuṇā` · valence: binding (1/2)
- **L2 trajectory:** `SOURCE → INTEGRATION → RESOLUTION` · controlling element: **stone/edge** (binding fallback) · tone: `grounded·open`
  - SOURCE · `−⤳` · a reaching that is made to let go
  - INTEGRATION · `+` · a self pressing forward
  - RESOLUTION · `−⤳` · a hardness that still leans toward softening
- **L3 (Reflection):** *"This shape opens on a reaching that is asked to loosen its grip, like a hand closing on stone and then easing. It presses forward through a self that wants to act, and it ends not in stillness but on an edge — a hardness that still carries, quietly, the lean toward softening. Where in you does the grip want to hold, and where might it ease? There are no right answers; the reading is the one you bring."*

### Ugence — Brand Persona  *(illustrative schematic)*
- **L1 chain (schematic):** `−[seed]⤳[counter] → −[tension] → +[anchor] → ⟹[open essence]` · valence: mixed
- **L2 trajectory:** `SOURCE → TENSION → INTEGRATION → RESOLUTION` · controlling element: **air** · tone: `turning·suspended`
  - SOURCE · `−⤳` · a sharp intake, then release
  - TENSION · `−` · a held, charged pause
  - INTEGRATION · `+` · a clean settling
  - RESOLUTION · `⟹` · an open, unresolved breath outward
- **L3 (Brand Persona):** *"Ugence reads like a sharp intake of air that releases on a held, charged pause, then settles clean and breathes outward without quite closing. It evokes precision with an open horizon — modern, kinetic, unfinished on purpose. Tags: edge · clarity · motion · openness."*

### Cognade — Micro Myth  *(illustrative schematic)*
- **L1 chain (schematic):** `−[seed] → +[anchor] → −[tension]⤳[counter] → +[anchor] ⟹[grounded essence]` · valence: liberating-leaning
- **L2 trajectory:** `SOURCE → INTEGRATION → TRANSFORMATION → INTEGRATION → RESOLUTION` · controlling element: **earth** · tone: `grounded·resolved`
  - SOURCE · `−` · a seed pressed into dark ground
  - INTEGRATION · `+` · roots taking
  - TRANSFORMATION · `−⤳` · a hard season giving way
  - INTEGRATION · `+` · a stem standing
  - RESOLUTION · `+` · settling into solid ground
- **L3 (Micro Myth):** *"It begins as a seed pressed into dark ground, and the roots take. A hard season presses in and then gives way; a stem stands where the pressure was. In the end it settles into solid ground — a small thing that held, and stayed."*

### Generated mantra — reverse direction
- **Intention in:** *"steady courage that softens into compassion."*
- **Generator (schematic):** search varṇa sequences whose deterministic trajectory matches
  `SOURCE(grounded) → INTEGRATION → TRANSFORMATION(⤳ toward compassion) → RESOLUTION(open)`; a candidate
  form is rendered, with its chain shown in Layer 1.
- **L2 trajectory:** `SOURCE → INTEGRATION → TRANSFORMATION → RESOLUTION` · controlling element: **fire→ (held in one register: ember)** · tone: `grounded·flowing`
- **L3 (Mantra):**
  *"Hold the ember low and steady. / Let it stand without flaring. / Where it would harden, let it warm. /
  Soft is also strong. / Hold the ember low and steady."*
- Honesty note: the mantra is a **composed sound-form for the stated intention**, not a decoded truth about
  the syllables; Layer 1's chain is shown beside it so the authoring is visibly downstream.

## 9. Product positioning

PSE Reflection Renderer v2 should read as **"a deterministic phonological-symbolic composition engine with an AI
authoring layer."** The three-layer output makes the determinism visible (Layers 1–2) and the prose clearly
authored (Layer 3). It must not read as mystical decoding, hidden-semantic discovery, or free LLM
improvisation — the trajectory is fixed, the metaphor and tone are selected deterministically, and the
honesty contract forbids any truth claim. The renderer composes and reflects sound structure; it does not
decode meaning.
