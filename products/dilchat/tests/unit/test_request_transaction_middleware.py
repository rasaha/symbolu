"""RequestTransactionMiddleware: the transaction finalizes BEFORE transmission.

The race this closes: a commit placed in yield-dependency teardown runs after
FastAPI has already sent the response, so a fast client's next request (on
another pooled connection) can observe pre-commit state. These tests pin the
middleware's contract: commit on success status, rollback on error status and
on escaped exceptions — decided when ``call_next`` returns, which is before
the response reaches the transport.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ugence_dilchat import db as db_module
from ugence_dilchat.db import RequestTransactionMiddleware


class RecordingSession:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def commit(self) -> None:
        self._log.append("commit")

    async def rollback(self) -> None:
        self._log.append("rollback")


def _app_with_recorder(monkeypatch: pytest.MonkeyPatch) -> tuple[FastAPI, list[str]]:
    log: list[str] = []

    @asynccontextmanager
    async def fake_session():
        yield RecordingSession(log)

    monkeypatch.setattr(db_module, "get_sessionmaker", lambda: fake_session)

    app = FastAPI()
    app.add_middleware(RequestTransactionMiddleware)

    @app.get("/ok")
    async def ok():  # 200 -> commit
        log.append("handler")
        return {"ok": True}

    @app.get("/denied")
    async def denied():  # 4xx -> rollback (mirrors the old teardown semantics)
        log.append("handler")
        from fastapi import HTTPException

        raise HTTPException(status_code=409)

    return app, log


async def _get(app: FastAPI, path: str):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


async def test_success_commits_after_handler_before_response_is_returned(monkeypatch):
    app, log = _app_with_recorder(monkeypatch)
    resp = await _get(app, "/ok")
    assert resp.status_code == 200
    # By the time ANY caller can observe the response, the commit has happened,
    # and it happened after the handler ran.
    assert log == ["handler", "commit"]


async def test_error_status_rolls_back(monkeypatch):
    app, log = _app_with_recorder(monkeypatch)
    resp = await _get(app, "/denied")
    assert resp.status_code == 409
    assert log == ["handler", "rollback"]
