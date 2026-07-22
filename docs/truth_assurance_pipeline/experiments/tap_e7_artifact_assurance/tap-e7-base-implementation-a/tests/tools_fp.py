"""M12 helper: prove the runtime config fingerprint is independent of corpus membership."""
import json, os
def fp_independent_of_corpus(pkg):
    rm = json.load(open(os.path.join(pkg, "manifest/resource-manifest.json")))
    runtime = [e["path"] for e in rm["resources"] if e.get("outcome_affecting")]
    # no corpus/ or expected/ path may be a runtime (fingerprint) resource
    return not any(p.startswith(("corpus/", "expected/", "derivations/")) for p in runtime)
