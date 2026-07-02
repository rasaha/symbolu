# Track C Failure Audit — is the scramble test too strict, or the representation too lossy? (docs only)

**Deterministic inspection only. No experiment rerun, no new scoring beyond deterministic
lexical inspection, no threshold change, no artifact change, no Stage A change.** `manifest.json`
remains NOT_READY; the runner remains NOT_RUN. This audit does **not** overturn or weaken the
recorded Track C conclusion (no robust signal); it characterizes *why* the failures occur.

## Data source (and an honest limitation)

The Track C run saved only **aggregate** metrics (`track_c_result.json`: MRR/Top1/scramble
delta) — **not** per-word GloVe ranks — and that file is pod-local; the GloVe asset cannot be
re-run here. So a faithful per-word audit of the *GloVe* run is **not possible from saved
outputs**, and fabricating GloVe ranks is forbidden.

Instead this audit uses **per-word ranks under the lexical (Jaccard) realizer** — computed
deterministically here with no asset — as a faithful **proxy**. Justification: GloVe's aggregate
MRR (0.3606) sits barely above lexical (0.3478), so the *failure structure* is representative.
Every per-word number below is **lexical (deterministic), explicitly not GloVe.**

## Deterministic findings (whole corpus)

- **Only 1 of 107 active words has any gloss↔meaning token overlap** (Jaccard self-similarity
  > 0). For **106/107**, the true meaning shares **zero** surface tokens with the composed
  varṇa-gloss sequence → it ties at similarity 0 with its distractors → its rank is decided by
  the **tie-break**, i.e. **near-random**.
- The true-meaning rank distribution is ~uniform across 1–8: `{1:15, 2:12, 3:12, 4:17, 5:11,
  6:15, 7:8, 8:17}` — the signature of chance, consistent with the recorded at-chance MRR.
- **The single "hit" is tautological:** `kāma` (desire) scores 0.125 **only because** the gloss
  for `ka` literally contains the word *"desire"* ("hope / forward-grasping **desire**"). That is
  gloss↔meaning **leakage**, not compositional signal — and it is the *best* case in the corpus.

## §1–2, §6 — Ten concrete weak cases (lexical proxy; all rank 8 = last)

Realized gloss = first sense of each atom's English vṛtti gloss, composed in varṇa order.
"Scrambled similar?" — for a zero-overlap word, permuting the assignment yields *different*
glosses that **still** share ~0 tokens with the (concrete) meaning, so scrambled ≈ real ≈ 0
(this is exactly why the aggregate delta is tiny).

| # | word_id | spelling | meaning | varṇa seq | realized gloss sequence | true rank | top wrong (sim) | scrambled ≈? | class |
|---|---|---|---|---|---|---|---|---|---|
| 1 | w052 | hṛdaya | heart | ha·da·ya | night + peevishness + lack-of-confidence | 8 | lobha/greed (0.0) | yes | domain-mismatch / no-signal |
| 2 | w078 | mṛga | deer | ma·ga | annihilation + effort | 8 | deha/body (0.0) | yes | domain-mismatch / no-signal |
| 3 | w080 | megha | cloud | ma·gha | annihilation + attachment | 8 | dharma/righteousness (0.0) | yes | domain-mismatch / no-signal |
| 4 | w087 | kāṣṭha | wood | ka·ssa·ttha | hope + inertia + repentance | 8 | lobha/greed (0.0) | yes | domain-mismatch / no-signal |
| 5 | w089 | mūla | root | ma·la | annihilation + cruelty | 8 | moha/delusion (0.0) | yes | domain-mismatch / no-signal |
| 6 | w090 | bīja | seed | ba·ja | indifference + ego | 8 | kāla/time (0.0) | yes | domain-mismatch / no-signal |
| 7 | w091 | kṣetra | field | ksha·ta·ra | material-knowledge + inertia + defeatism | 8 | agni/fire (0.0) | yes | domain-mismatch / no-signal |
| 8 | w101 | ratha | chariot | ra·tha | defeatist-annihilation + melancholy | 8 | manas/mind (0.0) | yes | domain-mismatch / no-signal |
| 9 | w104 | madhu | honey | ma·dha | annihilation + craving | 8 | putra/son (0.0) | yes | domain-mismatch / no-signal |
| 10 | w098 | dhanus | bow | dha·na·sa | craving + blind-attachment + escapism | 8 | deha/body (0.0) | yes | domain-mismatch / no-signal |

