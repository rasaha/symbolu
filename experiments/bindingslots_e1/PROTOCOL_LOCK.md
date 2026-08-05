# E1 protocol lock — frozen protocol (Stage 2)

**Result: `E1_PROTOCOL_LOCKED`.** All load-bearing choices are frozen on non-reserved development
fixtures; the reserved final pool and reserved seeds were never read in Stage 2. The machine-readable
lock is `results/protocol_lock.json` (source hashes, dataset/split hashes, frozen config + gates).
Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `KDA_VALIDATION_BLOCKED`.

## Frozen task & arms
Shared compositional semantic-matching task (see `DESIGN_DECISIONS.md`): identity = pair of entity
primitives; attribute = one primitive; fact = (identity, attribute) → value. Keys use canonical surface
forms; queries use different synonym surface forms + reorder + filler (no verbatim overlap). Identities
partitioned disjointly into train / dev / **final(reserved)** pools (774 / 181 / 173).
- **B0** — anonymous soft content-addressed slots (32), own next-value objective, no explicit key, no
  abstention.
- **E1** — explicit-key dual encoder (shared embedding; separate key/query heads; cosine; learned null
  key; **hard top-1** value read; contrastive InfoNCE over episode-local keys + null).

## Frozen config
`D=64`, train episodes = 1500 (seed 7, no-match frac 0.40), `STEPS=1800`, `BATCH=48`, `LR=1e-3`,
`TAU=0.05`, 32 keys/episode. Reserved seeds = `[2028,2029,2030,2031,2032]`; **4 of 5** must pass all
primary gates; worst-seed G1 floor 0.70. Determinism: CPU fp32, `threads=4`, seeded, byte-identical
replay (verified).

## Frozen numeric gates (grounded in dev calibration; margins below dev)
Dev (3 seeds) observed: G1 addr 0.99–1.00, e2e 0.93–0.95; G2 0.98–0.99; G3 0.99–1.00; G7 0.99–1.00;
no-match false-accept 0.09–0.13, recall 0.87–0.91, precision 0.92–0.95; B0 e2e 0.02–0.07.

Generalization (min addr): G1 0.80 · G2 0.80 · G3 0.80 · G4 0.75 · G5 0.80. No-match: max false-accept
0.30 · min recall 0.70 · min precision 0.70 · max confident-false-accept 0.20 · max valid false-reject
0.15 · min answer-availability 0.80. End-to-end: min ordinary retrieval 0.70 · **min improvement over
B0 0.50** · min oracle-key value 0.99 · max oracle-to-predicted gap 0.30 · min G7-stable addr 0.90.
Fresh-seed: 5 seeds, ≥4 pass, worst-seed G1 ≥ 0.70. (All numbers frozen from dev; none set on reserved.)

## Dev calibration result (non-reserved)
`determinism_ok = True`; leakage suite `all_pass = True`; **3/3 dev seeds pass all primary gates**. B0 is
at chance on every generalization split; E1 clears all gates with margin. Evidence:
`results/dev_calibration.json`, `results/determinism.json`, `results/leakage_report.json`.

## Compute & futility (frozen)
Max steps/seed = 1800; reserved seeds = 5; futility: stop when max possible remaining passes < 4; also
stop on determinism failure, leakage detection, or resource exhaustion; **no selective seed restarts**;
no post-evaluation tuning. A mechanical verifier (`protocol_lock.py`) confirms no reserved seed was run
before lock.

## Resolved `APPROVAL_REQUIRED_BEFORE_EXECUTION` items
Every placeholder from the merged gate/compute plan is now a frozen number above, justified by dev
evidence or engineering constraint: τ (0.05), no-match training fraction (0.40), all gate thresholds,
final-seed set, dev-seed count, steps/wall-clock bound, partial-vs-not-selected rule (n_pass≥1 → PARTIAL;
n_pass=0 → dominant-failure verdict).
