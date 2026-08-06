# Typed-vs-prose single-hop benchmark — independent audit report (Stage 2)

Audit reconstructed from Git, committed artifacts, and the frozen executable code — not from
prior prose, branch names, or integrity booleans. Companion documents:
`…_AUDIT_PROVENANCE.md` (Stage 1), `…_AUDIT_ANALYSIS.md` (constant-output & shortcut),
`runs/audit/audit_manifest.json` (fingerprints), `runs/audit/audit_replay_traces.json`
(AUDIT_REPLAY_DERIVED per-example predictions).

## Audit decision: `MERGE_READY_AFTER_SCOPED_CORRECTIONS`
All required reproducibility fingerprints were reconstructable from immutable committed artifacts;
deterministic replay reproduced the reported result **exactly**; the verdict reconstructs
independently; the shortcut anomaly and the constant-output limitation are documented. The scoped
corrections are the audit/provenance/fingerprint/replay/analysis records added in this PR plus the
bounded-wording caveats in the results report — no raw scientific value, serializer, dataset, gate,
or seed was changed.

## A. Protocol-lock ancestry — PASS
The merged protocol lock (`…_PROTOCOL_LOCK.md`, on the result lineage) froze the exact values the
execution used. Cross-checked mechanically:
- Primary = macro-average {S1 exact-entity, S2 FK, S3 relation-validity, S5 evidence-F1, S6
  abstention} == code `PRIMARY_SPLITS`.
- Every Decision-3 threshold (0.80 / 0.08 / 4-of-5 with 0.75 & 0.05 / per-split
  0.85·0.85·0.80·0.90·0.90·0.90 / S8 ≥0.90 / S8-regress ≤0.02 / partial ≥0.75 & ≥0.04 & 3-of-5)
  matches `driver.apply_gates`.
- Causal thresholds (A1/A2 decline ≥0.20; A3 abstention ≥0.90 & unsupported ≤0.05; A6 degradation
  ≤0.05) match `driver._causal_gates_pass`.
- Sub-seed rule `seed*1_000_003 + DOMAIN_ID*97 + 13` matches `driver.sub_seed`.
- Seed roles (smoke 76 / dev 760–762 / final 7160–7164) match `config.py`.
- **One non-locked item, documented:** the 96-token evaluation decode cap is not in the protocol
  lock (the lock froze the 384-token *training* output allowance; eval decode length was
  unspecified). It is arm-neutral (see E) and cannot change any valid output; classified as an
  implementation parameter, not a protocol departure affecting results.

## B. Authorization ordering — PASS
Linear ancestry, UTC-normalized commit timeline, monotonic: protocol lock 03:48Z →
implementation authorization 04:56Z → implementation 05:13Z → harness reconcile 06:21Z →
freeze design + driver + `EXECUTION_AUTHORIZATION.md` 06:40Z → reserved execution results 07:07Z.
No results artifact predates the execution-authorization/freeze commit (`977f6638` is an ancestor
of `422ab3e5`).

## C. Implementation & configuration — PASS
One shared backbone (`symbolu_neural.clean_softmax.backbone.SoftmaxTransformerLM`) used identically
for both arms; identical parameter count (209,728) and identical initialization per seed (see D);
same optimizer/steps/batch order; the **only** arm-conditional code is the serialization selection
`pair.b0 if arm=="B0" else pair.b1`. Grep confirms **no** BindingSlots, E1/episodic memory,
event/quadratic reader, external-table correction, pointer/copy network, pretrained adapter, or any
arm-specific post-processing in the package. Source hashes recorded in the manifest.

## D. Arm-fairness — PASS
For every final seed the two arms share **one** model-initialization digest (`init_param_digest`)
and one batch-order digest (both derived from the shared `init`/`batch` sub-seeds); the dataset is
built once per seed and serialized both ways. Final parameter digests differ between arms, as
expected, purely from the differing input serialization. The only permitted difference (B0 vs B1
serialization) is the only observed difference.

## E. Evaluation decode-cap — PASS
Cap = 96 output tokens, identical across arms, present in `benchmark.py` at the freeze commit
(before final execution). Over all 1920 evaluations the **maximum emitted output was 38 tokens**
for both arms (≤ the 62-token maximum any valid output could need) — **zero outputs truncated**.
Parser failures: B0 = 5/960 (0.5%), B1 = 0/960; since 38 ≪ 96 these are genuine malformed prose-arm
generations, not truncation artifacts. The cap cannot advantage either representation.

## F. Raw evidence completeness — PASS
Force-added from a `runs/`-ignored directory (the directory is git-ignored as a scratch/output
location; the four result JSONs were explicitly force-added as evidence). All parse. Coverage:
smoke seed 76 (both arms); dev seeds 760/761/762; final seeds 7160–7164 (both arms each); no
duplicate/omitted/selectively-excluded run; filenames agree with internal seed/arm metadata; run
counts match the protocol (1 smoke, 3 dev, 5 final). Aggregate granularity is addressed in I.

