"""Offline password-hash generator (P3E §9).

    python -m governance_studio_deployment.generate_password_hash

Reads the password from a TTY prompt (or stdin when piped), prints ONLY the hash to
stdout. The original password is never printed or logged.
"""
from __future__ import annotations

import getpass
import sys

from .passwords import hash_password, verify_password


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if sys.stdin.isatty():
        pw = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm: ")
        if pw != confirm:
            sys.stderr.write("passwords do not match\n")
            return 2
    else:
        pw = sys.stdin.readline().rstrip("\n")
    if not pw:
        sys.stderr.write("empty password\n")
        return 2
    encoded = hash_password(pw)
    assert verify_password(pw, encoded)  # self-check; never prints the password
    sys.stdout.write(encoded + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
