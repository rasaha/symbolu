#!/usr/bin/env bash
set -Eeuo pipefail
# ---------------------------------------------------------------------------
# verify_rm1_results.sh <run_dir> — inspect a run's JSON with Python (not fragile
# greps), print the preregistered acceptance scorecard (MET / NOT MET /
# NOT MEASURABLE), and hard-fail on integrity/validity violations. Never alters
# result files; it only writes new scorecard/taxonomy files into <run_dir>.
# ---------------------------------------------------------------------------
RM1_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${RM1_DIR}/common.sh"

RUN_DIR="${1:-}"
[[ -n "${RUN_DIR}" && -d "${RUN_DIR}" ]] || die "usage: verify_rm1_results.sh <run_dir>"

banner "VERIFY ${RUN_DIR}"

export RM1_RUN_DIR="${RUN_DIR}"
export RM1_EXPECT_MODEL_ID="${UGENCE_REAL_MODEL_ID:-}"
export RM1_EXPECT_DEVICE="${RM1_DEVICE}"
export RM1_REPO_DIR="${UGENCE_REPO_DIR}"
export RM1_CANONICAL_JSON="${UGENCE_REPO_DIR}/${RM1_CANONICAL_JSON_REL}"
export RM1_CANONICAL_HASH
export RM1_VERIFY_MODE="${RM1_VERIFY_MODE:-full}"
# HF_TOKEN passed only so the leakage check can look for its literal; never printed.

PY="$(rm1_python)"
"${PY}" - <<'PYEOF'
import hashlib, json, os, re, sys

run_dir   = os.environ["RM1_RUN_DIR"]
exp_model = os.environ.get("RM1_EXPECT_MODEL_ID", "")
exp_dev   = os.environ.get("RM1_EXPECT_DEVICE", "cuda")
mode      = os.environ.get("RM1_VERIFY_MODE", "full")
canon_json= os.environ.get("RM1_CANONICAL_JSON", "")
canon_hash= os.environ.get("RM1_CANONICAL_HASH", "")
hf_token  = os.environ.get("HF_TOKEN", "")

hard = []      # hard failures -> exit 1
warn = []      # non-fatal warnings

def p(path):
    return os.path.join(run_dir, path)

def load_json(path):
    with open(path) as f:
        return json.load(f)

# ---- required files exist + parse ----
res_path = p("REAL_MODEL_RESULTS.json")
for f in ("REAL_MODEL_RESULTS.json", "REAL_MODEL_VALIDATION_REPORT.md", "RESOURCE_MANIFEST.json"):
    if not os.path.isfile(p(f)):
        hard.append(f"missing artifact: {f}")

res = None
if os.path.isfile(res_path):
    try:
        res = load_json(res_path)
    except Exception as exc:
        hard.append(f"REAL_MODEL_RESULTS.json does not parse: {exc}")

def getpath(d, *keys, default=None):
    node = d
    for k in keys:
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node

scorecard = {}
present = {}
taxonomy = {"not_met": [], "quarantine_reasons": {}, "notes": []}

