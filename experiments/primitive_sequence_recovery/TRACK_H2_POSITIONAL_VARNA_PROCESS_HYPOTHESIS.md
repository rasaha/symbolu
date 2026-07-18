# Track H2 — Positional Varṇa-Meaning Process (design materials, proposal only)

**Status: proposal only. Docs, no build.** No runner, no fixtures, no run, no model call. `frozen/manifest.json` NOT_READY; base run manifests `run_enabled:false` / `NOT_APPROVED`; Stage A untouched; **Track B BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege, no semantic-truth claim.

**Corrected H2 framing.** G2P is **pronunciation normalization only**; a frozen varṇa table supplies dual meaning poles; a positional rule selects **blocked / bridge / resolution** roles; the output is a **sequential varṇa-process reading**, not a scalar net polarity (the scalar-counting version was rejected because it collapses into CV cancellation / cluster-coda counting). This is a **fresh** hypothesis and **does not rescue or reinterpret** Track G.

**Track G negative preserved exactly (`1fe5562`):** `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`, `malformed_rate 0.0`. Static varṇa-derived polarity lost to its own random sign-flip and to context. **Track B remains BLOCKED.**

---

## Homonym / Homophone Handling

This section adds a conceptual constraint to H2. It is a **falsifiability guard**, not a new way to claim success: it hard-codes "same sound → same profile," which structurally blocks gloss-conditioned storytelling (H2's biggest threat). Including it makes H2 **harder to fool, not more likely to be true.**

### 1. Definitions
- **Homonym** (umbrella): one form, multiple unrelated senses — often same **spelling *and* sound** (*bank*, *bat*, *light*).
- **Homophone**: same **pronunciation**, sense (and maybe spelling) differs (*right / write / rite*).
- **Homograph**: same **spelling**, pronunciation may differ.
- **Heteronym**: a homograph whose **pronunciation differs** (*lead* /liːd/ vs /lɛd/; *tear* /tɪər/ vs /tɛər/).

**Why G2P is the key:** the base profile is keyed on **pronunciation**, not spelling and not gloss.
- **Same pronunciation → same base varṇa-process profile (mandatory).**
- **Different pronunciation → different base profile is allowed** (heteronyms) — but only where the difference is traceable to the **G2P output**, never to the meaning.

### 2. Architectural rule
> **"Same pronounced form = same varṇa-process profile. Context selects referent meaning."**

Three firewalled layers:
- **Layer 1 — G2P / varṇa-process substrate.** Pronunciation → varṇa units → positional roles → process reading. **Gloss-blind, target-blind, context-blind, deterministic, hashed.** Identical pronunciation ⇒ byte-identical Layer-1 output, reused across all senses.
- **Layer 2 — context / referent selection.** The **only** layer allowed to disambiguate. By construction the varṇa substrate cannot.
- **Layer 3 — final semantic interpretation.** The human-readable sense, revealed **only after scoring**.

### 3. Examples

| Word / senses | Pronunciation | Base profile: same or differ? | Who selects the sense |
|---|---|---|---|
| **bank** = river edge / financial | /bæŋk/ | **Same** (mandatory) | Context only |
| **light** = illumination / not heavy | /laɪt/ | **Same** (mandatory) | Context only |
| **right** = correct / direction / entitlement (also *write*, *rite*) | /raɪt/ | **Same** across senses and homophones | Context only |
| **bat** = animal / implement | /bæt/ | **Same** (mandatory) | Context only |
| **lead** = guide vs metal | /liːd/ **vs** /lɛd/ | **May differ** — different G2P → different profile is legitimate | Pronunciation splits them; context confirms |
| **tear** = eye fluid vs rip | /tɪər/ **vs** /tɛər/ | **May differ** — heteronym; different sound → different profile allowed | Pronunciation splits them; context confirms |

For *bank/light/right/bat* the varṇa layer **must be constant** and is structurally incapable of telling the senses apart — that job belongs to context. For *lead/tear* the split is carried by **pronunciation** (G2P), never by the gloss.

### 4. Experimental implication
- Homonyms are an **audit / leakage-control bucket, not proof of varṇa meaning.**
- The varṇa layer alone is **not expected to disambiguate** homonyms — and must not, since its output is identical across same-sound senses.
- **Context-only (X) may beat the varṇa arm (A)** on homonym sense-selection, **and that is not a failure** — it is the predicted, correct outcome.
- Sharp consequence: because A's profile is **identical** across same-sound senses, if A scores **above chance** at picking the context-correct sense, that can **only** be leakage. The homonym bucket therefore doubles as a **built-in leakage tripwire**.

### 5. Leakage & post-hoc-fitting risk
Allowing different varṇa readings for the same pronunciation would make H2 **unfalsifiable**. Hard prohibitions:
- **No gloss-conditioned varṇa profile** — Layer 1 never sees the gloss.
- **No per-sense rewritten varṇa reading** — one pronunciation, one reading, reused verbatim.
- **No choosing positive/negative pole after seeing the target meaning** — poles frozen before scoring (`INVALID_POSTHOC` otherwise).
- **No handcrafted explanation per homonym sense** — automatic generation only; one hand-edit voids the run.

### 6. Safe scoring modes
**Mode A — Sense-disambiguation.** Expectation: **context (X) dominates**; the varṇa profile is **constant**. Not used to prove varṇa meaning; A above chance ⇒ leakage alarm, not success.

**Mode B — Shared-process-substrate.** Do both senses share the **same automatically generated abstract process reading**? Generated **before** any gloss is seen; judged against **random (R)** and **scrambled (S)** controls so the shared reading isn't a generic Barnum arc.

Neither mode can produce positive evidence *for* varṇa meaning; both are integrity checks.

### 7. Controls
- **X** context-only · **D** dictionary/gloss-only · **R** random varṇa meanings (same pronunciation) · **S** scrambled varṇa order · **F** sign-flipped positional roles · **C** cluster/coda-only · **H** **homonym-pair consistency check** (mandatory): for every same-pronunciation sense set, assert the Layer-1 profiles are **identical**; any divergence = automatic fail.

### 8. Required invariants (hard)
- **Same G2P output → same hash → same base profile.** Profile is a pure function of the phoneme string.
- **One base profile reused across all senses** of a same-pronunciation set (byte-identical).
- **Profile generation cannot access gloss, target, context, or answer key.**
- **Only Layer 2 (context) may select the referent.**
- **Audit dump (B3 `--all-raw-dump`) must show identical base profile** for all homophone senses; profiles may differ **only** for heteronyms, and only where the **G2P string differs** — the diff must be attributable to pronunciation, never to meaning.

### 9. Kill criteria
Kill or downgrade H2 if any hold:
- Same pronunciation produces **different base profiles** across senses.
- The varṇa explanation **changes because the gloss changed**.
- Homonym performance **depends on word-identity leakage**.
- **Context-only explains** the results (expected here — in this bucket, A-beats-X is a *leakage* signal, not a win).
- Profile is useful **only after handcrafted interpretation**.
- Any result is used to claim **ontology, Sanskrit privilege, or Track B support**.

### 10. Recommendation
**GO-WITH-CONDITIONS — include homonyms strictly as an audit / leakage-control bucket, never as primary evidence.**

- This constraint **strengthens H2's falsifiability**; it structurally blocks gloss-conditioned storytelling. Good hygiene.
- But by construction the homonym bucket **cannot generate positive evidence for varṇa meaning** — the varṇa layer is deliberately blind to sense there. Its value is **negative/diagnostic**: it catches leakage and post-hoc drift. It does **not** raise the prior on a defensible positive (still low); it only makes a *false* positive less likely.
- **Conditions:** the §8 invariants (pronunciation-keyed hashing, gloss-blind Layer 1, identical-profile audit) must be **built and verified on toy fixtures before any model run**; the **H consistency control** is mandatory; and it must be pre-registered that **X beating A on homonyms is expected and not a failure**, while **A beating X on homonyms triggers a leakage investigation.**
- **NO-GO** the moment any pathway lets a sense/gloss influence the Layer-1 profile — that single leak makes the track unfalsifiable.

Net: adopt the homonym rule, framed exactly as an **audit and leakage-control bucket, not primary evidence.**

---

Track G's negative stands exactly (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`, `malformed_rate 0.0`); Track B remains BLOCKED; no ontology validation, no Sanskrit privilege, no semantic-truth claim, no rescue of Track G.

Structure, not validated meaning.