Common pattern: the vṛtti inventory is a fixed set of ~34 **psychological/affliction concepts**
(hope, greed, fear, cruelty, delusion, craving, annihilation-thought, …). Composing them cannot
plausibly yield **concrete-noun** meanings (deer, honey, chariot, field). The wrong top candidate
also scores 0 — it merely won the tie-break — so this is **not** a distractor artifact; it is an
absence of any recoverable relation.

## §3 — Failure classification (honest, from the data)

- **Semantic-domain mismatch / genuine no-signal (dominant, ~106 words):** affliction-vṛtti
  glosses bear no recoverable relation to (mostly concrete) word meanings; self-sim 0, rank ≈
  chance. This is the main failure mode.
- **English-realization / gloss-leakage artifact (1 word, kāma):** the only "success" is a gloss
  string literally containing the meaning word — an artifact, not composition.
- **Vowel-loss / prefix-loss (3 words, excluded):** the collision pairs (§4) — unrankable by
  construction.
- **Not observed as drivers:** homonym/polysemy (sense_id fixed), distractor-too-easy/hard (top
  wrongs score 0, so ties, not spurious matches), etymology-dominance (untestable at lexical
  level). Vague-gloss overlaps with domain-mismatch for abstractions but is not the concrete-noun
  story.

## §4 — The three collision pairs (deterministic)

| pair | canonical atoms (identical) | dropped by consonant-only |
|---|---|---|
| vidyā (knowledge) / **avidyā** (ignorance) | atom_28·atom_17·atom_25 | initial vowel `a` (a-privative) |
| himsā (violence) / **ahimsā** (nonviolence) | atom_32·atom_24·atom_31 | a-privative `a` |
| nara (man) / **nārī** (woman) | atom_19·atom_26 | vowel length + gender vowel |

(**bold** = excluded.) Effect on the test: the two members of each pair map to the **identical
opaque sequence**, so **no realizer — lexical or semantic — can ever rank them apart**; the
meaning-distinguishing information was deleted at decomposition. Including them would inject
guaranteed-unrankable items; excluding them was correct. But it means the consonant-only test is
**provably blind** to this class of contrasts (see `DROPPED_VOWEL_ANTONYM_PROBE.md`).

## §5 — Is the scramble test too strict, or the representation too lossy?

**Neither strict nor mis-calibrated — the scramble test is correct.** It asks: does the *real*
varṇa→gloss assignment beat *random* assignments of the same glosses? For 106/107 words the real
assignment produces gloss tokens that share **zero** surface (and, per the near-flat GloVe
result, negligible semantic) relation to the meaning — so real and scrambled both sit at chance
and the delta is ~0. **The test is not being harsh; there is little to detect.** A pass would
require the real assignment to genuinely help, which it essentially does not.

**The representation is lossy, but in two distinct ways — and the smaller one is the vowel gap:**
1. **Vowel/prefix loss (narrow):** provably fatal for the 3 collision pairs. A vowel-aware
   ontology fixes exactly these.
2. **Semantic-domain gap (dominant):** the vṛtti inventory is psychological/affliction concepts;
   the corpus is largely concrete nouns. Composing afflictions into "honey" or "chariot" is not
   expected to work **regardless of vowels**. Vowel-awareness does **not** address this.

**What a fairer Version 2 test would need:** (a) a **vowel-aware / prefix-aware** representation
(fixes the 3 collisions, ~3% of the corpus); **and, more importantly,** (b) a **domain-matched
corpus** — restricting to abstract/psychological/emotional words where the vṛtti glosses could
plausibly compose — or an explicit acknowledgement that concrete nouns are out of the theory's
claimed domain; and (c) a genuine **semantic** scorer with the full control battery (scramble,
equal-length text, etymology-incremental), not lexical overlap. (a) alone is necessary but far
from sufficient.

## §7 — Final conclusion

**Track C is not overturned — it is reinforced and explained.** The recorded no-robust-signal
result is corroborated at the per-word level: 106/107 words carry zero lexical signal, the lone
exception is tautological leakage, and ranks are chance. The dominant failure is a
**semantic-domain mismatch** (affliction-vṛttis vs concrete nouns), **not** primarily vowel-loss.

Therefore: a **vowel-aware / prefix-aware Version 2 is justified only for the narrow collision
class** (~3% of the corpus) and would **not** address the dominant failure. A genuinely fairer
Version 2 would need vowel-awareness **plus** a domain-matched corpus **plus** a controlled
semantic scorer — i.e. it is a **new hypothesis with a new pre-registration**
(`PREREG_TRACK_D_INCREMENTAL_UTILITY.md` / a vowel-aware ontology), not a tweak that would
rescue the consonant-only result. Nothing here supports Symbol-U or `ONTOLOGICAL_SIGNAL`, and the
Version 1 negative stands.

> structure, not validated meaning.
