# Varṇa Lens × LLM — Integration Design

> **Read first:** `CONCEPT_BRIEF.md`, `RULES.md`, `RESULTS_ACOUSTIC_SIGNAL*.md`,
> `RESULTS_UTILITY_SIGNAL*.md`, `STRATEGY_POST_FALSIFICATION.md`. This document assumes those as
> settled and does not re-argue them.

## 0. The non-negotiable starting point

The Varṇa Lens is a **deterministic phoneme→propensity function**. Input a word; the engine
(`varna_lens.analyze`) emits a fixed, reproducible structure:

```
analyze("kala") ⇒ {
  sequence:  [ («Ka»,−, worldly="Hope",      counter="Detachment"),
               («a», +, essence="Birth"),
               («La»,+, worldly/counter="Compassion") ],          # the ordered chain
  whole_word_essence: { iast:"a", sign:"+", essence:"Birth" },     # final-vowel summary
  essence_short: "−Hope⤳Detach → +Birth → +Compassion ⟹ [+Birth]",
  model: "vowel_attachment", rule: "..."
}
```

This is the **scaffold**. It is *consistent* (same word → same chain, forever) and *ownable*. It is
**not** a meaning, a score, a semantic vector, or a quality signal — two pre-registered blind tests
with scrambled-lexicon controls returned **NO_SIGNAL** (lexical, real ≈ chance ≈ scrambled) and
**NO_UTILITY_SIGNAL** (Δ ≈ 0.07, far under the 0.30 threshold, and confounded by a position bias
larger than the effect). Apparent aptness is **reader-supplied**.

### The honesty contract (every pattern below is checked against this)

- **(a) Determinism / authorship split.** The scaffold is deterministic; any *reading* on top is
  **LLM-authored** and must be presented as crafted reflection, never as the word's decoded meaning.
- **(b) Aesthetic-only signal.** The scaffold may drive **style / structure / sound-pattern /
  aesthetic palette**. It may **never** be a meaning, quality, semantic, or scoring signal.
- **(c) C×R×S firewall.** The scaffold is firewalled from C×R×S / Conscious Generation — never a
  feature, prior, score, retrieval key, or reranker into it (`phoneme_overreach` taboo).
- **(d) No back-door revival.** No training objective, reward, or eval may teach a model to treat the
  chain as *meaning* — that would re-introduce the falsified signal through the back door.

The architectural invariant that satisfies all four: **the lens feeds the LLM as a fixed symbolic
seed the LLM elaborates; the LLM never feeds the lens, and the lens never feeds the meaning/quality
path.**

```
word ─► [DETERMINISTIC LENS] ─► consistent scaffold ─► [LLM AUTHORING] ─► reading/artifact
        (frozen, reproducible)   (style/aesthetic only)  (fluent, owned)
        ── the lens is a SOURCE, never a SINK; never a SCORE ──
```

---

## 1. Integration patterns

Each pattern lists: **what it buys**, **where the scaffold ends and authoring begins**, a
**contract check (a–d)**, and a **verdict** (BUILD / FLAG / REJECT). Patterns are grouped into
inference-time and training-time.

### A. INFERENCE-TIME patterns

#### A1. Lens-as-tool / function call  — ✅ BUILD (safest)
The lens is registered as a tool (`varna_lens.analyze(word) → scaffold JSON`). The LLM calls it when
a user asks for a reading/palette, receives the deterministic chain, and authors prose around it.

- **Buys:** determinism + provenance for free. The chain in the transcript is verifiably the
  engine's output, not a hallucination; the same word always returns the same tool result.
- **Scaffold ends / authoring begins:** scaffold = the tool's return value (frozen). Authoring =
  everything the model writes after reading it. The boundary is *literally a tool-call boundary* —
  the cleanest possible separation.
- **Contract:** (a) ✅ chain is tool output, prose is model output — visibly distinct; (b) ✅ used to
  seed reflective/aesthetic text; (c) ✅ the tool lives in `varna_lens/`, callable only from the
  reflection product, never importable by C×R×S; (d) ✅ no training touched.
- **Verdict:** BUILD. This is the reference implementation of the contract.

