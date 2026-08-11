"""RA-6 idempotency + concurrency (task §19).

Explicitly covers: duplicate epoch-advance (idempotent), same command twice (one
effect), two distinct advances (monotonic two-step), out-of-order replication
(max epoch wins), duplicate revoke (idempotent), revoke-then-stale-update
(revocation not lost), concurrent tenant updates (isolated). No lost updates,
no rollback, no resurrection.
"""

from __future__ import annotations

import threading

import ra6_scenario as C
from ugence_risk_authority_status_runtime import (
    AuthorityStateExport,
    ReferenceAuthorityStore,
)


def _store_with(*tenants) -> ReferenceAuthorityStore:
    s = ReferenceAuthorityStore()
    for t in tenants:
        s.seed_tenant(t)
    return s


def test_duplicate_epoch_command_same_change_id_advances_once():
    s = _store_with("t")
    e1, c1 = s.advance_epoch("t", "chg-1")
    e2, c2 = s.advance_epoch("t", "chg-1")
    assert (e1, c1) == (2, True)
    assert (e2, c2) == (2, False)
    assert s.current_epoch("t") == 2


def test_two_distinct_advances_are_monotonic_two_step():
    s = _store_with("t")
    s.advance_epoch("t", "a")
    s.advance_epoch("t", "b")
    assert s.current_epoch("t") == 3  # base 1 -> 2 -> 3


def test_out_of_order_replication_max_epoch_wins():
    s = _store_with("t")
    s.merge(AuthorityStateExport("t", epoch=7))
    s.merge(AuthorityStateExport("t", epoch=4))  # stale, ignored
    assert s.current_epoch("t") == 7


def test_duplicate_revoke_idempotent():
    s = _store_with("t")
    assert s.revoke_envelope("t", "e") is True
    assert s.revoke_envelope("t", "e") is False
    assert s.export("t").revoked_envelopes == frozenset({"e"})


def test_revoke_then_stale_cache_update_does_not_lose_revocation():
    s = _store_with("t")
    s.revoke_envelope("t", "e")
    # a stale replicated export (older epoch, no knowledge of the revoke) must not
    # drop the local revocation — merge is grow-only union + max epoch.
    s.merge(AuthorityStateExport("t", epoch=1))
    assert "e" in s.export("t").revoked_envelopes


def test_epoch_rollback_never_resurrects_authority():
    s = _store_with("t")
    s.advance_epoch("t", "a")
    s.advance_epoch("t", "b")
    assert s.current_epoch("t") == 3
    s.merge(AuthorityStateExport("t", epoch=2))  # rollback attempt
    assert s.current_epoch("t") == 3  # unchanged


def test_concurrent_tenant_updates_isolated():
    s = _store_with(*[f"t{i}" for i in range(8)])

    def bump(tenant):
        for n in range(50):
            s.advance_epoch(tenant, f"{tenant}-{n}")

    threads = [threading.Thread(target=bump, args=(f"t{i}",)) for i in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    for i in range(8):
        # base 1 + 50 distinct change_ids = 51, per tenant, no cross-talk
        assert s.current_epoch(f"t{i}") == 51


def test_concurrent_same_tenant_no_lost_updates():
    s = _store_with("t")

    def bump(start):
        for n in range(100):
            s.advance_epoch("t", f"chg-{start}-{n}")

    threads = [threading.Thread(target=bump, args=(k,)) for k in range(5)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    # 5 * 100 distinct change_ids, all applied exactly once: base 1 + 500.
    assert s.current_epoch("t") == 501


def test_concurrent_duplicate_change_id_advances_once():
    s = _store_with("t")

    results = []

    def bump():
        results.append(s.advance_epoch("t", "same-key"))

    threads = [threading.Thread(target=bump) for _ in range(20)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    # Exactly one advance despite 20 concurrent identical commands.
    assert s.current_epoch("t") == 2
    assert sum(1 for _, changed in results if changed) == 1
