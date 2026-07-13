"""Tier 1 — deterministic integrity fixtures.

These are AUTHORED SYNTHETIC contexts whose oracle contributions are hand-mapped
to the real gate's facts. They exist to prove the ablation pipeline detects each
effect class; they are NOT product validation, and (per origin.py) cannot emit a
scientific verdict. Each fixture is designed against the real reference ruleset
(action_gate_ref/policy.py DEFAULT_RULES R1..R8).
"""

from __future__ import annotations

from ..origin import SYNTHETIC
from ..units import Context, SemanticUnit as U


def _filler(uid, text="This ticket was opened during the weekly maintenance window.",
           stype="sentence"):
    return U(id=uid, source_type=stype, text=text)


def hidden_negation() -> Context:
    # SECRET_READ export: the decisive commitment is that the sink IS approved.
    return Context(
        id="t1_hidden_negation", data_origin=SYNTHETIC,
        description="Removing the 'approved sink' commitment flips ALLOW->DENY.",
        base={"tool": "filesystem", "verb": "read", "target": ["file://secrets/db"],
              "args": {"export": True},
              "approvals": [{"approver_policy": "single", "approvers": "single"}]},
        units=(
            U(id="sink", source_type="policy_rule",
              text="Export is permitted only to an approved sink; this destination is an approved sink.",
              contrib={"args": {"sink_approved": True}}),
            _filler("f1"),
            _filler("f2", "The requester is on the platform on-call rotation."),
        ))


def rule_plus_distant_exception() -> Context:
    # NET_EXPOSE widening triggers a required single approver (rule + exception).
    return Context(
        id="t1_rule_exception", data_origin=SYNTHETIC,
        description="Widening rule needs approver; approval is the exception that permits it.",
        base={"tool": "http", "verb": "request", "target": ["net://svc/api"], "args": {}},
        units=(
            U(id="rule", source_type="policy_rule",
              text="This change widens network exposure.",
              contrib={"args": {"widening": True}}),
            _filler("f1", "The service serves the internal analytics dashboard."),
            U(id="appr", source_type="approval_record",
              text="Change approved by the security lead (single approver).",
              contrib={"approvals": [{"approver_policy": "single", "approvers": "single"}]}),
        ),
        linked_pairs=(("rule", "appr", "widening_needs_approval"),))


def changed_amount() -> Context:
    # DB_MUTATION affected_count is an envelope field; changing it changes E.
    return Context(
        id="t1_changed_amount", data_origin=SYNTHETIC,
        description="The row-count span changes the envelope arguments (envelope-critical).",
        base={"tool": "filesystem", "verb": "write", "target": ["db://orders"],
              "args": {},
              "evidence": [{"kind": "simulation", "fidelity": "MEDIUM"}]},
        units=(
            U(id="amt", source_type="tool_argument",
              text="The migration updates 5000 records.",
              contrib={"args": {"affected_count": "5000"}}),
            _filler("f1", "The migration adds a nullable column."),
        ))


def approval_and_backup() -> Context:
    # DB_DELETE hard case: backup is dispositive; approver required.
    return Context(
        id="t1_approval_backup", data_origin=SYNTHETIC,
        description="Removing verified backup flips to DENY; removing approval escalates.",
        base={"tool": "kubernetes", "verb": "delete", "target": ["db://replica/7"],
              "args": {}, "reversibility": "REVERSIBLE_WITH_COST"},
        units=(
            U(id="backup", source_type="evidence_record",
              text="A verified restorable backup exists and restore was tested.",
              contrib={"evidence": [{"kind": "verified_restorable_backup"}]}),
            U(id="appr", source_type="approval_record",
              text="Dual-control approval by the security and SRE leads.",
              contrib={"approvals": [{"approver_policy": "dual_control", "approvers": "dual"}]}),
            _filler("f1", "The replica has been drained of live traffic."),
        ),
        linked_pairs=(("backup", "appr", "backup_and_approval"),))