if res is not None:
    # ---- real-model execution gates (also apply to smoke) ----
    exe = res.get("actual_model_execution")
    if exe != "VERIFIED":
        hard.append(f"actual_model_execution != VERIFIED (got {exe!r})")
    desc = res.get("model_descriptor", {}) or {}
    proof = res.get("execution_proof", {}) or {}
    if desc.get("execution") == "MOCK" or proof.get("model_class") == "MockBackend" \
            or res.get("status") in ("MOCK_PLUMBING",):
        hard.append("backend is MOCK — a mock result must never be classified as scientific evidence")
    got_model = res.get("requested_model")
    if exp_model and got_model != exp_model:
        hard.append(f"model id mismatch: results={got_model!r} expected={exp_model!r}")
    if "requested_revision" not in res:
        hard.append("requested_revision not recorded")
    elif res.get("requested_revision") in (None, ""):
        warn.append("model revision not pinned (UGENCE_MODEL_REVISION unset) — recommended for reproducibility")
    # proof fields
    if not proof.get("generated_token_ids"):
        hard.append("execution_proof.generated_token_ids not recorded")
    if not proof.get("logits_shape"):
        hard.append("execution_proof.logits_shape not recorded")
    if exp_dev == "cuda" and "cuda" not in str(proof.get("device", "")).lower():
        hard.append(f"CUDA device not recorded in proof (device={proof.get('device')!r})")

    # ---- presence of the RM0..RM7 arms ----
    acc = getpath(res, "arms", "arms_accuracy", default={}) or {}
    arm_keys = ["RM0", "RM1", "RM2", "RM3", "RM4", "RM5", "RM6", "RM7_explained"]
    for a in arm_keys:
        present[a] = "PRESENT" if a in acc else "NOT MEASURABLE"

    ea_available = bool(getpath(res, "arms", "event_attention_available", default=False))

    # ---- metric presence (hard-fail if a required metric is entirely absent) ----
    def req(name, value):
        present[name] = "PRESENT" if value is not None else "MISSING"
        if value is None:
            hard.append(f"required metric absent: {name}")
        return value

    schema_ok   = req("schema_valid_extraction", getpath(res, "arms", "extraction", "schema_ok_rate"))
    span_exact  = req("source_span_exact_match", getpath(res, "arms", "extraction", "span_verified_rate"))
    surv        = req("required_event_survival", getpath(res, "arms", "extraction", "required_event_survival"))
    id_pres     = req("evidence_id_preservation",
                      getpath(res, "arms", "integrity", "evidence_id_preservation")
                      if getpath(res, "arms", "integrity", "evidence_id_preservation") is not None
                      else getpath(res, "controls", "evidence_id_preservation"))
    unauth      = req("unauthorized_inclusion", getpath(res, "controls", "unauthorized_events_admitted"))
    corrupt_rej = req("corrupt_record_rejection", getpath(res, "controls", "corrupt_authoritative_rejected"))
    gap         = req("oracle_to_predicted_gap", getpath(res, "arms", "decisive_comparisons", "RM5_minus_RM3_construction_gap"))
    sup_prec    = req("supported_claim_precision", getpath(res, "arms", "faithfulness", "supported_claim_precision"))
    unsup_rec   = req("unsupported_claim_recall", getpath(res, "controls", "unsupported_claim_recall"))
    qual_pres   = req("qualifier_preservation", getpath(res, "arms", "faithfulness", "qualifier_preservation"))
    rm3 = acc.get("RM3"); rm1 = acc.get("RM1")
    rm4_rm3     = getpath(res, "arms", "decisive_comparisons", "RM4_minus_RM3")
    rm4_rm3_rel = getpath(res, "arms", "decisive_comparisons", "RM4_minus_RM3_relational")

    # ---- scorecard evaluation ----
    def crit(name, value, ok, measurable=True):
        if not measurable or value is None:
            scorecard[name] = {"value": value, "status": "NOT MEASURABLE"}
        else:
            status = "MET" if ok else "NOT MET"
            scorecard[name] = {"value": value, "status": status}
            if status == "NOT MET":
                taxonomy["not_met"].append(name)

    crit("schema_valid_extraction>=0.95", schema_ok, schema_ok is not None and schema_ok >= 0.95)
    crit("source_span_exact_match>=0.90", span_exact, span_exact is not None and span_exact >= 0.90)
    crit("evidence_id_preservation==1.00", id_pres, id_pres is not None and abs(id_pres - 1.0) < 1e-9)
    crit("unauthorized_inclusion==0.00", unauth, unauth is not None and float(unauth) == 0.0)
    crit("corrupt_record_rejection==1.00", corrupt_rej, corrupt_rej is not None and abs(float(corrupt_rej) - 1.0) < 1e-9)
    crit("required_event_survival>=0.75", surv, surv is not None and surv >= 0.75)
    crit("RM3-RM1>=0.10", (None if (rm3 is None or rm1 is None) else rm3 - rm1),
         (rm3 is not None and rm1 is not None and (rm3 - rm1) >= 0.10))
    crit("RM4-RM3>=-0.01(overall)", rm4_rm3, (rm4_rm3 is not None and rm4_rm3 >= -0.01), measurable=ea_available)
    crit("RM4-RM3>=0.05(relational)", rm4_rm3_rel, (rm4_rm3_rel is not None and rm4_rm3_rel >= 0.05), measurable=ea_available)
    crit("oracle_to_predicted_gap<=0.15", gap, gap is not None and gap <= 0.15)
    crit("supported_claim_precision>=0.95", sup_prec, sup_prec is not None and sup_prec >= 0.95)
    crit("unsupported_claim_recall>=0.90", unsup_rec, unsup_rec is not None and unsup_rec >= 0.90)
    crit("qualifier_preservation>=0.95", qual_pres, qual_pres is not None and qual_pres >= 0.95)

    if not ea_available:
        taxonomy["notes"].append("event attention operator unavailable: RM4-RM3 criteria NOT MEASURABLE")

