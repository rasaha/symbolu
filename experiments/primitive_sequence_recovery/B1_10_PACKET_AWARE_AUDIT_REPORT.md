# B1.10 — Packet-Aware Audit Report (Stage 3)

**Executed exactly per the frozen pre-registration `B1_10_PACKET_AWARE_AUDIT_PREREG.md` (commit `9510c054`).**
Audit target: the assembled non-Claude blind set `B1_10_OFFICIAL_CONTEXTS_v3_QWEN.md` (canonical 12-sentence
block sha256 `a0abccb89091578cc6ee81b22143bd2bcd82ee9eb8624ba6855224825a418bfc`, commit `79d101ff`). Auditor:
Claude (packet-aware role). Deterministic numbers from `b1_10_packet_aware_echo_audit.py`
(`b1_10_author_v3_perword/echo_audit_output.json`).

Interpretation ceiling (unchanged): a positive later judge result can show **source-condition legibility to
judges only** — not ontology, semantic truth, Sanskrit privilege, generation utility, or word-specific varṇa
mapping. **B1.4b′ remains `NULL_RETURN_BOTTOM`. No `GENUTILITY_*`. No `ONTOLOGICAL_SIGNAL`. Structure, not
validated meaning.**

---

## 1. Quantitative results (frozen Jaccard method, cap 0.20)

| word | Tier-3 echo Jaccard | echo verdict | convergence max (vs excluded dev / Claude-v2) | conv. flag (>0.50) |
|---|---|---|---|---|
| pride | 0.0000 | CLEAN | 0.0625 | no |
| freedom | 0.0000 | CLEAN | 0.0625 | no |
| patience | 0.0000 | CLEAN | 0.0385 | no |
| courage | 0.0000 | CLEAN | 0.0323 | no |
| control | 0.0000 | CLEAN | 0.0606 | no |
| doubt | 0.0000 | CLEAN | 0.0000 | no |

Every word's context↔Tier-3 lexical overlap is **zero** (verified as genuine disjointness, not empty sets:
e.g. pride context = 21 stems, Tier-3 = 35 stems, ∩ = ∅). This is the expected consequence of genuine blind
authoring: the Qwen author never saw the Tier-3 facet wording, and used concrete everyday scenarios while
Tier-3 facets are abstract phenomenological phrases. Convergence with the excluded development / Claude-v2
sets is ≤ 0.0625 for all six — no accidental reproduction of packet-aware wording. **No word fails the echo
gate (2c) or the convergence advisory.**

## 2. Per-word verdicts (all four checks)

Legend — naturalness: natural/forced; condition-fit: FIT/FAIL; echo: CLEAN/SUSPECT; fairness: FAIR/UNFAIR.

### pride — **PASS**
- A: "Sarah beamed with pride as she watched her son win the championship, knowing her years of coaching had paid off." — contingent on an outside result (the win) and comparison (championship). **Condition A: FIT.**
- B: "Mark felt a quiet pride in his ability to solve complex problems without needing external validation or praise." — "without needing external validation" = self-grounded. **Condition B: FIT.**
- naturalness natural · condition-fit FIT · echo CLEAN (0.0) · fairness FAIR → **PASS**

### freedom — **REJECT_ITEM**  (condition-fit failure — the pre-registered "despite" flag fires)
- A: "She felt a surge of freedom when she finally quit her job and started her own business, despite the uncertainty." — intended Condition A, but on independent reading the sentence does **not** dominantly express dependence on comparison/approval/possession/outside-results. Its core (quitting to start **her own business** = **autonomy**) and its tail (**"despite the uncertainty"** = freedom **independent of outcome**) are both **Condition-B** features (autonomy; action independent of outcome are listed under Condition B). The "despite" clause introduces the opposite condition into an A-intended sentence, and the scenario itself leans B. Per pre-reg §2b this is a **condition-fit FAIL** (mixed / mislabelled pole).
- B: "He found true freedom in his daily walks through the park, enjoying the quiet solitude and natural beauty." — clean Condition B.
- naturalness natural · **condition-fit FAIL (A sentence)** · echo CLEAN (0.0) · fairness FAIR → **REJECT_ITEM**
- Failure is on **condition-fit (2b), not echo (2c)** — echo is zero. The item is **not edited**; only this word-pair returns to a fresh blind per-word authoring run (§4).

### patience — **PASS**
- A: "She could barely keep her patience as she waited for the promotion that her colleagues seemed to be receiving." — comparison with colleagues + contingent on an outside result (promotion). **Condition A: FIT.**
- B: "He practiced patience while meditating, focusing on his breath without seeking external validation." — inward, no external validation. **Condition B: FIT.**
- **Stimulus-integrity check (flagged):** the canonical 12-sentence block contains **only** patience's two sentences + self-check lines; the model's Section-9 provenance-template echo tail (present in `accepted/patience_ACCEPTED.txt`) is **NOT** in the block and does **not** enter the stimulus. Confirmed.
- naturalness natural · condition-fit FIT · echo CLEAN (0.0) · fairness FAIR → **PASS**

