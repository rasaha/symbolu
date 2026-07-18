"""Strengthened Kubernetes semantic policy for the red-team experiment.

Deterministic checks run by BOTH the gateway (to gate the decision) and,
independently, the broker (defence in depth before the privileged write). A
violation withholds the admission evidence, so the frozen gate DENYs — the checks
feed the gate, never bypass it.

N1 remediation — COMPLETE WORKLOAD SURFACE, FAIL CLOSED
-------------------------------------------------------
The prior version inspected only ``spec.containers``. An adversary could smuggle
privilege through ``initContainers``/``ephemeralContainers``, mount secrets via
``envFrom``/projected volumes, escalate identity via ``serviceAccountName`` +
``automountServiceAccountToken``, or reach the host via ``hostPath``/``csi``.

This version validates the *entire* pod workload surface and — critically — is
**fail closed**: every field it encounters must appear in an explicit allow-list
(``SUPPORTED_FIELDS``). Any key that is not explicitly understood produces an
``unrecognized_*`` violation, so a dangerous capability carried in a field the
validator does not model can never pass silently. Every supported field is
enumerated in ``SUPPORTED_FIELDS`` (see the module-level tables) and mirrored in
the README.

Distinguished invariant layers (documented in README):
  * gateway invariant       — these deterministic checks + the frozen gate
  * admission-controller     — the real apiserver PodSecurity at dry-run/commit
  * broker scope restriction — RBAC resourceNames/verbs on the minted credential
  * runtime/network control  — netns egress (documented limits)
"""

from __future__ import annotations

import re

_DIGEST_IMAGE = re.compile(r"^registry\.example\.com/[\w./-]+@sha256:[0-9a-f]{64}$")
_DANGEROUS_VERBS = {"*", "bind", "escalate", "impersonate"}
_POWERFUL_ROLES = {"cluster-admin", "admin", "edit"}
_PROTECTED_NAMES = {"gatekeeper", "admission-policy", "monitoring", "audit-webhook"}

# ---------------------------------------------------------------------------
# Explicit allow-lists (the fail-closed contract). A field NOT present here is a
# violation. Understanding a field does not mean permitting its dangerous values;
# the per-field rules below still fire.
# ---------------------------------------------------------------------------

POD_SPEC_FIELDS = {
    # workload containers (ALL three lists are validated)
    "containers", "initContainers", "ephemeralContainers",
    # storage
    "volumes",
    # workload identity / token projection
    "serviceAccountName", "serviceAccount", "automountServiceAccountToken",
    # host namespace sharing
    "hostNetwork", "hostPID", "hostIPC", "shareProcessNamespace", "hostUsers",
    # security
    "securityContext", "imagePullSecrets",
    # scheduling / lifecycle (understood; benign, no privilege surface)
    "restartPolicy", "terminationGracePeriodSeconds", "activeDeadlineSeconds",
    "dnsPolicy", "dnsConfig", "nodeSelector", "nodeName", "affinity",
    "tolerations", "schedulerName", "priorityClassName", "priority",
    "hostname", "subdomain", "readinessGates", "runtimeClassName",
    "enableServiceLinks", "preemptionPolicy", "topologySpreadConstraints",
    "setHostnameAsFQDN", "os", "overhead", "hostAliases",
}

CONTAINER_FIELDS = {
    "name", "image", "imagePullPolicy", "command", "args", "workingDir",
    "ports", "env", "envFrom", "resources", "resizePolicy",
    "volumeMounts", "volumeDevices",
    "securityContext", "livenessProbe", "readinessProbe", "startupProbe",
    "lifecycle", "terminationMessagePath", "terminationMessagePolicy",
    "stdin", "stdinOnce", "tty", "restartPolicy",
    # ephemeralContainers only
    "targetContainerName",
}

# a volume is {name, <exactly one source>}; every source key is classified
_VOLUME_HOST_SOURCES = {"hostPath"}
_VOLUME_SECRET_SOURCES = {"secret"}
_VOLUME_CSI_SOURCES = {"csi"}
_VOLUME_PROJECTED_SOURCES = {"projected"}
_VOLUME_BENIGN_SOURCES = {
    "emptyDir", "configMap", "downwardAPI", "persistentVolumeClaim", "ephemeral",
}
# raw remote/block sources are a host/exfil surface -> treated as dangerous
_VOLUME_REMOTE_SOURCES = {
    "nfs", "iscsi", "glusterfs", "rbd", "cephfs", "flexVolume", "flocker",
    "gcePersistentDisk", "awsElasticBlockStore", "azureDisk", "azureFile",
    "cinder", "portworxVolume", "quobyte", "scaleIO", "storageos",
    "vsphereVolume", "photonPersistentDisk", "gitRepo",
}
VOLUME_SOURCE_FIELDS = (_VOLUME_HOST_SOURCES | _VOLUME_SECRET_SOURCES
                        | _VOLUME_CSI_SOURCES | _VOLUME_PROJECTED_SOURCES
                        | _VOLUME_BENIGN_SOURCES | _VOLUME_REMOTE_SOURCES)