def simulation_requirement() -> Context:
    # DEPLOY requires signed artifact + HIGH simulation.
    return Context(
        id="t1_simulation_req", data_origin=SYNTHETIC,
        description="Removing the HIGH simulation flips ALLOW->SIMULATE_AND_RETRY.",
        base={"tool": "terraform", "verb": "apply", "target": ["svc://billing"], "args": {}},
        units=(
            U(id="artifact", source_type="evidence_record",
              text="A signed build artifact is attached.",
              contrib={"evidence": [{"kind": "signed_artifact"}]}),
            U(id="sim", source_type="evidence_record",
              text="A high-fidelity deployment simulation passed.",
              contrib={"evidence": [{"kind": "simulation", "fidelity": "HIGH"}]}),
            _filler("f1", "The deploy targets the billing service in region us-east."),
        ))


def rollback_reversibility() -> Context:
    # DB_DELETE MAX_IRREVERSIBILITY: the rollback span sets reversibility.
    return Context(
        id="t1_rollback", data_origin=SYNTHETIC,
        description="The rollback span sets reversibility (assurance-input field).",
        base={"tool": "kubernetes", "verb": "delete", "target": ["db://replica/9"],
              "args": {},
              "evidence": [{"kind": "verified_restorable_backup"}],
              "approvals": [{"approver_policy": "dual_control", "approvers": "dual"}]},
        units=(
            U(id="rollback", source_type="clause",
              text="Rollback plan: restore from the verified backup (reversible with cost).",
              contrib={"reversibility": "REVERSIBLE_WITH_COST"}),
            _filler("f1", "The cluster is running Kubernetes 1.30."),
        ))


def widened_scope() -> Context:
    # NET_EXPOSE admin port to the world -> DENY.
    return Context(
        id="t1_widened_scope", data_origin=SYNTHETIC,
        description="The admin-port-to-world span forces DENY.",
        base={"tool": "http", "verb": "request", "target": ["net://svc/admin"], "args": {}},
        units=(
            U(id="scope", source_type="policy_rule",
              text="The rule opens the admin port to 0.0.0.0/0.",
              contrib={"args": {"cidr": "0.0.0.0/0", "admin_port": True}}),
            _filler("f1", "The admin console is used by the ops team."),
        ))


def duplicated_critical_fact() -> Context:
    # SECRET_READ export approved-sink stated TWICE (redundancy set).
    return Context(
        id="t1_duplicated_fact", data_origin=SYNTHETIC,
        description="Approved-sink stated twice: single ablation inert, set ablation flips.",
        base={"tool": "filesystem", "verb": "read", "target": ["file://secrets/db"],
              "args": {"export": True},
              "approvals": [{"approver_policy": "single", "approvers": "single"}]},
        units=(
            U(id="sink1", source_type="policy_rule",
              text="Export destination is an approved sink.",
              contrib={"args": {"sink_approved": True}}, redundancy_set="approved_sink"),
            U(id="sink2", source_type="chat_turn",
              text="Confirmed: the destination bucket is on the approved-sink allowlist.",
              contrib={"args": {"sink_approved": True}}, redundancy_set="approved_sink"),
            _filler("f1", "The export is part of the quarterly audit."),
        ))


def table_contained_constraint() -> Context:
    return Context(
        id="t1_table_constraint", data_origin=SYNTHETIC,
        description="A table row carries the affected-count constraint (envelope field).",
        base={"tool": "filesystem", "verb": "write", "target": ["db://ledger"],
              "args": {}, "evidence": [{"kind": "simulation", "fidelity": "MEDIUM"}]},
        units=(
            U(id="row", source_type="table_row",
              text="| parameter | value |  | max_affected_rows | 5000 |",
              contrib={"args": {"affected_count": "5000"}}),
            _filler("f1", "Change window: Saturday 02:00-04:00 UTC."),
        ))


