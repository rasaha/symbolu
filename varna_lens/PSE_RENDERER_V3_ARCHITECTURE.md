# PSE Renderer v3 — decoupling the renderer from polarity

> **Status:** architecture / design document. **Date:** 2026-06-25.
> **Scope:** architectural refactor only. **No engine, ontology, decoding, or experiment changes; no
> implementation.** This document specifies an abstraction boundary so the renderer stops depending on the
> polarity model (`+`, `−`, `⤳`) and instead consumes a neutral, deterministic **Trajectory** object.
> Aligns with `CONCLUSION_MODEL_SELECTION.md` (varṇas = sound-binding units; polarity is not the long-term
> ontology) and supersedes the engine-coupled assembly in `PSE_RENDERER_V2_DESIGN.md`.

## 0. The problem in one line

v2 is `Engine → Renderer`: the renderer's role labels (INTEGRATION/TENSION) are read *directly* from `+`/`−`
and TRANSFORMATION from `⤳`. That hard-wires the renderer to a polarity ontology the project has concluded
is provisional. v3 inserts a **Trajectory Builder** between them so the renderer never sees polarity at all.

```
v2:  Engine ─────────────────────────▶ Renderer        (renderer inspects +, −, ⤳)
v3:  Engine ──▶ Trajectory Builder ──▶ Renderer        (only the Builder inspects +, −, ⤳;
                  (adapter)              (pure)          the Renderer consumes a neutral Trajectory)
```

## 1. Renderer v3 architecture

Three layers with a single, frozen contract between them — the **Trajectory schema** (§2).

```
┌──────────────┐   engine-specific      ┌────────────────────┐   neutral Trajectory   ┌────────────┐
│   ENGINE     │ ─────────────────────▶ │  TRAJECTORY BUILDER │ ─────────────────────▶ │  RENDERER  │
│ (frozen)     │   output (+, −, ⤳,     │  (a.k.a. ADAPTER)   │   (schema §2)          │  (pure)    │
│              │   essence, elemental)  │                     │                        │            │
└──────────────┘                        └────────────────────┘                        └────────────┘
        ▲                                         ▲                                          ▲
 knows ontology + polarity              the ONLY component that may              knows NOTHING about
 (unchanged)                            inspect +, −, ⤳; converts them           varṇas, polarity, or ⤳;
                                        into neutral interaction roles           consumes Trajectory only
```

**Contracts (the heart of the refactor):**

- **Renderer** is a *pure function* `Trajectory → prose` (per mode). It may read only the §2 schema. It is
  forbidden, by interface, from importing the engine, the lexicon, or the symbols `+ − ⤳`. Everything the
  renderer needs (imagery, texture, motion, tone) is *already materialised* in the Trajectory.
- **Trajectory Builder** is an *adapter*: one builder per engine. It is the **sole** component permitted to
  read `+`, `−`, `⤳`, `essence`, `emergent_valence`, `elemental`. It emits the neutral Trajectory.
- **Engine** is untouched and unaware of either.

This is the standard **Hexagonal / Ports-and-Adapters** shape: the Trajectory schema is the *port*; each
engine gets an *adapter* (builder); the renderer is the application core that depends only on the port.

## 2. Trajectory schema (the frozen contract)

A neutral, deterministic, serialisable object. No polarity vocabulary appears anywhere in it.

```yaml
trajectory:                      # version-tagged so renderer can assert compatibility
  schema_version: 1
  word: <string>                 # the input form (for display only; renderer never re-parses it)
  source_kind: <string>          # provenance tag, opaque to renderer (e.g. "polarity-v1", "binding-v1")

  beats:                         # ordered; the narrative spine
    - role:    <RoleEnum>        # SOURCE | FORMATION | INTERACTION | COHERENCE | TRANSFORMATION | RESOLUTION
      element: <Element|null>    # earth | water | fire | air | ether | null
      imagery: <string>          # a concrete image fragment (verb-first), already element-resolved
      texture: <TextureEnum>     # dense | open | sharp | soft | flowing | still   (felt quality)
      motion:  <MotionEnum>      # inward | outward | rising | settling | turning | holding
      weight:  <float 0..1>      # salience for clause budgeting (optional; default 1.0)

  overall:
    trajectory:       [<RoleEnum>...]     # the role sequence, for quick display
    dominant_element: <Element>           # the single sustained metaphor
    tone:             <string>            # e.g. "expansive·resolved" (opaque tag for diction)
    resolution:       <ResolutionEnum>    # resolved | open | suspended
    coherence:        <float 0..1>        # how unified the arc is (replaces "⤳ density"; see §3)
```

**Enums (closed sets; the renderer pattern-matches on these and nothing else):**

