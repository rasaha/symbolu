# StoryGraph — Public API

The supported public surface is the curated **`ugence_storygraph.api`** module
(also re-exported from the top-level `ugence_storygraph` namespace). Import from
there; do not import internal implementation modules.

```python
from ugence_storygraph.api import (
    SequenceRiskAnalyzer, StoryGraph, evaluate_proposed_action,
    to_advisory_evidence, ACCOUNT_TAKEOVER_TRANSFER, DIGITAL_ONTOLOGY,
    OBSERVE, ESCALATE, UNAVAILABLE,
)
```

## Categories

| Group | Symbols |
|---|---|
| Analyzer | `SequenceRiskAnalyzer`, `CompositeThreatMonitor`, `Finding`, `IngestResult`, `RunReport`, `recover_from_audit` |
| Matcher (domain) | `StoryGraph`, `StoryMatch`, `DimensionResult`, `ObservedEvent`, `PartialEscalationPolicy`, `story_match`, `story_from_recipe`, `story_evaluate` |
| Witness / verdict | `evaluate_proposed_action` (non-mutating), `completion_witness`, `would_complete`, `ProposedActionResult`, `CompletionWitness`, `StoryVerdict`, `BenignSummary` |
| Advisory evidence / authority | `to_advisory_evidence`, `PolicyBinding`, `OBSERVE`, `ESCALATE`, `UNAVAILABLE` |
| Domain model | `Fragment`, `FragmentInstance`, `Ontology`, `Recipe`, `DIGITAL_ONTOLOGY`, `FINANCIAL_ONTOLOGY`, `PHYSICAL_FIREARM_ONTOLOGY`, `ONTOLOGIES`, `AssemblyKeySpec`, `BY_*` |
| Providers / ledgers | `ProviderRegistry`, `FixtureProvider`, `BenignEvidenceProvider`, `FailingProvider`, `ProviderUnavailable`, `AuditLog`, `DurableAuditLog` |
| Reference stories | `ACCOUNT_TAKEOVER_TRANSFER`, `DIGITAL_EXFILTRATION_STORY`, `STORY_LIBRARY`, `ACCOUNT_RECOVERY_STORY`, `BANK_ASSISTED_TRANSFER_STORY`, `LEGITIMATE_LIBRARY` |
| Frozen version identifiers | `MATCHER_SEMANTICS_VERSION`, `PARTIAL_ESCALATION_POLICY_VERSION`, `STORYGRAPH_SCHEMA_VERSION` |

Policy-pack compilation and replay use the `ugence_storygraph.policypack`
subpackage (`compiler`, `reference`, `replay`, `replay_gates`) — see
`../policy-packs/` and `../replay/`.

## Stability & compatibility

- The full, per-symbol stability inventory (PUBLIC_STABLE / internal, with the
  legacy→canonical mapping) lives with the migration evidence at
  `../../../../docs/migrations/storygraph/API_INVENTORY.md` (repository-level).
- **Legacy path (deprecated):** `import composite_threat_detector` still resolves
  to the same objects via a compatibility redirect. New code must use
  `import ugence_storygraph`. See `../../MIGRATION.md`.

## Authority

Every symbol here is advisory. See `../limitations/KNOWN_LIMITATIONS.md`.