def json_contained_field() -> Context:
    return Context(
        id="t1_json_field", data_origin=SYNTHETIC,
        description="A JSON field carries the decisive approved-sink flag.",
        base={"tool": "filesystem", "verb": "read", "target": ["file://secrets/db"],
              "args": {"export": True},
              "approvals": [{"approver_policy": "single", "approvers": "single"}]},
        units=(
            U(id="json", source_type="json_field",
              text='{"sink_approved": true, "sink": "s3://approved-bucket"}',
              contrib={"args": {"sink_approved": True}}),
            _filler("f1", "Request id REQ-4821 logged by the export service."),
        ))


def entity_alias() -> Context:
    # entity + alias: removing the entity breaks a surviving reference (structure).
    return Context(
        id="t1_entity_alias", data_origin=SYNTHETIC,
        description="An alias span references the entity span; removing the entity breaks it.",
        base={"tool": "terraform", "verb": "apply", "target": ["svc://billing"], "args": {},
              "evidence": [{"kind": "signed_artifact"}, {"kind": "simulation", "fidelity": "HIGH"}]},
        units=(
            U(id="entity", source_type="state_fact",
              text="The acting principal is agent://sre/1.",
              contrib={}),
            U(id="alias", source_type="sentence",
              text="The deployer (see principal above) initiated the apply.",
              contrib={}, references=("entity",), dependency_links=("entity",)),
            _filler("f1", "The apply was scheduled by the release bot."),
        ))


def jointly_necessary_pair() -> Context:
    # Two redundant HIGH-sim evidences for DEPLOY, encoded as a LINKED PAIR (not a
    # redundancy_set) so single ablation misses them and pair ablation catches them.
    return Context(
        id="t1_jointly_necessary", data_origin=SYNTHETIC,
        description="Two sim spans each suffice; single ablation inert, pair ablation flips.",
        base={"tool": "terraform", "verb": "apply", "target": ["svc://payments"], "args": {},
              "evidence": [{"kind": "signed_artifact"}]},
        units=(
            U(id="simA", source_type="evidence_record",
              text="Simulation A (high fidelity) completed successfully.",
              contrib={"evidence": [{"kind": "simulation", "fidelity": "HIGH"}]}),
            U(id="simB", source_type="evidence_record",
              text="Redundant simulation B (high fidelity) also completed successfully.",
              contrib={"evidence": [{"kind": "simulation", "fidelity": "HIGH"}]}),
            _filler("f1", "Payments deploy reviewed by two engineers."),
        ),
        linked_pairs=(("simA", "simB", "either_sim_suffices"),))


def coherent_one_commitment() -> Context:
    # A coherent paragraph of inert sentences + one decisive simulation span.
    return Context(
        id="t1_coherent_one_commitment", data_origin=SYNTHETIC,
        description="Low critical fraction: one decisive span amid coherent filler.",
        base={"tool": "terraform", "verb": "apply", "target": ["svc://search"], "args": {},
              "evidence": [{"kind": "signed_artifact"}]},
        units=(
            _filler("f1", "The search service handles autocomplete for the storefront."),
            _filler("f2", "This change updates the ranking weights for popular queries."),
            _filler("f3", "The team reviewed the change in the weekly sync."),
            _filler("f4", "Latency budgets are unaffected by the ranking tweak."),
            U(id="sim", source_type="evidence_record",
              text="A high-fidelity simulation of the deploy passed.",
              contrib={"evidence": [{"kind": "simulation", "fidelity": "HIGH"}]}),
            _filler("f5", "Rollout is gated behind a feature flag at 5 percent."),
        ))


ALL_FIXTURES = [
    hidden_negation, rule_plus_distant_exception, changed_amount, approval_and_backup,
    simulation_requirement, rollback_reversibility, widened_scope, duplicated_critical_fact,
    table_contained_constraint, json_contained_field, entity_alias, jointly_necessary_pair,
    coherent_one_commitment,
]


def load() -> list:
    return [f() for f in ALL_FIXTURES]
