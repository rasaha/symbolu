"""Shared database-mutation actuation model (CER V0.3).

One request -> identical identity across independent producers; each producer
stamps its own (non-identity) provenance. The ``DbContext`` carries authority +
state binding + policy; ``DbActuation`` carries the identity-bearing payload and
the flat tool-call args a database tool would receive. A generic tool-runtime
adapter reconstructs the actuation block from intercepted tool-call args; the
native producer uses it directly. Both converge on the same CER identity.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict


@dataclass(frozen=True)
class DbContext:
    principal: str
    permissions: tuple
    delegator_id: str
    resource_version: str
    state_hash: str
    as_of: str
    operational: Dict[str, Any]   # database operational-safety fixture facts
    policy_version: str
    policy_digest: str
    correlation_id: str
    sequence_id: str = "1"
    delegation_grant: str = "*"
    risk_tier: str = "GOVERNED"

    def envelope_sections(self) -> dict:
        return {
            "authority": {
                "principal": self.principal, "permissions": list(self.permissions),
                "delegator": {"id": self.delegator_id, "type": "HUMAN"},
                "delegation_chain": [{"grant": self.delegation_grant}],
            },
            "state_binding": {
                "resource_version": self.resource_version, "state_hash": self.state_hash,
                "as_of": self.as_of, "source": "database",
                "correlation_id": self.correlation_id, "sequence_id": self.sequence_id,
                "operational": dict(self.operational),
            },
            "policy_ref": {"version": self.policy_version, "digest": self.policy_digest},
        }

    def with_(self, **over) -> "DbContext":
        return replace(self, **over)


@dataclass(frozen=True)
class DbActuation:
    connection_ref: str
    schema: str
    table: str
    sql_operation: str
    statement_digest: str
    estimated_rows: int
    expected_row_version: str
    unbounded: bool = False
    isolation: str = "SERIALIZABLE"
    txn_mode: str = "in_transaction"
    compensation_ref: str = ""
    parameters_digest: str = ""
    predicate_digest: str = ""
    reversibility: str = "REVERSIBLE_WITH_COST"
    PROFILE = "database.mutation.v1"

    def tool_args(self) -> dict:
        args = {
            "connection_ref": self.connection_ref, "schema": self.schema, "table": self.table,
            "sql_operation": self.sql_operation, "statement_digest": self.statement_digest,
            "estimated_rows": self.estimated_rows, "unbounded": self.unbounded,
            "isolation": self.isolation, "transaction_mode": self.txn_mode,
            "expected_row_version": self.expected_row_version,
            "reversibility": self.reversibility,
        }
        if self.compensation_ref:
            args["compensation_ref"] = self.compensation_ref
        if self.parameters_digest:
            args["parameters_digest"] = self.parameters_digest
        if self.predicate_digest:
            args["predicate_digest"] = self.predicate_digest
        return args

    def actuation_block(self) -> dict:
        block: Dict[str, Any] = {
            "operation": "DB_MUTATION",
            "target": {"connection_ref": self.connection_ref, "schema": self.schema,
                       "table": self.table},
            "sql_operation": self.sql_operation,
            "statement_digest": self.statement_digest,
            "affected_scope": {"estimated_rows": str(self.estimated_rows),
                               "unbounded": bool(self.unbounded)},
            "transaction": {"mode": self.txn_mode, "isolation": self.isolation},
            "expected_row_version": self.expected_row_version,
            "reversibility": self.reversibility,
        }
        if self.parameters_digest:
            block["parameters_digest"] = self.parameters_digest
        if self.predicate_digest:
            block["predicate_digest"] = self.predicate_digest
        if self.compensation_ref:
            block["compensation_ref"] = self.compensation_ref
        return block


def actuation_block_from_tool_args(args: dict) -> dict:
    """Rebuild the CER actuation block from intercepted db.mutation tool-call args."""
    act = DbActuation(
        connection_ref=args["connection_ref"], schema=args["schema"], table=args["table"],
        sql_operation=args["sql_operation"], statement_digest=args["statement_digest"],
        estimated_rows=int(args["estimated_rows"]),
        expected_row_version=args["expected_row_version"],
        unbounded=bool(args.get("unbounded", False)),
        isolation=args.get("isolation", "SERIALIZABLE"),
        txn_mode=args.get("transaction_mode", "in_transaction"),
        compensation_ref=args.get("compensation_ref", ""),
        parameters_digest=args.get("parameters_digest", ""),
        predicate_digest=args.get("predicate_digest", ""),
        reversibility=args.get("reversibility", "REVERSIBLE_WITH_COST"))
    return act.actuation_block()


def assemble_cer(ctx: DbContext, actuation_block: dict, provenance: dict) -> dict:
    cer = {
        "cer_version": "0.2", "profile": DbActuation.PROFILE, "risk_tier": ctx.risk_tier,
        "actuation": actuation_block, "provenance": provenance,
    }
    cer.update(ctx.envelope_sections())
    return cer
