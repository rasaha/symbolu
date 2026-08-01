# StoryGraph Public API Inventory & Freeze

Gate **S4** support. Produced **before** code movement. Classifies every symbol on the
legacy public surface (`composite_threat_detector.__all__`, 75 symbols) into a stability
class, records its canonical replacement path, and states the compatibility requirement.

Stability classes: `PUBLIC_STABLE` · `PUBLIC_EXPERIMENTAL` · `INTERNAL` · `TEST_ONLY` ·
`DEPRECATED`.

## Canonical surfaces after migration

- **Canonical small API:** `ugence_storygraph.api` — the deliberately small
  `PUBLIC_STABLE` surface (re-exported curated symbols only; no raw submodules).
- **Canonical full namespace:** `ugence_storygraph` — retains the exact legacy
  `__all__` (identity-preserving) so **no public symbol disappears**.
- **Legacy compatibility path:** `composite_threat_detector` (and every
  `composite_threat_detector.<sub>`) resolves to the **same** canonical module objects
  via an explicit, logic-free compatibility redirect (see `MIGRATION.md`).

## PUBLIC_STABLE — the curated `ugence_storygraph.api` surface

These are the supported public API. Consumers: internal tests, packaging smoke tests,
and any future product composition (e.g. *Ugence Sequence*). Replacement canonical path:
`ugence_storygraph.api` (also available at `ugence_storygraph` top level).

| Symbol | Type | Role |
|---|---|---|
| `SequenceRiskAnalyzer` | class | primary advisory analyzer entrypoint |
| `CompositeThreatMonitor` | class | multi-key monitor wrapper |
| `Finding`, `IngestResult`, `RunReport` | dataclass | analyzer result types |
| `recover_from_audit` | function | rebuild analyzer state from audit log |
| `StoryGraph` | class | story-graph matcher (domain core) |
| `StoryMatch`, `DimensionResult` | dataclass | matcher result types |
| `ObservedEvent` | dataclass | matcher input event |
| `PartialEscalationPolicy` | class | partial-match escalation policy |
| `story_match` | function | one-shot graph match |
| `story_from_recipe` | function | build a graph from a recipe |
| `story_evaluate` | function | evaluate a story |
| `evaluate_proposed_action` | function | **non-mutating** proposed-action simulation |
| `completion_witness`, `would_complete` | function | mandatory-edge completion witness |
| `ProposedActionResult`, `CompletionWitness` | dataclass | verdict/witness types |
| `StoryVerdict`, `BenignSummary` | dataclass | verdict types |
| `to_advisory_evidence` | function | advisory-evidence emitter (authority boundary) |
| `PolicyBinding` | class | advisory→consequence binding (never ALLOW/DENY itself) |
| `TimescalePolicy`, `StateLimits` | class | ledger bounds |
| `ProviderRegistry`, `FixtureProvider`, `BenignEvidenceProvider`, `FailingProvider`, `ProviderUnavailable` | class | context-provider ports/adapters |
| `AuditLog`, `DurableAuditLog` | class | evidence/audit ledgers |
| `LegitimateStory`, `Authorization`, `CoverageRule` | class | legitimate-story (counter-story) types |
| `Fragment`, `FragmentInstance`, `Ontology`, `Recipe` | class | domain model types |
| `AssemblyKeySpec`, `BY_ACTOR`, `BY_CASE`, `BY_TARGET`, `BY_ACTOR_TARGET`, `BY_CORRELATION` | class/const | assembly-key specs |
| `OBSERVE`, `ESCALATE`, `UNAVAILABLE` | const | advisory signals (effect ceiling) |
| `DIGITAL_ONTOLOGY`, `FINANCIAL_ONTOLOGY`, `PHYSICAL_FIREARM_ONTOLOGY`, `ONTOLOGIES` | const | ontologies (firearm = synthetic illustration only) |
| `ACCOUNT_TAKEOVER_TRANSFER`, `DIGITAL_EXFILTRATION_STORY`, `STORY_LIBRARY` | const | frozen harmful graphs / library |
| `ACCOUNT_RECOVERY_STORY`, `BANK_ASSISTED_TRANSFER_STORY`, `LEGITIMATE_LIBRARY` | const | legitimate (counter) stories |
| `MATCHER_SEMANTICS_VERSION`, `PARTIAL_ESCALATION_POLICY_VERSION`, `STORYGRAPH_SCHEMA_VERSION` | const | frozen version identifiers |

## Re-exported submodules — retained on the FULL namespace, excluded from `api`

Legacy `__all__` also re-exports raw submodule objects: `providers`, `purpose`,
`ordering`, `governance`, `audit`, `signals`, `policy`, `legitimate`, `contradictions`,
`stories`, `storygraph`, `storyverdict`, `story_bridge`, `financial`.

Classification: **INTERNAL** (module handles). They remain importable on
`ugence_storygraph` and via the legacy path for backward compatibility, but are **not**
promoted into the curated `ugence_storygraph.api` surface — per the phase rule "do not
expose internal matcher/persistence/fixture/evaluation details merely for compatibility."
They stay reachable as `ugence_storygraph.<name>` (full-namespace) so nothing disappears.

## TEST_ONLY / EVALUATION

`evaluation.*` (harness, corpus, freeze, evidence_chain, prior_runs, …) and `demos.*`
are **TEST_ONLY / evaluation infrastructure**. They were never under the
`composite_threat_detector` namespace (they were sibling top-level packages reachable
only because `conftest.py` put the ctd root on `sys.path`). Canonical paths become
`ugence_storygraph.evaluation.*` and `ugence_storygraph.demos.*`. No global
`evaluation`/`demos` compatibility name is created (they are not a stable public surface
and the bare names would collide repo-wide).

## Compatibility requirement summary

| Requirement | Mechanism |
|---|---|
| Every `PUBLIC_STABLE` symbol keeps behaving identically | pure move; verified by re-run + digest equality |
| Canonical symbols available from `ugence_storygraph` (+ `.api`) | new namespace |
| Legacy `composite_threat_detector[.sub]` imports resolve | redirect finder → same objects |
| Internal symbols do not become newly public | `api` excludes submodule handles |
| No public symbol vanishes without an explicit compat export | full `__all__` retained on canonical namespace + legacy redirect |
| Symbol identity preserved across old/new paths | redirect returns the *same* module object |
