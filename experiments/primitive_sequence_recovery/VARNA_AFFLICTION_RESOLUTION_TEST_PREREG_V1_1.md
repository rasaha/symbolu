# Varṇa–Affliction Resolution Test — Preregistration V1.1 (evaluation-methodology refinement)

**Docs-only methodology refinement. Preserves `VARNA_AFFLICTION_RESOLUTION_TEST_PREREG_V1.md` unchanged and
controlling for the hypothesis and the verdict rules.** V1.1 strengthens only the **evaluation process** — it
adds a three-layer workflow (PEM → PR → CR) that makes the reasoning explicit and hardens the test against
holistic ("it all sounds meaningful") rescue. **The hypothesis is unchanged. The verdict is still determined by
the frozen resolution score and nothing else.**

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. No word list selected, no packet computed, no run,
no freeze. Parser, lexicon, mappings, thresholds, and all prior results/preregs unchanged.

**Readiness: `READY_FOR_WORDLIST_PRECOMMITMENT`** (unchanged from V1 — the added layers are documentation/
explanation and do not alter the next gate).

---

## 1. Rationale

V1's disclosed limitation (§6) is that Stage-C adjudication is **nonblind**, so a motivated interpreter could let
a persuasive *whole-word narrative* paper over components that actually embody their afflictions — the Barnum
failure mode. V1 already guards this with blind Stage-A, bidirectional arguments, the minimum-component
safeguard, coverage gating, and anti-rescue rules (§6, §7 R10, §13). V1.1 makes the guard **structural** by
splitting evaluation into three explicitly independent layers and forbidding the two non-verdict layers from
ever moving the verdict. It changes **no** hypothesis, scale, threshold, or frozen rule.

## 2. Three-layer methodology (evaluate strictly in order, per component)

- **Layer 1 — Percentage Evidence Mapped (PEM):** how well-supported the frozen *mapping itself* is for this
  word. **Documentation only. Never scores the hypothesis.**
- **Layer 2 — Directional Component Resolution (PR):** does the stable prototype **resolve** or **conspicuously
  embody** this frozen affliction? **This is V1's §7 R7 score, unchanged — the ONLY layer that determines the
  verdict.**
- **Layer 3 — Combined Reconciliation (CR):** do the already-PR-scored components cohere into one stable picture?
  **Explanatory only. Never rescues a component.**

Layers run **in order**; a later layer may never revise an earlier one.

## 3. Definitions — PEM ≠ PR ≠ CR (independent measurements)

### 3.1 Percentage Evidence Mapped (PEM) — Layer 1, documentation only
For each consonant occurrence, record the **strongest evidence supporting** and the **strongest evidence
opposing** the frozen mapping's *relevance* to the word (philosophy, history, symbolism, function, traditional
literature, stable characteristics, ordinary understanding — bidirectional, per V1 Stage-B discipline). Then
assign PEM on the frozen absolute scale `{0,25,50,75,100}`: **100** overwhelming evidence the mapping genuinely
relates to the word · **75** strong · **50** plausible-but-mixed · **25** weak/indirect · **0** no defensible
relationship.
**PEM measures:** how strongly evidence supports the *frozen mapping itself*.
**PEM must NEVER:** contribute numerically to PASS; raise or lower PR; rescue a failed component; enter any
verdict. It exists solely to make the reasoning explicit and auditable. **A high PEM is not support** — it is
equally consistent with the referent *embodying* the affliction (see §7 krodha).

### 3.2 Directional Component Resolution (PR) — Layer 2, the ONLY verdict layer
For each consonant occurrence, **ignore relevance** and ask only: *does the stable, prototypical, unqualified
referent resolve, transcend, stand free from — or instead conspicuously embody — this specific frozen binding
affliction?* Assign PR on the frozen `{0,25,50,75,100}` scale exactly per V1 §7 R7 (**100** clear resolution …
**0** conspicuous embodiment). **All V1 rules are retained unchanged:** occurrence-level scoring (R4),
AND-composition (R5), no-progression (R6), mean (R9), **minimum component** (R10), embodiment counts (R11),
coverage ≥80% (R12), and **any component = 0 cannot PASS** (§8). PR — and only PR — yields
PASS / PARTIAL_FIT / FAIL / INDETERMINATE per V1 §8. **No threshold is changed.**
**PR measures:** to what extent the stable prototype resolves vs embodies the mapping.