#### A2. Scaffold-in-context (Stage-2 authoring) — ✅ BUILD
The product calls `analyze()` itself, injects the scaffold into the prompt with the Part-4 reflection
template + hard language rules (never "means/represents/reveals"; always "invites reflection
on/notice whether"), and the LLM writes the reflection / journaling prompts / naming mood palette.

- **Buys:** the core product loop (journaling companion, naming tie-breaker, creative seeds) with
  full control over framing. No tool-calling round-trip needed.
- **Scaffold ends / authoring begins:** scaffold = the injected `sequence` + `whole_word_essence`.
  Authoring = the generated questions/palette. The **system prompt enforces the boundary** — it
  instructs the model that the chain is a consistent symbolic mirror, not a decoding.
- **Contract:** (a) ✅ enforced by the template's language rules + persistent honesty banner; (b) ✅
  output is reflection/mood, explicitly hypothetical; (c) ✅ self-contained in the reflection app;
  (d) ✅ inference-only.
- **Verdict:** BUILD. This is the primary recommendation (see §2).

#### A3. Constrained / logit-biased decoding toward a propensity *palette* — ⚠️ FLAG (build narrowly)
For sound-patterned generation (poetry, naming, branding), map a *target palette* (e.g. "soft /
expansive" vs "sharp / driving") to **phonetic constraints**: bias decoding toward words whose
varṇa chain matches the requested palette — i.e. toward sound classes (sibilants, retroflexes,
open vowels), not toward meanings.

- **Buys:** genuine sound-controllability — generate a brand-name shortlist or a line of verse whose
  *acoustic texture* is steered. This is a real, honest capability the lens uniquely enables, because
  the lens is fundamentally a deterministic map from **sounds** to a label set.
- **Scaffold ends / authoring begins:** scaffold = the deterministic palette→phoneme-class mapping
  used to build the logit mask/bias. Authoring = the model choosing fluent, meaningful words *within*
  that acoustic constraint.
- **Contract:** (a) ✅ if the bias targets **phonetic classes** the lens labels, not semantic
  targets; (b) ⚠️ this is the danger line — the bias must be derived from **sound** ("favor onset-CV
  retroflexes"), **never** from "favor words that *mean* compassion." The moment the palette is
  treated as a meaning to hit, it violates (b) and (d); (c) ✅ stays in the generation product;
  (d) ✅ inference-only, but watch the framing.
- **Verdict:** FLAG → BUILD only with the bias defined strictly over phoneme classes, and the
  product copy saying "sound-patterned," never "meaning-patterned." If you cannot cleanly state the
  constraint as a sound constraint, do not ship it.

#### A4. Style / control tokens at inference — ✅ BUILD (pairs with A3/B2)
Expose the palette as a small set of **style control tokens / tags** (`<palette:soft-expansive>`)
that condition generation, analogous to genre or tone tags.

- **Buys:** an ergonomic control surface; lets the palette be one knob among many (tone, length,
  register) rather than a bespoke pipeline.
- **Scaffold ends / authoring begins:** scaffold = the deterministic word→palette tagging used to
  *label* training/conditioning data and to set the token at inference. Authoring = the generated
  text.
- **Contract:** (a) ✅; (b) ✅ as long as the token names an **aesthetic/sound** axis, not a meaning
  ("soft-sibilant," not "means-peace"); (c) ✅; (d) ✅ at inference. (The training side that *creates*
  the token is B2 — checked there.)
- **Verdict:** BUILD, with sound-named tokens only.

#### A5. Lens output as a *retrieval key / reranker* — ⛔ REJECT
Tempting: embed the chain, use it to retrieve "similar-essence" words, or rerank candidates by
chain-similarity to a target meaning.

- **Why rejected:** this treats the chain as a **semantic key**. NO_SIGNAL means chain-similarity
  carries no meaning information — it is noise correlated with nothing, which can still fit
  spuriously on small data and **inflate apparent performance** (measurement harm) while smuggling
  the falsified sound→meaning leak back in (epistemic harm). Direct violation of (b), (c), (d).
- **Verdict:** REJECT. (A *sound*-similarity reranker for pure phonetic clustering would be a
  different, non-lens tool; do not dress the lexicon up as a meaning index.)

#### A6. Lens score as a generation *quality / aptness* filter — ⛔ REJECT
"Pick the name whose chain best matches the brief," "score outputs by essence-fit."

- **Why rejected:** a quality/scoring signal — exactly what (b) forbids and what the utility test
  found doesn't exist (Δ ≈ 0.07). It would make the system look like it learned aptness it provably
  cannot. Violates (b), (c), (d).
- **Verdict:** REJECT. Contrast/comparison for **human** choice (A2 naming mode) is fine *because the
  human scores*; the machine must not.

### B. TRAINING-TIME patterns

#### B1. Instruction-tune on (word → authored reading) pairs — ✅ BUILD (with care)
Fine-tune a model on a dataset of `(word, scaffold, authored_reflection)` so it internalizes the
**authoring style** — the Part-4 voice (hypothetical, image-rich, never "means"), the
worldly→dissolution motion, the reflective-question form.

- **Buys:** the model produces on-brand reflections without the full template each call; cheaper,
  more consistent voice; works offline/edge.
- **Scaffold ends / authoring begins:** scaffold = the `analyze()` output, included verbatim in each
  training example as the *given* the target prose elaborates. Authoring = the target text, whose
  **style** is what we teach. We teach *how to elaborate a chain*, not *what a word means*.
- **Contract:** (a) ✅ if the input always contains the deterministic chain, so the model learns
  "given THIS chain, write THIS style," not "given this word, recall its meaning"; (b) ✅ teaches
  style; (c) ✅ the tuned model is for the reflection product, never C×R×S; (d) ⚠️ **the back-door
  risk lives here** — if examples drop the scaffold and pair `word → reading` directly, or if the
  prose asserts decoded meaning, the model learns to fabricate meaning from spelling. Mitigations:
  **always include the scaffold in the input**; lint every target for forbidden verbs
  ("means/represents/reveals/signifies"); keep targets explicitly hypothetical.
- **Verdict:** BUILD, conditioned on scaffold-in-input + language linting. Reject any variant that
  trains `word → meaning`.

#### B2. Data augmentation conditioned on propensity palettes — ✅ BUILD
Use the deterministic word→palette map to **label** a generation corpus with sound-palette tags,
then train a controllable generator (the training counterpart of A4/A3).

- **Buys:** a model with a learned, low-cost **sound-aesthetic control axis** for poetry/naming/
  branding — controllable acoustic texture without inference-time masking.
- **Scaffold ends / authoring begins:** scaffold = the deterministic tagging of existing text by its
  phoneme-derived palette. Authoring/learning = the model learning to honor the tag stylistically.
- **Contract:** (a) ✅ labels are mechanical; (b) ✅ **iff** the tag is a sound/aesthetic class
  ("retroflex-heavy," "open-vowel/expansive"), not a meaning class; (c) ✅; (d) ✅ — crucially, the
  label describes *how the text sounds*, which is veridically what the lens computes (it really is a
  function of sounds), so no falsified claim is learned. The forbidden version is labeling text by
  "essence/meaning" and training the model to emit that meaning.
- **Verdict:** BUILD, sound-defined labels only.

#### B3. Phoneme-aware tokenization / embeddings as an orthogonal input feature — ⚠️ FLAG
Add a phonetic/varṇa-aware input channel (a g2p-derived feature stream) so the model has sound
information alongside subwords.

- **Buys:** better sound modeling generally (useful for rhyme/meter/pun/poetry). Phonetics is real
  and veridical — g2p is not the falsified part.
- **Scaffold ends / authoring begins:** the *phonetics* (g2p) is honest signal. The **varṇa
  propensity labels** are the falsified part. So: a **phoneme** feature is fine; injecting the
  **propensity essence** as a feature is not.
- **Contract:** (a) n/a (architectural); (b) ⚠️ a raw phoneme feature is aesthetic/structural and
  OK; the propensity *essence* as a feature is a meaning signal → forbidden; (c) ⛔ if this feature
  stream is anywhere near C×R×S it violates the firewall — keep phoneme features (if used at all) in
  the generation product only; (d) ⚠️ do not let "varṇa embeddings" become a learned meaning space.
- **Verdict:** FLAG. Permissible as **phonetics only**, outside C×R×S. The lens's *labels* must not
  enter the embedding table as semantic features. If in doubt, this is plain phoneme-aware modeling,
  not a "lens" feature — name it honestly.

#### B4. Preference / RLHF on a sound-aesthetic dimension — ⚠️ FLAG
Collect human preferences on **sound-aesthetic** quality ("which name sounds softer/punchier") and
optimize a reward for *acoustic palette adherence*.

- **Buys:** sharper controllability and human-aligned sound aesthetics for the generation product.
- **Scaffold ends / authoring begins:** scaffold = the deterministic palette target a sample is
  graded against. The reward measures **sound-match + human aesthetic preference**, both legitimate.
- **Contract:** (a) ✅; (b) ⚠️ the reward must be over **sound aesthetics**, never "did it capture the
  word's meaning/essence." If raters are asked "does this match the essence," that re-imports the
  falsified signal as a reward (worst-case (d) violation: optimizing the model to believe the
  falsified claim); (c) ✅; (d) ⚠️ this is the highest-risk training pattern for back-door revival —
  the reward function is exactly where meaning could sneak back in.
- **Verdict:** FLAG → BUILD only if the reward is provably "sounds like the target palette / humans
  prefer this sound," with rater instructions audited to exclude meaning/aptness language. Otherwise
  REJECT.

### Pattern summary

| # | Pattern | Time | Verdict |
|---|---|---|---|
| A1 | Lens-as-tool / function call | inference | ✅ BUILD |
| A2 | Scaffold-in-context (Stage-2 authoring) | inference | ✅ BUILD (primary) |
| A3 | Logit-biased decoding to a sound palette | inference | ⚠️ FLAG → build narrowly |
| A4 | Sound-named style/control tokens | inference | ✅ BUILD |
| A5 | Retrieval key / semantic reranker | inference | ⛔ REJECT |
| A6 | Quality / aptness scoring filter | inference | ⛔ REJECT |
| B1 | Instruction-tune on (word→authored reading) | training | ✅ BUILD (scaffold-in-input) |
| B2 | Data augmentation by sound palette | training | ✅ BUILD (sound labels) |
| B3 | Phoneme-aware tokenization/embeddings | training | ⚠️ FLAG (phonetics only, off C×R×S) |
| B4 | RLHF on a sound-aesthetic reward | training | ⚠️ FLAG → audited reward only |

The three rejected/most-dangerous items (A5, A6, and the meaning-flavored variants of B1/B4) all
share one tell: **they turn the lens from a source into a score** — using the chain to *judge,
rank, retrieve, or decode* rather than to *seed*. That is the line.

---

## 2. Recommended primary architecture

**Recommendation: A2 (scaffold-in-context, Stage-2 authoring) as the spine, with A1 (lens-as-tool)
as the integration shape, and an optional A4/B2 sound-palette control as a later add-on.**

Why this one: it is the most **buildable** (no model training, no decoding-internals work — pure
prompt + deterministic engine) and the most **contract-safe** (the deterministic chain is a literal,
inspectable input; the LLM only authors; nothing scores; nothing touches C×R×S). It delivers the
core product loops (journaling, naming tie-breaker, creative seeds) immediately. Training patterns
(B1/B2) are deferred optimizations of *style cost*, not prerequisites.

### Data-flow sketch

```
            ┌─────────────────────────── reflection / naming product ───────────────────────────┐
 user word  │                                                                                    │
 ──────────►│  varna_lens.analyze(word)  ──►  scaffold JSON (frozen, deterministic)              │
            │      (g2p / IAST / pin)              { sequence[], whole_word_essence, short }      │
            │                                          │                                          │
            │                                          ▼                                          │
            │   prompt assembler:  system(honesty rules + Part-4 template)  +  scaffold  +  intent│
            │                                          │                                          │
            │                                          ▼                                          │
            │                                    LLM (authoring)                                  │
            │                                          │                                          │
            │                                          ▼                                          │
            │   render:  honesty banner  +  chain shown as IMAGES (not "means")  +  authored      │
            │            reflection questions / naming mood palette  ──►  user  ──►  journal      │
            └────────────────────────────────────────────────────────────────────────────────────┘

                                   ✋ HARD FIREWALL ✋  (no edge crosses this)

            ┌──────────────── C×R×S / Conscious Generation ────────────────┐
            │   imports nothing from varna_lens/ ; no varṇa value is a      │
            │   feature / prior / score / retrieval key / reranker here     │
            └───────────────────────────────────────────────────────────────┘
```

### Minimal components

1. **Engine adapter** — thin wrapper over `varna_lens.analyze()` returning structured JSON
   (`sequence` of `{iast, sign, worldly, counter}`, `whole_word_essence`, `essence_short`). Already
   ~exists; just needs a `--json` / library entry point. *Deterministic boundary lives here.*
2. **Prompt assembler** — system prompt with the §STRATEGY Part-4 **hard language rules** + the
   reflection/naming template; injects scaffold + user intent. *Authoring boundary lives here.*
3. **Output renderer + persistent honesty banner** — never the verb "means"; chain shown as images;
   every output terminates in a question (reflection) or a labeled mood palette (naming).
4. **Output linter** — post-generation guard that rejects/regenerates any text containing
   forbidden verbs ("means / represents / reveals / signifies / your word is / you will"). Cheap,
   high-leverage safety net for (a) and (d).
5. **Firewall gate** — a CI/import check (or documented review gate) asserting nothing under
   `varna_lens/` is imported by C×R×S code and no varṇa-derived value appears as a feature there
   (Part-6). *Enforces (c) mechanically.*

Everything beyond this (tool-calling exposure A1, sound-palette control A3/A4, style fine-tune B1)
is an additive layer on the same spine and can ship later without rework.

---

## 3. Honest evaluation

The thing we are **forbidden to measure as success** is meaning accuracy — it is already falsified,
and a positive there would only mean the eval leaked. We evaluate the integration on three axes the
product actually claims:

### 3.1 Consistency / determinism (the moat)
- **Metric:** scaffold identity. For N words run K times, `analyze()` output is byte-identical
  (target **100%**). For the *authored* layer, measure **paraphrase stability** — same word, same
  intent, re-run M times: do the reflections stay on the same images/themes (high semantic-overlap of
  the surfaced propensities), even as wording varies? Report theme-stability, not text-identity.
- **Positive result lets us claim:** "the mirror is stable — return to the same word and you meet the
  same scaffold." It does **not** let us claim the scaffold is correct/meaningful.

### 3.2 Style-controllability (for A3/A4/B2 sound-palette work)
- **Metric:** request palette P, generate, run the deterministic lens on the *output*, measure
  **palette-adherence** = fraction of outputs whose recomputed phoneme-class profile matches P.
  Closed-loop and fully objective because the lens is deterministic. Report adherence vs. an
  unconditioned baseline (Δ should be large and positive if control works).
- **Positive result lets us claim:** "we can steer the **sound texture** of generated names/verse."
  It does **not** let us claim the sound carries meaning.

### 3.3 Human-preferred aesthetic / usefulness (debiased)
- **Metric:** blind human preference, **counterbalanced** (each pair shown A/B *and* B/A, averaged —
  the utility test failed partly on uncontrolled position bias of magnitude ~0.12 > the ~0.07
  effect). Compare: (i) lens-seeded reflection vs. a no-scaffold LLM reflection; (ii) lens-seeded
  naming palette vs. a generic one. Pre-register a **MIN_EFFECT** (the utility prereg used 0.30 on a
  5-pt scale) and judge by the registered rule, not by eye.
- **Critical control (carry over from the falsification):** include a **scrambled-lexicon** arm. If
  users prefer the real-lexicon reflections **no more than** scrambled-lexicon ones, then the value
  is in the *template + ritual + determinism*, **not** the specific sound→propensity map — and we say
  so. The utility test already found real ≈ scrambled; honesty requires we keep checking and keep
  reporting it.
- **Positive result lets us claim:** "people find the lens-seeded reflective/naming experience more
  useful than baseline X" — a **product** claim about the experience. It would **never** license
  "the lens decodes meaning" or "real beats scrambled because the lexicon is true" unless a *new*
  pre-registered real≫scrambled blind test passes the bar it has twice failed.

### What no positive result can ever buy
Meaning recovery, semantic validity, or any C×R×S signal. Those require clearing the original blind
bar (real ≫ scrambled). Until then, every win here is a win about **style, consistency, and
experience** — never about truth.

---

## 4. Failure modes & the line that must not be crossed

**Failure modes (watch-list):**
1. **Score creep (A5/A6).** Someone uses the chain to rank/retrieve/filter for aptness. → The lens
   becomes a meaning signal. *Guard:* the lens is a SOURCE, never a SINK or SCORE; firewall gate +
   code review.
2. **Verb leak.** Authored text drifts to "this name *means* / *reveals*…". → Determinism/authorship
   split (a) breaks; users hear an oracle. *Guard:* output linter (component 4) + non-dismissible
   honesty banner.
3. **Scaffold-dropping in fine-tune (B1).** Training on `word → reading` without the chain in the
   input teaches the model to **hallucinate meaning from spelling** — the falsified signal, baked in.
   *Guard:* scaffold always in the training input; reject the bare-pair dataset.
4. **Meaning-flavored reward (B4) / meaning labels (B2).** Rewarding/labeling by "captures the
   essence" optimizes the model to *embody* the falsified claim. *Guard:* reward/labels defined over
   **sound classes** only; audit rater instructions for meaning language.
5. **Firewall erosion (c).** A varṇa value sneaks into C×R×S "as a weak experiment." NO_SIGNAL means
   it adds noise correlated with nothing — spurious fit + epistemic rot. *Guard:* import/feature CI
   gate (Part-6); never "lightly," never "just to try."
6. **Eval self-deception.** Measuring meaning accuracy and celebrating noise, or dropping the
   scrambled-lexicon control. *Guard:* pre-registration, counterbalancing, mandatory scrambled arm.

**The line that must not be crossed:**

> **The Varṇa Lens may seed generation (sound, style, structure, reflective scaffold) but may never
> score, rank, retrieve, decode, or otherwise act as a meaning or quality signal — and may never
> touch C×R×S / Conscious Generation.** The deterministic chain is an input the LLM *elaborates*;
> the LLM's reading is *authored*, never the word's decoded meaning. Any integration that turns the
> lens from a source into a score, or that teaches a model to treat the chain as meaning, re-imports
> the twice-falsified signal and is rejected — not weakened, rejected.