# ---- trace + quarantine validity ----
tr = p("REAL_MODEL_TRACES.jsonl")
if not os.path.isfile(tr):
    hard.append("REAL_MODEL_TRACES.jsonl missing")
else:
    lines = [l for l in open(tr).read().splitlines() if l.strip()]
    if not lines:
        hard.append("REAL_MODEL_TRACES.jsonl is empty")
    else:
        for i, l in enumerate(lines):
            try:
                json.loads(l)
            except Exception as exc:
                hard.append(f"trace line {i} invalid JSON: {exc}")
                break

qf = p("QUARANTINE.jsonl")
if os.path.isfile(qf):
    for i, l in enumerate([x for x in open(qf).read().splitlines() if x.strip()]):
        try:
            rec = json.loads(l)
            r = rec.get("reason", "unknown")
            taxonomy["quarantine_reasons"][r] = taxonomy["quarantine_reasons"].get(r, 0) + 1
        except Exception as exc:
            hard.append(f"quarantine line {i} invalid JSON: {exc}")
            break

# ---- canonical hash unchanged ----
if canon_json and os.path.isfile(canon_json):
    got = hashlib.sha256(open(canon_json, "rb").read()).hexdigest()
    if got != canon_hash:
        hard.append(f"canonical controlled-result hash CHANGED: {got}")
else:
    warn.append("canonical results JSON not found for hash check")

# ---- secret / credential leakage scan ----
leak_patterns = [re.compile(r"hf_[A-Za-z0-9]{20,}")]
for fn in os.listdir(run_dir):
    fp = os.path.join(run_dir, fn)
    if not os.path.isfile(fp):
        continue
    try:
        blob = open(fp, "r", errors="ignore").read()
    except Exception:
        continue
    if hf_token and hf_token in blob:
        hard.append(f"HF_TOKEN literal leaked into artifact: {fn}")
    for pat in leak_patterns:
        if pat.search(blob):
            hard.append(f"possible HF token pattern found in artifact: {fn}")
            break

# ---- report ----
print("== RM1 acceptance scorecard (mode=%s) ==" % mode)
for name, d in scorecard.items():
    print(f"  [{d['status']:>14}] {name} = {d['value']}")
print("\n== RM0-RM7 arm presence ==")
for a, s in present.items():
    if a.startswith("RM"):
        print(f"  {a}: {s}")

# ---- write scorecard + taxonomy (new files only; never alter results) ----
with open(p("rm1_scorecard.json"), "w") as f:
    json.dump({"mode": mode, "scorecard": scorecard, "arm_presence": present}, f, indent=2)
with open(p("rm1_scorecard.txt"), "w") as f:
    for name, d in scorecard.items():
        f.write(f"[{d['status']}] {name} = {d['value']}\n")
with open(p("rm1_failure_taxonomy.json"), "w") as f:
    json.dump(taxonomy, f, indent=2)

if warn:
    print("\n== warnings ==")
    for w in warn:
        print(f"  WARN: {w}")

if hard:
    print("\n== HARD FAILURES ==")
    for h in hard:
        print(f"  FAIL: {h}")
    sys.exit(1)

print("\nVERIFY OK (no integrity/validity violations). NOT-MET criteria, if any, are scientific outcomes.")
PYEOF

log "verification complete for ${RUN_DIR}"