### courage — **PASS**
- A: "Sarah felt a surge of courage when she saw her rival falter, knowing this was her moment to shine." — rivalry/comparison + being seen ("moment to shine"). **Condition A: FIT.**
- B: "In the silence of his meditation, Mark found the courage to face his fears without needing anyone's approval." — "without needing anyone's approval" = self-grounded. **Condition B: FIT.**
- naturalness natural · condition-fit FIT · echo CLEAN (0.0) · fairness FAIR → **PASS**

### control — **PASS** (with documented caveat)
- A: "She maintained a tight grip on the reins, her success hinging on her ability to control the spirited horse." — control + fear of loss (success hinging) + outside result. **Condition A: FIT.**
- B: "He let go of the steering wheel, trusting the car's autonomous system to control the vehicle smoothly." — the person's dominant state is **letting go / non-grasping** (Condition B), which is the intended pole and matches the label. **Condition B: FIT (credible letting-go reading).**
- **Caveat (documented, not a reject):** in B the target word "control" is attributed to the **car's system**, not to the person's inner source-condition; the B source-condition is carried by "let go… trusting." Unlike freedom, the **label matches the dominant condition** (B), so this is a stylistic weakness, not a pole mismatch. Pre-registered watch: if control's judge margins behave oddly downstream, this caveat is the pre-noted reason (analogous to the microtest's "love" soft-flag).
- naturalness natural · condition-fit FIT (caveat) · echo CLEAN (0.0) · fairness FAIR → **PASS**

### doubt — **PASS**
- A: "Sarah felt a surge of doubt when she compared her progress to her colleagues', wondering if she was good enough." — explicit comparison + approval-seeking. **Condition A: FIT.**
- B: "Tom maintained a calm inner resolve, allowing his doubt to fade as he trusted in his own journey." — dominant state is calm self-grounded resolve (B); "doubt to fade" sits inside that B state, not an A→B transition. **Condition B: FIT.**
- naturalness natural · condition-fit FIT · echo CLEAN (0.0) · fairness FAIR → **PASS**

## 3. Tier-1 / Tier-2 fairness (all six FAIR)

Because every context's Tier-3 echo is zero and the contexts express **generic** other-conditioned vs
self-grounded contrasts (comparison/approval/outside-results vs inward/non-grasping), the generic **Tier-2
source-condition** packets remain clearly plausible fits, and **Tier-1 valence** remains a (weaker) plausible
competitor. The controls are **credible**, so fairness is FAIR for all six. Neutral methodological note (not a
result claim): the blind contexts lean toward *generic* source-condition scenarios, which makes the Tier-2
control a **strong** competitor and the Tier-3 increment a **conservative / hard** test — this is a property
of the stimuli, not a prediction of the outcome.

## 4. Decision

| word | naturalness | condition-fit | echo | fairness | decision |
|---|---|---|---|---|---|
| pride | natural | FIT | CLEAN | FAIR | **PASS** |
| freedom | natural | **FAIL** | CLEAN | FAIR | **REJECT_ITEM** |
| patience | natural | FIT | CLEAN | FAIR | **PASS** |
| courage | natural | FIT | CLEAN | FAIR | **PASS** |
| control | natural | FIT (caveat) | CLEAN | FAIR | **PASS** |
| doubt | natural | FIT | CLEAN | FAIR | **PASS** |

- **PASS: 5** (pride, patience, courage, control, doubt)
- **REJECT_ITEM: 1** (freedom)
- **DROP: 0**
- **Whole-set: NOT APPROVED** — approval requires all six PASS.

## 5. Required action (per pre-reg §4 — no edits, no substitution, no cherry-picking)

Return **only `freedom`** to a **fresh blind per-word authoring run** (`b1_10_perword_author_run.py --words
freedom`). The rejected freedom pair is **not** edited, patched, or reinterpreted; the five passing pairs are
**unchanged** and are **not** re-authored (accept-first-pass). Because generation is seed-deterministic, the
freedom re-run must draw with a **fresh, pre-declared seed** (the escalation ladder handles *surface*
failures; an *audit* rejection needs a genuinely different blind draw — otherwise the runner would reproduce
the identical rejected sentence). Pre-declared here: freedom re-authoring uses `--seed-offset 100` (freedom
base seed 20260721 → 20260821), a block disjoint from all prior freedom attempts. After the new freedom pair
passes surface validation, **re-run this audit on freedom only**; if it PASSes, the set becomes APPROVED.

No judges, no evidence-freeze declaration, no items rebuild, no new experiment number were produced by this
audit.

## 6. Guardrails
Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no semantic-truth /
ontology / Sanskrit-privilege claim. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B
blocked. Structure, not validated meaning.**
