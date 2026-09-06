# ADR — Live agent attestation scoping (ACC-COUPLING, ACC-RECONFIG, ACC-FACTS, ACC-ATTESTER)

**Status:** rulings ratified by the owner, 2026-09-06; `ACC-COUPLING` implemented
in `ugence-agent-constitution-activation` 0.2.0. `ACC-RECONFIG`, `ACC-FACTS` and
`ACC-ATTESTER` are recorded and implement nothing.
**Maturity:** no attestation ships. Presented facts remain a **disclosed caller
assertion**, `OD-C3=B` and `OD-C4=A` hold, and no `ACC-FC-5` gate is closed by
this round.
**Predecessors:** `ADR_UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_SCOPING.md`
(`OD-C1`–`OD-C5`), `ADR_UGENCE_AGENT_CONSTITUTION_AMENDMENT_ROUND_RATIFICATION.md`
(the carried `[G]`), the `ACC-IA` round (`populate_reference_map`),
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 5, row 3).

## 1 — The question

Wave 5 row 3 names the conformance reference-map gap. Audit found the gap was
already mostly closed, and that the row's remaining content is two different
things: one uncoupled seam in the repository, and an attestation layer that does
not exist anywhere.

## 2 — Audit findings

| Finding | Evidence |
| --- | --- |
| The gap is stated by the package itself and carried by ruling `[V]` | conformance README, *What is deliberately absent*: "the mapping is injected configuration, and its population remains ungoverned, a disclosed, carried gap"; `ADR_..._AMENDMENT_ROUND_RATIFICATION.md:189` |
| **`ACC-IA-3` already narrowed it**: an entry exists only by derivation from an issued record, the artifact/coordinate bond is re-derived through the adapter rather than trusted, and a conflicting entry fails closed `[V]` | `agent-constitution-activation/.../reference_map.py`; `ReferenceMapConflictError` |
| **Nothing coupled derivation to consumption.** Both composition helpers accepted any `Mapping`, and no conformance module referenced `populate_reference_map`, so a deployment could hand-build a map and prove conformance against whatever it said `[G]` | before this change: `activation/composition.py` `constitution_resolver`; repository-wide search |
| Removal, re-pointing and choosing which entries compose were deliberately left outside `ACC-IA-3` `[V]` | `reference_map.py` module docstring |
| Presented facts are caller-assembled, and the package says so `[V]` | `GovernedRoleFacts`; conformance README: "that those facts equal a live role's declarations is the caller's assertion" |
| **No role, subject or agent attestation contract exists anywhere under `src/`.** The only signed attestation is RA-8's `EffectAttestation`, over an execution *observation*, resolving anchors through the reference-grade Trusted Evidence Authority `[V]` | repository-wide search |
| Adding one is a ratification, not an implementation: the ratified surface fixes the predicate, and "no `verified` boolean … None may be added without a new ruling" `[R]` | conformance README |
| `ACC-FC-5` gate 4 is reference-map population, forced-ordered behind gates 1 and 2 (custody; approving authority), and "**No PR can advance gates 1 or 2**" `[V]` | `AGENT_CONSTITUTION_PENDING_WORK_PRIORITY.md` |

## 3 — Rulings

| Ruling | Consequence in code |
| --- | --- |
| **ACC-COUPLING = DERIVED_MAP_ONLY** | `populate_reference_map` returns a `DerivedReferenceMap`: a read-only `Mapping` that this module alone can construct — a caller who could build one could type the entries it claims to have derived — carrying `derived_from`, the coordinates of the records every entry came from. `ActivationRoot.constitution_resolver` requires exactly that type and refuses anything else with `ActivationRequestError`. **Scope, stated rather than implied:** the coupling is enforced in *activation*, because conformance must not depend on activation and its injected-trust posture is ratified. `build_constitution_resolver` still accepts any mapping, so a deployment composing conformance directly still carries the original disclosed gap. The gap is narrowed to one path, not eliminated. |
| **ACC-RECONFIG = OPERATOR_ACTION_OUTSIDE_THE_REPOSITORY** | No removal seam and no re-pointing seam is added, and none may be added without a further ruling. An operator needing a different map derives one from the records it intends: omission is how an entry leaves, and a conflicting entry still fails closed rather than being overwritten. This keeps `OD-C4=A` intact — a removal seam that took effect on a live deployment would be lifecycle authority under another name. |
| **ACC-FACTS = FACTS_STAY_A_DISCLOSED_ASSERTION** | Nothing is added to the conformance boundary. No `verified` boolean, no attested-facts parameter, no disposition. The predicate stays role membership plus three subset checks, and the README's disclosure stands as the honest statement of what replay proves. |
| **ACC-ATTESTER = DEFER_BEHIND_TEA** | No role-attestation contract is minted, in `governance-contracts` or anywhere. Minting a surface with no authority able to fill it would be the shape without the substance, and RA-8's attestation is over an execution observation, not a role's declarations. The question returns when the Trusted Evidence Authority has a production trust-anchor resolver — DD-10b and D-32(4)'s successors — not before. |

## 4 — What this does not do

It closes no `ACC-FC-5` gate; gates 1 and 2 remain unadvanceable by any pull
request. It mints no authority, no lifecycle seam, no disposition and no
attestation. It does not make presented facts true, and it does not claim the
reference-map gap is closed — only that the orchestrated composition path can no
longer be handed a map that was typed rather than derived.

## 5 — Next step

Row 3's attestation half sits behind the same authority maturity as wave 5 row
4's GV-4 half. Neither moves until an attesting authority exists.
