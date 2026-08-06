# Unseen-identifier copy/selection — independent post-merge implementation-integrity audit

Documentation-only record. This audit was conducted **independently of the prior session's audit
conclusions**, reconstructing integrity from the merged authoritative-default state. The prior
session implemented, self-audited, and merged the implementation; that "independent audit" claim is
treated as untrusted here.

## Verdict
**`IMPLEMENTATION_INTEGRITY_CONFIRMED_AFTER_SCOPED_CORRECTIONS`** — one fail-closed weakness was
found and corrected under the permitted "fail-closed guard strengthening" class (corrective
PR #1372, merged); the post-correction re-audit on default `773a7c93` is **confirmed** across all
audit dimensions A–P. Implementation and execution posture unchanged: **execution remains
separately unauthorized.**

Standing invariants preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` ·
`E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`.

## Reconciliation note (post-#1377; audit rebased onto the phase-protocol default)
This audit was performed on default `773a7c93`, which still carried a caller-supplied **cryptographic**
authorization layer. PR #1377 subsequently **removed** that layer — signed authorization
records/artifacts, `AuthorizationContext`, `authorize()` / `validate_authorization_record`, the
capability registry / `active_authorization` / mint keys, the recognized authorization states
(`SMOKE_EXECUTION_AUTHORIZED` and siblings), any Git-provenance authority root, and the
`--authorization-record` / `--authorization-artifact` CLI inputs — and replaced it with lightweight
**experimental-protocol control**: an explicit `--phase` (fixture/smoke/development/final), exact
seed-role validation, exactly one seed per invocation, the primitive-level fail-closed guard now
carrying the declared phase, and fixture-only CI. The scientific-integrity findings below (A–P: recipe
hashes, 209,728 params, reserved-seed non-consumption, determinism/fingerprints, task/serializer/
parser/verdict/shortcut conformance, invariants) are **independent of the authorization layer** and
remain valid on the current phase-protocol default `6c8fb71…`; #1377 reorganized the test suite
(phase-protocol tests replacing the authorization-security tests) without changing any scientific
behavior. Where this audit referenced a per-run "token", read it as the **declared phase** under the
current model — no secret, record, or runtime self-verification exists.

## Authoritative commits & chronology (UTC)
| Ref | Commit | Merged (UTC) |
|---|---|---|
| Protocol lock (PR #1369) | `ec9145f2` | 2026-08-06 09:42 |
| Implementation authorization (PR #1370) | `85f80546` | 2026-08-06 10:18 |
| Implementation (PR #1371) | `a67244a9` | 2026-08-06 10:39 |
| Guard-strengthening correction (PR #1372) | `773a7c93` (default at audit time) | 2026-08-06 (this audit) |
| Execution-interface + shortcut completion (PR #1375) | later default | 2026-08-06 |
| Authorization-layer removal → phase protocol (PR #1377) | `6c8fb71…` (current default) | 2026-08-06 |

Linear ancestry verified: `#1369 ⟶ #1370 ⟶ #1371 ⟶ #1372` (with #1375, #1377 following on the current
default). Authorization preceded implementation; no implementation file predates the authorization
merge; no scientific execution artifact exists.

