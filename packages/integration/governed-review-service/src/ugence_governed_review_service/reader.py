"""A read-only façade over the durable stores, for run detail.

The screen/API audit found that no read surface over the durable stores exists outside
the adapter's own ``status()`` and that the studio may never import a database driver.
This module is that façade, on the composition side of the boundary (HR-2): it reads
the checkpoint and the runtime event log the DBOS adapter keeps and returns plain
mappings. It writes nothing, and it never constructs a runtime.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

import sqlalchemy as sa

from ugence_durable_execution.postgres.schema import SCHEMA_NAME

__all__ = ["RunReader", "DbosRunReader", "StaticRunReader"]

@runtime_checkable
class RunReader(Protocol):
    """What the service needs to know about an instance, and nothing more."""

    def checkpoint(self, instance_id: str) -> Optional[Mapping[str, Any]]:
        """The latest checkpoint as a mapping, or ``None`` for an unknown instance."""

    def events(self, instance_id: str) -> Sequence[Mapping[str, Any]]:
        """The full event log, oldest first, each as ``{seq, event_type, body, attempt_token}``."""

class DbosRunReader:
    """Reads the DBOS adapter's tables through the same datasource the adapter uses.

    ``datasource.run_tx_step(None, fn)`` runs ``fn`` in one read-only transaction
    outside any durable workflow, which is exactly how the adapter's own ``status()``
    reads. The state store's ``load`` verifies the checkpoint's integrity digests before
    returning it, so a tampered checkpoint is an error here, never a rendered page.
    """

    def __init__(self, *, datasource: Any, bundle: Any) -> None:
        for name, obj, attr in (("datasource", datasource, "run_tx_step"),
                                ("datasource", datasource, "sql_session"),
                                ("bundle", bundle, "state_store")):
            if not hasattr(obj, attr):
                raise TypeError(f"{name} must provide {attr}")
        self._ds = datasource
        self._bundle = bundle

    def checkpoint(self, instance_id: str) -> Optional[Mapping[str, Any]]:
        def _load() -> Optional[Mapping[str, Any]]:
            ckpt = self._bundle.state_store.load(instance_id)
            return None if ckpt is None else _checkpoint_view(ckpt)

        return self._ds.run_tx_step(None, _load)

    def events(self, instance_id: str) -> Sequence[Mapping[str, Any]]:
        def _read() -> Sequence[Mapping[str, Any]]:
            rows = self._ds.sql_session().execute(
                sa.text(
                    f"SELECT seq, event_type, body, attempt_token FROM {SCHEMA_NAME}.runtime_events "
                    "WHERE instance_id = :i ORDER BY seq ASC"
                ),
                {"i": instance_id},
            ).all()
            out = []
            for seq, event_type, body, token in rows:
                if isinstance(body, str):
                    body = json.loads(body)
                out.append({"seq": int(seq), "event_type": str(event_type or ""),
                            "body": dict(body), "attempt_token": token})
            return tuple(out)

        return self._ds.run_tx_step(None, _read)

class StaticRunReader:
    """A reader over mappings a composition root or a test supplies. Reads only."""

    def __init__(self, checkpoints: Mapping[str, Mapping[str, Any]] = (),
                 events: Mapping[str, Sequence[Mapping[str, Any]]] = ()) -> None:
        self._checkpoints = dict(checkpoints)
        self._events = {k: tuple(v) for k, v in dict(events).items()}

    def checkpoint(self, instance_id: str) -> Optional[Mapping[str, Any]]:
        ckpt = self._checkpoints.get(instance_id)
        return None if ckpt is None else dict(ckpt)

    def events(self, instance_id: str) -> Sequence[Mapping[str, Any]]:
        return self._events.get(instance_id, ())

def _checkpoint_view(ckpt: Any) -> Mapping[str, Any]:
    """The neutral projection of a runtime checkpoint: status, tasks and the latest
    canonical execution state per task. Lineage and digests stay inside the store."""

    states = {}
    for task_id, state in (getattr(ckpt, "execution_states", None) or {}).items():
        state = dict(state)
        states[task_id] = {
            key: state.get(key) for key in (
                "workflow_status", "task_status", "attempt", "provider_id", "operation",
                "idempotency_key", "proposal_fingerprint", "governance_disposition",
                "evaluation_reference", "valid_until",
            )
        }
    return {
        "instance_id": ckpt.instance_id,
        "workflow_id": ckpt.workflow_id,
        "status": str(ckpt.status),
        "correlation_id": ckpt.correlation_id,
        "tasks": {tid: dict(t) for tid, t in (ckpt.tasks or {}).items()},
        "execution_states": states,
        "checkpoint_digest": getattr(ckpt, "digest", ""),
    }
