# ACP Freeze Implications

## Two independent freeze mechanisms

### 1. Platform freeze (`platform/PLATFORM_FREEZE_V1.json`) — NOT affected

- **Nothing** under `acp/` or `symbolu_robotics/autonomous_control_plane/` is in the platform freeze.
- Frozen `CORE_TREES`: `decision_governance`, `governance_providers`, `actiongate_provider`, `tap_provider`.
  Frozen `PUBLIC_API_MODULES`: the `.api` surfaces of those four. ACP is in none of them.
- `python -m platform_freeze.verify` PASSES at baseline (substantive digest `d4ad77e1…a174a1a6`) and is
  **unaffected** by ACP source movement.
- **CI caveat:** `.github/workflows/terminology-ci.yml` triggers on **any** `**/*.md` change and runs a
  **blocking** `platform_freeze.verify` step. This audit's docs will trigger that workflow, but the verifier
  still PASSES (ACP isn't frozen), so there is no platform-freeze impact.

### 2. ACP V1 local freeze (`Project_documentation/control_plane/acp/ACP_V1_FREEZE.md`) — WOULD be affected by a source move

- The ACP core carries its **own** doc-asserted digest contract: per-module `SHA-256[:16]` for 13 modules
  and a combined digest **`8f8660e293308cf94c983a26a2ae69c9`** over the 10 reusable-core modules.
- **Verified byte-accurate in this audit** — all 13 live-module hashes match the freeze doc exactly (see
  `BASELINE.md` §5). The freeze is real and current.
- The freeze contract is re-asserted "unchanged" at V2/V2.1/V2.2 completion (`ACP_V2_RESULTS.md:10-11`,
  `ACP_V2_1_RESULTS.md:9`, `CONTROL_PLANE_RESULTS.md:11`), and `acp_k8s_integrated/test_integrated.py:246-259`
  pins a hash of the 10 frozen core modules.

## What a migration would do to the ACP freeze

| Migration action | Freeze effect |
|---|---|
| Move a core module verbatim (same bytes, new path) | Content hash unchanged; but the freeze doc's path references and any path-based pin need updating |
| Convert internal absolute imports → relative imports | **Content changes → per-module SHA-256 changes → combined digest changes → freeze BROKEN** |
| Neutralize robotics envelopes (`world_state.py`, `envelopes.py`) | Content changes → freeze BROKEN (and semantics change) |
| `acp_k8s_integrated` frozen-core hash pin | Would fail unless the pin is updated in lockstep |

**Conclusion:** a byte-identical migration is **not** feasible (see `DETERMINISM_AND_EQUIVALENCE.md`); any
real migration changes the ACP core content and therefore **requires a freeze amendment / replay
re-baseline** of `Project_documentation/control_plane/acp/ACP_V1_FREEZE.md` and the `acp_k8s_integrated` pin. That amendment is **out of scope
for this audit** and must not be performed here.

## What this audit does NOT do

- Does not re-baseline or modify `platform/PLATFORM_FREEZE_V1.json` or any `platform/api-snapshots/*`.
- Does not modify `Project_documentation/control_plane/acp/ACP_V1_FREEZE.md` or recompute/replace its digests.
- Does not move any source, so no freeze evidence changes. `git status` confirms only
  `docs/audits/action_clearance/**` changes.

## Recommendation

Before any ACP source move, produce a **freeze-amendment plan**: (a) decide whether the ACP V1 digest freeze
is retired, superseded by a package-level freeze, or re-based on the neutral kernel; (b) update the
`acp_k8s_integrated` frozen-core hash pin in the same change; (c) preserve a within-domain byte-identical
replay for any adapter (e.g. `cloud/`) that is moved verbatim. This is a **PREREQUISITE**, tracked in
`RISK_REGISTER.md` (frozen-source movement) and `MIGRATION_SEQUENCE.md`.