## G. Fingerprint remediation — PASS (audit-derived)
The original run stored behavioral determinism (a boolean) but not digest **values**. The audit
manifest now records actual values — source/config/serializer/schema/evaluator/tokenizer hashes,
frozen recipe, per-seed canonical fact-set digest, B0/B1 serialization digests, initialization
digest, data-order digest, per-arm final parameter digests, prediction/evaluation digest, and an
environment manifest — each labeled `AUDIT_DERIVED_FROM_UNCHANGED_ARTIFACT` (reconstructed by the
auditor from the exact committed code, not recorded contemporaneously with the original run).

## H. Information-equivalence hard path — PASS
`make_pair` calls `assert_information_equivalent`, which **fails closed** (raises) on any semantic
mismatch, re-serializes each arm twice for byte-identity, and requires the B1 JSON to round-trip to
`episode.visible_canonical()`. Independent recomputation over **all 960 paired final examples**
(5 × 192) → **0 mismatches**; `B0_fact_hash == B1_fact_hash` holds for 100%.

## I & J. Aggregate-only evidence, deterministic replay, mechanical reconstruction — PASS
The original final artifacts store per-seed/per-split **aggregates**, not per-example predictions.
Therefore: *the original result is not independently reconstructible from stored predictions alone
and relies on deterministic replay of the frozen implementation.* The audit performed that replay
(retrained both arms for all five final seeds under the frozen recipe, reconstructed per-example
predictions, recomputed every aggregate and the verdict independently):
- Reconstructed **B0 = 0.4567, B1 = 0.4350, B1−B0 = −0.0217, 0/5 seeds pass** — identical to
  reported, per-seed and per-split matching to 1e-9.
- Independent verdict = **`TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_NOT_FOUND`**. Rounding does not
  affect any gate outcome (endpoints fail by wide margins).

## K. Constant-output splits — PASS with explicit caveat
Two of the five primary components (S3 always `relation_supported=True`; S6 always
`INSUFFICIENT_EVIDENCE`) are **constant-gold**: a constant predictor scores 1.000. Both arms floor
at 2/5 = 0.40. Protocol-compliant (Decision 3 defines the primary this way) and symmetric across
arms. Required caveat recorded: *two of the five primary components are constant-output components,
so the absolute primary overstates general relational competence, while the paired B1−B0
comparison remains mechanically symmetric.* Audit-only non-constant diagnostic {S1, S2, S5-F1}:
**B0 = 0.094, B1 = 0.058** — both near floor. (Detail in `…_AUDIT_ANALYSIS.md`.)

## L. Shortcut-gate — documented limitation + process deviation, not verdict-changing
Locked bound = chance + 0.05 = 0.55. Lexical-overlap: dev mean 0.458 (below chance); final
per-seed 0.639/0.514/0.583/0.514/0.486, mean 0.547 — the reported "0.639" is the worst of five.
Two findings: (1) a **process deviation** — the locked protocol expects shortcut baselines
investigated *before* reserved execution, but the driver computed it *during* the final phase;
(2) the baseline marginally exceeds the bound on 2/5 reserved seeds. It **cannot** satisfy the
validated outcome (far below the 0.80/0.85 bars), the learned models scored *below* it, and the
endpoint verdict is NOT_FOUND independently — so it is classified as a documented limitation and
process deviation that does not change the outcome. Not remediated by touching the benchmark
(forbidden after inspecting reserved results).

## M. Tenant-isolation — bounded
Mechanically: **0 unauthorized cross-tenant inclusions** across every final example, seed, and arm
(S7), and A5 = 0 unauthorized / 0 out-of-tenant. Supported claim: *no unauthorized cross-tenant
inclusion was observed under the tested conditions.* **Not** supported: positive tenant-aware
selection — on S7 the model **abstains** (abstention 1.000) rather than selecting a valid in-tenant
target, and clean positive-selection competence (S1/S2) is near floor. A universally-abstaining
model has not demonstrated positive tenant-aware relational selection.

## N. Causal-gate interpretation — underpowered
A1 clean entity accuracy ≈ 0.05; A2/A4 clean competence similarly near floor. With almost no clean
competence, lack of collapse under perturbation is **not** evidence of causal impurity — the
ablations are **underpowered**. Endpoint failure, causal-gate outcome, and competence floor are
reported separately. A5 (tenant) is the exception and passed.

## O. Repository invariants — PASS
No file changed outside typed-vs-prose scope (`git diff --name-only default..HEAD`);
`experiments/phase_lc/results/abc.json` and all prior evidence unchanged; no prior verdict
rewritten. Forbidden verdict strings (`E1_STRUCTURAL_TRANSFER_CONFIRMED`,
`E1_FOLLOW_ON_RESEARCH_ELIGIBLE`, `KDA_VALIDATION_ELIGIBLE`, `PRODUCTION_READY`) appear only in
prohibition context. Standing invariants preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`
· `E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`.

## Summary
The reported result is **provenance-clean, authorization-ordered, fair, information-equivalent,
deterministically reproducible to the bit-of-metric, and correctly classified**. Its two honest
limitations — the constant-output composition of the primary and the shortcut-baseline anomaly /
pre-execution process gap — are documented and do not change the mechanically-reconstructed verdict
`TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_NOT_FOUND`. Decision: **`MERGE_READY_AFTER_SCOPED_CORRECTIONS`**.
