"""Fix the mounted volume's ownership as root, then drop to the worker's uid and exec.

**Why this file exists.** The three SQLite stores live under ``UGENCE_REVIEW_DATA_DIR``,
which on a managed host is a mounted volume rather than the directory the image created.
A freshly provisioned volume is owned by root and the mount discards the image's
build-time ``chown``, so a container that has already dropped to uid 10001 cannot create
its stores and dies on ``sqlite3.OperationalError: unable to open database file``. The
platform's escape hatch is to run the whole worker as root (Railway's ``RAILWAY_RUN_UID=0``),
which fixes the write and discards the non-root posture with it.

This entrypoint takes the narrower path: hold root exactly long enough to chown the data
directory, drop every privilege, and only then exec the worker. The worker itself never
runs with a privilege this file could have kept.

**It never exec's the worker as root.** If the drop does not verify, or root cannot make
the directory writable, it exits non-zero rather than continuing — a worker running as
root is not a degraded success. Started as an unprivileged user (the platform already
dropped, or no volume is involved), it changes nothing and exec's directly, so the file is
inert wherever it is not needed.

Standard library only, and no import from the worker: this runs before the application
exists and must not fail for any reason the application could introduce.
"""

from __future__ import annotations

import grp
import os
import pwd
import sys

#: The account the image creates and the worker is expected to run as.
WORKER_UID = 10001
WORKER_GID = 10001

#: What is exec'd once privileges are gone. The module's own entry point.
WORKER_ARGV = [sys.executable, "-m", "governed_runtime_worker"]

#: Where the stores live. The image sets this; the deployment may override it.
DATA_DIR_ENV = "UGENCE_REVIEW_DATA_DIR"
DEFAULT_DATA_DIR = "/var/lib/ugence-review"


def _fail(message: str) -> "NoReturn":  # type: ignore[valid-type]
    sys.stderr.write(f"ENTRYPOINT_REFUSED: {message}\n")
    raise SystemExit(1)


def prepare_data_dir(data_dir: str, *, uid: int = WORKER_UID, gid: int = WORKER_GID) -> None:
    """Make ``data_dir`` exist and belong to the worker. Root only; never recursive.

    Only the directory itself and its immediate entries are chowned: a volume carrying a
    previous deployment's stores must become writable, and nothing outside the data
    directory is ever touched.
    """
    os.makedirs(data_dir, exist_ok=True)
    os.chown(data_dir, uid, gid)
    os.chmod(data_dir, 0o700)
    for name in os.listdir(data_dir):
        path = os.path.join(data_dir, name)
        if not os.path.islink(path):
            os.chown(path, uid, gid)


def drop_privileges(*, uid: int = WORKER_UID, gid: int = WORKER_GID) -> None:
    """Become the worker's uid irrecoverably, and prove it before returning."""
    os.setgroups([])
    os.setgid(gid)
    os.setuid(uid)
    if os.getuid() != uid or os.geteuid() != uid or os.getgid() != gid:
        _fail("privileges were not dropped; refusing to run the worker as root")
    try:  # a real drop cannot be undone
        os.setuid(0)
    except OSError:
        return
    _fail("root is still reachable after the drop; refusing to run the worker")


def main(argv: "list[str] | None" = None) -> int:
    data_dir = os.environ.get(DATA_DIR_ENV) or DEFAULT_DATA_DIR
    if os.geteuid() == 0:
        try:
            pwd.getpwuid(WORKER_UID) and grp.getgrgid(WORKER_GID)
        except KeyError:
            _fail(f"uid {WORKER_UID}/gid {WORKER_GID} does not exist in this image")
        try:
            prepare_data_dir(data_dir)
        except OSError as exc:
            _fail(f"root could not prepare {data_dir!r}: {exc}")
        drop_privileges()
        sys.stderr.write(
            f"entrypoint: prepared {data_dir} and dropped to uid {WORKER_UID}\n")
    elif os.geteuid() != WORKER_UID:
        # Already unprivileged, but not as the account the image provisioned. Say so and
        # continue: the deployment chose this, and the worker's own failure will be clearer.
        sys.stderr.write(
            f"entrypoint: running as uid {os.geteuid()}, not {WORKER_UID}; "
            f"{data_dir} must already be writable by this user\n")
    os.execv(WORKER_ARGV[0], WORKER_ARGV + list(argv or []))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
