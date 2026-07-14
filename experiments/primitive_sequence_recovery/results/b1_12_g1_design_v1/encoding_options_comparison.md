# B1.12 Gate G1 — Evaluator-Facing Encoding Options (A–E)

`DIAGNOSTIC_ONLY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. Compares five evaluator-facing encodings for the
G0-selected six against the central G1 requirement: *preserve and communicate ordered composition while
preventing direct reconstruction of the Sanskrit word and keeping the order-scrambled (B) and unordered-inventory
(D) controls meaningfully distinguishable.* Worked example uses `W20 jñāna` (opaque true order
`U09 U22 U29 U14 U25`).

| option | example render (A) | preserves order | preserves repeats | leakage protection | evaluator can use it without a key | verdict for B1.12 |
|---|---|---|---|---|---|---|
| **A — pure opaque ordered IDs** | `U09 U22 U29 U14 U25` | ✔ exact | ✔ | ✔ strong (no IAST/Devanāgarī) | only for a **structural** task (no semantic recovery) | **basis of primary** |
| **B — keyed opaque identities** (legend → parser-native class: C/V/marker, aspiration, akṣara role) | `C U09 · V U22 · …` | ✔ | ✔ | ⚠ class legend narrows candidates; risks phonetic reconstruction | partially — classes leak toward IAST | rejected as primary (leakage toward reconstruction) |
| **C — semantic ordered varṇa glosses** | `<gloss09> <gloss22> …` | ✔ | ✔ | ✗ low — glosses are near-IAST-identifying; reintroduces B1.10 prose | yes, but tests gloss quality | secondary-only, high-risk (B1.10 confound) |
| **D — position-tagged inventory** | `p1:U09 p2:U22 p3:U29 p4:U14 p5:U25` | ✔ | ✔ | ✔ strong | same as A, plus explicit positions | **adopted as the formatting of the primary** |
| **E — paired relation (ordered bigrams)** | `U09>U22 U22>U29 U29>U14 U14>U25` | ✔ (as adjacency) | ✔ | ✔ strong, but adjacency set is a stronger fingerprint | emphasizes local order | useful **secondary** order-emphasis arm |

## Why the primary is Option A content in Option D formatting (position-tagged opaque IDs)

- **Leakage:** opaque IDs (`U\d\d`) carry no IAST/Devanāgarī and no semantic gloss; the leakage audit confirms no
  linguistic characters, no word-transliteration substring, and — critically — that **content-masked renders of
  A, B, D are byte-identical** (`p1:• p2:• …`), so arm identity is carried *only* by the ordered content, never
  by a template/length artifact.
- **Order availability:** position tags make order explicit and uniform across arms without adding
  discriminative formatting. A, B, D of one word share the identical token multiset, length, and tag skeleton,
  so **only order varies** — inventory and length carry zero within-trial signal.
- **Option B rejected as primary:** a parser-native class legend (consonant/vowel/aspiration/akṣara-role) is
  interpretable but *narrows the word* — class+position is a partial phonetic reconstruction path, weakening the
  no-reconstruction guarantee. It may return later as a controlled secondary probe, never the primary.
- **Option C rejected as primary:** semantic glosses re-import a varṇa→meaning mapping and collapse toward the
  B1.10 prose-packet regime (tests gloss quality / progression narratives, not order). Permitted only as an
  explicitly-labelled secondary arm that preserves exact order and repetition.
- **Option E kept as secondary:** ordered-bigram rendering isolates local adjacency but its adjacency **set** is
  a stronger cross-word fingerprint; it is a useful order-emphasis complement, not the primary.

## Task-model choice (Models 1–4)

- **Model 2 (candidate-relative cross-word match) — rejected primary.** The six words have **distinct
  inventories** and a **unique first opaque unit each**, so a cross-word candidate task is solvable by inventory
  / first-unit alone → it would test **inventory recognition, not order**.
- **Model 4 (semantic composition judgment) — rejected primary.** Depends on glosses (Option C) → B1.10 confound.
- **Model 1 (learned-key identification) — deferred.** Needs a training/reference phase not yet designed.
- **Model 3 (same-word order discrimination) — SELECTED primary.** The evaluator is *not* asked to recover a word
  or meaning; it makes a **structural order judgment** over arms of a single hidden word (true order vs its own
  scramble vs its own unordered inventory), where inventory and length are held identical. Any above-chance
  performance must use **order**. This directly tests the *necessary* condition for H2 (order is preserved and
  recoverable) while remaining leakage-safe — at the cost of not testing semantic word-identity, which the
  narrowed claim states honestly.
