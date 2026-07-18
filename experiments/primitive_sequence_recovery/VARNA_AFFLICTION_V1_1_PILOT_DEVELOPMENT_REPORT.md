# Varṇa–Affliction Test V1.1 — Methodology Pilot (development report)

**`DEVELOPMENT_ONLY` · `EXPLORATORY` · `NOT_CONFIRMATORY_EVIDENCE`.** A small adversarial pilot to check whether
the frozen V1.1 three-layer methodology (PMM → PR → CR) is *practical* before a real study. **This is not
evidence, not the §10 confirmatory word-precommitment, and not an official run.** All PR judgments below are my
own **nonblind reasoned** adjudications (exactly the limitation V1 §6 discloses) offered to stress-test the
rubric, not to measure the theory. No methodology document, threshold, scale, or frozen artifact was modified.
Words were chosen to **exercise every branch of the scoring system**, not to pass — and several fail.

Frozen inputs used read-only: parser `sanskrit_stage1_parser.py` (`d885391f…`), lexicon
`varna_native_stage1_merged_v1.json` (`af4c1f54…`). Primary arm = consonant backbone only (vowels excluded, per
V1 §4). Scale, thresholds, and §8 verdicts applied exactly as frozen.

---

## Precommitted pilot set (9 words, mixed categories)

`gaja` (elephant, animal) · `śānti` (peace, virtue) · `jñāna` (knowledge, abstract) · `krodha` (anger, neg-emotion)
· `bhaya` (fear, neg-emotion) · `agni` (fire, natural) · `jala` (water, natural/concrete) · `ghaṭa` (pot,
concrete object) · `siṃha` (lion, fierce animal). No repeated consonants occur in this set (occurrence-level R4
trivially satisfied); coverage = 100% for all (no MISSING consonant mappings).

## Per-word results

PMM = evidence the mapping *relates* to the word (documentation only). PR = directional resolution
`{0,25,50,75,100}` (the verdict layer). Glosses shown short; full frozen text in the lexicon.

### 1. gaja (elephant) — animal
| varṇa | frozen gloss (short) | PMM | PR | directional reasoning |
|---|---|---|---|---|
| g | restless striving that cannot stop | 40 | **50** | *resolve:* the stable elephant is deliberate, patient, unhurried; *embody:* it forages ~18 h/day — "ceaseless outward striving clung to mundane ends" is a real reading. Genuinely mixed. |
| j | inflated 'I did / I control' doership | 25 | 75 | *resolve:* an elephant shows no human doership-ego; *embody:* mild dominance in a bull. Stands mostly free. |
- **min PR 50 · mean 62.5 · N_embodied(≤25) 0 · N_clear(0) 0 · CR ~70.** **Verdict: PARTIAL_FIT** (mean in
  [50,75)). *Note:* PR(g) swings 50↔75 on how "restless striving" is read against foraging — a nonblind call.

### 2. śānti (peace) — virtue
| varṇa | gloss | PMM | PR | reasoning |
|---|---|---|---|---|
| ś | kāma — worldly desire | 100 | 100 | peace stands free from grasping desire. |
| n | moha — blind attachment | 100 | 100 | peace stands free from fixated attachment. |
| t | jāḍya — inertia/dullness/torpor | 90 | **50** | **decisive tension:** *resolve:* true śānti is alert awakened stillness; *embody:* peace-as-passivity/torpor is inertness. Genuinely ambiguous. |
- **min PR 50 · mean 83.3 · N_embodied 0 · CR ~85.** **Verdict: PASS** (mean ≥75, min ≥50, no 0/25). *Note:*
  **fragile** — if `t` is read as 25 (peace = torpor), min = 25 → PARTIAL_FIT. A single component flips the
  verdict, and a component at the 50 floor is decisive for a PASS (see Final Review Q4).

### 3. jñāna (knowledge) — abstract
| varṇa | gloss | PMM | PR | reasoning |
|---|---|---|---|---|
| j | inflated doership-ego | 100 | 50 | *resolve:* self-knowledge dissolves ego; *embody:* vidyā-mada (pride of learning). Both real. |
| ñ | hypocrisy / concealment | 40 | 50 | knowledge → transparency vs knowledge-used-to-conceal. Mixed. |
| n | moha — attachment/delusion | 60 | 75 | jñāna classically *dispels* moha; residual attachment-to-views. |
- **min PR 50 · mean 58.3 · CR ~75.** **Verdict: PARTIAL_FIT** (mean [50,75); genuine mixture).

