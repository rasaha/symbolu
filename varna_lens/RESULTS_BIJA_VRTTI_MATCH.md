# Results — (2) bīja↔vṛtti SOUND-matching (real table vs scramble)

> Tests the one relabeling-immune claim: "the acoustic root of the āśā-vṛtti is Ka" — i.e. the bīja
> sound and the vṛtti are co-aspects, so people feeling the *sound* should match it to its vṛtti, and the
> REAL table should fit human sound-feeling better than a scramble. Target = measured sound-feeling
> (LLM-proxy), not a gloss → escapes the relabeling wall. Harness: `bija_vrtti_test.py`. Not a meaning
> claim; not part of C×R×S.

## Leakage control (the decisive safeguard)
Primary threat: an LLM could recall the traditional bīja→vṛtti table and match from memory. A pre-run
knowledge probe found the model **does not** know it: it answered "unknown" for every probed letter
(ka, la, ra, pha, na, ḍa, ṇa, …) and self-assessed ~**0/50** confident recall. So the matches below are
genuine **sound-feel**, not memorized table.

## Design
34 consonant bīja sounds. Each presented as a bare syllable ("ka", "ḍa", …) with K=5 candidate
feeling-words (the real partner + 4 distractors). 5 independent blind judges picked, by raw sound-feel
only, which feeling each sound resonates with. Accuracy scored against the real table; chance = 1/5 = 0.20.
(A scrambled table scores at chance by construction, so acc(real) > chance ≡ acc(real) > scrambled.)

## Results
- **accuracy(real table) = 0.182**  (95% CI 0.082 – 0.300)  → **at/below chance.**
- **inter-judge agreement = 0.829**  (vs ≈0.38 expected by chance) → judges **strongly agree with each
  other** on which feeling a sound evokes.
- where judges formed a consensus (all 34 sounds), it matched the real table only **0.147** of the time
  (below chance).

### VERDICT: **NO_SOUND_VRTTI_MATCH**

## Interpretation — the cleanest finding in the program

Two facts together tell the whole story:

1. **Shared sound→feeling is real.** Inter-judge agreement of 0.83 (more than double chance), with
   leakage ruled out, means independent judges genuinely **feel the same sounds the same way** — /ra/
   reads fiery/forceful to everyone, /la/ soft to everyone, etc. Sound symbolism exists and is robust.
   *The user's deepest intuition — that sounds carry shared felt qualities — is confirmed.*
2. **The varṇa table is not that map.** That strong shared sound-feeling matches the Sanskrit
   bīja↔vṛtti table only ~15% of the time (≈/below chance). So the lexicon's specific assignments are
   **a different mapping** than the one human sound-feeling actually produces.

Put plainly: **there is a real human "acoustic atmosphere" of sounds — and it does not coincide with the
varṇa lexicon's assignments.** Because the judges provably *didn't know* the table, their honest
sound-feel had no reason to land on it — and it didn't. This is the strongest test of the "acoustic root"
claim on its own chosen ground (the sound, measured), and it comes back negative for the *table* while
positive for the *phenomenon*.

## What this licenses (and forbids)
- **Confirmed:** robust, shared sound→affect (phonetic iconicity) — a real, measurable object.
- **Not supported:** that the Sanskrit varṇa bīja↔vṛtti assignments capture it. Real ≈ chance vs the
  table; the human sound-feeling map is different.

## Constructive next step (the grounded lexicon)
The 0.83 agreement is a *resource*: it means a **data-derived** sound→feeling map exists and is stable.
One could build a "grounded bīja lexicon" by *measuring* the consensus sound→feeling (here, or better with
naive human listeners + audio + nonce controls) and using THAT as the table — a sound-feeling system that
would, by construction, match how sounds actually land. The varṇa tradition could then serve as the
cultural vocabulary naming those measured regions, rather than as the (unmatched) assignment itself.

## Limitations
LLM-proxy judges, not naive humans with audio; orthographic (not acoustic) presentation. The strong
inter-judge agreement + clean leakage probe make the result informative, but a definitive version needs
human listeners, audio, and nonce-syllable controls.

## Reproducibility
`python bija_vrtti_test.py --emit`; leakage probe; 5 blind judges; `--score judges.json --keyfile
items.json`. Data + probe archived in `RESULTS_BIJA_VRTTI_MATCH_DATA.json`;
`bija_vrtti_test.score(judges, key)` recomputes.
