"""The entrypoint drops root, or it does not start the worker.

These are the properties the image's non-root posture now rests on, since the Dockerfile
carries no ``USER`` instruction: root is held only to prepare the data directory, the drop
is verified before the worker is exec'd, and every failure path exits rather than
continuing as root. The suite runs unprivileged, so ``os`` is substituted — what is under
test is the order and the refusals, not the kernel's implementation of setuid.
"""

from __future__ import annotations

import importlib.util
import os
import pytest

_SPEC = importlib.util.spec_from_file_location(
    "worker_entrypoint",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "entrypoint.py"),
)
entrypoint = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(entrypoint)


class FakeOs:
    """Enough of ``os`` to record what a root start does, in the order it does it."""

    def __init__(self, *, euid=0, drop_works=True, chown_error=None):
        self.calls: list = []
        self._euid, self._uid, self._gid = euid, euid, euid
        self._drop_works, self._chown_error = drop_works, chown_error
        self.path = os.path

    def geteuid(self): return self._euid
    def getuid(self): return self._uid
    def getgid(self): return self._gid
    def listdir(self, path): self.calls.append(("listdir", path)); return []
    def makedirs(self, path, exist_ok=False): self.calls.append(("makedirs", path))
    def chmod(self, path, mode): self.calls.append(("chmod", path, oct(mode)))

    def chown(self, path, uid, gid):
        if self._chown_error:
            raise self._chown_error
        self.calls.append(("chown", path, uid, gid))

    def setgroups(self, groups): self.calls.append(("setgroups", groups))
    def setgid(self, gid):
        self.calls.append(("setgid", gid))
        if self._drop_works:
            self._gid = gid

    def setuid(self, uid):
        self.calls.append(("setuid", uid))
        if uid == 0 and self._uid != 0:          # regaining root after a real drop
            raise OSError("operation not permitted")
        if self._drop_works:
            self._uid = self._euid = uid

    def execv(self, path, argv): self.calls.append(("execv", path, tuple(argv)))


@pytest.fixture
def run(monkeypatch):
    def _run(fake, data_dir="/var/lib/ugence-review"):
        monkeypatch.setattr(entrypoint, "os", fake)
        monkeypatch.setenv(entrypoint.DATA_DIR_ENV, data_dir)
        monkeypatch.setattr(entrypoint, "pwd", type("p", (), {"getpwuid": staticmethod(lambda _: object())}))
        monkeypatch.setattr(entrypoint, "grp", type("g", (), {"getgrgid": staticmethod(lambda _: object())}))
        fake_env = {entrypoint.DATA_DIR_ENV: data_dir}
        fake.environ = fake_env
        return entrypoint.main([])
    return _run


def test_root_prepares_the_directory_then_drops_then_execs(run):
    fake = FakeOs(euid=0)
    run(fake)
    names = [c[0] for c in fake.calls]

    assert names.index("chown") < names.index("setuid") < names.index("execv"), \
        "the chown must happen while root, and the exec only after the drop"
    assert ("chown", "/var/lib/ugence-review", 10001, 10001) in fake.calls
    assert ("setgroups", []) in fake.calls and ("setgid", 10001) in fake.calls
    assert fake.calls[-1] == ("execv", entrypoint.WORKER_ARGV[0], tuple(entrypoint.WORKER_ARGV))


def test_a_drop_that_does_not_take_refuses_to_exec_the_worker(run):
    fake = FakeOs(euid=0, drop_works=False)
    with pytest.raises(SystemExit) as exit_info:
        run(fake)
    assert exit_info.value.code == 1
    assert "execv" not in [c[0] for c in fake.calls], "the worker must not run as root"


def test_a_directory_root_cannot_prepare_refuses_to_exec_the_worker(run):
    fake = FakeOs(euid=0, chown_error=PermissionError("read-only file system"))
    with pytest.raises(SystemExit) as exit_info:
        run(fake)
    assert exit_info.value.code == 1
    assert "execv" not in [c[0] for c in fake.calls]


def test_an_unprivileged_start_changes_no_ownership_and_execs_directly(run):
    fake = FakeOs(euid=10001)
    run(fake)
    names = [c[0] for c in fake.calls]

    assert names == ["execv"], f"nothing but the exec should happen unprivileged, got {names}"


def test_the_worker_is_the_only_thing_exec(run):
    assert entrypoint.WORKER_ARGV[1:] == ["-m", "governed_runtime_worker"]
