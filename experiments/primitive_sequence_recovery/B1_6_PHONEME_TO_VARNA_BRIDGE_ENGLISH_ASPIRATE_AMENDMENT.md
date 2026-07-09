# B1.6 — Phoneme→Varṇa Bridge — English Aspirate Policy Amendment

**Status:** Amendment note (docs + manifest only) to `B1_6_PHONEME_TO_VARNA_BRIDGE_SPEC.md` (`b680063`). Adds an
explicit **language-mode** policy for the Sanskrit aspirated/conjunct varṇa keys and for English `ph`. **No code,
no generation run, no target-scaffold instantiation, no evidence freeze.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`, no `L1_L2_L3_ATTRIBUTE_SIGNAL`. Original B1.4b remains blocked. Track B remains
blocked. Structure, not validated meaning.**

**Readiness label: `B1_6_PHONEME_VARNA_BRIDGE_SPEC_READY_ENGLISH_POLICY_AMENDED`.**

Amends: `B1_6_PHONEME_TO_VARNA_BRIDGE_SPEC.md` (`b680063`). Manifest updated:
`frozen/b1_6_phoneme_to_varna_bridge_manifest.json`.

---

## 0. Why this amendment

The base bridge spec noted that 9 varṇa keys — `kha, gha, cha, jha, ttha, ddha, pha, bha, ksha` — are
**unreachable** because the decomposer does not carry aspiration through the phoneme stream. That is correct as a
*coverage* statement, but it left one thing implicit: for **ordinary English targets**, these Sanskrit aspirated
keys must **not** be treated as if English digraphs could reach them. In particular, English **`ph`** is the
`/f/` sound, **not** Sanskrit **`pha`** (an aspirated labial stop). This amendment makes the English-vs-Sanskrit
handling **explicit** so no English digraph is ever forced into a Sanskrit aspirated varṇa.

## 1. English-mode rule

For **English targets** (decomposer track `A_PRIME_EN`; the default for ordinary English words):

- **`ph` is interpreted as `/f/`** where applicable — consistent with the frozen decomposer, which already maps
  `ph → ['f']`. English `ph` is **never** mapped to Sanskrit `pha`.
- Since **no `fa`/`f` varṇa profile key exists** (§4), `/f/` is recorded as **`UNSUPPORTED_NO_VARNA`** — retained
  in the sequence, excluded from `{VARNA_PROFILE_TABLE}`, reported visibly.
- **No English digraph is forced into a Sanskrit aspirated varṇa.** English `t/th`, `p/ph`, `k`, `c/ch`, `g/gh`,
  `b/bh` etc. resolve only to the **unaspirated / reachable** keys the base bridge already defines (e.g. English
  `th → tha` dental, `t → ta`, `p → pa`, `k → ka`), or to `UNSUPPORTED_NO_VARNA` — never to `pha/kha/gha/…`.

## 2. Sanskrit/transliteration-mode rule

For **Sanskrit or explicit transliteration targets only** (decomposer track `A_PRIME_SA`, or an item explicitly
tagged transliteration-mode), aspirated/conjunct keys may be reached **only** where (a) the selected profile
table actually contains the key and (b) the IAST input carries the distinction:

- `kh → kha`
- `gh → gha`
- `jh → jha`
- retroflex `ṭh` (th-retroflex) `→ ttha`
- retroflex `ḍh` (dh-retroflex) `→ ddha`
- `ph → pha`
- `bh → bha`
- `kṣ` / `ksh` `→ ksha`
- `ch` / `cch` handling **only if** the selected table key is explicitly present and the transliteration carries
  it.

**These rules are NOT applied to ordinary English words.** (Note: reaching them still depends on the frozen
decomposer actually emitting the distinction; the base spec §7 records that some aspirates are split even in
`A_PRIME_SA`. This amendment governs *policy/eligibility by language mode*; it does not modify the decomposer or
claim to recover aspiration the decomposer discards.)

## 3. Ignored / unreachable English keys

For ordinary **English-mode** targets, the Sanskrit aspirated/conjunct keys —

`kha, gha, cha, jha, ttha, ddha, pha, bha, ksha`

— **remain unreachable** and are simply **not used**. A target reaches them **only** when it is explicitly marked
**Sanskrit/transliteration**. English targets neither reach nor require these keys; their aspirated digraphs map
to unaspirated/reachable keys or to `UNSUPPORTED_NO_VARNA`.

## 4. No invented `fa` profile

The selected varṇa profile table (`track_g_varna_polarity_table.json`) contains **no `fa` key** (and no other
`f-` key) — **verified**. **No `fa` profile is invented.** English `/f/` remains **`UNSUPPORTED_NO_VARNA`** (or
no-profile) unless and until a **frozen, authoritative** `fa`/`/f/` profile source already exists — which it does
not. This is consistent with §1 and with the base spec's unsupported policy.

## 5. Manifest update

`frozen/b1_6_phoneme_to_varna_bridge_manifest.json` updated to record:

- **English `ph` policy** — `ph → /f/ → UNSUPPORTED_NO_VARNA`; never `pha`.
- **Sanskrit/transliteration aspirate policy** — aspirated/conjunct keys reachable only in
  sanskrit_transliteration mode, only where the table key exists and the IAST input carries the distinction.
- **`fa` existence** — `fa_in_profile_table: false` (none invented).
- **Updated readiness label** — `B1_6_PHONEME_VARNA_BRIDGE_SPEC_READY_ENGLISH_POLICY_AMENDED`.
- **Language mode** — derived from the decomposer track (`A_PRIME_EN → english_mode`, `A_PRIME_SA →
  sanskrit_transliteration_mode`), overridable by an explicit per-item mode tag, **frozen before target
  selection**.

The base `mapping` table and its `mapping_table_sha256` are **unchanged** — this amendment adds a language-mode
**gate** on the already-unreachable aspirated keys and an explicit English `ph→/f/` statement; it does not alter
any consonant→varṇa entry.

## 6. Readiness label

**`B1_6_PHONEME_VARNA_BRIDGE_SPEC_READY_ENGLISH_POLICY_AMENDED`.**

Missing `fa` is **not** a blocker for the pilot: English `/f/` is simply recorded as `UNSUPPORTED_NO_VARNA`.
Therefore **not** `B1_6_PHONEME_VARNA_BRIDGE_BLOCKED_FA_PROFILE_MISSING`. The language mode is unambiguous
(decomposer track + optional explicit per-item tag), so **not**
`B1_6_PHONEME_VARNA_BRIDGE_BLOCKED_AMBIGUOUS_LANGUAGE_MODE`. The base bridge remains
`..._SPEC_READY` for the decomposition→profile join; this amendment refines its English handling.

## 7. Guardrails

- **No code implementation.** **No generation run.** **No evidence freeze.** **No invented varṇa meanings** (no
  `fa` fabricated). **No semantic-success claim.** **No ontology claim.** No Sanskrit privilege. No rescue of
  B1.4b′. **B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original B1.4b remains blocked. Track B remains blocked.
  **Structure, not validated meaning.**

---

## Final report

- **Files created/modified:** created
  `experiments/primitive_sequence_recovery/B1_6_PHONEME_TO_VARNA_BRIDGE_ENGLISH_ASPIRATE_AMENDMENT.md`; updated
  `experiments/primitive_sequence_recovery/frozen/b1_6_phoneme_to_varna_bridge_manifest.json` (readiness label +
  English-aspirate policy; base mapping table unchanged). The base spec `B1_6_PHONEME_TO_VARNA_BRIDGE_SPEC.md`
  is **not** modified (this amendment governs it by reference).
- **Commit hash:** (recorded on commit below).
- **Does English `ph` now map to `/f/` rather than Sanskrit `pha`?** **Yes** — English `ph → /f/`, recorded
  `UNSUPPORTED_NO_VARNA` (no `fa` key); **never** `pha`.
- **Does `fa` exist in the selected profile table?** **No** — `track_g_varna_polarity_table.json` has no `fa`/
  `f-` key; none invented.
- **Does ordinary English mode ignore the Sanskrit aspirated/conjunct keys?** **Yes** — `kha, gha, cha, jha,
  ttha, ddha, pha, bha, ksha` remain unreachable/unused in English mode; reachable only for items explicitly
  marked Sanskrit/transliteration, and only where the table key exists.
- **No generation was run.**

> B1.6 English aspirate policy amended docs-only. English ph is not Sanskrit pha. No generation run. No evidence
> freeze. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B remains blocked. Structure,
> not validated meaning.