## Clean-room environment
Fresh checkout of authoritative default; `__pycache__` and any stale outputs removed. Python
3.11.15, torch 2.2.2+cu121. Command: `pytest -q tests/experiments/unseen_identifier_copy_selection`.
**45 tests passed** at audit time (44 original + 1 added by the correction; the suite was later
reorganized by #1377 into fixture-only phase-protocol tests). No command trained the model or
generated a scientific cohort.

## Findings A–P
- **A. Provenance/scope** — the implementation diff is limited to the authorized package
  (`experiments/unseen_identifier_copy_selection/`, incl. a bounded package `README.md`),
  `tests/experiments/unseen_identifier_copy_selection/`, and
  `.github/workflows/unseen-identifier-integrity.yml`. No unrelated code entered.
- **B. Clean-room** — 45/45 tests pass from a clean checkout.
- **C. Scope conformance** — every file is explicitly authorized or reused-as-authorized; no
  candidate-index / constrained decoding / ranking / pointer-copy head / task-specific head /
  tokenizer change / capacity change / pretrained / BindingSlots / E1 / relational reader /
  external-table / multi-hop / temporal / enterprise code (AST + import inspection).
- **D. Recipe** — reused `StructuredOutputModel` (`SoftmaxTransformerLM`), **209,728 params**; all
  recipe values match the lock; source hashes match exactly (`config.py 324be79d…`, `tokenizer.py
  1849fd1f…`, `model.py 39a2a128…`, `trainer.py ea0af36e…`). No new trainable module or head.
- **E. Reserved-seed non-consumption** — seeds 9070 / 9071–9073 / 90760–90764 appear **only** in
  constant declarations, the fail-closed gate, fail-closed tests, and docs; **none passed to any
  generator/trainer**; no scientific pool/dataset/manifest/checkpoint/prediction exists in the tree
  or Git history.
- **F. Fixture policy** — fixtures use only `993000–993004`, verified disjoint from reserved seeds
  **and** their domain-separated sub-seeds; fixtures cannot emit a scientific verdict.
- **G. Identifier-pool generator** — protocol-lock Decision 3 froze the required *properties*
  (alphabet, length, disjoint pools, collision rules, tokenizer strata, source–target independence),
  not a specific algorithm. The implementation's disjoint-master-stream + per-split-window is a
  conformant concretization of those properties — **implementation detail, not protocol drift**.
  Verified: fixed alphabet/length, opaque 4-char IDs, deterministic generation, collision rejection,
  train/final/evidence disjointness (by construction), character-visibility, no surface leakage.
- **H. Task generators C1–C8** — verified: C1 direct copy (no selection); C2 relation lookup
  (one matching source, balanced position); C3 evidence lookup (separate evidence domain); C4
  mechanically balanced first/middle/last; C5 1–2 char lexical decoys, no duplicate/ prefix
  shortcut; C6 seen-pool, C7 disjoint unseen-pool (mechanics match); C8 absent query source, exact
  abstention token, reported separately. No constant-gold component in the primary score.
- **I. Serializer/parser** — byte-conformant with the frozen Decision-2 templates
  (`TASK =`, `QUERY_SOURCE`, `FACTS:`, `->`, `| EVIDENCE =`, `ANSWER =`, `INSUFFICIENT_EVIDENCE`);
  one serializer, no alternative representation, no candidate-index, no constrained decoding. Parser
  classifies the seven categories with no silent repair of malformed IDs.
- **J. Canonical verdict** — the runtime emits exactly one canonical string
  `UNSEEN_IDENTIFIER_SELECTION_FAILED` for C1-pass/C2-fail; `UNSEEN_IDENTIFIER_COPY_ONLY_PARTIAL`
  appears only as an explanatory comment, never emitted. Total-order first-match-wins precedence
  verified for integrity → resource → copy/generalization base → selection → evidence → abstention
  → confirmed, with boundary and co-occurrence tests.
- **K. Shortcuts** — protocol-lock Decision 9 requires baselines "each on its relevant split"; the
  per-split implementation is **conformant** (threshold chance + 0.05 unchanged, no baseline
  removed, no seed added). The prior larger-n convergence check is classified as **authorized
  fixture-level implementation validation** (fixture seeds only, no training, no scientific claim,
  no committed scientific artifact) — it demonstrates the baselines converge to chance (no leakage).
- **L. Execution guards — FINDING + CORRECTION.** The reserved-seed guard originally lived only in
  the runner (`build_cohort`/`enter_final_phase`); direct primitive calls
  (`generate_split("C2","unseen",9070)`, `build_pools(90760)`, `generate_pool(9071,…)`) generated
  reserved-seed data **without the gate** — a trivial bypass. **Corrected** (PR #1372): the three
  data-generation primitives now call `require_execution_authorization(seed, phase)` at entry (the
  declared phase threaded from `build_cohort`); re-verified **27/27** primitive fail-closed checks
  across all nine reserved seeds, fixtures still ungated. Under the current phase-protocol model
  (PR #1377) that guard argument carries the **declared phase**, not a secret token. No reserved
  phase was declared and no scientific command was run during this audit.
- **M. Determinism/fingerprints** — byte-identical pool/dataset/serialization regeneration; stable
  canonical-example and dataset digests; `manifest` produces actual digest values (source/config/
  tokenizer/pool/dataset/serializer/example hashes), not booleans. Scientific digests remain absent.
- **N. Tests/CI** — the suite spans pools, C1–C8, serializer, parser, metrics, verdict precedence,
  shortcuts, seed guards (incl. primitive-level), recipe hashes, parameter count, forbidden-module
  scan, fingerprints, CLI refusal. CI job `unseen-identifier-integrity` runs fixture-only checks
  and does not train, generate scientific cohorts, consume reserved seeds, or emit a verdict; it
  fails on source-hash / parameter-count drift, guard removal, or a forbidden component.
- **O. Artifacts/side-effects** — no datasets/checkpoints/predictions/logs/result-JSON in the tree
  or history. Importing the package writes no files, mutates no global RNG, and instantiates **no**
  model (0 `nn.Module` instances; `build_model` not exposed). `torch` is pulled transitively via the
  **authorized** sibling-recipe `__init__` (`single_hop_typed_vs_prose.model`), not by any unseen-ID
  package module — acceptable reuse; no heavyweight work happens at import.
- **P. Standing invariants / claim boundary** — preserved; no code or doc claims typed superiority,
  unseen-ID competence, selection/generalization competence, evidence grounding, tenant competence,
  multi-hop, production readiness, or KDA eligibility. Verdict vocabulary strings are gate outputs
  for future execution, not affirmative claims.

## Conclusion
Implementation integrity is **independently confirmed** after the single scoped fail-closed
correction, and the scientific-integrity findings carry forward unchanged to the current
phase-protocol default `6c8fb71…`. Nothing was executed, generated, trained, or seeded during this
audit. The diagnostic is ready for the **documentation-only** smoke/development execution-authorization
(companion documents); execution itself remains a separate, operator-directed phase-named step.
