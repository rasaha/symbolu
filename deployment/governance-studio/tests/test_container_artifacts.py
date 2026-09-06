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
    assert cfg["data_classification"] == "SYNTHETIC_DEMONSTRATION_ONLY"
    assert "agent_execution" in cfg["prohibited"]
    assert cfg["frozen"]["openapi_sha256"] == "dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656"
    # CR-2: v2 is served behind v1; its contract is frozen by hash exactly as v1's is.
    assert cfg["frozen"]["api_v2_contract"] == "governance_studio.api.v2"
    assert cfg["frozen"]["openapi_v2_sha256"] == _sha256(
        os.path.join(HERE, "..", "..", "apps", "ugence-governance-studio", "contracts", "openapi_v2.json"))
    assert cfg["frozen"]["served_api"].startswith("create_combined_app")


def test_approved_runtime_config_permits_exactly_one_egress_the_review_relay():
    """CR-2 amended the egress claim from none to one named destination. The record
    stays exact: default none, one permitted destination, https, the six review
    routes (five since CR-2, the start relay since FD-10.4), the one forwarded header,
    and gate evidence recorded as unset."""
    import json
    cfg = json.load(open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8"))
    egress = cfg["external_network_egress"]
    assert egress["default"] == "none"
    (permitted,) = egress["permitted"]
    assert "UGENCE_STUDIO_REVIEW_SERVICE_URL" in permitted["destination"]
    assert permitted["scheme"] == "https"
    assert len(permitted["routes"]) == 7 and permitted["routes"][4] == "POST /review/decisions"
    assert permitted["routes"][6] == "GET /review/audit/{correlation_id}"
    assert permitted["routes"][5] == "POST /review/runs"
    assert permitted["forwarded_header"].startswith("X-Ugence-Approver-Proof")
    assert "unset" in egress["container_gate_note"]
    assert list(cfg["configuration_added"]) == ["UGENCE_STUDIO_REVIEW_SERVICE_URL",
                                                "UGENCE_STUDIO_CONSTITUTION_REGISTRY_PATH",
                                                "UGENCE_STUDIO_TENANT_ID",
                                                "UGENCE_STUDIO_POLICY_IDENTITIES",
                                                "UGENCE_STUDIO_SIMULATION_PROVIDER",
                                                "UGENCE_STUDIO_SYSTEM_REGISTRY_PATH"]
    assert cfg["deployment_version"] == "0.8.0"


def test_approved_runtime_config_records_front_door_seam_3_exactly():
    """FD-7: the provider registry is handed (one pinned in-image provider); the hook
    stays the runtime default and a permissive one is prohibited; the decision store
    and console stay absent; seam 2 unchanged; packages unchanged (no new package)."""
    import json
    cfg = json.load(open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8"))
    seams = cfg["front_door_seams"]
    assert [s.split(" ")[0] for s in seams["handed_to_build_studio_context"]] == [
        "review_service_base_url", "activation_root", "policy_registry", "policy_identities",
        "provider_registry", "system_registry"]
    assert [s.split(" ")[0] for s in seams["absent_by_ruling"]] == [
        "decision_store", "governance_hook", "console_base_url"]
    assert "RUNTIME_DEFAULT_BLOCK" in seams["absent_by_ruling"][1]
    assert "refused" in seams["tenant_binding"] and "never displayed" in seams["tenant_binding"]
    assert "prohibition stands" in seams["persistent_database"]
    assert "read-only, tenant-bound" in cfg["constitution_registry"]["reachable_acts"]
    sim = cfg["simulation"]
    from governance_studio_deployment.simulation import (
        SIMULATION_PROVIDER_ID, SIMULATION_PROVIDER_MATURITY, SIMULATION_PROVIDER_VERSION,
        StudioSimulationProvider,
    )
    assert sim["provider"]["provider_id"] == SIMULATION_PROVIDER_ID == StudioSimulationProvider.provider_id
    assert sim["provider"]["version"] == SIMULATION_PROVIDER_VERSION == StudioSimulationProvider.version
    assert sim["provider"]["maturity"] == SIMULATION_PROVIDER_MATURITY
    assert sim["provider"]["implementation"].endswith("simulation.StudioSimulationProvider")
    assert sim["modes"] == ["DRY_RUN", "SIMULATION", "SHADOW"] and "LIVE" not in sim["modes"]
    assert "GOVERNANCE_NOT_CONFIGURED" in sim["governance_hook"]
    assert "prohibited" in sim["permissive_hook"] and "refuse_permissive_hook" in sim["permissive_hook"]
    assert sim["composition_record"].startswith("composition-record.json")
    # FD-7.1: the prohibition keeps its identifier and carries its ruled definition
    assert "agent_execution" in cfg["prohibited"]
    assert cfg["prohibited_definitions"]["agent_execution"].startswith(
        "agent execution against any non-fixture provider")
    assert "external_tool_calls" in cfg["prohibited"] and "external_model_calls" in cfg["prohibited"]
    assert len(cfg["first_party_packages_in_image"]) == 13


def test_approved_runtime_config_records_the_constitution_registry_seam_exactly():
    """Front-door seam 1 (FD-5): a sqlite file under the runtime volume, deny-by-default
    trust, no key material, preflight only, and the persistent-database prohibition
    standing. The image's first-party package list is pinned against the Dockerfile."""
    import json
    cfg = json.load(open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8"))
    seam = cfg["constitution_registry"]
    assert "SqlitePolicyRegistry" in seam["store"] and "/var/run/ugence-studio" in seam["store"]
    assert "no key material" in seam["trust"] and "DenyAll" in seam["trust"]
    assert seam["reachable_acts"].startswith("preflight only")
    assert "persistent_database" in cfg["prohibited"] and "persistent_database" in seam["durability"]
    assert cfg["writable_paths"] == ["/tmp", "/var/run/ugence-studio"]
    assert seam["composition_record"].startswith("composition-record.json")
    df = _read("Dockerfile")
    for distribution in cfg["first_party_packages_in_image"]:
        assert f"COPY {distribution} /build/" in df, distribution
    assert len(cfg["first_party_packages_in_image"]) == 13


def _sha256(path: str) -> str:
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def test_approved_runtime_config_records_front_door_seam_5_exactly():
    """FD-9: the tenant-bound system registry file is handed; register is the only
    write; the registrant is presented and unproven; the v2 amendment is recorded; one
    package added to the image (ai-system-registry) and nothing else."""
    import json
    cfg = json.load(open(os.path.join(HERE, "approved-runtime-config.json"), encoding="utf-8"))
    seam = cfg["system_registry"]
    assert "SqliteSystemRegistry" in seam["store"] and "/var/run/ugence-studio" in seam["store"]
    assert "no server, no driver, no DSN" in seam["store"]
    assert "never re-bound" in seam["tenant_binding"] and "typed refusal" in seam["tenant_binding"]
    assert "PRESENTED_UNPROVEN" in seam["registrant"]
    assert seam["reachable_acts"].startswith("register (the only write")
    assert "no edit, revocation, gate, admission, promotion or attestation" in seam["reachable_acts"]
    assert "v2_registry_register" in seam["contract"]
    assert seam["composition_record"].startswith("composition-record.json")
    assert "persistent_database" in cfg["prohibited"] and "prohibited persistent_database" in seam["durability"]
    assert cfg["first_party_packages_in_image"][-1] == "packages/integration/ai-system-registry"
    assert "COPY packages/integration/ai-system-registry /build/" in _read("Dockerfile")
    assert "openapi_v2_amendment" in cfg["frozen"] and "v2-A1" in cfg["frozen"]["openapi_v2_amendment"]
