# MVP 1F Limitations

> MVP 1F is a bounded operational-validation phase. It runs, annotates, analyzes,
> and closes out a shadow pilot and produces an enforcement-readiness verdict. It
> does not enforce anything and does not change what the product may do.

## Honest evidence status

This build is `IMPLEMENTED_AND_OFFLINE_VERIFIED`. The offline demo uses supplied
snapshots, synthetic controls, and mock reviewer annotations — none counted as live
enterprise evidence. No live customer pilot occurred, no reviewer agreement was
measured against real reviewers, no false-positive/false-negative rates were
established, and GitHub permissions were not verified against a real installation.
The default readiness verdict is `INSUFFICIENT_LIVE_EVIDENCE` and the live pilot is
`LIVE_PILOT_NOT_RUN`.

## Explicitly out of scope

No execution · no GitHub writes or checks · no approve/merge/close/label/comment/
assign/modify of PRs · no `reserve_once` · no authorization-consumption ledger · no
GitHub execution provider · no deployment/merge enforcement · no `ProviderKind` · no
external production database · no broad analytics platform · no automatic policy
change from reviewer feedback · no fabricated live results · supplied snapshots are
never described as real enterprise evidence.

## Discipline

Reviewer agreement is not absolute ground truth. Small-sample findings are not
overstated. No precision/recall/accuracy is claimed without a defensible protocol.
Calibration recommendations do not alter policy automatically. A readiness verdict
does not enable enforcement. The canonical Action Clearance package is unchanged;
the only changed product boundary is `products/code-governance/`.

See `CODE_GOVERNANCE_NEXT_PHASES.md`.
