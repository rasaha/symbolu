"""Static structure checks for the container artifacts (P3E §20, §21, §25).

The OCI image cannot be built/run in this environment (no Docker daemon), so these
tests validate the container DEFINITION: non-root, single port, healthcheck, no npm or
compiler in the runtime layer, no embedded secrets, read-only-root compatibility, OCI
labels, and a hardened compose file. Image build/run itself is a CI-gated step.
"""
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name: str) -> str:
    return open(os.path.join(HERE, name), encoding="utf-8").read()


def test_dockerfile_runs_non_root_fixed_uid():
    df = _read("Dockerfile")
    assert "USER 10001:10001" in df
    assert "--uid 10001" in df and "--gid 10001" in df


def test_dockerfile_exposes_only_8443():
    df = _read("Dockerfile")
    exposes = [ln for ln in df.splitlines() if ln.strip().startswith("EXPOSE")]
    assert exposes == ["EXPOSE 8443/tcp"]


def test_dockerfile_has_healthcheck_and_entrypoint():
    df = _read("Dockerfile")
    assert "HEALTHCHECK" in df
    assert 'ENTRYPOINT ["python", "/app/entrypoint.py"]' in df


def test_runtime_layer_has_no_npm_or_compiler_toolchain():
    df = _read("Dockerfile")
    runtime = df.split("AS runtime", 1)[1]
    for banned in ("npm ", "npm ci", "node ", "gcc", "build-essential", "apt-get install"):
        assert banned not in runtime, f"runtime layer references {banned!r}"


def test_multistage_build_present():
    df = _read("Dockerfile")
    assert "AS frontend" in df and "AS backend" in df and "AS runtime" in df


def test_no_embedded_secret_or_production_cert():
    df = _read("Dockerfile")
    for banned in ("PASSWORD=", "server.key", "COPY .env", "tests/certs"):
        assert banned not in df


def test_oci_labels_present():
    df = _read("Dockerfile")
    for label in ("org.opencontainers.image.title", "org.opencontainers.image.version",
                  "org.opencontainers.image.source"):
        assert label in df


def test_dockerignore_excludes_secrets_and_vcs():
    di = _read(".dockerignore")
    for pattern in (".git", "*.key", "**/.env", "tests/certs", "node_modules"):
        assert pattern in di


def test_compose_is_hardened():
    c = _read("compose.private.yml")
    assert "read_only: true" in c
    assert "no-new-privileges:true" in c
    assert "cap_drop" in c and "- ALL" in c
    assert 'user: "10001:10001"' in c
    assert "/var/run/ugence-studio" in c  # tmpfs writable mount
    assert "8443:8443" in c


def test_compose_has_no_inline_secret():
    c = _read("compose.private.yml")
    # secrets come from env/.env references, never inline literals
    assert "PASSWORD_HASH: scrypt$" not in c
    assert "${UGENCE_STUDIO_PASSWORD_HASH" in c


def test_approved_runtime_config_declares_boundaries():
    import json
    cfg = json.load(open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8"))
    assert cfg["exposed_ports"] == ["8443/tcp"]
    assert cfg["read_only_root_filesystem"] is True
    assert cfg["external_network_egress"] == "none"
    assert cfg["data_classification"] == "SYNTHETIC_DEMONSTRATION_ONLY"
    assert "agent_execution" in cfg["prohibited"]
    assert cfg["frozen"]["openapi_sha256"] == "dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656"
