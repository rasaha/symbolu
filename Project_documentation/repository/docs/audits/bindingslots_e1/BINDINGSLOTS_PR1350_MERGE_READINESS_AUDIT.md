# PR #1350 (E1 preregistration) — independent merge-readiness audit

**Decision: `E1_PREREG_MERGE_READY`.** Merged via the repository's merge-commit method (`da4d695a`).

## Live ground truth (from Git + GitHub)
- Default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`; PR base = default tip
  `d555b69d` (not behind/diverged); head `735fd19d`.
- State: open, draft, not merged; `mergeable_state: clean`; **CI 7/7 success**; **0 review threads**.
- Scope: exactly the 3 `.md` deliverables under `docs/audits/bindingslots_e1/` — documentation-only.
- No E1 model implementation, no training, no reserved-seed run existed on the branch; B0 / V100 /
  external-fallback / `abc.json` (`b31989a3…`) evidence unmodified; KDA remained blocked.
- PR #1349 merged and reachable from default.

## Scientific audit (§2) — all preserved
Capability-probe-not-reliability framing; B0-frozen vs E1-successor (a positive result is not a repair of
anonymous slots); open-set episode-local matching; differentiable contrastive addressing + hard top-1
read with no soft/Gumbel/STE/top-k/mixture; ≈32-key density; G1–G7 generalization-led verdict
(in-distribution not the gate); no-match as a primary gate with one frozen mechanism (learned null key);
full shortcut-prohibition list; determinism prerequisite; frozen gate structure + compute/futility + no
post-evaluation tuning.

## Merge
Documentation-only, faithful, internally consistent, CI green, no threads — nothing required correction.
Merged; commit reachable from default; local default synchronized; tree clean.
