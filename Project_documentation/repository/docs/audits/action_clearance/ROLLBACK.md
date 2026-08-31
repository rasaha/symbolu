# ACP Audit — Rollback

## Nothing to roll back at runtime

This is a **documentation-only** audit. It changes **only** files under `docs/audits/action_clearance/**`.
No source moved, no package was created, no contract/API-snapshot/freeze/behavior changed. `git status`
after the audit shows only additions under that directory.

## To undo this audit entirely

```bash
git rm -r docs/audits/action_clearance
git commit -m "docs: remove ACP product-core separation audit"
```

or drop the audit branch's commits:

```bash
git checkout claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF   # default branch
git branch -D claude/acp-product-core-separation-audit-qrwlxv
```

Neither affects any runtime code, package, or freeze manifest, because the audit added none.

## Rollback for the (future, not-yet-started) migration

If a later phase begins the migration and needs reversal, the safe rollback is the same identity-preserving
pattern used by the prior migrations:

1. Revert the consumer-migration commits so `cer_v0_*` import the legacy `.cloud.*` paths again.
2. Remove the `packages/capabilities/action-clearance/` package and its legacy shim.
3. Restore `Project_documentation/control_plane/acp/ACP_V1_FREEZE.md` and the `acp_k8s_integrated` frozen-core pin to their pre-migration digests
   (the freeze was verified byte-accurate in this audit, so the pre-migration digests are known:
   combined `8f8660e293308cf94c983a26a2ae69c9`).
4. Re-run the baseline in `BASELINE.md` and confirm the same PASS results and the same three pre-existing
   failures.

Because the current audit performs none of the above, this section is documentation for a future phase only.

## Verification that the audit is inert

- `python -m platform_freeze.verify` → PASS, unchanged digest `d4ad77e1…a174a1a6`.
- `scripts/validate_terminology.py`, `scripts/check_doc_links.py` → PASS.
- ACP tests (112), governance suites, ActionGate, control_plane → unchanged.
- The two platform-freeze-tooling failures and the one bounded_shadow_pilot failure remain **exactly** as at
  baseline (pre-existing; not introduced by the audit).
