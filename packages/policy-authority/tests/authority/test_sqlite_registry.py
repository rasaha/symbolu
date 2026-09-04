"""ADR §15.7 — the durable single-node registry (decision D-3, D-22 Posture B).

Proves the SQLite registry keeps every rule the in-memory reference keeps
(parity script), adds what §15.7 asked for (durability across reopen, single-host
coordination across processes, revocation visible to every process at once,
append-only tables, a hash-linked ledger), rehydrates every shipped family
faithfully enough that trusted resolution succeeds from a cold start, and
declares exactly what it claims on the consistency descriptor.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import sqlite3
import tempfile
from dataclasses import replace

import pytest

from _authority_fixtures import (
    ALL_FAMILIES,
    ONE_SECOND,
    T_MID,
    coordinate_of,
    make_authority,
    make_policy,
    registry_snapshot,
)
from ugence_policy_authority.api import (
    InMemoryPolicyRegistry,
    PolicyArtifactCodec,
    PolicyRegistry,
    PolicyRegistryConflictError,
    PolicyRegistryConsistencyClaim,
    PolicyRegistryConsistencyDescriptor,
    PolicyRegistryConsistencyScope,
    PolicyRegistryProductionModeError,
    PolicyRegistryStorageError,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    PolicyRevocationReasonCode,
    PolicySupersessionRecord,
    SQLITE_REGISTRY_SCHEMA_VERSION,
    SqlitePolicyRegistry,
    UnsupportedPolicyArtifactError,
    UviPolicyArtifactCodec,
    declared_consistency,
    revoke_policy,
)
from ugence_uvi_policy_contracts.api import PolicyFamily, PolicyScope

CLAIMED = PolicyRegistryConsistencyClaim.CLAIMED_WITHIN_DECLARED_SCOPE
DISCLAIMED = PolicyRegistryConsistencyClaim.EXPLICITLY_DISCLAIMED


def _path(tmp_path=None) -> str:
    return os.path.join(str(tmp_path or tempfile.mkdtemp(prefix="pa-")), "registry.sqlite3")


def _sqlite(path) -> SqlitePolicyRegistry:
    return SqlitePolicyRegistry(path, codec=UviPolicyArtifactCodec())


@pytest.fixture
def path(tmp_path):
    return _path(tmp_path)


@pytest.fixture
def registry(path):
    r = _sqlite(path)
    yield r
    r.close()


# --------------------------------------------------------------------------- #
# Protocol, descriptor, production posture
# --------------------------------------------------------------------------- #
def test_the_sqlite_registry_satisfies_the_protocol_and_keeps_its_surface_narrow(registry):
    assert isinstance(registry, PolicyRegistry)
    for forbidden in ("latest", "current", "newest", "find_by_id", "resolve_latest", "head",
                      "search", "query", "delete", "remove", "update", "replace", "clear",
                      "pop", "overwrite"):
        assert not hasattr(registry, forbidden), forbidden


def test_consistency_descriptors_claim_exactly_what_each_scope_provides(registry):
    durable = declared_consistency(registry)
    local = declared_consistency(InMemoryPolicyRegistry())
    assert durable.scope is PolicyRegistryConsistencyScope.SINGLE_NODE_DURABLE
    assert local.scope is PolicyRegistryConsistencyScope.PROCESS_LOCAL_ONLY
    for name in ("process_local_atomicity", "read_after_write"):
        assert getattr(durable, name) is CLAIMED and getattr(local, name) is CLAIMED
    for name in ("durability", "multi_process_coordination", "cross_process_atomic_revocation"):
        assert getattr(durable, name) is CLAIMED, name
        assert getattr(local, name) is DISCLAIMED, name
    for name in ("distributed_strong_consistency", "eventual_consistency_safety"):
        assert getattr(durable, name) is DISCLAIMED and getattr(local, name) is DISCLAIMED
    # An undeclared registry is never assumed stronger than process-local.
    assert declared_consistency(object()).scope is PolicyRegistryConsistencyScope.PROCESS_LOCAL_ONLY
    # No assignment path: the answers are properties, not fields.
    assert [f for f in PolicyRegistryConsistencyDescriptor.__dataclass_fields__] == ["scope"]
    with pytest.raises(Exception):
        PolicyRegistryConsistencyDescriptor("DURABLE")  # type: ignore[arg-type]


def test_reference_registries_are_refused_in_production_mode(path):
    with pytest.raises(PolicyRegistryProductionModeError):
        InMemoryPolicyRegistry(production_mode=True)
    with pytest.raises(PolicyRegistryProductionModeError):
        SqlitePolicyRegistry(":memory:", codec=UviPolicyArtifactCodec(), production_mode=True)
    r = SqlitePolicyRegistry(path, codec=UviPolicyArtifactCodec(), production_mode=True)
    assert r.production_mode is True
    r.close()
    with pytest.raises(PolicyRegistryStorageError):
        SqlitePolicyRegistry(path, codec=object())  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Parity with the in-memory reference
# --------------------------------------------------------------------------- #
def _script(registry) -> list:
    """One operation sequence; outcomes are values or exception class names."""

    log: list = []

    def step(fn):
        try:
            log.append(fn())
        except Exception as exc:  # noqa: BLE001 — parity of classes is the point
            log.append(type(exc).__name__)

    authority = make_authority(registry=registry)
    policy = make_policy()
    record = authority.issue(policy, record_id="rec-1")
    coordinate = coordinate_of(policy)
    step(lambda: registry.get_issued(coordinate) == record)
    step(lambda: registry.append_issuance(record) == record)                     # idempotent
    step(lambda: registry.append_issuance(replace(record, record_id="rec-2")))    # conflict
    rival = make_authority().issue(make_policy(overrides={"governed_outcome_unit": "other"}),
                                   record_id="rec-3")
    step(lambda: registry.append_issuance(rival))                                # slot conflict
    step(lambda: registry.get_issued(replace(coordinate, tenant_id="other")))    # cross-tenant miss
    step(lambda: registry.get_issued("pol-1"))                                   # non-coordinate
    step(lambda: registry.revocations_for(coordinate))
    other = make_policy(version="2.0.0")
    step(lambda: authority.issue(other, record_id="rec-4").record_id)
    step(lambda: [r.record_id for r in registry.issued_records_for_identity(
        policy_family=coordinate.policy_family, policy_id=coordinate.policy_id,
        scope=coordinate.scope, tenant_id=coordinate.tenant_id)])
    step(lambda: revoke_policy(reference=policy.reference, revocation_id="rv-1",
                               reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
                               registry=registry, adapters=authority.adapters,
                               signer=authority.revocation_signer,
                               signature_verifier=authority.key_ring,
                               revoked_at=T_MID + ONE_SECOND).revocation_id)
    step(lambda: len(registry.revocations_for(coordinate)))
    step(lambda: registry.revocations_for(coordinate)[0] == registry.append_revocation(
        registry.revocations_for(coordinate)[0]))                                # idempotent
    step(lambda: registry.append_revocation(replace(registry.revocations_for(coordinate)[0],
                                                    revocation_id="rv-2")))      # conflict
    step(lambda: authority.resolve(policy.reference, as_of=T_MID + 2 * ONE_SECOND).reason.value)
    step(lambda: authority.resolve(other.reference).status.value)
    return log


def test_parity_with_the_in_memory_reference(registry):
    reference = _script(InMemoryPolicyRegistry())
    assert _script(registry) == reference
    assert reference.count("PolicyRegistryConflictError") == 3
    assert "REVOKED" in reference and "RESOLVED" in reference


# --------------------------------------------------------------------------- #
# Durability and cold-start trusted resolution, every shipped family
# --------------------------------------------------------------------------- #
def test_every_family_resolves_from_a_cold_start(path):
    first = _sqlite(path)
    authority = make_authority(registry=first)
    policies = {fam: make_policy(fam, policy_id=f"p-{fam.value.lower()}") for fam in ALL_FAMILIES}
    records = {fam: authority.issue(pol, record_id=f"rec-{fam.value.lower()}")
               for fam, pol in policies.items()}
    first.close()

    reopened = _sqlite(path)
    cold = make_authority(registry=reopened)
    for fam, pol in policies.items():
        got = reopened.get_issued(coordinate_of(pol))
        assert got == records[fam], fam
        assert type(got.policy) is type(pol) and got.policy == pol
        assert got.policy is not pol  # rebuilt, not cached
        resolution = cold.resolve(pol.reference)
        assert resolution.status is PolicyResolutionStatus.RESOLVED, (fam, resolution.reason)
        assert resolution.record == records[fam]
    assert reopened.verify_chain()
    reopened.close()


def test_a_stored_record_the_codec_cannot_rehydrate_fails_closed(path):
    class RefusingCodec:
        def encode(self, policy):
            return UviPolicyArtifactCodec().encode(policy)

        def decode(self, *, adapter_id, policy_type, canonical):
            raise UnsupportedPolicyArtifactError("this deployment decodes nothing")

    assert isinstance(RefusingCodec(), PolicyArtifactCodec)
    seeded = _sqlite(path)
    policy = make_policy()
    make_authority(registry=seeded).issue(policy)
    seeded.close()
    blind = SqlitePolicyRegistry(path, codec=RefusingCodec())
    with pytest.raises(PolicyRegistryStorageError, match="cannot rehydrate"):
        blind.get_issued(coordinate_of(policy))  # never None: unreadable is not absent
    blind.close()


def test_a_closed_registry_and_a_foreign_schema_are_storage_errors(path):
    r = _sqlite(path)
    r.close()
    with pytest.raises(PolicyRegistryStorageError):
        r.get_issued(coordinate_of(make_policy()))
    raw = sqlite3.connect(path)
    raw.execute("UPDATE meta SET value='other' WHERE key='schema_version'"); raw.commit(); raw.close()
    with pytest.raises(PolicyRegistryStorageError, match=SQLITE_REGISTRY_SCHEMA_VERSION):
        _sqlite(path)


# --------------------------------------------------------------------------- #
# Single-host coordination: two connections, then N processes
# --------------------------------------------------------------------------- #
def test_a_revocation_committed_on_one_connection_is_seen_by_another_at_once(path):
    a, b = _sqlite(path), _sqlite(path)
    authority_a, authority_b = make_authority(registry=a), make_authority(registry=b)
    policy = make_policy(effective_to=None)
    authority_a.issue(policy)
    assert authority_b.resolve(policy.reference).status is PolicyResolutionStatus.RESOLVED
    revoke_policy(reference=policy.reference, revocation_id="rv-1",
                  reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT, registry=b,
                  adapters=authority_b.adapters, signer=authority_b.revocation_signer,
                  signature_verifier=authority_b.key_ring, revoked_at=T_MID + ONE_SECOND)
    outcome = authority_a.resolve(policy.reference, as_of=T_MID + 2 * ONE_SECOND)
    assert outcome.status is PolicyResolutionStatus.UNRESOLVED
    assert outcome.reason is PolicyResolutionReason.REVOKED
    a.close(); b.close()


def _conflicting_writer(path, barrier, index, queue):
    registry = _sqlite(path)
    policy = make_policy(policy_id="p", version="1.0.0",
                         overrides={"governed_outcome_unit": f"unit-{index}"})
    record = make_authority().issue(policy, record_id=f"rec-{index}")
    barrier.wait()
    try:
        registry.append_issuance(record)
        queue.put(("stored", record.record_id))
    except PolicyRegistryConflictError:
        queue.put(("conflict", record.record_id))
    finally:
        registry.close()


def _identical_writer(path, barrier, index, queue):
    registry = _sqlite(path)
    record = make_authority().issue(make_policy(), record_id="rec-same")
    barrier.wait()
    try:
        stored = registry.append_issuance(record)
        queue.put(("stored", stored == record))
    except Exception as exc:  # noqa: BLE001
        queue.put(("error", type(exc).__name__))
    finally:
        registry.close()


@pytest.mark.skipif("fork" not in mp.get_all_start_methods(), reason="fork start method required")
@pytest.mark.parametrize("worker,expected", [
    (_conflicting_writer, {"stored": 1, "conflict": 11}),
    (_identical_writer, {"stored": 12}),
])
def test_processes_racing_one_identity_slot(path, worker, expected):
    _sqlite(path).close()  # create the schema before forking
    n = sum(expected.values())
    ctx = mp.get_context("fork")
    barrier, queue = ctx.Barrier(n), ctx.Queue()
    procs = [ctx.Process(target=worker, args=(path, barrier, i, queue)) for i in range(n)]
    for p in procs: p.start()
    results = [queue.get(timeout=60) for _ in range(n)]
    for p in procs: p.join(timeout=60)
    assert all(p.exitcode == 0 for p in procs)
    counts = {}
    for kind, _ in results:
        counts[kind] = counts.get(kind, 0) + 1
    assert counts == expected
    check = _sqlite(path)
    assert len(check.issued_records_for_identity(policy_family=PolicyFamily.DOMAIN.value,
                                                 policy_id="p" if worker is _conflicting_writer else "pol-1",
                                                 scope=PolicyScope.GLOBAL.value, tenant_id="")) == 1
    assert check.verify_chain()
    check.close()


# --------------------------------------------------------------------------- #
# Supersession as one act, append-only tables, hash chain
# --------------------------------------------------------------------------- #
def _supersession(predecessor, successor, sid="sup-1"):
    return PolicySupersessionRecord(
        supersession_id=sid, coordinate=predecessor, successor_coordinate=successor,
        superseding_authority_id="ugence.policy-authority", key_id="k", signature_alg="Ed25519",
        signature=b"\x01" * 64, superseded_at=T_MID + ONE_SECOND)


def test_successor_and_supersession_commit_together_or_not_at_all(path):
    registry = _sqlite(path)
    authority = make_authority(registry=registry)
    v1 = make_policy(version="1.0.0")
    v2 = make_policy(version="2.0.0")
    v3 = make_policy(version="3.0.0")
    rec1 = authority.issue(v1, record_id="rec-1")
    rec2 = make_authority().issue(v2, record_id="rec-2")
    rec3 = make_authority().issue(v3, record_id="rec-3")
    c1, c2, c3 = coordinate_of(v1), coordinate_of(v2), coordinate_of(v3)
    issued, stored = registry.append_issuance_with_supersession(rec2, _supersession(c1, c2))
    assert issued == rec2 and stored.successor_coordinate == c2
    before = registry_snapshot(registry)
    # A rival successor for the same predecessor: the supersession conflicts, so
    # the rival's issuance must not survive either.
    with pytest.raises(PolicyRegistryConflictError, match="superseded twice"):
        registry.append_issuance_with_supersession(rec3, _supersession(c1, c3, "sup-2"))
    assert registry.get_issued(c3) is None
    assert registry_snapshot(registry) == before
    registry.close()
    reopened = _sqlite(path)
    assert reopened.supersessions_for(c1) == (stored,)
    assert reopened.get_issued(c1) == rec1 and reopened.get_issued(c2) == rec2
    reopened.close()


def test_tables_are_append_only_and_the_ledger_detects_tampering(path):
    registry = _sqlite(path)
    make_authority(registry=registry).issue(make_policy())
    assert registry.verify_chain()
    raw = sqlite3.connect(path)
    for statement in ("UPDATE issuances SET record_id='x'", "DELETE FROM issuances",
                      "UPDATE ledger_events SET kind='x'", "DELETE FROM ledger_events"):
        with pytest.raises(sqlite3.IntegrityError):
            raw.execute(statement)
    raw.executescript("DROP TRIGGER issuances_no_update; UPDATE issuances SET record_bytes=X'00';")
    raw.close()
    assert registry.verify_chain() is False
    registry.close()


def test_failed_appends_leave_the_durable_store_byte_identical(registry):
    authority = make_authority(registry=registry)
    policy = make_policy()
    good = authority.issue(policy)
    before = registry_snapshot(registry)
    for bad in (replace(good, record_id="other"), replace(good, key_id="other-key")):
        with pytest.raises(PolicyRegistryConflictError):
            registry.append_issuance(bad)
    assert registry_snapshot(registry) == before
    assert registry.get_issued(coordinate_of(policy)) == good
