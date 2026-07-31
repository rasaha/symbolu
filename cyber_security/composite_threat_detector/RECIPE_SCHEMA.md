# Recipe Schema (versioned)

A recipe encodes one prohibited/high-risk capability as an assembly of benign
fragments plus the structural constraints that distinguish a real assembly from a
sequence that merely shares nouns. Recipes are data; the matcher (`matcher.py`) is
domain-agnostic. Defined in `composite_threat_detector/model.py::Recipe`.

Identity is `recipe_id@version`; every finding names it, like the gate's
`policy_version`.

| Field | Type | Meaning |
|-------|------|---------|
| `recipe_id` | str | stable id |
| `version` | str | recipe version (bump on any semantic change) |
| `name` | str | human-readable capability name |
| `required` | set[fragment_id] | load-bearing fragments; all needed to complete |
| `optional` | set[fragment_id] | corroborating fragments |
| `mutually_exclusive` | tuple[set] | two members of one set present ⇒ recipe impossible |
| `ordering` | tuple[(before, after)] | `before` must occur at an earlier order coordinate than `after` |
| `max_assembly_gap` | float \| None | max span (timescale units) across contributing required fragments |
| `pair_gaps` | {(a,b): (min,max)} | per-pair temporal bounds |
| `actor_scope` | ANY_ACTOR / SAME_ACTOR / REQUIRE_MULTI_ACTOR | actor constraint across required fragments |
| `resource_scope` | ANY / SAME_TARGET_FAMILY | resource constraint |
| `completion_threshold` | float (0,1] | fraction of `required` to be "complete" |
| `escalation_threshold` | float (0,1] | fraction of `required` to escalate |
| `observe_threshold` | float (0,1] | fraction to raise OBSERVE |
| `required_corroboration` | set[fragment_id] | fragments that must ALSO be present to escalate |
| `min_optional_for_escalation` | int | minimum optional fragments present to escalate |
| `benign_exclusions` | set[tag] | benign-context tags that can qualify an escalation when scope-matched |
| `severity` | LOW/MEDIUM/HIGH/CRITICAL | |
| `recommended_consequence` | str | advisory recommendation to policy (non-binding) |
| `explanation_template` | str | concise finding text |

## Matching semantics (matcher.py)

Fragment count is **necessary but not sufficient**. `ESCALATE` requires the
completeness threshold **and** all of: no mutually-exclusive conflict; ordering
satisfied; temporal bounds satisfied; actor scope satisfied; resource scope
satisfied; required corroboration present; minimum-optional met. If the count
would escalate but a constraint fails, the signal is capped at `OBSERVE` ("right
nouns, wrong structure"). A benign context (see `benign.py`) may further downgrade
a structurally-complete `ESCALATE` to `OBSERVE` only with valid, scope-matched
approval evidence.

## Fragment decay class

Each `Fragment` has `decay_class ∈ {PERSISTENT, TRANSIENT}`. PERSISTENT fragments
(acquired capability) survive in the capability ledger until explicitly revoked;
TRANSIENT fragments (e.g. discovery reads) decay. This is what makes long-and-slow
assemblies detectable without an unbounded raw-event window.

## Versioning

Bump `version` on any change to required/optional/constraints/thresholds. Findings
record the version in force at emission time; the analyzer supports swapping the
recipe library mid-case (`SequenceRiskAnalyzer.load_ontology`) while preserving
accumulated ledger state.
