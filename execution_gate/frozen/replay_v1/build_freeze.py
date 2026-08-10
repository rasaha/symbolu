"""Build the immutable replay_v1 freeze: copy artifacts + emit MANIFEST.json with hashes.

Run once to create the freeze. Re-running reproduces byte-identical artifacts + manifest
(the aggregate hash excludes the human-facing timestamp so it is deterministic).
"""
import hashlib, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ART = os.path.join(HERE, "artifacts")

# (source path relative to repo, role)
SOURCES = [
    ("execution_gate/scenarios.py", "scenario_dataset_and_ground_truth"),
    ("execution_gate/baselines.py", "baseline_configuration"),
    ("execution_gate/gate.py", "eligibility_policy_engine"),
    ("execution_gate/model.py", "eligibility_types_and_gate_config"),
    ("execution_gate/states.py", "eligibility_state_semantics"),
    ("execution_gate/reason_codes.py", "reason_code_version"),
    ("execution_gate/registry.py", "executable_registry"),
    ("execution_gate/policy.py", "model_policy"),
    ("execution_gate/harness.py", "metric_definitions_and_simulator"),
    ("execution_gate/results/evaluation.json", "evaluation_output"),
    ("Project_documentation/governance/docs/execution_eligibility/EXECUTION_ELIGIBILITY_EVALUATION_PROTOCOL.md", "evaluation_protocol"),
    ("Project_documentation/governance/docs/execution_eligibility/EVALUATION_REPORT.md", "evaluation_report"),
    ("Project_documentation/governance/docs/execution_eligibility/LIMITATIONS_AND_FALSIFICATION.md", "limitations_and_falsification"),
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main(creation_timestamp, commit_sha):
    os.makedirs(ART, exist_ok=True)
    files = []
    for rel, role in SOURCES:
        src = os.path.join(REPO, rel)
        dst_name = os.path.basename(rel)
        shutil.copy2(src, os.path.join(ART, dst_name))
        files.append({"role": role, "frozen_name": dst_name, "source_path": rel,
                      "sha256": sha256(os.path.join(ART, dst_name))})
    files.sort(key=lambda f: f["frozen_name"])
    agg = hashlib.sha256("".join(f["sha256"] for f in files).encode()).hexdigest()
    ev = json.load(open(os.path.join(ART, "evaluation.json")))
    manifest = {
        "artifact_version": "replay_v1",
        "protocol_version": "execution_eligibility_evaluation_protocol_v1",
        "package_version": "execution_gate@replay_v1",
        "repository_commit_sha": commit_sha,
        "creation_timestamp": creation_timestamp,
        "scenario_count": ev["scenarios"],
        "baseline_count": len(ev["aggregate"]),
        "metric_names": sorted(next(iter(ev["aggregate"].values())).keys()),
        "primary_endpoint": "invalid_selection_rate = policy_violation + (1 - first_attempt_success), vs retry_only",
        "success_criteria": [
            "policy_violation_rate == 0",
            "false_eligible_critical == 0",
            "invalid_selection >= 30% below retry_only",
            "selection_regret >= 30% below retry_only",
            "added latency not exceeding latency saved from avoided failed calls",
        ],
        "reported_result_summary": {
            "execution_gate_policy": ev["aggregate"]["execution_gate_policy"],
            "retry_only": ev["aggregate"]["retry_only"],
        },
        "files": files,
        "aggregate_manifest_hash": agg,
        "immutability_statement": ("This version is OUTCOME-BEARING and is no longer tunable. "
                                   "Any change to design, thresholds, scenarios, or ground truth "
                                   "must be a new version (replay_v2), never an edit to replay_v1."),
    }
    json.dump(manifest, open(os.path.join(HERE, "MANIFEST.json"), "w"), indent=2, sort_keys=True)
    open(os.path.join(HERE, "MANIFEST.json"), "a").write("\n")
    print("aggregate_manifest_hash:", agg)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
