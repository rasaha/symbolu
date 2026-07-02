# Track E Smoke — Dry-Run Packet Preview (human inspection)

**Dry-run packet preview only. No model call, no scoring, no run.** Generated with
`track_e_smoke_runner.dry_run()` (preview mode). `frozen/manifest.json` remains **NOT_READY** (not
touched); the smoke manifest stays `run_enabled:false` / `approval_status:"NOT_APPROVED"`; the psr
runner remains **NOT_RUN**; Stage A untouched; four-sphere JSON **not integrated**; **Track B
remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege. Nothing here reinterprets the
Track C / D0 negatives.

## 1. Dry-run status

- **Total packets generated:** **108**.
- **Expected count:** 12 cases × [5 single-arm packets (A, B, X, F, D) + 4 Barnum variants for arm
  I] = 12 × 9 = **108**. ✅ matches.
- **Per-arm counts:** A 12, B 12, X 12, F 12, D 12, **I 48** (= 12 × 4 Barnum variants).
- **Model calls:** **0** (`report.model_calls == 0`). **Scored:** `false`. No network, no LLM.

## 2. Leak scan summary

Every one of the 108 packets passed the scanner (`report.leak_scan == "clean"`). Confirmed absent
from all scorer-facing fields (premise, instructions, candidate texts, candidate ids):

- **surface words** (Sanskrit target tokens) — none (whole-word scan; substring hazards like
  `bala`⊂`balance` explicitly excluded);
- **varṇa names** (`ka…ksha`) — none;
- **root names** (moha/bhaya/kāma/tṛṣṇā/…) — none;
- **arm labels / codes** (A/B/X/F/D/I, `boundary_real`, `true_arm`, …) — none;
- **candidate role labels** (`context_correct`, `hard_negative`, `barnum_compatible`, …) — none;
- **hidden answer key** (correct id, arm, opt→cand map, authored/shuffled orders) — none (0 packets
  carry any hidden field);
- **four-sphere references** — none (`sphere` appears in 0 scorer-facing strings; the runner never
  loads `track_e_varna_sphere_lexicon.json`).

## 3. Shuffle verification

- **Candidate order differs from authored order:** ✅ for **all 108** packets
  (`all_shuffled_differ_from_authored == true`). Packet candidates are re-labeled to opaque
  `opt_1…opt_6`; the runtime shuffle uses `seeds.candidate_shuffle`.
- **Hidden key separate:** ✅ the correct candidate id and the true arm are absent from every
  packet; the hidden key (case_id, true_arm, correct id, orders, opt→cand, exploratory_only) lives
  only in the separate key structure, never in a packet.

## 4. Representative packet samples (redacted)

The arm *type* is labelled below **for the human reviewer only** — the actual packet contains no
arm label, no correct-answer marker, and no role labels. Candidate order is the shuffled `opt_*`
order; **the correct candidate is not revealed**.

**Sample 1 — arm A (real boundary), abstract case**
> premise: *"After the long fever finally broke, a quiet loosening settled over her. Consider this
> internal constraint: internal constraint emphasizing: escapism / premature static withdrawal ;
> worry / impersonal thought"*
> candidates: peaceful contentment · good fortune / prosperity · ego gratification · a general
> sense of well-being · relief after strain · sensory pleasure

**Sample 2 — arm B (scrambled boundary), abstract case**
> premise: *"Seeing the official take bread from the starving crowd, she rose to her feet, unable
> to stay quiet. Consider this internal constraint: internal constraint emphasizing: shyness ;
> static inertia / worldly desire ; melancholy / dejection"*
> candidates: cold resentment · a strong negative feeling · petty irritation · explosive rage ·
> righteous indignation at injustice · physical heat / feverishness

**Sample 3 — arm X (context-only), concrete control case**
> premise: *"They loaded the boat and let the current carry them downstream toward the sea."*
> candidates: the flow of time (figurative) · a small stream / brook · a large natural feature ·
> an artificial canal · a flowing natural watercourse · the bank at the water's edge

**Sample 4 — arm F (etymology-only), abstract case**
> premise: *"When the others fled, he alone stood his ground at the gate. Consider this internal
> constraint: Older usage centers on the chest as the seat of inner life."*
> candidates: one's true inner nature · the physical organ in the chest · courage / inner resolve ·
> the seat of emotion · openness to being hurt · tender affection

