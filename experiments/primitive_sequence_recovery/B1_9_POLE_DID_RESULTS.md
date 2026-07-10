# B1.9 Pole Diff-in-Diff — Results Record (INCONCLUSIVE, contrastive-framing confound)

**Status:** results record for the real B1.9 pole-DiD run (`B1.9_pole_did`). **The primary statistic is
INCONCLUSIVE for pole correctness** — the "flipped" pole was frequently used as a *contrastive* scaffold, so the
correct-vs-flipped manipulation did not cleanly vary pole correctness. This is **not** a definitive
pole-resolution falsification; it is a weak/inconclusive result under a permissive generation prompt.

**No terminal verdict. No `GENUTILITY_*`. No `ONTOLOGICAL_SIGNAL`. No semantic-truth / ontology / Sanskrit-
privilege claim. B1.4b′ remains `NULL_RETURN_BOTTOM`.** Raw `run_out/` is not committed; only the aggregates below.

---

## 1. Run provenance

- Design/driver: `run_b1_9_pole_did.py`, prereg `B1_9_POLE_DID_PREREG.md`, scaffold
  `frozen/b1_9_pole_did_scaffold.json` (approved classification, commit `f4057b8`).
- 24 items (12 binding / 12 liberating), 4 arms
  (`OWN_CORRECT_POLE`, `OWN_FLIPPED_POLE`, `CONTROL_CORRECT_POLE`, `CONTROL_FLIPPED_POLE`).
- Generators Mistral-7B-Instruct-v0.3 (M1) + Qwen2.5-7B-Instruct (M2): **192 outputs** (24×4×2), 0 failures.
- Judges Llama-3.1-8B + Meta-Llama-3-8B + Gemma-2-9b: **576 ratings** (192×3), complete grid, per-arm n=144.
- Consonant-only canonical varṇas (Stage A′ + bridge); vowel omission is a stated limitation (prereg §5b).

## 2. Primary statistic (as measured)

`DiD = (OWN_CORRECT − OWN_FLIPPED) − (CONTROL_CORRECT − CONTROL_FLIPPED)`, paired by item:

| quantity | value |
|---|---|
| **mean DiD** | **−0.075** |
| bootstrap CI95 | **[−0.211, +0.064]** |
| sign (pos/neg) | **11 / 13** |
| mean OWN diff (OWN_CORRECT − OWN_FLIPPED) | **−0.007** |
| mean CONTROL diff (CONTROL_CORRECT − CONTROL_FLIPPED) | **+0.068** |

Arm-level penalty-adjusted composite (higher = better):

| arm | mean adj |
|---|---|
| CONTROL_CORRECT_POLE | 5.287 |
| CONTROL_FLIPPED_POLE | 5.219 |
| OWN_FLIPPED_POLE | 5.213 |
| OWN_CORRECT_POLE | 5.206 |

All four arms fall within 0.081; `OWN_CORRECT_POLE` is the lowest.

## 3. Contrastive-framing audit (why this is inconclusive)

Rate at which each arm framed a facet contrastively (as the word's obstacle/opposite/what it overcomes/resists/
is free from), matched by a keyword scan over the generated readings:

| arm | contrastive rate |
|---|---|
| OWN_CORRECT | 28/48 = **58%** |
| OWN_FLIPPED | 32/48 = **67%** |
| CONTROL_CORRECT | 22/48 = **46%** |
| CONTROL_FLIPPED | 29/48 = **60%** |

- Contrastive framing is **pervasive** across all arms and **higher on the flipped arms** (own +9pp, control
  +14pp): the model reaches for contrastive framing more when handed the theoretically-wrong pole.
- **`OWN_FLIPPED` beat `OWN_CORRECT` in 11/24 items; 10/11 (91%) of those used contrastive framing.** The
  flipped-pole wins are almost entirely a contrastive-reframing artifact, not evidence the flipped pole is
  "correct."

### 3b. Three worked samples (mechanism)
- **resentment (DiD ≈ 0):** own correct−flipped +0.58 ≈ control +0.59 — binding vocabulary fits a binding word
  whether the varṇas are its own or a distant word's → generic, cancels.
- **cage (DiD +0.56):** positive because cage's *own flipped* reading was absurd ("spiritual elevation" for a
  steel cage) and the control's flipped happened to say "earth-bound hardness" (fits a cage) — a coincidence of
  facet phrasing, not the mapping.
- **equanimity (DiD −0.81):** the "correct" (liberating) pole read *worse* (4.62) than the flipped (binding) pole
  (5.48), because the model reframed the binding facets contrastively: *"equanimity is a shield against
  forward-grasping desire and blind attachment."* The directional premise (correct → better) fails per item.

## 4. Interpretation (honest)

- The correct-vs-flipped **manipulation is leaky**: "flipped" is not a clean wrong-pole condition — ~60–67% of
  flipped readings use it as a usable contrastive scaffold, and the flipped-pole wins are ~91% contrastive.
- Effect on the DiD: this **compresses / sometimes reverses** the correct-vs-flipped gap and thereby **biases
  the DiD toward null** (it can mask a true pole effect). It **cannot** manufacture a false positive (contrastive
  use is present in all arms and largely differences out), but it makes the test **weak**.
- **Therefore this run is labeled INCONCLUSIVE for pole correctness** — "no pole signal detected under a
  confounded, permissive prompt" — **not** a definitive pole-resolution falsification.
- This is a limitation of the **pole** manipulation only. It does **not** imply anything positive for Symbol-U;
  resolving it is a prompt fix, not evidence.

## 5. Relationship to the other results (unchanged)

The pole-DiD inconclusive result does **not** touch the content-level nulls, which never used the pole
manipulation:
- **B1.4b′** `NULL_RETURN_BOTTOM`;
- **B1.9 embedding** distant-source content null (mean_delta −0.018, perm p 0.58);
- **B1.8 / B1.9 generation** content nulls (B1.9-gen: 6/6 resolver-free, 5/7 resolved).

Net picture: **content** shows no varṇa-specific signal (multiple nulls); the **pole-resolution** question is
**inconclusive pending a cleaner (non-contrastive) test** (see the `B1.9_pole_did_strict` variant).

## 6. Next step

Re-run the 4-arm DiD under a **stricter prompt** that forbids contrastive/opposite framing (facet rendered as the
word's *direct inner meaning*), with an output-side contrastive-marker audit — representation version
`B1.9_pole_did_strict`. If the pole effect is real it should sharpen; if still ≈0 under a direct rendering, that
is a much cleaner null.

## 7. Guardrails

No terminal verdict. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no semantic-truth / ontology / Sanskrit-privilege
claim. No raw `run_out/` committed (only the aggregates above). **B1.4b′ remains `NULL_RETURN_BOTTOM`.** Structure,
not validated meaning.
