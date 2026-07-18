"""Thin CLI for the isolated experiment.

    python3 -m action_gateway_isolated.cli <deploy|run|baselines|status|teardown|verdict>

Never prints private keys, bearer tokens, or secret contents.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from . import layout

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _sh(script):
    return subprocess.run(["bash", str(_SCRIPTS / script)]).returncode


def cmd_deploy(_):
    return _sh("deploy.sh")


def cmd_teardown(_):
    return _sh("teardown.sh")


def cmd_run(_):
    from . import run
    return run.main()


def cmd_verdict(_):
    p = layout.RUNTIME_DIR / "redteam_results.json"
    if not p.exists():
        print(json.dumps({"verdict": "ISOLATION_NOT_PROVEN",
                          "reason": "no run recorded; run 'deploy' then 'run'"}))
        return 2
    d = json.loads(p.read_text())
    print(json.dumps({"verdict": d["verdict"], "environment": d["environment"]}, indent=2))
    return 0


def cmd_baselines(_):
    from action_gateway_k8s import cluster
    from . import baselines
    admin = cluster.admin_client()
    mx = baselines.matrix(admin, cluster.SERVER, str(cluster.CA_CERT), redteam_supported=True)
    print(json.dumps(mx, indent=2))
    return 0


def cmd_status(_):
    from action_gateway_k8s import cluster
    print(json.dumps({"cluster": cluster.is_available(),
                      "gateway_socket": layout.GATEWAY_SOCK.exists(),
                      "replay_db": layout.REPLAY_DB.exists(),
                      "audit_db": layout.AUDIT_DB.exists()}, indent=2))
    return 0


def main(argv=None):
    argv = argv or sys.argv[1:]
    cmds = {"deploy": cmd_deploy, "teardown": cmd_teardown, "run": cmd_run,
            "verdict": cmd_verdict, "baselines": cmd_baselines, "status": cmd_status}
    if not argv or argv[0] not in cmds:
        print("usage: cli <deploy|run|baselines|status|teardown|verdict>", file=sys.stderr)
        return 1
    return cmds[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(main())
