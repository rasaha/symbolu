# DOCS_ONLY — EXPERIMENTAL VOWEL POSITIONAL POLARITY — MECHANICALLY VALIDATED — NOT SEMANTIC EVIDENCE

*Docs-only memo. No files beyond this note, no commit of results, no code change, no model, no generation, no scoring, no result change.*

Provenance: implementation commit `28d2f1a` (`tools(varna): add experimental vowel positional polarity`).

---

## 1. Summary

An **opt-in experimental variant** was added to the L1/L2 harness so a **word-initial vowel** can take a positional binding role instead of the default field role. It is enabled only via `--vowel-mode positional_polarity`; the default (`field_only`) is unchanged and byte-identical. A no-model structural comparison over five antonym/negation pairs confirmed the variant changes **only phonemic unit index 0** of vowel-initial words, leaves consonant-initial controls identical, and does **not** alter Layer 2 synthesis. This is a **mechanical/data-fidelity** result — it demonstrates correct reading of lexicon fields and correct mode-switching, and **nothing about semantic truth**.

## 2. What changed in implementation

- `profile(word, vowel_mode="field_only")` — new defaulted parameter. In `positional_polarity`, a vowel at phonemic index 0 becomes role `VOWEL_SEED`, pole `worldly(binding)`, term = vowel `binding_state` **read directly from `lexicon_authoritative.json`**. Every non-initial vowel stays `FIELD` / `liberating_state`. Consonants are untouched. A missing pole is marked `MISSING` (never invented).
- `render(..., vowel_mode="field_only")` — threads the mode; appends the experimental label **only** when `positional_polarity` is active.
- CLI flag `--vowel-mode field_only|positional_polarity`, default `field_only`.
- Constants `VOWEL_MODES` and `VOWEL_POSITIONAL_LABEL`.
- `synthesize()` — **unchanged** (signature and logic). Layer 2 does not consume `VOWEL_SEED`.
- New hermetic test module `test_vowel_positional_polarity.py`. **No other file was modified** (lexicon, L2 bridge, L3, L4, L5, and existing tests all untouched).

## 3. Default behavior preserved

- Default is `field_only`; no argument change is required of any caller.
- All existing callers (`render`, L3 `render_layer3`, L4 `render_layer4`, L5 `render_demo`) use the default → **byte-identical** output.
- In `field_only`: every vowel is `FIELD`, term = `liberating_state`, **no** annotation line, **no** `VOWEL_SEED`.
- `love` Layer 2 synthesis remains byte-identical: `separative harshness moves toward compassion/gentleness, and order/dharmic relation is the resolving principle`.
- All five pre-existing suites pass **unmodified**, serving as the default-preservation regression gate.

## 4. Experimental mode behavior

In `positional_polarity`:
- **Word-initial vowel (index 0 only):** `FIELD` → `VOWEL_SEED`; `active_essence(liberating)` → `worldly(binding)`; term switches from the vowel's `liberating_state` to its `binding_state`, both read from the lexicon.
- **Non-initial vowels:** remain `FIELD` / `liberating_state`.
- **Consonants:** unchanged (`ONSET_SEED` binding / `TRANSFORMER` liberating / `INTERNAL_UNRESOLVED`).
- **Layer 2 synthesis:** unchanged (VOWEL_SEED is not fed to `synthesize()`).
- **Explicitly not implemented:** later-vowel-as-transformer, arbitrary per-vowel alternation, spelling/roman fallback, any semantic inference, any model interpretation, any scoring.

## 5. Structural comparison results

No-model, no result files. Only role/pole/term and L2-synthesis change are reported.

