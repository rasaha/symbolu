# Guna/Vritti Label Source — PRE-REGISTRATION (label usability, doc-only)

> **Status: DESIGN ONLY, doc-only, locked before any labelling or probe run.** No training; no synthetic
> validation claims; no runtime change; no Bhava labelling. This document decides **whether Guna/Vritti
> labels can be made trustworthy and non-circular enough to run the hidden-state probe at all** — it is a
> *label-quality* gate, NOT a learnability claim. Pairs with `docs/CG_TRAINING_GUNA_VRITTI_HARNESS.md`.

## 1. Why labels are the blocker (not compute)
The harness is plumbing-complete, but every run on the synthetic fixture is `CG_GUNA_VRITTI_SYNTHETIC_ONLY`
by construction. A probe is only meaningful with **real labels that are (a) well-defined, (b) reliable
across labellers, and (c) NOT a trivial readout of the model input.** The central failure mode — seen
across the closed Bhava/CSR_policy/agentic tracks — is **circularity**: if the label is a deterministic
function of surface text that the hidden state trivially encodes, a "successful" probe proves nothing. So
labels get their own pre-registration and their own pass/fail gate **before** any GPU time.

## 2. Scope & non-goals
- **In scope:** label schemas, weak (heuristic) label derivation, a human-label protocol, leakage/
  circularity controls, agreement checks, and gates for whether labels are USABLE.
- **Out of scope / NON-GOALS:** training; running the probe; claiming Guna/Vritti are real cognitive
  states; labelling Bhava; any runtime change; treating weak labels or a synthetic fixture as validation.

## 3. Conceptual definitions (observable criteria — sourced, not invented)
Targets are **properties of the response** (given the prompt and, where available, ground truth).

**Vritti — cognitive mode (5-class, single dominant label).** Names from the codebase
(`vritti_scorer.py`, `jepa/state_projector.py`): PRAMĀṆA · VIPARYAYA · VIKALPA · NIDRĀ · SMṚTI.
| class | observable criterion |
|---|---|
| `pramana` (valid cognition) | response makes **correct, grounded** claims (matches ground truth) |
| `viparyaya` (error) | response makes **incorrect/false** claims (contradicts ground truth) |
| `vikalpa` (imagination) | **speculative / hypothetical / fictional** content, no truth-claim |
| `nidra` (void/latency) | **empty / evasive / refusal / "I don't know"** — a non-answer |
| `smriti` (memory) | **recall** of prior context / given facts / conversation history |

**Guna — energetic/quality profile (multi-label).** ⚠️ **Definitional ambiguity flagged, not invented:**
the source code names the 6 dims inconsistently — `evaluation.py` = `SAT·RAJ·TAM·SAT2·RAJ2·TAM2`;
`jepa/state_projector.py` = `SATTVA·RAJAS·TAMAS·VELOCITY·ACCEL·STABLE`. Only the **first three** have a
stable, observable meaning:
| dim | observable criterion |
|---|---|
| `sattva` (clarity) | clear, balanced, lucid, well-organized |
| `rajas` (activity) | active, energetic, urgent, action-oriented |
| `tamas` (inertia) | dull, confused, heavy, evasive, low-signal |
| dims 4–6 (`velocity/accel/stable` **or** `sat2/raj2/tam2`) | **UNDERDEFINED in the source docs** — these read as *state-trajectory dynamics*, not single-response qualities |

**Decision on Guna dims 4–6: do NOT invent criteria.** Until a source definition is located, they are
either (a) **human-interpretive only**, or (b) **excluded** from the usable label set. The pre-registered
default is **(b) exclude** — label only `sattva/rajas/tamas` (3-D) unless a cited definition for dims 4–6
is found, in which case a label-schema amendment is filed. The harness keeps emitting 6-D sigmoid outputs
(formula unchanged); only dims 4–6 carry no labels (masked from the loss/metrics).

