"""CER V0.3 cross-domain factorial corpus (§9). Deterministic.

Buckets:
  * existing-profile regression (scale/rollout digests unchanged);
  * new-domain valid (equal across two independent producers + provenance/objective/
    argument-order invariance);
  * expected identity differences (database/table/operation/statement/scope/principal/
    state-binding/compensation/optional-field/profile);
  * invalid & security (secret, unsupported op, ambiguous target, malformed id, bad
    numeric, unknown profile, unsupported extension, missing state binding, stale,
    modified-after-approval, cross-domain evidence transfer, profile downgrade, bypass,
    unbounded).

Each case is preregistered: equal | different | invalid | governance_hold |
authorization_deny (+ the expected composed class where a governed run applies).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .db_actuation import DbActuation, DbContext
from .producers.tool_runtime_db import ToolRuntimeDbAdapter
from .producers.ugence_db import UgenceDbProducer

NOW = "2026-01-01T00:10:00.000Z"
FRESH = "2026-01-01T00:09:30.000Z"

_UG = UgenceDbProducer()
_TR = ToolRuntimeDbAdapter()
PRODUCERS = {"ugence": _UG, "tool-runtime": _TR}


def _op(**over):
    d = {"observed_row_version": "orders@v17", "reachable": True, "healthy": True,
         "active_transactions": 3, "max_transactions": 100, "max_affected_rows": 10000,
         "migration_active": False, "freeze_active": False, "replication_healthy": True,
         "replication_lag_s": 0.5, "max_replication_lag_s": 5.0, "lock_contention_ok": True,
         "backup_available": True, "observation_time_s": 600.0}
    d.update(over)
    return d


def _ctx(**over) -> DbContext:
    base = DbContext(
        principal="agent:data-ops", permissions=("db.write",), delegator_id="dba",
        resource_version="row-1001", state_hash="sha-256:" + "bb" * 32, as_of=FRESH,
        operational=_op(), policy_version="1.0.0+abc", policy_digest="pd",
        correlation_id="prod-orders/public/orders")
    return base.with_(**over)


def _act(**over) -> DbActuation:
    d = dict(connection_ref="prod-orders", schema="public", table="orders",
             sql_operation="UPDATE", statement_digest="sha256:" + "aa" * 32,
             estimated_rows=42, expected_row_version="orders@v17",
             compensation_ref="backup:orders:2026-01-01")
    d.update(over)
    return DbActuation(**d)


def _both(ctx, act) -> Dict[str, dict]:
    return {name: p.propose(ctx, act) for name, p in PRODUCERS.items()}


@dataclass
class Case:
    case_id: str
    expect: str                       # equal | different | invalid | governance | deny
    description: str
    cers: Dict[str, dict] = field(default_factory=dict)
    base_ref: Optional[str] = None
    malformed_cer: Optional[dict] = None
    expect_cp_class: Optional[str] = None
    stale: bool = False
    missing_evidence: bool = False
    unbounded: bool = False
    bypass: bool = False
    evidence_transfer: Optional[str] = None   # "k8s_to_db" | "db_to_k8s"
    approval_replay: bool = False
    notes: str = ""


def build_corpus() -> List[Case]:
    cases: List[Case] = []
    ctx = _ctx()
    base = _both(ctx, _act())

    # ---- new-domain valid (equal) ----
    cases.append(Case("D01_valid_both_producers", "equal",
                      "Identical safe mutation from ugence + tool-runtime", cers=base,
                      expect_cp_class="PROCEED"))
    cases.append(Case("D02_diff_provenance", "equal",
                      "Same mutation; provenance differs across producers", cers=base))
    cases.append(Case("D03_diff_objective", "equal",
                      "Same mutation; objective prose differs per producer", cers=base))
    # argument-map insertion order: build the actuation block with reordered keys
    reordered = copy.deepcopy(base["ugence"])
    a = reordered["actuation"]
    reordered["actuation"] = {"reversibility": a["reversibility"], "transaction": a["transaction"],
                              "operation": a["operation"], "expected_row_version": a["expected_row_version"],
                              "affected_scope": a["affected_scope"], "sql_operation": a["sql_operation"],
                              "target": a["target"], "statement_digest": a["statement_digest"],
                              "compensation_ref": a["compensation_ref"]}
    cases.append(Case("D04_argument_order", "equal",
                      "Equivalent actuation with different key insertion order",
                      cers={"ugence": base["ugence"], "reordered": reordered}))

    # ---- expected identity differences ----
    diffs = [
        ("D10_changed_database", _act(connection_ref="prod-orders-replica")),
        ("D11_changed_table", _act(table="line_items")),
        ("D12_changed_operation", _act(sql_operation="INSERT")),
        ("D13_changed_statement", _act(statement_digest="sha256:" + "11" * 32)),
        ("D14_changed_scope", _act(estimated_rows=99)),
        ("D16_changed_state_binding", _act(expected_row_version="orders@v18")),
        ("D17_changed_compensation", _act(compensation_ref="backup:orders:2026-02-02")),
        ("D18_optional_present", _act(parameters_digest="sha256:" + "cc" * 32)),
    ]
    for cid, act in diffs:
        cases.append(Case(cid, "different", f"{cid} differs from base",
                          cers=_both(ctx, act), base_ref="D01_valid_both_producers"))
    # changed principal (authority-semantic) -> different identity
    cases.append(Case("D15_changed_principal", "different",
                      "Different principal -> different identity",
                      cers=_both(_ctx(principal="agent:other-ops"), _act()),
                      base_ref="D01_valid_both_producers"))

    # ---- invalid & security (fail closed) ----
    def _bad(**mut):
        c = copy.deepcopy(base["ugence"])
        for k, v in mut.items():
            c["actuation"][k] = v
        return c

    secret = _bad(); secret["actuation"]["password"] = "hunter2"
    cases.append(Case("I01_raw_credential", "invalid", "Raw credential in actuation",
                      malformed_cer=secret))
    cases.append(Case("I02_unsupported_operation", "invalid", "Unsupported SQL operation",
                      malformed_cer=_bad(sql_operation="DELETE")))
    ambiguous = copy.deepcopy(base["ugence"]); del ambiguous["actuation"]["target"]["table"]
    cases.append(Case("I03_ambiguous_target", "invalid", "Target missing table",
                      malformed_cer=ambiguous))
    cases.append(Case("I04_malformed_identifier", "invalid", "statement_digest not sha256",
                      malformed_cer=_bad(statement_digest="not-a-digest")))
    nan = copy.deepcopy(base["ugence"])
    nan["actuation"]["affected_scope"] = {"estimated_rows": float("nan"), "unbounded": False}
    cases.append(Case("I05_bad_numeric", "invalid", "NaN affected-row count",
                      malformed_cer=nan))
    cases.append(Case("I06_unknown_profile", "invalid", "Unknown profile",
                      malformed_cer={**base["ugence"], "profile": "database.delete.v9"}))
    ext = copy.deepcopy(base["ugence"]); ext["extensions"] = {"x-evil": {"a": "1"}}
    cases.append(Case("I07_unsupported_extension", "invalid", "Non-empty unknown extension",
                      malformed_cer=ext))
    nosb = copy.deepcopy(base["ugence"]); del nosb["state_binding"]["state_hash"]
    cases.append(Case("I08_missing_state_binding", "invalid", "Missing state_binding.state_hash",
                      malformed_cer=nosb))
    downgrade = _bad(replicas="3")  # kubernetes-only field under database profile
    cases.append(Case("I13_profile_downgrade", "invalid", "K8s field under database profile",
                      malformed_cer=downgrade))

    # ---- governance (hold / deny / pending) ----
    cases.append(Case("I09_stale_db_state", "governance",
                      "Stale DB state (expected_row_version drift) -> ACP hold",
                      cers=_both(_ctx(operational=_op(observed_row_version="orders@v18")), _act()),
                      stale=True, expect_cp_class="HELD_BY_ACP"))
    cases.append(Case("I15_unbounded", "deny", "Unbounded mutation -> ActionGate DENY",
                      cers=_both(ctx, _act(unbounded=True)), unbounded=True,
                      expect_cp_class="BLOCKED_BY_AUTHORIZATION"))
    cases.append(Case("D20_missing_simulation", "governance",
                      "No simulation evidence -> PENDING", cers=base,
                      missing_evidence=True, expect_cp_class="PENDING_AUTHORIZATION"))

    # ---- cross-domain evidence transfer + approval replay + bypass ----
    cases.append(Case("I11_k8s_evidence_to_db", "invalid_transfer",
                      "Kubernetes evidence cannot authorize a DB mutation",
                      cers=base, evidence_transfer="k8s_to_db"))
    cases.append(Case("I12_db_evidence_to_k8s", "invalid_transfer",
                      "DB evidence cannot authorize a Kubernetes action",
                      cers=base, evidence_transfer="db_to_k8s"))
    cases.append(Case("I10_modified_after_approval", "invalid_transfer",
                      "Action modified after approval -> approval fails closed",
                      cers=base, approval_replay=True))
    cases.append(Case("I14_direct_bypass", "equal",
                      "Direct db.mutation tool bypass yields no execution identity",
                      cers=base, bypass=True))

    return cases
