# B1 — D1–D4 Metadata-Only Re-Freeze Record (docs/data)

**Result: `D1_D4_METADATA_REFREEZE_COMPLETE`.** The four contradictions D1–D4 are applied as a **metadata-only**
change, delivered as a **superseding versioned table** (`v3.1`) rather than an in-place edit — because
`varna_polarity_table_v3.json` is hash-pinned by three completed English-run evidence-freeze declarations, and
in-place editing would invalidate prior-experiment provenance (out of scope). **No pole content changed.**

## Provenance chain

| item | value |
|---|---|
| authoritative decision source | `varna_table_reconciliation/d1_d4_resolution.json` (reconciliation commit **`26d680c9`**) |
| method | versioned supersession — v3.1 for native use; v3.json byte-identical for the completed English runs |
| change class | **METADATA_ONLY** |
| new table | `frozen/varna_polarity_table_v3_1_metadata_refreeze.json` |

## Hash comparison

| artifact | sha256 | status |
|---|---|---|
| parser `sanskrit_stage1_parser.py` | `d885391f…03721947` | **UNCHANGED** |
| `varna_polarity_table_v3.json` | `d3ff8efd…8494d0b3` | **UNCHANGED** (byte-identical; run01 pins intact) |
| pole-content hash (both v3 and v3.1, reachability fields excluded) | `e59acad3…fd965837` | **IDENTICAL** |
| `varna_polarity_table_v3_1_metadata_refreeze.json` (new) | `9ac712a6…5bd64b27` | new artifact |

## Exact fields / text changed (v3 → v3.1)

- **`important_caveats[1]` (D1, pa):** rewritten from "PARTIALLY INVERTS the source-attested pole" → resolved-state
  note (pa = ghṛṇā = BINDING; option-A inversion superseded; pa entry authoritative).
- **`important_caveats[3]` (D2, ṭha):** rewritten from "…is unresolved…" → resolved-state note (anutāpa = pole axis;
  night/moon = associations; per `varnas.ttha.classical_discrepancy = 'RESOLVED'`).
- **`important_caveats[4]–[8]` (D3/D4):** prefixed `DEPRECATED ENGLISH-G2P BRIDGE ONLY:`; new `[10]` records the
  D3/D4 resolution (native parser reaches all consonants; थ → tha is correct).
- **per-varṇa reachability:** added `english_g2p_bridge_reachable` (= old `practically_reachable` value) and
  `native_parser_reachable` (true for all consonants except `ksha`, which decomposes to k+ṣ); `practically_reachable`
  retained as a **deprecated alias**.
- **top-level:** added `reachability_model` (native vs deprecated-bridge scopes) and `metadata_refreeze` provenance
  block; `status` → `ACTIVE_APPLIED_METADATA_REFREEZE_v3_1`.

**Unchanged:** every binding pole, every liberating pole, every source citation
(`source_note`/`source_quote_verified`/`provenance`/`attested_vs_authored`), `classical_discrepancy`,
`primary_text_scope`, `classical_side_attested`. Verified byte-identical per varṇa (`test_d1_d4_metadata_refreeze.py`).

## Reachability model (now explicit)

- `native_parser_reachable` — authoritative for native-Sanskrit inventory; true for all 33 producing consonants.
- `english_g2p_bridge_reachable` — historical deprecated-bridge coverage (19/34); provenance only.
- `practically_reachable` — **DEPRECATED** alias; native consumers must not use it.

## Derived-artifact regeneration

- **Provenance register** (`b1_varna_provenance_register.py` → `varna_provenance_register/*`): now reads v3.1 and
  `native_parser_reachable`. D1–D4 marked `RESOLVED_BY_METADATA_REFREEZE_v3_1`; **0 unresolved contradictions**;
  active-status counts `ACTIVE=33 / INACTIVE=1 (ksha)`. **Pole-provenance counts unchanged**
  (`PRIMARY_ATTESTED 26 / AUTHORED_PROVISIONAL 27 / INFERRED 13 / SECONDARY_ATTESTED 2`). Readiness verdict changed
  `BLOCKED_BY_SOURCE_CONTRADICTIONS` → **`BLOCKED_BY_PROVENANCE_GAPS`**.
- **Integration audit** (`b1_stage1_mapping_integration_audit.py` → `stage1_mapping_integration/*`): active status now
  from `native_parser_reachable`; consonants `active=33, contradictory=0`; aspirates `10/10 active`; D3/D4 marked
  `RESOLVED`. Verdict unchanged (`BLOCKED_BY_MISSING_VOWEL_AND_MARKER_MAPPINGS`) — the missing inventory is the
  dominant remaining blocker.

## Provenance status changes

- D1, D2 → resolved (doc-vs-doc staleness; entries were already authoritative).
- D3, D4 → resolved/dissolved (English-bridge artifacts scoped to the deprecated bridge).
- D5 (SIBILANT_SWAP), D6 (BACK_FIT) → **unchanged** open provenance hazards (out of D1–D4 scope).
- No pole provenance class changed.

## Validation

`test_d1_d4_metadata_refreeze.py` (7) + provenance-register (6) + integration-audit (9) + Gate G0 (10) + parser
(122) + parser-corrective (222) = **all pass**. No test weakened.

## Updated blocker status

- **Cleared:** `BLOCKED_BY_SOURCE_CONTRADICTIONS` (D1–D4).
- **Remaining (dominant):** the wholly **MISSING vowel / anusvāra / visarga / candrabindu inventory**
  (`BLOCKED_BY_MISSING_VOWEL_AND_MARKER_MAPPINGS` / `BLOCKED_BY_PROVENANCE_GAPS`).
- **Remaining (secondary):** authored-provisional liberating poles, `ha` BACK_FIT, `sha`/`ssa` SIBILANT_SWAP.

**Single recommended next action:** the **missing-inventory architecture decision** for vowels, anusvāra, visarga,
and candrabindu — how each category obtains author-or-attest provenance under the established
blinding/pre-registration discipline. (Not semantic testing, not composition pre-registration.)