### 4. krodha (anger) — negative emotion
| varṇa | gloss | PMM | PR | reasoning |
|---|---|---|---|---|
| k | āśā — grasping / clinging hope | 100 | 25 | anger = frustrated grasping → embodies. |
| r | sarvanāśa — annihilation-thought | 100 | **0** | anger IS the destructive annihilation impulse → conspicuous embodiment. |
| dh | tṛṣṇā — craving | 100 | 25 | anger craves retribution → embodies. |
- **min PR 0 · mean 16.7 · N_clear(0) 1 · CR ~65.** **Verdict: FAIL** (component = 0; mean < 50). High PMM, PR≈0;
  a coherent "anger is transient, the composed transcend it" CR **cannot** rescue (anti-rescue held).

### 5. bhaya (fear) — negative emotion
| varṇa | gloss | PMM | PR | reasoning |
|---|---|---|---|---|
| bh | mūrcchā — loss of discernment/entrancement | 100 | **0** | fear/panic suspends judgment → conspicuous embodiment. |
| y | aviśvāsa — self-doubt/distrust | 100 | 25 | fear embodies self-doubt. |
- **min PR 0 · mean 12.5 · N_clear 1 · CR ~55.** **Verdict: FAIL.** Same signature: high PMM, embodiment PR.

### 6. agni (fire) — natural phenomenon
| varṇa | gloss | PMM | PR | reasoning |
|---|---|---|---|---|
| g | restless striving that cannot stop | 100 | **0** | fire ceaselessly consumes, never rests → conspicuous embodiment. |
| n | moha — fixation/attachment | 30 | 50 | fire "clings" to fuel? weakly; else free. Mixed. |
- **min PR 0 · mean 25 · N_clear 1 · CR ~50.** **Verdict: FAIL.** A natural force that embodies its lead
  affliction — the adversarial-category failure the test must be able to return.

### 7. jala (water) — natural / concrete
| varṇa | gloss | PMM | PR | reasoning |
|---|---|---|---|---|
| j | inflated doership-ego | 20 | 100 | water = emblem of humility/yielding; stands free from doership. **But the affliction is barely relevant (low PMM).** |
| l | kruratā — cruelty | 25 | 75 | stable water is nourishing/gentle (floods = excluded exceptional subtype). |
- **min PR 75 · mean 87.5 · CR ~85.** **Verdict: PASS** — **but see the vacuous-pass caveat (Q4):** the high PR
  comes largely from the afflictions being **low-PMM / weakly relevant**, so "does not embody" is closer to
  *inapplicable* than *resolved*.

### 8. ghaṭa (pot) — concrete inanimate object
| varṇa | gloss | PMM | PR | reasoning |
|---|---|---|---|---|
| gh | mamatā — possessive 'mine-ness' | 15 | 100 | an inanimate pot has no possessiveness → "not embodied." |
| ṭ | vitarka — garrulous over-talk | 5 | 100 | a pot is silent → trivially "free from over-talk." |
- **min PR 100 · mean 100 · CR ~90.** **Verdict: PASS — VACUOUS.** The mapped afflictions are
  **human-psychological and categorically inapplicable** to an inanimate object, so every component scores high
  PR via *non-embodiment by inapplicability*, not resolution. This is the clearest exposure of a rubric hole
  (Q4).

### 9. siṃha (lion) — fierce animal
| varṇa | gloss | PMM | PR | reasoning |
|---|---|---|---|---|
| s | sattvic impulse clung to as superiority | 20 | 50 | lion's *physical* dominance ≠ *spiritual* sattva-clinging; partial/vacuous. |
| h | outward vision — fixation on the manifest/physical | 65 | **25** | a lion IS fixated on the visible/physical (prey, territory) → substantial embodiment. |
- **min PR 25 · mean 37.5 · N_embodied 1 · CR ~55.** **Verdict: FAIL** (mean < 50; a 25 prevents PASS). Honest
  adversarial failure for a fierce predator.

## Pilot distribution (honest, not optimized)

**PASS 3** (śānti — *fragile*; jala — *vacuous*; ghaṭa — *vacuous*) · **PARTIAL_FIT 2** (gaja, jñāna) ·
**FAIL 4** (krodha, bhaya, agni, siṃha) · INDETERMINATE 0. Every verdict branch except INDETERMINATE was
exercised; the four failures are reported as they fell.

## Final review

**1. Were PMM and PR consistently distinguishable?** **Yes — strongly validated.** The pilot populated all four
quadrants: high-PMM/low-PR (krodha, bhaya, agni — relevance via *embodiment*), high-PMM/high-PR (śānti ś,n —
relevant *and* resolved), low-PMM/high-PR (jala, ghaṭa — irrelevant → trivially not embodied), and mixed
(jñāna). PMM and PR are genuinely orthogonal; the two-layer split does real work.