## 4. Label schemas (exact)
```json
{ "id": "ex_001", "prompt": "...", "response": "...",
  "labels": {
    "vritti": "pramana",                  // one of: pramana|viparyaya|vikalpa|nidra|smriti
    "guna": [1, 0, 0, null, null, null]   // [sattva,rajas,tamas, dim4,dim5,dim6]; null = unlabelled/masked
  },
  "label_meta": {
    "source": "weak_heuristic | human | adjudicated",
    "guna_labelled_dims": ["sattva","rajas","tamas"],
    "rater_ids": ["r1","r2"], "ground_truth_available": true,
    "derived_from": "prompt+response+ground_truth (NEVER hidden states)" }
}
```
`guna` values are 0/1 (multi-label, sigmoid targets); `null` = masked (dims 4–6 by default). `vritti` is
single-label. **Bhava is never labelled.**

## 5. Weak (heuristic) label derivation — explicitly weak
Deterministic rules over **prompt + response + ground truth ONLY** (never hidden states), each marked
`source = weak_heuristic`:
- `vritti`: `nidra` if refusal/empty/low-content; else `viparyaya` if contradicts ground truth; else
  `vikalpa` if speculation markers dominate ("imagine", "suppose", fiction); else `smriti` if it recalls
  given context; else `pramana`.
- `guna`: `sattva` if clear/structured (readability/structure proxy); `rajas` if action/imperative
  density high; `tamas` if low-signal/hedge-heavy/confused. Dims 4–6 left `null`.
> **Disclaimer (pre-registered):** weak labels are a **proxy**, partly **surface-derivable**, and CANNOT
> by themselves validate a "deep" hidden-state finding. A probe that predicts weak labels may simply be
> re-deriving the heuristic. Weak labels are for **plumbing + a weak upper bound only** — never a
> `LEARNS_SIGNAL` claim on their own (see §9).

## 6. Human-label option (the trustworthy path)
- **Raters:** ≥ 2 independent; plain-language rubric (the §3 observable criteria), **no** "Bhava/Guna/
  Vritti/cognitive-state" jargon shown to raters — they label observable response qualities
  (clear/active/dull; factual/false/speculative/evasive/recall).
- **Items:** a balanced set (≥ ~30 per Vritti class where feasible; both 0/1 present per Guna dim).
- **Adjudication:** disagreements on `vritti` resolved by majority/named tie-breaker (fixed before
  labelling); `guna` dims by majority. Record per-item rater values (disagreement is data).
- Raters see **prompt + response only** (and ground truth for the factuality call) — never hidden states,
  never the model's internal anything.

## 7. Leakage & circularity controls (the core)
1. **Labels are NEVER derived from hidden states** (asserted in `label_meta.derived_from`).
2. **Surface-feature baseline (anti-circularity):** before/alongside any probe, fit a simple baseline that
   predicts each label from **transparent surface features** (length, hedge/▁refusal markers, imperative
   density, readability, ground-truth-match flag). The hidden-state probe's claim is bounded by this: if a
   label is already ~fully predicted by surface features, the probe is **surface-confounded** and CANNOT
   claim a cognitive-structure finding (it must *beat* the surface baseline by a margin to mean anything).
3. **Report label↔surface correlation** per label; flag any label with AUROC_surface ≥ 0.85 as
   surface-confounded.
4. **Grouped splits:** train/val/test split by item; no item (or near-duplicate prompt template) across
   splits. Balanced prevalence enforced.
5. **No response-text features fed to the probe** beyond the pooled hidden state (the probe's only input
   is the hidden state; the surface baseline is a *separate* control, not a probe feature).

## 8. Agreement & quality checks
- **Vritti:** Cohen/Fleiss **κ** across raters (per class + overall).
- **Guna (per labelled dim):** Cohen **κ** (binary) per dim.
- **Weak-vs-human concordance:** agreement between weak labels and adjudicated human labels (shows whether
  weak labels are an acceptable cheap proxy or diverge).
- **Prevalence:** each Vritti class and each Guna dim must have enough positives (non-degenerate).
- **Surface-baseline AUROC/F1** per label (from §7.2).