- `RoleEnum` = the v3 vocabulary (§ below).
- `Element` = {earth, water, fire, air, ether}.
- `TextureEnum` = {dense, open, sharp, soft, flowing, still}.
- `MotionEnum` = {inward, outward, rising, settling, turning, holding}.
- `ResolutionEnum` = {resolved, open, suspended}.

**Why texture & motion are first-class:** they are the *interaction-level* primitives the renderer actually
needs to choose diction. They are derivable from polarity *today* (§3) but are **not** polarity — a
no-polarity engine supplies them directly (§4). Putting them in the schema is what makes the renderer
polarity-agnostic rather than polarity-renamed.

## 3. New trajectory vocabulary — and the justification

Candidate set evaluated: `SOURCE · FORMATION · INTERACTION · COHERENCE · TRANSFORMATION · RESOLUTION`.

**Adopted, with COHERENCE demoted to a scalar.** Reasoning per role:

| Role | Meaning (interaction-centric, polarity-free) | Keep? |
|---|---|---|
| **SOURCE** | the onset that seeds the form; where the trajectory begins | ✅ |
| **FORMATION** | a unit binding/discretising into the chain — a stable sound taking shape | ✅ (replaces the polarity-named INTEGRATION/TENSION with a *binding* concept) |
| **INTERACTION** | a unit acting on / coupling with its neighbours (the core "trajectory emerges from interaction" beat) | ✅ |
| **TRANSFORMATION** | a turn in the trajectory — one configuration giving way to another | ✅ (now defined by *change in the interaction*, not by `⤳` specifically) |
| **RESOLUTION** | the closing/whole-form settling | ✅ |
| ~~COHERENCE~~ | how unified the arc is | ➖ **demoted to `overall.coherence` (scalar)** — coherence is a *property of the whole trajectory*, not a per-beat role; making it a beat would double-book FORMATION/INTERACTION |

**Final per-beat `RoleEnum` = {SOURCE, FORMATION, INTERACTION, TRANSFORMATION, RESOLUTION}**, with
`coherence` as an overall scalar.

Why this beats the v2 set: v2's **INTEGRATION/TENSION are literally `+`/`−`** — polarity wearing role names.
v3's **FORMATION/INTERACTION** name what a sound-binding unit *does* (bind, then interact), which is exactly
the post-conclusion ontology (varṇas as discretisation units; trajectory from interaction). The vocabulary
is *causally* about sound interaction, so it survives the removal of polarity. SOURCE/TRANSFORMATION/
RESOLUTION are already polarity-neutral (position/change/closure) and are retained.

## 4. Mapping A — current polarity engine → Trajectory (the adapter that exists today)

The **Trajectory Builder for the polarity engine** is the only place `+ − ⤳` are read. It reproduces v2's
behaviour exactly, then translates into neutral terms:

| Engine signal (read ONLY here) | v3 `role` | `texture` | `motion` |
|---|---|---|---|
| first scored varṇa | SOURCE | from element | rising |
| interior, anchored (`+`) | **FORMATION** | open / soft | settling |
| interior, worldly with `⤳` | **TRANSFORMATION** | flowing | turning |
| interior, worldly bare (`−`, no `⤳`) | **INTERACTION** | dense / sharp | inward / holding |
| final-vowel essence (or last varṇa) | RESOLUTION | from element | settling / outward |

Derived scalars (also computed only in the builder):

- `overall.coherence` = `1 − (⤳-density)` — a high `⤳` count (much worldly→counter easing) reads as a
  *less settled* arc; the renderer sees only the scalar, never `⤳`.
- `overall.resolution` = essence sign → {`+`→resolved, `−`→open, none→suspended} (computed here, exposed as
  the neutral enum).
- `overall.dominant_element` / `imagery` = exactly the v2 controlling-element + image-bank logic, **moved
  into the builder**. The renderer receives finished imagery strings.
- `overall.tone` = the v2 tone tag, computed here, passed through opaquely.

Net effect: **v2's renderer logic splits in two** — the *trajectory-construction* half (which touched
polarity) moves into the builder; the *prose-authoring* half (modes, prompt, honesty, single-metaphor join)
stays in the renderer and now reads only the schema. **Zero behavioural change** for the polarity engine.

## 5. Mapping B — a future no-polarity engine → the same Trajectory

A "binding/discretisation" engine has **no `+ − ⤳`**. It instead emits, per unit, an *interaction profile*
(e.g. coupling strength to neighbours, onset/coda position, a binding-stability score) and an articulatory
element. Its builder fills the **identical** schema:

| No-polarity engine signal (read ONLY in its builder) | v3 `role` | `texture` | `motion` |
|---|---|---|---|
| first unit (onset of the form) | SOURCE | from element | rising |
| a unit that binds with high stability, low coupling | **FORMATION** | soft / still | settling |
| a unit strongly coupled to neighbours | **INTERACTION** | sharp / flowing | turning / inward |
| a point where the interaction regime changes (binding→release, cluster boundary) | **TRANSFORMATION** | flowing | turning |
| the whole-form settling / final unit | RESOLUTION | from element | settling |