| Pair | Word | Source | Initial unit | idx0 change (field_only → positional) | L2 changed? |
|---|---|---|---|---|---|
| Alakshmi / Lakshmi | Alakshmi | fixture | V | FIELD→**VOWEL_SEED**, liberating→**binding**, `'Birth of cognition / raw potential'`→`'restless starting without sustaining'` | No |
| | Lakshmi | fixture | C | NONE | No |
| amoral / moral | amoral | natural | V | FIELD→**VOWEL_SEED**, liberating→**binding**, `'Practical thought, benefit'`→`'overthinking, nitpicking'` (`e`) | No |
| | moral | natural | C | NONE | No |
| asymmetry / symmetry | asymmetry | natural | V | FIELD→**VOWEL_SEED**, liberating→**binding** (`e`) | No |
| | symmetry | natural | C | NONE | No |
| anhydrous / hydrous | anhydrous | fixture | V | FIELD→**VOWEL_SEED**, liberating→**binding** (`a`) | No |
| | hydrous | natural | C | NONE | No |
| atheist / theist | atheist | natural | V | FIELD→**VOWEL_SEED**, liberating→**binding** (`e`) | No |
| | theist | fixture | C | NONE | No |

**Observed = expected:** default unchanged; positional marks only the word-initial vowel as `VOWEL_SEED`; later vowels stay FIELD; consonant-initial controls identical; L2 synthesis unchanged across all examples.

## 6. Natural G2P vs fixture caveat

- **Natural G2P (cmudict):** `amoral/moral`, `asymmetry/symmetry`, `hydrous`, `atheist`.
- **Fixture-based (not in cmudict, hermetic phoneme fixtures with lexicon-valid keys):** `Alakshmi`, `Lakshmi`, `anhydrous`, `theist` — **labeled fixture-based, not natural-run evidence**.
- **Important G2P fact:** English written `a-` forms (`amoral`, `asymmetry`, `atheist`) are mapped by cmudict to ARPAbet **`EY`**, which the engine maps to varṇa **`e`** — **not** the Sanskrit short `a`. So the natural-run term shift shown is `e`'s pole pair, not the Sanskrit privative-`a`. The `Alakshmi` fixture is conceptually cleaner for a Sanskrit `a-` prefix but is **fixture-based**, so it carries no natural-run weight. No claim is made that the `a-`/`e` mapping reflects the words' meaning.

## 7. What this validates

- Vowel `binding_state` and `liberating_state` are **read correctly** from `lexicon_authoritative.json`.
- The `field_only` ↔ `positional_polarity` **mode switch works** and is opt-in.
- **Default behavior is preserved** byte-for-byte (regression suites green).
- Changes are **localized** to phonemic index 0 of vowel-initial words; consonants and Layer 2 are untouched.
- No forbidden artifact changed; no model, no generation, no scoring, no result files.

## 8. What this does not validate

- That vowel positional polarity is **semantically true**.
- Any **generation utility** or output-quality improvement.
- **Ontology** or metaphysical claims about phonemes.
- **Sanskrit privilege** (the natural runs actually key off English `EY`→`e`, not Sanskrit `a`).
- **Track B** support or **Track G** rescue.
- Any claim that the `a-` prefix "means" negation in the model.

## 9. Recommended use

- Treat `positional_polarity` as an **inspection-only experimental toggle**, off by default.
- Keep `field_only` as the default for all L2/L3/L4/L5 paths.
- If used in any future study, it must go through a **separate, pre-registered** protocol with the full control stack; the fixture examples must not be presented as natural evidence, and the `EY`→`e` G2P behavior must be disclosed.
- Do **not** wire `VOWEL_SEED` into Layer 2 synthesis without separate explicit approval.

## 10. Guardrails

- No ontology validation.
- No Sanskrit privilege.
- No semantic-truth claim.
- No Track G rescue.
- No Track B unblock.
- Track G negative preserved: `1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`.
- Track B remains **BLOCKED**.
- Prior PSE negatives remain valid.
- Track F prior remains `CORRECTNESS_DEGRADED`.
- Frozen manifest remains `NOT_READY`.

## 11. Final status line

`STATUS: EXPERIMENTAL_VOWEL_POSITIONAL_POLARITY_IMPLEMENTED_AND_MECHANICALLY_VALIDATED — NOT_SEMANTIC_EVIDENCE — NOT_DEFAULT`

---

**Structure, not validated meaning.**