**Sample 5 — arm D (dictionary-only), abstract case**
> premise: *"Consider this reference meaning: power / strength"*  (no context sentence, by design)
> candidates: domination over others · political authority · a body of troops / an army · bodily
> strength / muscular force · capacity / capability · a great inner force

**Sample 6 — arm I (Barnum boundary, variant B1), abstract case**
> premise: *"Each night before the verdict, he lay awake staring at the ceiling, unable to picture
> the days ahead. Consider this internal constraint: internal constraint emphasizing: a broad
> emotional pull that could fit almost any heartfelt reading"*
> candidates: reverent awe · sudden startle / fright · anxious dread of what may come · an
> unsettled feeling · timid shyness · physical danger itself

## 5. Human inspection checklist

| Check | Sample 1 (A) | Sample 2 (B) | Sample 3 (X) | Sample 4 (F) | Sample 5 (D) | Sample 6 (I) |
|---|---|---|---|---|---|---|
| context understandable | yes | yes | yes | yes | n/a (no context) | yes |
| candidates plausible | yes | yes | yes | yes | yes | yes |
| no candidate trivially signaled | yes | yes | yes | mostly¹ | mostly² | yes |
| boundary/control not obviously leaking | yes | yes | n/a | mostly¹ | n/a | yes |
| Barnum not too weak/overpowering | — | — | — | — | — | yes³ |
| context-only arm fair | — | — | yes | — | — | — |
| etymology/dictionary not revealing answer | — | — | — | mostly¹ | mostly² | — |

¹ **F:** the etymology text "…seat of **inner** life" shares the token *inner* with two candidates
("one's true **inner** nature", "courage / **inner** resolve") — a mild lexical nudge, not a direct
name of the answer. ² **D:** the reference meaning "power / **strength**" shares *strength* with the
candidate "bodily **strength** / muscular force" — expected for a dictionary baseline, but a lexical
overlap. ³ **I:** "could fit almost any heartfelt reading" is deliberately generic; appropriate for
a Barnum control (vague, not overpowering).

## 6. Potential concerns

Listed even where minor:

1. **Redundant boundary wording (cosmetic, all A/B/I packets).** The premise reads *"Consider this
   internal constraint: internal constraint emphasizing: …"* — "internal constraint" is printed
   twice, because the runner prepends `"Consider this internal constraint: "` to a boundary
   description that already begins `"internal constraint emphasizing: "`. Not a leak and not a
   scoring risk, but it is awkward and a reviewer will notice. **Fix:** adjust `_premise` (or the
   bundle boundary descriptions) so the prefix is not doubled.
2. **Arm-F etymology lexical overlap (minor).** "inner life" ↔ "inner" candidates (see ¹). Because
   A must *beat* F, an inflated F only makes the bar **harder** (conservative), but the overlap is
   worth neutralizing or documenting.
3. **Arm-D dictionary lexical overlap (accepted-conservative).** "strength" appears in both the D
   reference and one candidate (see ²). This is inherent to a dictionary-only baseline and, like F,
   raises rather than lowers the bar for A — not a false-positive risk, but note it.
4. **Emotional/abstract candidate density.** The abstract cases lean on affliction/emotion-style
   candidates (the Track C/D0 pattern). Hard negatives are genuinely adjacent (e.g. relief vs
   contentment vs pleasure; irritation vs resentment vs rage), which is good, but the primary set is
   emotion-heavy; the concrete controls (Sample 3) are the counterweight and read as fair.
5. **No easy-context or weak-hard-negative red flags observed.** Contexts do not contain candidate
   wording verbatim; hard negatives are non-trivial. No surface-word leakage risk found.

## 7. Recommendation

**`NEEDS_PACKET_REVISION`** — narrowly.

The bundle is **structurally sound and leak-clean** (108/108 pass, shuffles verified, hidden key
separate, no four-sphere), and the substantive design (hard negatives, fair X, conservative D/F) is
acceptable. The single clear defect is the **doubled "internal constraint" wording** (concern 1),
which a reviewer will flag; concerns 2–3 should at least be documented as accepted-conservative.
Recommend one small revision pass (fix the premise prefix; note/optionally neutralize the F/D
lexical overlap), then re-preview and move to `READY_FOR_APPROVAL_REVIEW`. No blocking issue was
found. Any revision is a separate change; **nothing is changed by this preview.**

## 8. Boundary statement

Dry-run packet preview only. No model call, no scoring, and no Track E result. Smoke pilot remains not approved or run. Track B remains blocked. Structure, not validated meaning.