**2. Did the anti-rescue rule function?** **Yes** — krodha/bhaya/agni have PR = 0 components, and no CR narrative
was allowed to lift them; each is FAIL. *Caveat:* the rule "functioned" because I, the adjudicator, held it —
it is a discipline constraint, only as strong as adjudicator honesty and (recommended) independent review.

**3. Did CR remain explanatory?** **Yes — CR changed no verdict.** But the pilot shows CR is largely
**redundant** in practice: PR already decides everything and CR cannot rescue, so CR's only operational value is
triggering **HOLISTIC-ONLY FIT** — which did **not** fire here (no high-CR-with-weak-PR-passing case arose).
Keep CR for that diagnostic, but recognize it is a reporting aid, not a driver.

**4. Were any rubric definitions unclear? — two real gaps found (this is the pilot's main yield):**
- **(A) Vacuous non-embodiment / low-PMM auto-pass (major).** The hypothesis's *"resolves **or does not
  conspicuously embody**"* disjunct means afflictions that are **categorically inapplicable** to the referent —
  especially **inanimate/concrete objects** (ghaṭa) and referents orthogonal to a human-psychological affliction
  (jala) — score high PR by *inapplicability*, yielding **PASS that supports nothing**. Because PMM is
  documentation-only, the rubric has **no gate** to separate "genuinely resolves a *relevant* affliction" from
  "affliction irrelevant → trivially not embodied." Left unfixed, concrete/inanimate words would systematically
  **inflate the pass rate** in a confirmatory run and confound the result.
- **(B) Boundary fragility under coarse scale + nonblind adjudication (moderate).** A single component swinging
  **25↔50** (śānti `t`=jāḍya; gaja `g`; siṃha `h`) flips PASS↔PARTIAL_FIT↔FAIL. The `{0,25,50,75,100}`
  granularity plus nonblind judgment makes borderline verdicts low-reliability.

**5. Which rules should remain unchanged?** The load-bearing core is sound and should **not** change:
occurrence-level scoring (R4); **any component = 0 → FAIL** and minimum-component (R10) — these did the real work
(krodha, bhaya, agni, siṃha); embodiment counts (R11); the **PMM ≠ PR ≠ CR** separation and PR-as-sole-verdict;
the hard anti-rescue rule; coverage gating. Keep all thresholds.

**6. Wording to clarify before a first real run:**
- **Add an inapplicability gate for gap (A):** where a component's affliction is *categorically inapplicable* to
  the referent class (e.g. a human-psychological affliction vs an inanimate object; PMM ≈ 0), score that
  component **`INDETERMINATE`, not high-PR** — so it counts against coverage (R12) rather than as a free
  resolution. (This uses PMM as a *gate to INDETERMINATE*, **not** as a numeric contributor to the verdict, so
  it respects "PMM never scores the hypothesis.") Alternatively, restrict the confirmatory sample to referents
  for which the afflictions are *applicable* (animate/psychological-capable), and report concrete-object results
  separately. This choice should be **preregistered** before words are committed.
- **For gap (B):** require **≥2 independent adjudicators** with an inter-rater agreement report on the pilot-hard
  components, and flag any 25↔50 boundary component explicitly. (Reliability protocol, not a threshold change.)
- **Minor:** clarify whether a component scored **50 ("genuinely ambiguous")** may sit inside a **PASS** (śānti
  passes with `t` = 50 at the minimum floor), or whether PASS should require min > 50 / no component at 50.

## Recommendation

**`NEEDS_MINOR_METHOD_CLARIFICATION`.** The V1.1 methodology is **practical and diagnostic**: PMM/PR separate
cleanly, the anti-rescue rule and the any-0→FAIL / minimum-component safeguards return honest failures on
adversarial words (krodha, bhaya, agni, siṃha), and no rescue path inflated a pass. It is **not**
`READY_FOR_FIRST_REAL_RUN` **only** because of gap (A): without an inapplicability/INDETERMINATE gate,
concrete/inanimate referents pass vacuously and would inflate a confirmatory pass rate. It is **not**
`NEEDS_MAJOR_REDESIGN` — the core rubric is sound; the fix is a preregistered clarification (inapplicability →
INDETERMINATE, plus a dual-adjudication reliability protocol), decided **before** the §10 word precommitment.

## Guardrails
Development pilot only; no methodology document, threshold, scale, or frozen artifact modified; V1, V1.1, parser,
lexicon, B1.10, B1.11 all unchanged; no confirmatory precommitment, no run of record, no freeze. PR judgments are
illustrative nonblind adjudications, not evidence. Structure, not validated meaning.
