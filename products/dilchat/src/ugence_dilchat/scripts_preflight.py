"""Deployment preflight: ``python -m ugence_dilchat.scripts_preflight``.

Validates a deployment BEFORE its processes start serving, so a misconfigured
pilot fails loudly at the gate instead of half-working. Checks, in order:

1. **configuration** — constructing ``Settings`` runs every fail-fast guard
   (debug off, explicit ``postgresql+asyncpg`` DSN, https push URL, signing key,
   approved provider, retention ≥ reporting window, heartbeat sanity).
2. **database** — the DSN actually connects.
3. **role** — the connected role is the one this process is supposed to be
   (``--expect-role`` or ``DILCHAT_EXPECTED_DB_ROLE``). Role separation
   (DEC-3C-4 / I6) is a deployment property: the web process must not be running
   on the worker's credentials, and this is where that gets caught.
4. **schema** — the database's Alembic revision matches the code's head, so no
   process starts against an un-migrated or ahead-of-code database.

Output is a content-free machine-readable summary; exit 0 only when every check
passes. Never prints a DSN, password, key, or token.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

from .config import Settings


def _head_revision() -> str | None:
    """The code's Alembic head, read without importing alembic's runtime."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
    except ImportError:  # pragma: no cover - alembic is a runtime dependency
        return None
    root = pathlib.Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    return ScriptDirectory.from_config(cfg).get_current_head()


async def _database_checks(settings: Settings, expect_role: str | None) -> tuple[dict, bool]:
    import asyncpg

    checks: dict[str, str] = {}
    ok = True
    dsn = settings.database_url.replace("+asyncpg", "")
    try:
        conn = await asyncpg.connect(dsn=dsn)
    except Exception:
        # Deliberately not echoing the driver error: it can embed the DSN.
        return {"database": "UNREACHABLE"}, False
    try:
        checks["database"] = "OK"
        role = await conn.fetchval("SELECT current_user")
        checks["db_role"] = str(role)
        if expect_role and role != expect_role:
            checks["db_role"] = f"MISMATCH expected={expect_role} actual={role}"
            ok = False
        try:
            stamped = await conn.fetchval("SELECT version_num FROM alembic_version")
        except Exception:
            stamped = None
        head = _head_revision()
        if stamped is None:
            checks["schema"] = "NOT_MIGRATED"
            ok = False
        elif head is None:
            checks["schema"] = f"stamped={stamped} (code head unknown)"
        elif stamped != head:
            checks["schema"] = f"MISMATCH stamped={stamped} code_head={head}"
            ok = False
        else:
            checks["schema"] = f"OK at={stamped}"
    finally:
        await conn.close()
    return checks, ok


async def preflight(
    settings: Settings | None = None, *, expect_role: str | None = None
) -> tuple[dict, bool]:
    checks: dict[str, str] = {}
    try:
        settings = settings or Settings()
    except Exception as exc:
        return {"configuration": f"INVALID: {exc}"}, False
    checks["configuration"] = "OK"
    checks["environment"] = settings.environment.value
    # D-PL-1: the pilot runs under `qa` but must mirror production discipline.
    # Surface which posture is actually enforcing, so "voluntary" is visible.
    checks["pilot_mode"] = str(settings.pilot_mode)
    checks["strict_config_guards"] = str(
        settings.environment.is_production_like or settings.pilot_mode
    )
    # Posture summary an operator should eyeball before a pilot start.
    checks["astrology_provider"] = settings.astrology_provider
    checks["push_transport"] = settings.push_transport
    checks["retention_purge_enabled"] = str(settings.retention_purge_enabled)

    db_checks, ok = await _database_checks(settings, expect_role)
    checks.update(db_checks)
    return checks, ok


def main() -> None:
    parser = argparse.ArgumentParser(description="DilChat deployment preflight")
    parser.add_argument(
        "--expect-role",
        default=None,
        help="database role this process must be connected as (e.g. dilchat_app)",
    )
    args = parser.parse_args()
    import os

    expect = args.expect_role or os.environ.get("DILCHAT_EXPECTED_DB_ROLE") or None
    checks, ok = asyncio.run(preflight(expect_role=expect))
    print(json.dumps({"preflight": "PASS" if ok else "FAIL", "checks": checks}, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
