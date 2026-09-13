#!/usr/bin/env python3
"""Container entrypoint for the MEU validation job.

A Cloud Run Job runs to completion and exits; this process is that run. The entrypoint
does four things and then gets out of the way:

1. refuses to run as root;
2. refuses to run inside a CI runner, before anything else is imported or read (LP-8);
3. names the configuration file from ``MEU_JOB_CONFIG`` (a PATH, never a secret);
4. execs the job's CLI and returns its exit code.

It reads no credential and no vendor key. The only environment variables it consults are
the CI markers and ``MEU_JOB_CONFIG``.
"""

from __future__ import annotations

import os
import sys

DEFAULT_CONFIG = "/etc/meu-validation-job/config.json"


def main() -> int:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("meu-validation-job refuses to run as root; the image drops to uid 10001", file=sys.stderr)
        return 2

    # LP-8: a CI runner may not possess or exercise the credential, whatever it claims.
    # Checked here so the refusal happens before the job reads a record or a config file.
    from ugence_model_egress_unit import ci_environment_markers_present
    markers = ci_environment_markers_present(
        {name: value for name, value in os.environ.items()})
    if markers:
        print(f"meu-validation-job refuses to run: this process is a CI runner "
              f"({', '.join(markers)} set). Only the deployed MEU instance may possess or "
              f"exercise the credential (LP-8). Offline fake-transport testing runs in "
              f"repository CI through the package suites, not through this job.", file=sys.stderr)
        return 2

    config = os.environ.get("MEU_JOB_CONFIG", DEFAULT_CONFIG)
    if not config.strip():
        print("MEU_JOB_CONFIG names the configuration FILE and must not be empty", file=sys.stderr)
        return 2

    from meu_validation_job.cli import main as job_main
    argv = sys.argv[1:] or ["validate"]
    return job_main([*argv, "--config", config])


if __name__ == "__main__":
    sys.exit(main())