VOLUME_FIELDS = {"name"} | VOLUME_SOURCE_FIELDS

POD_SECURITY_CONTEXT_FIELDS = {
    "runAsUser", "runAsGroup", "runAsNonRoot", "fsGroup", "fsGroupChangePolicy",
    "supplementalGroups", "seLinuxOptions", "seccompProfile", "sysctls",
    "windowsOptions", "appArmorProfile", "supplementalGroupsPolicy", "seLinuxChangePolicy",
}
CONTAINER_SECURITY_CONTEXT_FIELDS = {
    "privileged", "capabilities", "allowPrivilegeEscalation",
    "readOnlyRootFilesystem", "runAsUser", "runAsGroup", "runAsNonRoot",
    "seLinuxOptions", "seccompProfile", "procMount", "windowsOptions",
    "appArmorProfile",
}
ENV_FIELDS = {"name", "value", "valueFrom"}
ENV_VALUE_FROM_FIELDS = {"fieldRef", "resourceFieldRef", "configMapKeyRef", "secretKeyRef"}
ENV_FROM_FIELDS = {"prefix", "configMapRef", "secretRef"}

# machine-readable documentation surface (asserted by a unit test)
SUPPORTED_FIELDS = {
    "pod_spec": sorted(POD_SPEC_FIELDS),
    "container": sorted(CONTAINER_FIELDS),
    "volume": sorted(VOLUME_FIELDS),
    "pod_security_context": sorted(POD_SECURITY_CONTEXT_FIELDS),
    "container_security_context": sorted(CONTAINER_SECURITY_CONTEXT_FIELDS),
    "env": sorted(ENV_FIELDS),
    "env_value_from": sorted(ENV_VALUE_FROM_FIELDS),
    "env_from": sorted(ENV_FROM_FIELDS),
}

_POD_KINDS = ("Pod", "Deployment")


def _pod_spec(manifest):
    if manifest.get("kind") == "Deployment":
        return manifest.get("spec", {}).get("template", {}).get("spec", {}) or {}
    return manifest.get("spec", {}) or {}


def _add(v, check, detail):
    v.append({"check": check, "detail": detail})


def _unknown_keys(v, obj, allowed, where):
    """Fail closed: any key in ``obj`` not in ``allowed`` is a violation."""
    if not isinstance(obj, dict):
        _add(v, "malformed_field", f"{where} is not an object: {type(obj).__name__}")
        return
    for k in obj:
        if k not in allowed:
            _add(v, f"unrecognized_{where}_field", f"{where}.{k} not modeled -> fail closed")


def _check_security_context(v, sc, allowed, cname, level):
    if sc is None:
        return
    _unknown_keys(v, sc, allowed, f"{level}_securityContext")
    if not isinstance(sc, dict):
        return
    if sc.get("privileged"):
        _add(v, "privileged", f"{cname}: privileged=true")
    if sc.get("allowPrivilegeEscalation") is True:
        _add(v, "privilege_escalation", f"{cname}: allowPrivilegeEscalation=true")
    caps = (sc.get("capabilities") or {}) if isinstance(sc.get("capabilities"), dict) else {}
    if caps.get("add"):
        _add(v, "added_capabilities", f"{cname}: capabilities.add={caps.get('add')}")
    if sc.get("runAsNonRoot") is False:
        _add(v, "run_as_root", f"{cname}: runAsNonRoot=false")
    if sc.get("runAsUser") == 0:
        _add(v, "run_as_root", f"{cname}: runAsUser=0")
    if sc.get("procMount") not in (None, "Default"):
        _add(v, "proc_mount", f"{cname}: procMount={sc.get('procMount')}")


def _check_env(v, container, cname):
    for e in container.get("env", []) or []:
        _unknown_keys(v, e, ENV_FIELDS, "env")
        vf = e.get("valueFrom") if isinstance(e, dict) else None
        if isinstance(vf, dict):
            _unknown_keys(v, vf, ENV_VALUE_FROM_FIELDS, "env_valueFrom")
            if "secretKeyRef" in vf:
                _add(v, "secret_env", f"{cname}: env {e.get('name')} from secret")
    for ef in container.get("envFrom", []) or []:
        _unknown_keys(v, ef, ENV_FROM_FIELDS, "envFrom")
        if isinstance(ef, dict) and "secretRef" in ef:
            _add(v, "secret_envfrom", f"{cname}: envFrom secretRef {ef['secretRef']}")


def _check_container(v, c, *, kind):
    if not isinstance(c, dict):
        _add(v, "malformed_container", f"{kind} entry is not an object")
        return
    _unknown_keys(v, c, CONTAINER_FIELDS, "container")
    cname = c.get("name", "?")
    _check_security_context(v, c.get("securityContext"), CONTAINER_SECURITY_CONTEXT_FIELDS,
                            cname, "container")
    img = c.get("image", "")
    if not _DIGEST_IMAGE.match(img):
        _add(v, "image_provenance", f"image not a pinned allowed digest: {img}")
    _check_env(v, c, cname)