### 3.3 Combined Reconciliation (CR) — Layer 3, explanatory only
**After every component already has its PR score**, assign one CR ∈ [0,100]: do the **already-PR-scored**
components cohere into one stable understanding of the word? **CR measures:** how coherently the
*already-judged* components fit as one picture.
**CR must NEVER:** modify PEM or PR; rescue a failed component; remove an embodiment; convert a PR PASS/FAIL into
a different verdict; or turn PASS into "SUPPORT." CR is an **explanation of PR**, not evidence.

**Stated explicitly: PEM ≠ PR ≠ CR — three independent measurements. Only PR determines PASS or FAIL.**

## 4. Hard anti-rescue rule (preregistered)

> **If any component fails under the frozen PR rules (PR = 0, or the word fails V1 §8), neither PEM nor CR nor
> any holistic interpretation may overturn that failure.** A high combined narrative can only *explain how
> already-resolving components operate together*; it can **never invent resolution for a component that scored 0
> or 25.** This binds under V1 §13 (prohibited rescues) and V1 §6 ("do not infer the aggregate first and backfill
> components"); V1.1 makes it a structural constraint on the CR layer.

## 5. HOLISTIC-ONLY FIT (new explicit diagnostic outcome)

**Definition:** CR is high **but** one or more PR component scores are weak (≤ 25) — the holistic narrative is
stronger than the directional component evidence.
- **Reportable and scientifically interesting** (it locates where a whole-word story outruns the components).
- **Never counts as support**, and never as PASS. It is a flag that the combined picture is doing work the
  components do not justify — the exact Barnum signature this refinement exists to expose.

## 6. Updated evaluation workflow (maps onto V1 Stages A→C; nothing frozen is removed)

1. **Stage A (blind, V1 §6):** lock the prototypical unqualified referent profile — unchanged.
2. **Layer 1 — PEM (new, documentation):** bidirectional evidence for/against each mapping's relevance; assign
   PEM. Records reasoning; touches no verdict.
3. **Layer 2 — PR (= V1 §7 Stage C, unchanged):** bidirectional strongest-resolution vs strongest-embodiment;
   assign PR **before** any aggregate (R13); compute mean (R9), minimum (R10), embodiment counts (R11), coverage
   (R12); derive PASS/PARTIAL_FIT/FAIL/INDETERMINATE per §8. **This is the verdict.**
4. **Layer 3 — CR (new, explanatory):** only after all PR are fixed, assign CR; if CR high while any PR ≤ 25 →
   flag **HOLISTIC-ONLY FIT**. CR changes nothing.
5. **Report** all three (PEM, PR, CR) per component/word with full V1 §9 R14 traceability. **Evidence (PEM) →
   Directional judgment (PR) → Combined interpretation (CR); the verdict comes only from PR; CR is explanation,
   not evidence.**

## 7. Worked examples — ILLUSTRATIVE ONLY (not the §10 wordlist; not a run; not official scores)

These four demonstrate the *logic* of PEM vs PR vs CR. They are **not** precommitted words (V1 §10 forbids
prejudging), **not** official packets or verdicts, and carry no evidential weight; the illustrative PR judgments
are openly reasoned and remain subject to V1's disclosed nonblind-adjudication limitation. Consonant mappings are
the exact frozen binding glosses.

**A. `krodha` (anger)** — consonants k, r, dh → *k* "āśā — grasping / clinging hope"; *r* "sarvanāśa — the
defeatist annihilation-thought"; *dh* "tṛṣṇā — limitless thirst to acquire."
- **PEM:** all ~**100** — grasping, an annihilation/destructive impulse, and craving are *obviously and
  defensibly* related to anger.
- **PR:** all ~**0** — the stable prototype of anger **conspicuously embodies** grasping, destructive collapse,
  and craving; it does not resolve them.
- **CR:** a narrative ("anger is a passing disturbance the composed transcend") might sound coherent (~70) — but
  the *stable, unqualified* referent of anger is the embodiment.
- **Verdict: FAIL** (multiple PR = 0). **High PEM did not help; high CR cannot rescue.** ← primary demonstration.

**B. `bhaya` (fear)** — consonants bh, y → *bh* "mūrcchā — hypnotic entrancement, loss of discernment under a
ripu"; *y* "aviśvāsa — self-doubt that cannot commit."
- **PEM:** ~**100/75** — loss of discernment and self-doubt are clearly related to fear.
- **PR:** ~**0/25** — fear **embodies** loss of discernment and self-doubt.
- **CR:** ~60. **Verdict: FAIL.** Again: high PEM, low PR → embodiment; CR cannot lift it.

**C. `jñāna` (knowledge)** — consonants j, ñ, n → *j* "the inflated 'I did / I control this'"; *ñ* "hypocrisy /
concealment"; *n* "moha — blind attachment / infatuation."
- **PEM:** *j* ~75 (intellectual ego is a real theme), *ñ* ~25–50 (weak/indirect), *n* ~50–75 (attachment to
  views).
- **PR:** *n* ~**75–100** (knowledge characteristically **dispels** moha — clean resolution); *j* ~**50**
  (knowledge both dissolves and inflates ego — genuinely mixed); *ñ* ~**50** (contestable).
- **CR:** a coherent "knowledge as the faculty that dispels delusion" (~75) — but it may **not** raise the mixed
  *j*/*ñ* components.
- **Verdict: PARTIAL_FIT** (a genuine mixture; any component at 25 would cap it below PASS). Shows a mixed case
  where CR is explanatory only.

**D. `śānti` (peace)** — consonants ś, n, t → *ś* "kāma — worldly / physical desire"; *n* "moha — blind
attachment"; *t* "jāḍya — inertia, staticity, dullness, torpor."
- **PEM:** all ~75–100 (freedom-from-desire and freedom-from-attachment are central to peace; peace-vs-dull-
  torpor is a classic distinction).
- **PR:** *ś* ~**75–100** (peace stands free from desire); *n* ~**75–100** (free from fixated attachment); *t*
  ~**25–50** — the **decisive tension**: is settled peace *alert stillness* (resolution) or *dull torpor/inertia*
  (embodiment of jāḍya)? If an assessor scores *t* = 0/25 (peace as inertia), śānti is **at most PARTIAL_FIT**,
  no matter how coherent the CR.
- **Verdict: PASS *only if* every component including *t* clears the bar; otherwise PARTIAL_FIT.** Demonstrates
  that even a "clearly peaceful" word is not auto-pass, and that CR cannot resolve the *t*=jāḍya question.

**Takeaways demonstrated:** (i) **high PEM routinely coexists with low PR** — relevance is maximized by
*embodiment* (krodha, bhaya); (ii) **high CR cannot rescue a failed PR** (krodha); (iii) the **minimum component
and any-0-FAIL rules** still do the real work (śānti's *t*, jñāna's mixed components).

## 8. What changed vs. what stayed frozen

**Changed (evaluation methodology only):** added Layer-1 **PEM** (non-scoring evidence documentation); added
Layer-3 **CR** (explanatory-only combined score); added the **HOLISTIC-ONLY FIT** diagnostic; added the
**hard anti-rescue rule** binding PEM/CR under V1 §13/§6; specified the evidence→PR-verdict→CR-explanation
ordering.
**Stayed frozen (unchanged & controlling):** the **hypothesis** (V1 §1); the **PR / resolution scale and all
thresholds** (V1 §7 R7–R12, §8 PASS/PARTIAL_FIT/FAIL/INDETERMINATE, any-0-cannot-PASS); occurrence-level (R4),
AND-composition (R5), no-progression (R6), mean (R9), minimum (R10), embodiment counts (R11), coverage ≥80%
(R12), integrity safeguards (R13–R16); the vowel arm's `PROVISIONAL/DEVELOPMENT_ONLY` status (§5); the parser
(`d885391f…`), lexicon (`af4c1f54…`), 33 confirmatory consonants; and §10 wordlist precommitment. **No order, no
packet comparison, no specificity experiment, no dictionary recovery** is introduced.

## 9. Readiness

**`READY_FOR_WORDLIST_PRECOMMITMENT`** — V1.1 refines only the evaluation workflow; the hypothesis and the
verdict-determining PR layer are byte-for-byte the frozen V1 rules. The next gate is unchanged: pre-commit the
adversarial ~8–10-word mix (V1 §10) **before** any packet, then run Stage A → PEM → PR → CR and report per V1
§11–§12 with the V1.1 three-layer trace. No words selected, no packet computed here.

## Guardrails
Docs-only refinement. V1 preserved unchanged; parser, lexicon, mappings, thresholds, prior results/preregs, B1.10,
B1.11 all unchanged; no run, no freeze. Only PR determines the verdict; PEM and CR can never rescue a failure.
Structure, not validated meaning.
