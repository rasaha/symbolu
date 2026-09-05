"""Relay process entry point: ``python -m ugence_dilchat.relay``.

Settings come from the environment (DILCHAT_*), exactly like the API process;
the database credentials used here should belong to the ``dilchat_worker``
role in production. SIGTERM/SIGINT stop the loop after the current batch.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import pathlib
import signal
import tempfile

from ..base import utcnow
from ..config import Settings
from ..db import get_sessionmaker, init_engine
from .transports import build_transport
from .worker import RelayService

log = logging.getLogger("ugence_dilchat.relay")


def write_heartbeat(path: str) -> None:
    """Record liveness as an ISO timestamp — the relay's only health surface.

    Content-free by construction: a timestamp, never an event, token, or
    message. Written atomically (temp file + rename) so a reader never observes
    a half-written stamp, and best-effort: a failing heartbeat must never take
    down a relay that is otherwise delivering.
    """
    try:
        target = pathlib.Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".heartbeat-")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(utcnow().isoformat())
            os.replace(tmp, target)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
    except OSError:
        log.warning("relay heartbeat write failed")


async def run(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    init_engine(settings)
    relay = RelayService(
        settings=settings,
        sessionmaker=get_sessionmaker(),
        transport=build_transport(settings.push_transport, expo_url=settings.expo_push_url),
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    log.info("relay started transport=%s", settings.push_transport)
    next_prune = 0.0
    while not stop.is_set():
        published = await relay.process_batch()
        now = loop.time()
        if now >= next_prune:
            pruned = await relay.prune_published()
            if pruned:
                log.info("relay pruned published_rows=%s", pruned)
            next_prune = now + settings.relay_prune_interval_seconds
        if settings.relay_heartbeat_path:
            write_heartbeat(settings.relay_heartbeat_path)
        if published == 0:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    stop.wait(), timeout=settings.relay_poll_interval_seconds
                )
    log.info("relay stopped")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    asyncio.run(run())


if __name__ == "__main__":
    main()