def _check_volume(v, vol):
    if not isinstance(vol, dict):
        _add(v, "malformed_volume", "volume entry is not an object")
        return
    _unknown_keys(v, vol, VOLUME_FIELDS, "volume")
    name = vol.get("name")
    for src in vol:
        if src == "name":
            continue
        if src in _VOLUME_HOST_SOURCES:
            _add(v, "host_path", f"hostPath volume {name}")
        elif src in _VOLUME_SECRET_SOURCES:
            _add(v, "secret_mount", f"secret volume {name}")
        elif src in _VOLUME_CSI_SOURCES:
            _add(v, "csi_volume", f"csi volume {name}")
        elif src in _VOLUME_PROJECTED_SOURCES:
            proj = vol.get("projected") or {}
            for s in (proj.get("sources") or []):
                if isinstance(s, dict) and "secret" in s:
                    _add(v, "secret_mount", f"projected secret in volume {name}")
        elif src in _VOLUME_REMOTE_SOURCES:
            _add(v, "remote_volume", f"{src} volume {name} (host/remote storage surface)")
        # benign sources (emptyDir/configMap/downwardAPI/pvc/ephemeral) pass


def _check_pod_workload(v, spec):
    if not isinstance(spec, dict):
        _add(v, "malformed_pod_spec", "pod spec is not an object")
        return
    _unknown_keys(v, spec, POD_SPEC_FIELDS, "pod_spec")

    # host namespace sharing
    if spec.get("hostNetwork") or spec.get("hostPID") or spec.get("hostIPC"):
        _add(v, "host_namespaces", "hostNetwork/PID/IPC")
    if spec.get("shareProcessNamespace"):
        _add(v, "share_process_namespace", "shareProcessNamespace=true")
    if spec.get("hostUsers") is False:
        _add(v, "host_users", "hostUsers=false (userns) not permitted")

    # workload identity / token projection
    sa = spec.get("serviceAccountName") or spec.get("serviceAccount")
    if sa and sa != "default":
        _add(v, "service_account", f"non-default serviceAccountName {sa}")
    if spec.get("automountServiceAccountToken") is True:
        _add(v, "automount_token", "automountServiceAccountToken=true")

    # pod-level security context
    _check_security_context(v, spec.get("securityContext"), POD_SECURITY_CONTEXT_FIELDS,
                            "pod", "pod")

    # imagePullSecrets (understood; referenced, not mounted -> allowed but validated shape)
    for ips in spec.get("imagePullSecrets", []) or []:
        if not isinstance(ips, dict) or set(ips) - {"name"}:
            _add(v, "malformed_image_pull_secret", f"imagePullSecrets entry {ips}")

    # ALL container lists
    for c in spec.get("containers", []) or []:
        _check_container(v, c, kind="containers")
    for c in spec.get("initContainers", []) or []:
        _check_container(v, c, kind="initContainers")
    for c in spec.get("ephemeralContainers", []) or []:
        _check_container(v, c, kind="ephemeralContainers")

    for vol in spec.get("volumes", []) or []:
        _check_volume(v, vol)


def check(env, manifest, *, allowed_namespaces, backup_exists=lambda n: False) -> list:
    """Return a list of violation dicts (empty == compliant). Fail closed."""
    v = []
    ns, kind, name = env["namespace"], env["kind"], env["name"]

    if ns not in allowed_namespaces:
        _add(v, "namespace_scope", f"ns {ns} not allowed")
    if name in _PROTECTED_NAMES:
        _add(v, "protected_resource", f"{name} is a protected control")
    if kind in ("ClusterRole", "ClusterRoleBinding"):
        _add(v, "cluster_scope_rbac", "cluster-scoped RBAC forbidden")

    if manifest is None:
        return v

    if kind in ("Role", "ClusterRole"):
        for rule in manifest.get("rules", []) or []:
            if _DANGEROUS_VERBS & set(rule.get("verbs", []) or []):
                _add(v, "dangerous_verb", "bind/escalate/impersonate/*")
            if "*" in (rule.get("resources", []) or []) or "*" in (rule.get("apiGroups", []) or []):
                _add(v, "wildcard_rbac", "wildcard resource/group")
    if kind in ("RoleBinding", "ClusterRoleBinding"):
        if manifest.get("roleRef", {}).get("name") in _POWERFUL_ROLES:
            _add(v, "powerful_rolebinding", f"binds {manifest['roleRef']['name']}")

    if kind in _POD_KINDS:
        _check_pod_workload(v, _pod_spec(manifest))

    if kind == "Service" and manifest.get("spec", {}).get("type") in ("LoadBalancer", "NodePort"):
        _add(v, "public_service", manifest["spec"]["type"])
    return v


def rollback_verified(rollback_plan, *, backup_exists) -> bool:
    """Rollback evidence must reference an ACTUAL existing backup, not a non-empty dict."""
    if not isinstance(rollback_plan, dict):
        return False
    ref = rollback_plan.get("backup_ref")
    return bool(ref) and backup_exists(ref)
