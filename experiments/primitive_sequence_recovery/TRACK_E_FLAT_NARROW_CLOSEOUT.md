# Track E-flat (Narrow) — Closeout Memo

**Closeout memo only. Nothing run, scored, or changed.** No experiment, no LLM/scorer call, no
network. `frozen/manifest.json` remains NOT_READY; the base smoke manifest stays `run_enabled:false`
/ `NOT_APPROVED`; psr runner NOT_RUN; Stage A untouched; four-sphere JSON parked/not integrated;
**Track B remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege. This memo does not
reinterpret the negative as positive (see §8).

## 1. Scope of closeout

This closes **only the narrow Track E flat-boundary experiment**:

- the **flat boundary representation** (single vṛtti-gloss composition per word),
- arms **A / B / X / F / D / I**,
- the **12-case smoke pilot** and its one-shot revised-smoke plan.

It does **not** close: the four-sphere representation, a Track E-FS variant, Track F, or Symbol-U as
a broader architecture (see §6). It closes one narrow hypothesis-instance, not the program.

## 2. Final decision

- **Do not scale the current Track E-flat design to a full pilot.**
- **Do not claim `BOUNDARY_CONSTRAINT_SIGNAL`.**
- The result **remains `CONTEXT_ONLY_EXPLAINS`.**

The narrow flat-boundary path is **closed** on this evidence.

## 3. Evidence summary

From the committed `track_e_smoke_result.json` (RunPod run; scorer `mistralai/Mistral-7B-Instruct
-v0.3`, temp 0, 108 packets):

| Metric | Value |
|---|---|
| primary label | **`CONTEXT_ONLY_EXPLAINS`** |
| X (context-only) MRR | **0.9583** |
| A (real boundary) MRR | **0.7917** |
| `A_vs_X` (primary falsifier) | **−0.1667** |
| `A_vs_B` | −0.0139 |
| `A_vs_F` | −0.0556 |
| `A_vs_I` | −0.0833 |
| `A_vs_D` | +0.2681 |
| cases scored | 12 |
| dropped cases | 0 |
| malformed rate | 0.0093 |
| contamination | none |

The real boundary is worse than context-only and loses to scrambled (B), etymology (F), and Barnum
(I); it beats only the dictionary-only floor (D).

## 4. Diagnostic mechanism

- **Context ceiling:** context-only (X) ranked the correct candidate **#1 in 11/12 cases**
  (MRR 0.958), leaving almost no headroom for a boundary to add value.
- **Boundary helped no case cleanly:** there is **no case** where A beats X, B, F, D, and I together
  (A's one near-win, e000, is a tie with scramble).
- **Scramble-equivalent:** B ≥ A in **11/12 cases** (`A_vs_B ≈ 0`) — the specific varṇa→gloss
  mapping added nothing over a scrambled mapping of the same glosses.
- **Concrete distraction:** on the concrete controls the real boundary ranked the correct meaning
  6 / 3 / 2 (vs X = 1) — the affliction-vṛtti composition acted as a domain-mismatched distractor,
  not a constraint.
- **Beating D is insufficient:** `A_vs_D = +0.268` only shows boundary+context beats a context-free
  dictionary lookup — expected and trivial. Track E's **primary falsifier is `A_vs_X`**, which A
  fails; beating an intentionally weak baseline is not evidence of a boundary constraint.

## 5. Decision about the revised smoke

- A **revised harder-context smoke plan exists** (`TRACK_E_FLAT_REVISED_SMOKE_PLAN.md`) to test the
  context-ceiling confound.
- It is **not run.**
- It is **now parked, not active** — this closeout supersedes it as the current state.
- **Reopening it requires explicit new approval.**
- If ever reopened, its **one-rerun stop rule remains binding** (exactly one rerun; stop Track
  E-flat if A fails to beat X, or B, or I; no further tuning).

## 6. What remains open

This closeout does **not** close, and takes no position on:

- **Track F** (inference-steering / non-recovery uses),
- a possible **four-sphere Track E-FS** variant (separate prereg/config required),
- **non-semantic architecture / infrastructure** applications of the framework,
- **Symbol-U as a broader symbolic-control framework.**

Each of these is a distinct investigation to be proposed on its own merits.

## 7. What remains blocked

- **Track B remains blocked** (the confirmatory, non-circular path is unreachable in this
  environment; unchanged by this result).
- **No ontological claim.**
- **No Sanskrit-privilege claim.**
- **No semantic-validation claim** of any kind.

## 8. No-rescue rule

- This result **cannot be reinterpreted as positive**, a `BOUNDARY_CONSTRAINT_SIGNAL`, or support
  for Symbol-U.
- Any future variant (revised smoke, Track E-FS, four-sphere, etc.) requires its **own separate
  pre-registration and config**, authored before looking at more data.
- There is **no post-hoc rescue** of Track E-flat: this closeout records a clean negative and does
  not soften Track C, D0, or the Track B block.

## 9. Investor / research-safe wording

> We tested a narrow flat-boundary version of the varṇa candidate-selection hypothesis. The smoke
> test did not support incremental utility: context-only outperformed the boundary arm, and the real
> boundary did not beat scrambled or Barnum controls. We therefore closed this narrow path and are
> not using it as validation.

## 10. Boundary statement

Track E-flat narrow experiment is closed. Result: CONTEXT_ONLY_EXPLAINS. Track B remains blocked. Structure, not validated meaning.
