# Freeze & API Impact Assessment — Governance Provider Framework

Audit-only. **This audit does not re-baseline the freeze or modify any API
snapshot.** It records the current frozen state and the impact a *future*
migration would have.

## 1. Current frozen state (recorded, unchanged)

| Item | Value |
|---|---|
| Freeze manifest | `platform/PLATFORM_FREEZE_V1.json` |
| Platform | "Decision Governance Platform" v1.0.0 |
| `manifest_digest` | `6fb6d6c8b02538e7b002c404b3b3a9a0aadd88ce4670369538c995b5b0487cf7` |
| `freeze_commit` | `5ae4f70` |
| Verifier result (this audit) | **PASS**; substantive digest `477407149049968ed12eec71044a913dfc4dbbb8cf23327ea9eec5614d759bf0` |
| `governance_providers` core-tree hash | `ab12c0260bd9d49fdda37264aa1ad74e3b880bdc1b3bdfd303ae023e6c43cd2b` |
| `governance_providers.api` snapshot hash | `98dd02649e5fbb37879ef05e1b06afce1abd0cc10b5692b81974437d59f7a59b` |
| Framework component | `dgm-provider-framework: 0.1.0` |
| Is `governance_providers` a frozen core tree? | **YES** (one of four: `decision_governance`, `governance_providers`, `actiongate_provider`, `tap_provider`) |
| Is `ugence-governance-contracts` a frozen component? | **NO** — gap (see §4) |

### Provider-relevant frozen invariants
- **F16** Providers interact through neutral framework contracts.
- **F17** Providers of the same or different families do not invoke one another.
- **F18** Provider resolution is deterministic and auditable.
- **F19** Fallback cannot be used for governance shopping.
- **F20** Frozen package dependency direction remains acyclic.

`compatibility_rules.MAJOR` explicitly covers "provider-contract redesign,
authority/lifecycle/dependency-direction/fail-safe changes, new provider
families" — none of which a physical relocation triggers.

## 2. Precedent: what the prior migrations did to the freeze

Both directly relevant precedents changed **exactly two** manifest fields and
kept all four API snapshots byte-identical:

- **Governance Contracts migration** (carved contracts OUT of `governance_providers`):
  re-baselined `core_tree_hashes[governance_providers]` + `manifest_digest`;
  `governance_providers.api` snapshot **unchanged**; classified **PATCH**.
- **Decision Authority migration**: re-baselined
  `core_tree_hashes[decision_governance]` (`f38a6159…`→`3e98d8db…`) +
  `manifest_digest` (`f318dfd2…`→`6fb6d6c8…`); API snapshots byte-identical;
  "structural / PATCH".

## 3. Impact of a FUTURE framework migration (projected — not performed)

| Change dimension | Impact | Change class |
|---|---|---|
| **Physical path** (`governance_providers/` → `packages/governance-provider-framework/src/ugence_governance_provider_framework/`) | Changes `core_tree_hashes[governance_providers]` (tree becomes the legacy shim) | requires reviewed re-baseline of 2 fields via `platform_freeze` `write_manifest` |
| **Namespace** (add `ugence_governance_provider_framework`; keep `governance_providers` as identity-preserving shim) | Additive namespace; legacy paths preserved | no consumer change if shims exact |
| **Distribution** (`dgm-provider-framework` symlink repoint, or add `ugence-governance-provider-framework`) | Packaging metadata only | packaging test update |
| **Public API** (`governance_providers.api` export list + dataclass fields kept identical) | Snapshot hash **`98dd0264…` unchanged** | **PATCH** — no API change |
| **Object identity / serialization** | Preserved via re-export shims (not symlink) — same class objects | none |
| **Frozen vocabulary / conformance behavior** | Unchanged — no logic moves, only file location | none |
| **`manifest_digest`** | Recomputed after the 2 tree/hash edits | mechanical |

**Projected classification: PATCH / structural** — identical to the two prior
migrations. The API and behavior do not change; only physical location and
namespace do.

## 4. Freeze gaps & cautions to carry into the migration phase

1. **`ugence-governance-contracts` is not yet a frozen component.** The framework
   already depends on it, and the freeze verifier passes, but the contracts leaf
   is not listed in `components` / `core_trees`. The framework migration is a
   natural point to also fold `ugence-governance-contracts` (and, by extension,
   the other `ugence_*` leaves) into the freeze manifest — but that is a **freeze
   re-baseline decision** and must not be done in this audit.
2. **`governance_providers` is frozen, unlike StoryGraph.** StoryGraph's migration
   owed **no** platform freeze re-baseline (it isn't in the manifest). The
   framework's migration **does** owe one. Its acceptance bar is therefore higher:
   `platform_freeze.verify` must pass, the two edited fields must be reviewed, and
   `api_compatibility` must classify PATCH.
3. **Preserve object identity with re-export shims, not a symlink.** A symlink
   would create a second top-level module name and a second, non-identical class
   set, breaking the legacy-compat identity assertions. The prior migrations use
   logic-free re-export/redirect shims for exactly this reason.
4. **Keep the export list byte-identical.** Any reordering or symbol change flips
   the snapshot hash and escalates the change class above PATCH.

## 5. What must be separated (do not conflate)

| Layer of change | This migration | Class |
|---|---|---|
| Physical path change | Yes | structural |
| Namespace change (additive + shim) | Yes | structural |
| Distribution change | Yes (packaging) | structural |
| **Semantic change** | **No** | — |

The migration is a *relocation*, not a redesign. No authority, contract,
lifecycle, dependency-direction, or fail-safe semantics change — so it stays
below the `MAJOR` threshold and does not touch F1–F20 behavior.