- `overall.coherence` = the engine's own global stability/predictability of the sequence (e.g. an
  interaction-energy or predictive-information score) — **no polarity needed**.
- `overall.resolution` = whether the final unit closes the form (stable) or leaves it open — a structural
  fact, not a sign.

Because both builders emit the **same enums and the same finished imagery**, the renderer cannot tell which
engine produced the Trajectory, and **requires zero changes** to render either. `source_kind` differs
(`"polarity-v1"` vs `"binding-v1"`) but is opaque to the renderer.

## 6. Future-proofing — the decoupling proof

**Claim:** `Renderer → Trajectory schema → Engine` are fully decoupled, and the renderer never inspects
`−` or `⤳`.

**Argument (interface-level, enforceable):**

1. **Direction of dependency.** The renderer imports *only* the schema enums; the builder imports the engine
   *and* the schema; the engine imports neither. Dependencies point inward toward the schema (the stable
   core), never outward. So an engine swap changes only a builder.
2. **No leakage path.** `+ − ⤳` and `emergent_valence` appear in the builder's translation tables and
   nowhere downstream. The schema's vocabulary (RoleEnum/Texture/Motion/Resolution) contains no polarity
   token. Therefore the renderer has *no symbol to inspect* even if it tried.
3. **Substitutability (Liskov at the data level).** Any builder that emits a schema-valid Trajectory is an
   acceptable producer. §4 and §5 exhibit two structurally different producers that the renderer treats
   identically — the operational definition of decoupling.
4. **Testable invariants** (to be added when implemented, not now): (a) the renderer module does not import
   `varna_lens` or read the strings `"+"`, `"−"`, `"⤳"`; (b) golden-test that the polarity-builder Trajectory
   reproduces v2 prose byte-for-byte; (c) a synthetic no-polarity Trajectory renders without error and
   obeys the same honesty/single-metaphor invariants.

This is the dependency-inversion principle made concrete: the renderer and the engine both depend on the
*abstraction* (the Trajectory schema), not on each other.

## 7. Migration plan (no code in this document)

Strictly additive, behaviour-preserving, reversible at each step:

1. **Freeze the schema** (§2) as the contract; version it (`schema_version: 1`).
2. **Extract the builder.** Move the polarity-touching half of today's `pse_renderer.trajectory()` —
   role assignment, controlling-element selection, tone, coherence, imagery resolution — into a new
   `PolarityTrajectoryBuilder` that emits the schema. (Renames INTEGRATION/TENSION → FORMATION/INTERACTION.)
3. **Slim the renderer.** Reduce the renderer to `Trajectory → prose`: modes, prompt, honesty filter,
   single-metaphor join — all reading only the schema. Remove every engine/lexicon/`⤳` reference from it.
4. **Golden-test parity.** Assert the new pipeline reproduces v2 output exactly for the existing examples
   (river, kill, …) and that `renderer_test.py` still passes (roles, ⤳-only-easing now expressed as
   *TRANSFORMATION-only easing*, chain present, no forbidden words, engine unaltered).
5. **Add the enforcement tests** (§6.4).
6. **(Later, separate task) Add a second builder** for any no-polarity engine; the renderer is untouched.

Each step is independently committable; the engine is never modified.

## 8. Why this is the final renderer architecture

- **It is ontology-agnostic by construction.** The renderer depends on *interaction roles + felt qualities
  (texture/motion) + element + tone*, which are the irreducible inputs any "sound → expressive form"
  narrator needs. These are downstream of **any** future ontology — polarity, single-tendency, binding-
  operator, latent-field, or partition-quality — because every such ontology must still yield *some*
  ordered interaction profile per unit. Only the **builder** changes; the renderer is terminal.
- **It absorbs the project's own conclusions.** The model-selection arc ended at "varṇas are binding units;
  trajectory emerges from interaction." v3's vocabulary (FORMATION = binding, INTERACTION = coupling) is a
  direct encoding of that endpoint, so future ontology evolution *converges toward* this schema rather than
  away from it.
- **It bounds the blast radius forever.** Any future scientific change (even abandoning polarity entirely)
  touches exactly one swappable adapter. The narration layer — modes, honesty contract, three-layer output,
  single-metaphor discipline — never has to change again. That stability across arbitrary ontology change
  is precisely the definition of a final architecture.

**Therefore:** Renderer v3 = a pure `Trajectory → prose` core behind a frozen, polarity-free schema, fed by
per-engine adapters. The current polarity engine and any future no-polarity engine map into the same schema
with zero renderer changes — and that property is invariant under all anticipated ontology evolution.