## 9. Pass/fail gates — is the label set USABLE? (decision labels)
`LABELS_USABLE_HUMAN · LABELS_USABLE_WEAK_ONLY · LABELS_SURFACE_CONFOUNDED · LABELS_LOW_AGREEMENT ·
LABELS_DEGENERATE_PREVALENCE · LABELS_UNDERDEFINED_GUNA_DIMS · LABELS_UNAVAILABLE`

- **`LABELS_USABLE_HUMAN`** (the only label that licenses a real probe with a `LEARNS_SIGNAL` ceiling):
  human κ ≥ **0.60** on Vritti (and ≥ 0.50 per labelled Guna dim); non-degenerate prevalence
  (≥ ~8 positives per class/dim); **and** ≥ 1 label is NOT surface-confounded (surface-baseline
  AUROC < 0.85) — so a hidden-state win over the surface baseline is *possible*.
- **`LABELS_USABLE_WEAK_ONLY`** — weak labels are internally consistent + concordant with a small human
  spot-check, but no full human set: usable for **plumbing / weak upper bound**, NOT for a `LEARNS_SIGNAL`
  claim. Probe runs report `SYNTHETIC_ONLY`-equivalent caution.
- **`LABELS_SURFACE_CONFOUNDED`** — all labels predicted by surface features (AUROC ≥ 0.85): a probe
  cannot make a non-trivial claim; do not over-read any probe positive.
- **`LABELS_LOW_AGREEMENT`** — κ below threshold: labels not trustworthy; relabel or redefine criteria.
- **`LABELS_DEGENERATE_PREVALENCE`** — a class/dim too rare to score.
- **`LABELS_UNDERDEFINED_GUNA_DIMS`** — proceed on 3-D Guna; dims 4–6 stay masked until a source
  definition is filed (does not block Vritti / 3-D Guna).
- **`LABELS_UNAVAILABLE`** — no labels collected.

**Kill/usage rule:** only `LABELS_USABLE_HUMAN` permits interpreting a probe `LEARNS_SIGNAL`; everything
else caps the probe at `SHAPE_ONLY_PASS` / `SYNTHETIC_ONLY` / surface-confounded caution. No post-hoc
threshold tuning; a new attempt is a new pre-registration.

## 10. How this feeds the probe harness
The harness `metadata.source` field consumes this: `human`/`adjudicated` → eligible for `LEARNS_SIGNAL`
(subject to beating the surface baseline); `weak_heuristic`/`synthetic` → `SYNTHETIC_ONLY`-class only. The
surface-feature baseline becomes a required companion metric in `eval_guna_vritti_probe.py` before any
`LEARNS_SIGNAL` is reported (a follow-up implementation, not done here).

## 11. Risks
- **Circularity** (the main one) — mitigated by the surface baseline + "labels never from hidden states";
  even so, hidden states encode surface form, so the bar (beat surface baseline) is the real test.
- **Guna interpretive subjectivity** — low κ likely on `sattva/rajas/tamas`; honest κ reporting decides
  usability rather than forcing it.
- **Underdefined Guna dims 4–6** — handled by masking + a flagged TODO, not invention.
- **Vritti label/ground-truth coupling** — `pramana`/`viparyaya` depend on ground truth; for prompts
  without ground truth those two collapse → restrict factuality-based labels to items with ground truth.
- **Weak-label self-fulfilment** — a probe on weak labels can re-learn the heuristic; explicitly barred
  from `LEARNS_SIGNAL`.

## 12. Current claim / boundary
*The Guna/Vritti probe harness is built but has no usable labels. This pre-registration defines how Guna
(3-D usable + 3 underdefined) and Vritti (5-class) labels would be derived (weak heuristic) or collected
(human), the leakage/agreement controls, and the gates that decide whether labels are trustworthy enough
to run the probe. No labels have been collected; no training has been run; no Guna/Vritti cognitive-state
claim is made. Bhava is not labelled.*
