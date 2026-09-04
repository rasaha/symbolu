# Explicit-Key Addressing Scale-Up (E1-S) — Preregistration (DRAFT, requires ratification)

**Status: DRAFT. Authorizes nothing. No code exists for this line; no seed is reserved, consumed, or
signed by this document.** Roadmap item 2 of `HYBRID_LLM_ENTERPRISE_RELATIONAL_REASONING_V1_1.md` scaled
up; status-matrix row "Explicit-key semantic addressing → Enterprise/real-model transfer (unauth.)".
Owner instruction 2026-09-04: start this line after closing both BTRR arms.

Predecessors (unchanged, cited only): E1 `experiments/bindingslots_e1/` →
`EXPLICIT_KEY_SEMANTIC_MATCHING_VALIDATED` (5/5 reserved seeds 3140–3144); confirmation
`experiments/bindingslots_e1_confirmation/` → `E1_INDEPENDENTLY_CONFIRMED` (5/5, seeds 5140–5144).
Documented limitations (`Project_documentation/repository/docs/audits/bindingslots_e1/LIMITATIONS.md`):
~32-key density only; no-match is the weakest behaviour (false-accept ≈ 0.07–0.15, one seed 0.22);
the value path is a lookup; the mechanism has never been attributed to a bundle component.

## 1. Load-bearing question
Does explicit-key semantic addressing, exactly as validated at 32 episode-local memories, keep working when
the memory set is an order of magnitude denser, the keys have enterprise shape, and the entities are unseen?
Everything else in this document exists to make that one question falsifiable.

## 2. Hypotheses (frozen before any run)
Density ladder K ∈ {32, 128, 512} memories per episode. K = 32 is a replication anchor and must reproduce
E1 within tolerance or the run is `PROTOCOL_VIOLATED` (harness drift, not science).
- **H1 (transfer at density).** At K = 512, on ≥ 4 of 5 final seeds, every carried gate in §6 passes.
  *Falsified* if ≤ 3 seeds pass.
- **H2 (no-match survives density).** At K = 512, no-match false-accept ≤ 0.30 and confident false-accept
  ≤ 0.20 on ≥ 4 of 5 seeds. This is the predecessor's weakest behaviour and the a-priori most likely
  failure; it is reported separately even if H1 holds.
- **H3 (unseen entities and unseen key composition).** Addressing accuracy on unseen-identity and
  unseen-(subject-type, relation-type)-combination splits ≥ 0.80 at K = 512. Falsified otherwise.
A-priori expectation `[I]`: chance is 1/K, so raw accuracy is not the risk; near-miss keys are. With 512
keys the number of keys sharing a subject or a relation with the query grows ~16×, which is exactly the
regime where cosine matching over a masked-mean embedding is expected to confuse. Either outcome is
reportable; a density ceiling (pass at 128, fail at 512) is the most informative single result.

## 3. What is preserved verbatim from E1 (frozen)
Module `experiments/bindingslots_e1/models.py::E1` unchanged: shared 64-d embedding, masked-mean pooling,
`key_head`/`query_head` linear projections, L2-normalized cosine scores with a learned `null_key` at index
K, temperature `tau`, hard top-1 readout, InfoNCE over K+1 logits. Comparator `B0` (anonymous slots)
unchanged. Training recipe from `experiments/bindingslots_e1/engine.py` (Adam 1e-3, batch 48, CPU fp32,
determinism, `param_hash`). Leakage suite `leakage.py::run_all` (7 checks) re-run on the new generator.
Verdict precedence from `gates.py::verdict` (leakage → determinism → protocol → resource → pass/worst-floor
→ partial → dominant failure → not selected). Parameter count ≈ 24,384 at VOCAB 250; the enterprise
vocabulary in §4 changes VOCAB and therefore the embedding rows only; the analytic count is asserted at
ratification and the projection heads stay 64×64.

## 4. What changes (the whole difference)
| | E1 | E1-S |
|---|---|---|
| memories per episode | 32 | 32 / 128 / 512 (ladder) |
| key shape | unordered entity pair + attribute (primitives) | **enterprise-shaped**: `(subject_type, subject_id, relation_type, object_type)` per `experiments/enterprise_slots_quadratic/schema.py::Evidence.key_tuple`, drawn from that module's `SUBJECT_TYPES` / `RELATION_TYPES` / `OBJECT_TYPES` vocabularies; value = `object_id_or_value` |
| "semantic" | synonym groups per primitive, zero verbatim overlap query↔key | same mechanism, synonym groups per type/relation token; subject ids are opaque and appear verbatim (they are the thing to be matched, not paraphrased) |
| unseen splits | G1 unseen identity | G1 unseen subject ids (sha256-bucketed pools, no visible marker) **+ G8 unseen (subject_type, relation_type) combination** |
| near-miss structure | random negatives + profiles | negatives sampled to share subject OR relation with the query at controlled rates (profiles frozen at ratification) |
| evaluation size | per E1 | ≥ 200 queries per split per seed (cheap; removes the ±0.35 intervals BTRR suffered at n = 8) |

