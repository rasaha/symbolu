# Manifest Note — Primitive-Sequence Recovery (Step C.6)

**Status:** Validation/freeze only. Records `frozen/manifest.json`, which is **frozen but
truthfully declares `status = NOT_READY`**. No runner execution (beyond confirming
NOT_RUN), no scoring, no embeddings, no network/LLM/API, no model download, no concept
resolver, no Stage A change, no pre-registration change. `READY` was **not** forced.

## What the manifest does

The manifest now **tracks the sha256 of every currently frozen artifact**, so the input
bundle is pinned and tamper-evident:

| manifest field | artifact |
|---|---|
| `assignment_hash` | `assignment.json` |
| `realization_hashes` | `realization_en_gloss.json`, `realization_sa_term.json`, `realization_concept_id.json` (keyed by `realization_id`) |
| `word_hash` | `word_list.json` |
| `meaning_hash` | `meaning_reference.json` |
| `distractor_hash` | `distractors.json` |
| `realizer_hash` | `realizer.json` |
| `scramble_seed_hash` | `run_params.json` (seeds / thresholds) |
| `design_doc_sha256` | `varna_lens/PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md` |
| `independence_basis` | reason for every realization pair (3 pairs) |
| `status` | **`NOT_READY`** |

`scramble_seed_hash` is the run_params hash (the field the gate verifies for the
seeds/thresholds artifact); there is no separate `run_params_hash` in the schema.

## Readiness result (mechanically confirmed, no execution)

`check_readiness(frozen/)` returns:

- `status: NOT_READY`
- `hashes_ok: true` — every tracked hash matches the on-disk file
- `schema_ok: true` — all artifacts + the manifest validate
- `references_ok: true` — full cross-file referential integrity (atom coverage, meanings
  cover all realizations, distractor candidates resolve)
- `realization_count: 3`
- `realization_independence_ok: true` — independence declared for all 3 pairs

So the **inputs are frozen, well-formed, and mutually consistent** — and the bundle is still
NOT_READY. That is the point: a green input bundle says nothing about whether the varṇa
assignment carries signal.

## Why NOT_READY is intentional (the remaining blockers)

The gate reports these blockers, all of which are true right now:

1. `realizer status is not IMPLEMENTED`
2. `realizer execution_allowed is not true`
3. `realizer implementation_present is not true`
4. `realizer model_asset missing (no implicit model permitted)`
5. `realizer model_sha256 missing (asset must be pinned)`
6. `concept resolver not implemented (required by concept realization)`
7. `run_params run_enabled is not true`
8. `manifest.status is not READY`

None of these are input-quality problems; they all say the **execution layer does not exist
yet**. Forcing `status = READY` would be a false declaration — the manifest states the truth.

## What READY will require (a separate, approved step)

READY must be earned by a **separately approved implementation**, not by editing this
manifest. Concretely, a future step must:

- implement the offline, deterministic realizer and **pin a specific model asset** by hash
  (`model_asset` + `model_sha256` non-null), flipping `status → IMPLEMENTED`,
  `implementation_present → true`, `execution_allowed → true`;
- implement the **concept resolver** for the `concept_id` realization
  (`concept_resolver` non-null, `concept_resolver_status → IMPLEMENTED`);
- set `run_enabled → true` in `run_params.json`;
- re-freeze (new hashes) and only then set the manifest `status → READY`.

Per the immutability rule (`SCHEMA_SPECIFICATION.md` §Versioning), that revision should be a
**new manifest** (e.g. `manifest_v2.json`) rather than an in-place edit, so this NOT_READY
record is preserved.

## Minimal gate correction (and why)

To make the NOT_READY reasons **complete and honest**, one minimal check was added to
`check_readiness`: a realization whose `language == "concept"` (or `meaning_encoder.kind ∈
{synset_id, qid}`) now requires an implemented concept resolver, else it is a NOT_READY
blocker (reason 6 above). Without it, the manifest would silently omit the concept-resolver
gap even though a concept realization is present. This changes no artifact and cannot enable
execution; it only makes the gate report one more true blocker. Covered by a new gate test
(`test_concept_resolver_missing_blocks`); the fully-valid fixture, which ships an implemented
resolver, still reaches READY.

> structure, not validated meaning.
