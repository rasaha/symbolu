"""The authority plane's contract (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md, step 1 of
§11, under rulings AP-1 to AP-5).

    THIS MODULE SERVES NOTHING ITSELF. IT NAMES WHAT THE PLANE SERVES, AND WHAT IT NEVER MAY.

The authority plane is the surface for the acts the Governance Studio is ruled never
to perform: loading and revoking role grants, deciding approvals, activating and
issuing. Under AP-2 its routes belong on this worker, which already owns the stores
they would write. This module is the plane's contract in the same sense the studio's
frozen OpenAPI document is a contract: a committed, drift-tested enumeration that a
route must appear in before it may be served, with a verb test over it.

Two rules shape the enumeration.

**AP-4, the verbs.** The plane may name grant, revoke, activate and issue. It may never
name authorize, clear or execute: those three are runtime authority (ActionGate, the
Autonomous Control Plane, the runtime), and a plane that could name them would be the
control plane under another name. ``tests/test_authority_plane_contract.py`` scans
every operation id, path and summary here, in the shape of the studio's SD-2 test with
the sense reversed.

**AP-3 and AP-5, the gate.** Every write requires an ``IDP_AUTHENTICATED`` subject and
is refused, never recorded as presented, without one. No write is served until the
approver-identity adapter has been validated end to end against at least one real
enterprise issuer (AP-3, controlling; the owner reversed AW-1's sequencing change on
2026-09-07, §18). Reads may ship first, each answer labelled with the identity proof
the deployment can give. The two directory writes, grant and revoke, are implemented
in ``authority_writes.py`` behind that gate and proven against the in-process issuer,
which is implementation and conformance evidence only, never enterprise identity
validation; ``SERVED_WRITES`` stays empty until the owner records that validation.
Activate and issue act on packages this worker does not compose.

``composition.py`` mounts the reads through ``authority_reads.py`` (step 2) and the
writes router, which serves exactly ``SERVED_WRITES`` and so today serves nothing. The
test asserts that no other module names a write path or the directory's write methods,
and that no write path answers on the composed app.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

__all__ = [
    "CONTRACT_SCHEMA",
    "RULING",
    "READS_SERVED",
    "SERVED_WRITES",
    "IMPLEMENTED_WRITES",
    "WRITE_PROOF_HEADER",
    "PERMITTED_VERBS",
    "REFUSED_VERBS",
    "WRITE_GATE",
    "READ_LABEL",
    "PlaneOperation",
    "PLANE_OPERATIONS",
    "REUSED_EXISTING",
    "contract_document",
    "verb_violations",
]

CONTRACT_SCHEMA = "governed-runtime-worker.authority-plane-contract.v1"
RULING = ("ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md AP-1 AUTHORITY_PLANE_ONLY, "
          "AP-2 ADMIN_ROUTES_ON_THE_WORKER, AP-3 IDP_VALIDATED_FIRST, "
          "AP-4 GRANT_REVOKE_ACTIVATE_ISSUE_ONLY, AP-5 READS_FIRST; section 16 "
          "AW-2 DIRECTORY_WRITES_ONLY, AW-5 STRICTER_THAN_DECISIONS; section 18 "
          "AW-1 REVERSED, AP-3 controlling: no write served before enterprise issuer validation")

#: What each step serves. Step 1 served nothing; step 2 (AP-5 READS_FIRST) serves the
#: four reads through ``authority_reads.py``. The two directory writes are implemented
#: in ``authority_writes.py`` and served only when named here; under AP-3 (controlling,
#: section 18) this tuple stays empty until the owner records the adapter's validation
#: against a real enterprise issuer. Activate and issue are never named here: this
#: worker composes neither store (AW-2). These are read by the test and by the record,
#: and change only when a later record says so.
READS_SERVED = True
SERVED_WRITES: tuple[str, ...] = ()

#: The two writes whose implementation exists and is proven against the in-process
#: issuer (implementation and conformance evidence only). Re-serving them is one edit
#: to ``SERVED_WRITES`` once the validation AP-3 requires is recorded.
IMPLEMENTED_WRITES: tuple[str, ...] = ("authority_grant_role", "authority_revoke_grant")

#: The header a write's proof arrives on: the same one the decision route reads
#: (``ugence_governed_review_service.PROOF_HEADER``; a test asserts they are equal).
WRITE_PROOF_HEADER = "X-Ugence-Approver-Proof"

#: AP-4. Matched as substrings, case-insensitively, over operation id, path and summary.
PERMITTED_VERBS: tuple[str, ...] = ("grant", "revoke", "activate", "issue")
REFUSED_VERBS: tuple[str, ...] = ("authorize", "clear", "execute")

#: AP-3. The one condition every write carries.
WRITE_GATE = ("IDP_AUTHENTICATED subject required; a write reached without one is "
              "refused, never recorded as presented (AP-3); a served write also requires "
              "a human subject of this tenant and refuses everything else with a typed "
              "reason (AW-5)")

#: AP-5. What every read answer carries while the deployment cannot prove identity.
READ_LABEL = "identity_proof: the proof the deployment can actually give; PRESENTED_UNPROVEN until AI-C is validated against a real issuer"


@dataclass(frozen=True)
class PlaneOperation:
    operation_id: str
    method: str
    path: str
    summary: str
    #: ``read`` under AP-5 or ``write`` under AP-3.
    kind: str
    #: The one AP-4 verb a write names, or ``""`` for a read.
    names_verb: str
    #: The store or package the operation would act on. Named so the record is honest
    #: about what a write changes; nothing here reaches it.
    acts_on: str
    ruling: str

    def __post_init__(self) -> None:
        if self.kind not in ("read", "write"):
            raise ValueError(f"{self.operation_id}: kind must be read or write")
        if self.kind == "write" and self.names_verb not in PERMITTED_VERBS:
            raise ValueError(f"{self.operation_id}: a write must name one AP-4 verb")
        if self.kind == "read" and self.names_verb != "":
            raise ValueError(f"{self.operation_id}: a read names no verb")

    @property
    def gate(self) -> str:
        return WRITE_GATE if self.kind == "write" else READ_LABEL

    @property
    def served(self) -> bool:
        return READS_SERVED if self.kind == "read" else self.operation_id in SERVED_WRITES


#: The plane, in the order a later step would serve it: reads first (AP-5), then the
#: writes that wait on the identity gate (AP-3). Every path is namespaced under
#: ``/authority/`` so it can never collide with the review service's ``/review/`` routes.
PLANE_OPERATIONS: tuple[PlaneOperation, ...] = (
    # -- reads (AP-5) -------------------------------------------------------- #
    PlaneOperation(
        operation_id="authority_list_grants", method="GET", path="/authority/grants",
        summary="Role grants held by one principal at one instant",
        kind="read", names_verb="",
        acts_on="SqliteAuthorityDirectory.grants_for", ruling="AP-5"),
    PlaneOperation(
        operation_id="authority_list_holders", method="GET", path="/authority/holders",
        summary="Principals holding one role in one scope at one instant",
        kind="read", names_verb="",
        acts_on="SqliteAuthorityDirectory.holders_of", ruling="AP-5"),
    PlaneOperation(
        operation_id="authority_read_committee", method="GET",
        path="/authority/committees/{committee_id}",
        summary="Committee report: members, quorum and whether it is met",
        kind="read", names_verb="",
        acts_on="SqliteAuthorityDirectory.committee_report", ruling="AP-5"),
    PlaneOperation(
        operation_id="authority_read_grant_events", method="GET",
        path="/authority/grants/{grant_id}/events",
        summary="The append-only event history of one role grant",
        kind="read", names_verb="",
        acts_on="SqliteAuthorityDirectory.grant_events", ruling="AP-5"),
    # -- writes (AP-3) ------------------------------------------------------- #
    PlaneOperation(
        operation_id="authority_grant_role", method="POST", path="/authority/grants",
        summary="Load one time-bounded role grant for a principal",
        kind="write", names_verb="grant",
        acts_on="SqliteAuthorityDirectory.put_grant", ruling="AP-3"),
    PlaneOperation(
        operation_id="authority_revoke_grant", method="POST",
        path="/authority/grants/{grant_id}/revoke",
        summary="Revoke one role grant, appending its REVOKED event",
        kind="write", names_verb="revoke",
        acts_on="SqliteAuthorityDirectory.revoke_grant", ruling="AP-3"),
    PlaneOperation(
        operation_id="authority_activate_constitution", method="POST",
        path="/authority/constitutions/{constitution_id}/activate",
        summary="Activate one issued constitution under its activation root",
        kind="write", names_verb="activate",
        acts_on="ugence_agent_constitution_activation (permanently outside the studio)",
        ruling="AP-3"),
    PlaneOperation(
        operation_id="authority_issue_record", method="POST", path="/authority/issuances",
        summary="Issue one policy or constitution record under its authority",
        kind="write", names_verb="issue",
        acts_on="ugence_policy_authority / ugence_agent_constitution_activation",
        ruling="AP-3"),
)

#: AP-5 names the approval queue as a read of the plane. The review service already
#: serves it; the plane reuses that route rather than duplicating it.
REUSED_EXISTING: tuple[tuple[str, str, str], ...] = (
    ("GET", "/review/queue", "review_list_queue"),
)


def verb_violations(operations: tuple[PlaneOperation, ...] = PLANE_OPERATIONS) -> list[str]:
    """AP-4 over operation id, path and summary: any refused verb is a violation."""
    violations: list[str] = []
    for op in operations:
        for field in ("operation_id", "path", "summary"):
            lowered = getattr(op, field).lower()
            for verb in REFUSED_VERBS:
                if verb in lowered:
                    violations.append(f"{op.method} {op.path} -> {field} names '{verb}'")
    return violations


def contract_document() -> dict[str, Any]:
    """The committed rendering, ``authority-plane-contract.json``; drift-tested."""
    return {
        "schema": CONTRACT_SCHEMA,
        "ruling": RULING,
        "served": {"reads": READS_SERVED, "writes": list(SERVED_WRITES)},
        "implemented_unserved_writes": list(IMPLEMENTED_WRITES),
        "implemented_unserved_note": ("implemented in authority_writes.py behind the identity gate and proven "
                                      "against the in-process issuer (implementation and conformance evidence "
                                      "only); not served until the adapter is validated end to end against a "
                                      "real enterprise issuer (AP-3 controlling; AW-1 reversed, section 18)"),
        "write_proof_header": WRITE_PROOF_HEADER,
        "home": "deployment/governed-runtime-worker (AP-2): routes on the review service this worker composes, which owns the stores",
        "permitted_verbs": list(PERMITTED_VERBS),
        "refused_verbs": list(REFUSED_VERBS),
        "write_gate": WRITE_GATE,
        "read_label": READ_LABEL,
        "operations": [
            {**asdict(op), "gate": op.gate, "served": op.served} for op in PLANE_OPERATIONS
        ],
        "reused_existing": [
            {"method": m, "path": p, "operation_id": o,
             "note": "already served by the review service; the plane's approval-queue read (AP-5) reuses it"}
            for m, p, o in REUSED_EXISTING
        ],
        "not_on_the_plane": [
            "authorize, clear, execute: runtime authority, with ActionGate, the Autonomous Control Plane and the runtime (AP-4)",
            "module composition: providers, hooks, seam files; deployment-time, shown read-only by the studio's Status panel (MA-2 as amended)",
            "the console's nine module rows (MS-1)",
            "the tenant emergency stop: Risk Authority's own administrative path",
        ],
    }
