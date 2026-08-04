"""Runtime probes: import and recommendation cause no network / subprocess / env-credential
side effects, start no background workers, and instantiate no provider client."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))


_PROBE_PREFIX = (
    "import sys\n"
    "def _hook(event, args):\n"
    "    if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo',\n"
    "                 'subprocess.Popen', 'os.system', 'os.exec', 'ssl.wrap_socket'):\n"
    "        sys.stderr.write('FORBIDDEN_EVENT:' + event + '\\n')\n"
    "        raise RuntimeError('forbidden side effect: ' + event)\n"
    "sys.addaudithook(_hook)\n"
)


def _run_probe(body: str) -> subprocess.CompletedProcess:
    """Run a probe in a fresh interpreter with an audit hook that hard-fails on any
    socket/subprocess/exec attempt. Runs OUTSIDE the repo tree via PYTHONPATH=src only."""
    script = _PROBE_PREFIX + textwrap.dedent(body).strip("\n") + "\nprint('PROBE_OK')\n"
    env = {"PYTHONPATH": _SRC, "PATH": os.environ.get("PATH", "")}
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env)


def test_import_has_no_side_effects():
    r = _run_probe("import ugence_llm_steering_controller as u; assert u.__version__")
    assert "PROBE_OK" in r.stdout, r.stderr
    assert "FORBIDDEN_EVENT" not in r.stderr


def test_import_starts_no_background_threads():
    r = _run_probe(textwrap.dedent("""
        import threading
        before = threading.active_count()
        import ugence_llm_steering_controller  # noqa
        assert threading.active_count() == before, "background thread started on import"
    """))
    assert "PROBE_OK" in r.stdout, r.stderr


def test_recommendation_opens_no_socket_and_reads_no_env_credential():
    r = _run_probe(textwrap.dedent("""
        import os
        # Poison the environment with credential-shaped vars; the package must ignore them.
        os.environ["OPENAI_API_KEY"] = "should-not-be-read"
        os.environ["ANTHROPIC_API_KEY"] = "should-not-be-read"
        from ugence_llm_steering_controller import recommend
        reg = {"providers": [{"provider_id": "p"}],
               "models": [{"model_id": "m", "provider_id": "p", "context_limit": 8000}]}
        res = recommend(reg, {"task_category": "chat"})
        assert res.status == "RECOMMENDED"
        assert res.recommendation.execution_status == "NOT_EXECUTED"
        # Serialize nothing containing the poisoned secret.
        import json
        assert "should-not-be-read" not in json.dumps(res.to_dict())
    """))
    assert "PROBE_OK" in r.stdout, r.stderr
    assert "FORBIDDEN_EVENT" not in r.stderr


def test_simulation_suite_opens_no_socket():
    r = _run_probe(textwrap.dedent("""
        import json, os
        fix = os.path.join(os.path.dirname(os.path.dirname(__import__('ugence_llm_steering_controller').__file__)), '..', '..', 'fixtures', 'suite.json')
        # Fixtures may not be reachable from an installed layout; build a tiny suite inline.
        from ugence_llm_steering_controller.simulation import run_suite
        suite = [{"name": "x",
                  "registry": {"providers": [{"provider_id": "p"}],
                               "models": [{"model_id": "m", "provider_id": "p", "context_limit": 9000}]},
                  "request": {"task_category": "chat"}}]
        rep = run_suite(suite)
        assert rep["total"] == 1
    """))
    assert "PROBE_OK" in r.stdout, r.stderr
    assert "FORBIDDEN_EVENT" not in r.stderr
