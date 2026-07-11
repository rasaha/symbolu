# B1 — Varṇa-Table Contradiction Reconciliation D1–D4 (docs/data-only)

**Status: all four resolved on the table's own evidence. `changes_any_pole_content = false`. NOT applied to the
frozen table — application is a separate, explicitly-approved re-freeze.** This record clears the provenance
register's `BLOCKED_BY_SOURCE_CONTRADICTIONS` verdict at the *decision* level; the frozen
`varna_polarity_table_v3.json` is unchanged. Machine-readable adjudication: `varna_table_reconciliation/d1_d4_resolution.json`.

**Guardrails:** no pole meaning changed, no opposite authored, no polarity selected. Only stale **metadata**
(caveats, bridge-scoped reachability) is adjudicated. Structure, not validated meaning. No `GENUTILITY_*`; no
`ONTOLOGICAL_SIGNAL`. Track-G and all prior verdicts unchanged.

---

## Headline

The four contradictions split cleanly into two kinds, and **none requires touching a single pole or meaning**:

- **D1, D2 — doc-vs-doc staleness.** The table's *newer per-varṇa entries already adjudicate these*; only two
  stale `important_caveats` lines still describe the superseded state. Fix = update two caveats.
- **D3, D4 — deprecated-English-bridge artifacts.** They **dissolve** under the frozen native Stage-1 parser,
  because the `practically_reachable` field and caveats [4]–[8] describe the old English-G2P bridge, not the
  native Devanāgarī input path. Fix = scope that metadata to the bridge it actually describes.

## D1 — `pa` inversion (DOC_VS_DOC → resolved: entry wins)

- **Stale:** `important_caveats[1]` — *"pa's operator reading PARTIALLY INVERTS the source-attested pole…"*
- **Authoritative:** `varnas.pa.attested_vs_authored` — *"v3 OPTION B: pa = ghṛṇā (hatred) = BINDING … v3 follows
  the attested assignment … **SUPERSEDES the earlier option-A inversion … no inversion flag remains**."*
- **Adjudication:** the entry explicitly supersedes the inversion and aligns `pa` with every other ripu/pāsha
  (hatred = binding). The caveat describes the abandoned option-A state.
- **Fix:** rewrite `important_caveats[1]` to the resolved state ("pa = ghṛṇā = BINDING; option-A inversion
  superseded; resolved"). No pole text changes.

## D2 — `ṭha` night/moon vs repentance (DOC_VS_DOC → resolved: entry wins)

- **Stale:** `important_caveats[3]` — *"ṭha (ttha) … is **unresolved** — see classical_discrepancy."*
- **Authoritative:** `varnas.ttha.classical_discrepancy` — *"**RESOLVED** (see ledger): … Night/moon are ṭha's
  ASSOCIATIONS; anutāpa is its pole axis — associations vs pole, not a contradiction."*
- **Adjudication:** the very field the caveat points to now says **RESOLVED**. The caveat's "unresolved" pointer is
  stale and self-contradicts its target.
- **Fix:** rewrite `important_caveats[3]` to the resolved state (anutāpa = pole axis; night/moon = associations).
  No pole text changes.

## D3 — `tta`/`dda` reachability (CODE_VS_TABLE → dissolves under native parser)

- **English-bridge-scoped:** `important_caveats[5]` — *"fed only by phonemes the **English G2P** never emits …
  PRACTICALLY UNREACHABLE. Real **English** coverage is ~19 of 34."* `[6]` — *"the G2P PRE-SPLITS the cluster … the
  retroflex ḍa/ṭa are never produced … a **G2P change**, not retrofitted here."*
- **Native-parser fact:** the frozen Stage-1 parser emits `ṭ` (ट) and `ḍ` (ड) directly (e.g. `koṭi`; see
  `stage1_mapping_integration/word_resolution.json`).
- **Adjudication:** no genuine conflict once scope is explicit. `practically_reachable` and caveats [4]–[6]
  describe the **deprecated English-G2P bridge**; under the native parser every consonant grapheme is reachable.
  This is a scope-labelling defect, not a pole/identity error.
- **Fix:** rename `practically_reachable` → `english_bridge_reachable` (value unchanged); add
  `native_parser_reachable = true` for all 34 consonants; prefix caveats [4]–[6] with *"DEPRECATED ENGLISH-G2P
  BRIDGE ONLY:"*. Native-parser reachability supersedes the English-bridge flag as the input authority. No pole
  text changes.

## D4 — `th` routing (CODE_VS_DOC → dissolves under native parser)

- **English-bridge-scoped:** `important_caveats[7]` — *"the English 'th' grapheme is the dental FRICATIVES /θ/,/ð/
  … the bridge maps 'th' → tha … injects a spurious melancholy varṇa … a MIS-mapping."*
- **Native-parser fact:** `varnas.tha` operator note — *"थ = aspirated dental stop, **NOT** the English /θ/,/ð/
  fricatives."* The native parser maps थ → tha correctly and never consumes an English "th".
- **Adjudication:** the mis-mapping caveat is about the deprecated English bridge (and its later `thfix` th→ta
  remap). Under native Devanāgarī input, थ → tha is the correct, non-spurious mapping. The conflict dissolves once
  the caveat is scoped to the deprecated bridge.
- **Fix:** prefix caveats [7]–[8] with *"DEPRECATED ENGLISH-G2P BRIDGE ONLY:"* and note that under the native
  Stage-1 parser (frozen `a1988394`) थ → tha is correct. No pole text changes.

## What this does and does not clear

- **Clears:** the four cross-artifact contradictions (D1–D4) at the decision level → the register's
  `BLOCKED_BY_SOURCE_CONTRADICTIONS` primary blocker is resolvable with **metadata-only** edits and **zero** meaning
  changes.
- **Does NOT clear (out of scope here, unchanged):** the register's secondary blockers — 21/34 liberating poles
  `AUTHORED_PROVISIONAL`, `ha` `BACK_FIT`, `sha`/`ssa` `SIBILANT_SWAP` provenance hazards — and the entirely
  **MISSING** vowel / anusvāra / visarga / candrabindu inventory (the integration audit's
  `BLOCKED_BY_MISSING_VOWEL_AND_MARKER_MAPPINGS`).

## Application (gated, not done here)

Applying the four `exact_change_spec` items means editing **metadata only** in the frozen table
(`important_caveats` [1],[3],[4]–[8] and the reachability field), then re-running the wired tests and re-issuing the
provenance register. That is a separate, explicitly-approved **re-freeze** step. Until then the frozen table is
byte-unchanged.

**Recommended next step:** approve the metadata-only re-freeze that applies D1–D4, then proceed to the vowel /
anusvāra / visarga / candrabindu **inventory decision** (the remaining blocker) on the now-stable base.
