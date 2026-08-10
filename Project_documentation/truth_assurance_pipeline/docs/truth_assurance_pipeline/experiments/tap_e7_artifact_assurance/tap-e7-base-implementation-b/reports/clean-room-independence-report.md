# Clean-Room Independence Report

## Enforcement evidence (not just declaration)
- `clean_room_evidence/file-access-log.json` — the unique package paths B read; `any_forbidden` is false.
- `clean_room_evidence/blind-boundary-proof.json` — 0 reads of `expected/`/`derivations/` during blind execution; a guarded `fs.readFileSync` throws on any such read while blind is active.
- `clean_room_evidence/blind-output-root.json` — hash over the committed blind outputs, produced before Phase-2 comparison.
- `results/fixture-id-independence.json` — 0 corpus fixture-ID strings found in runtime `src/`.

## Independence achieved
- **Language:** JavaScript/Node (A is Python).
- **Architecture:** functional pipeline of pure functions with a raw-byte duplicate-key JSON scanner (A is class-based with a different strict-JSON strategy).
- **Dependencies:** Node stdlib only; nothing shared with A except the immutable package resources.
- Behavior is derived from the published resources + spec, gated on an independently recomputed fingerprint.

## Honest caveat (stated, not hidden)
Implementations A and B were authored by the **same agent**. This trial establishes language- and
architecture-level independence, not organizational independence. Genuine third-party authorship
remains a governance precondition for Stable promotion (see stable-promotion-assessment.md).