Nothing else changes: no natural language, no pretrained model, no reasoning, no temporal component.

## 5. Generator rules carried from the BTRR corrections (frozen)
1. Process-independent hashing only (`hashlib`), never the builtin `hash()` (BTRR F11).
2. Identity pools partitioned by an invisible hash of the id string; identical token and per-position
   distributions across train/dev/final; no role marker of any kind (F14).
3. Opaque ids never share a token class with high-frequency context tokens (F16). Ids are drawn from a
   reserved id-token range that appears nowhere else in a key or query.
4. No split has a constant or near-constant gold value; structure-blind baselines are real predictors
   (query-only majority, key-only nearest, most-frequent-value, random-valid-key), fitted on gold, with the
   E1 margin rule (F13). A constant emitter must trip the detector in a fixture test before any seed runs.
5. Every run writes a predictions file; an offline rescorer recomputes every metric from it.
6. Decisions are taken on ≥ 5 seeds; a single run ranks, it never decides.
7. `config_digest` binds vocabulary, density ladder, recipe (optimizer, lr, batch, updates, dataset size),
   gates, seeds. Two-key fail-closed execution guard reused from
   `experiments/relational_reasoning_bounded_context/execution.py` (owner-signed record + operator token).

## 6. Gates (carried from `experiments/bindingslots_e1/config.py::GATES`, per density level)
Absolute thresholds are carried unchanged, which makes the scale-up strictly harder than E1: addressing
≥ 0.80 on G1/G2/G3/G5/G8, ≥ 0.75 on G4; no-match false-accept ≤ 0.30; recall/precision ≥ 0.70; confident
false-accept ≤ 0.20; valid false-reject ≤ 0.15; availability ≥ 0.80; end-to-end ≥ 0.70; improvement over
B0 ≥ 0.50; oracle value ≥ 0.99; oracle gap ≤ 0.30; G7 stability ≥ 0.90; worst-seed G1 ≥ 0.70. Non-
compensation: every gate must pass at a density level for that level to pass. Owner decision [4] may
instead rescale the B0-improvement gate, since B0's chance floor falls with K.

## 7. Verdict vocabulary (new tokens; precedence inherited)
`EXPLICIT_KEY_SCALEUP_VALIDATED` (K = 512 passes on ≥ 4/5) · `EXPLICIT_KEY_SCALEUP_DENSITY_LIMITED`
(passes at a lower level, fails at 512; the ceiling is reported) · `EXPLICIT_KEY_SCALEUP_NOMATCH_FAILED`
(H2 fails while addressing passes) · `EXPLICIT_KEY_SCALEUP_NOT_VALIDATED` · `SHORTCUT_OR_LEAKAGE_DETECTED`
· `EXPLICIT_KEY_PROTOCOL_VIOLATED`.
Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`KDA_VALIDATION_BLOCKED`. Never emitted: `E1_TEMPORAL_TRANSFER_VALIDATED`, `E1_STRUCTURAL_TRANSFER_CONFIRMED`,
`KDA_VALIDATION_ELIGIBLE`, `ENTERPRISE_READY`, any production-readiness claim.
`[G]` The confirmation harness's `conf_gates.py` emits `E1_FOLLOW_ON_RESEARCH_ELIGIBLE` while the status
matrix states it is not emitted; this draft does not emit it and asks the owner to reconcile the record.

## 8. Seeds (proposal; owner confirms; disjoint from every prior block)
Prior blocks that must stay untouched: E1 3140–3144, 5140–5144, dev 500–502, burned 2028–2032; address-
generalization 28–32 (0–27 forbidden), fixture 99991; BTRR 8100–8103, 81600–81604, 8200–8203, 81700–81704,
fixtures 883000–883004. Proposed: dev `6100–6102`, final `6140–6144`, fixtures `886000–886004`. Fail-closed
until signed. Development seeds calibrate the near-miss profiles and confirm the K = 32 anchor; final seeds
run once, post-lock, all three densities per seed from one trained model per density.

## 9. Interpretation boundaries
- A pass is a statement about explicit-key addressing over synthetic keys with enterprise *shape*. It is
  not enterprise data, not natural language, not a pretrained model, and not reasoning.
- It does not repair anonymous BindingSlots and does not touch `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`.
- It does not unblock KDA.
- Compute is CPU-scale (tens of thousands of parameters); the constraint on this line is design
  discipline, not hardware.

## Owner decisions (5)
1. Ratify this line under the name E1-S and authorize implementation (no execution).
2. Density ladder {32, 128, 512} and K = 512 as the primary level, or a different ceiling.
3. Seed blocks in §8.
4. Gates carried unchanged (strictly harder) versus rescaling the B0-improvement gate with density.
5. Reuse the BTRR two-key execution mechanism for this line (recommended) or E1's lighter protocol lock.
