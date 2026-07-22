#!/usr/bin/env python3
"""PACKAGING VALIDATOR (role B): schemas/manifests/hashes/roots/placeholder/
§8.1 internal consistency + count invariants + projection hashes + diff + mapping.
Reads package bytes; does not judge byte-level phenomenon (that is the byte auditor)."""
import hashlib, json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import primitives as P
BASE=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..")
PKG=os.path.join(BASE,"tap-e7-base-companion-1.1.0"); REF=os.path.join(BASE,"v100_ref")
def rb(p):
    with open(os.path.join(PKG,p),"rb") as f: return f.read()
def rj(p): return json.loads(rb(p))
def sh(b): return "sha-256:"+hashlib.sha256(b).hexdigest()
def cj(o): return P.cjson(o)
POS={"FABRICATION","MEANING_DISTORTION","STATUS_UPGRADE","CERTAINTY_OVERSTATEMENT","SCOPE_EXPANSION",
     "QUALIFICATION_OMISSION","MISLEADING_CONTRADICTION_OMISSION","UNCERTAINTY_SUPPRESSION","PROVENANCE_MISMATCH","CITATION_MISMATCH"}
def out81(cats):
    ps={("POSITIVE_VIOLATION" if c in POS else "EVALUATION_LIMITATION") for c in cats}
    return "NOT_ASSURED" if "POSITIVE_VIOLATION" in ps else ("INDETERMINATE" if "EVALUATION_LIMITATION" in ps else "ASSURED")
FAIL=[]
def bad(m): FAIL.append(m)
allf=sorted(os.path.relpath(os.path.join(dp,f),PKG).replace(os.sep,"/") for dp,_,fs in os.walk(PKG) for f in fs)
rel=rj("manifest/release-manifest.json"); rm=rj("manifest/resource-manifest.json"); cm=rj("manifest/corpus-manifest.json")

# manifest digests
for e in rel["files"]:
    if not os.path.exists(os.path.join(PKG,e["path"])): bad("release missing "+e["path"])
    elif sh(rb(e["path"]))!=e["sha256"]: bad("release digest "+e["path"])
for e in rm["resources"]:
    if sh(rb(e["path"]))!=e["sha256"]: bad("resource digest "+e["path"])
for e in cm["fixtures"]:
    if sh(rb(e["path"]))!=e["sha256"]: bad("corpus digest "+e["path"])
    ep="expected/"+os.path.basename(e["path"]).replace(".json",".expected.json")
    if sh(rb(ep))!=e["expected_sha256"]: bad("expected digest "+ep)
    dp="derivations/"+os.path.basename(e["path"])
    if sh(rb(dp))!=e["derivation_sha256"]: bad("derivation digest "+dp)

# roots
def root_over(entries,kw="resources"): return sh((cj({kw:[{"path":x["path"],"sha256":x["sha256"]} for x in entries]})+"\n").encode())
r_res=root_over(rm["resources"]); r_sch=root_over([e for e in rm["resources"] if e["path"].startswith("schemas/")])
r_cor=root_over(sorted(cm["fixtures"],key=lambda e:e["path"]),"fixtures")
runtime=[e for e in rm["resources"] if e.get("outcome_affecting")]
r_cfg=sh((cj({"target_spec":"tap-e7-assurance/1.0.0","target_profile":"tap-e7-base/1.0","canonicalization":"tap-canon/1",
  "thresholds":{"T_accept":0.85,"T_reject":0.35},"runtime_resources":[{"path":e["path"],"sha256":e["sha256"]} for e in runtime]})+"\n").encode())
r_pkg=root_over(rel["files"])
roots=rel["roots"]
if r_res!=roots["resource_root"]: bad("resource_root")
if r_sch!=roots["schema_root"]: bad("schema_root")
if r_cor!=roots["corpus_root"]: bad("corpus_root")
if r_cfg!=roots["config_fingerprint"]: bad("config_fingerprint")
if r_pkg!=rb("hashes/package-root.txt").decode().strip(): bad("package_root")
# config fingerprint unchanged vs v1.0.0
v100_cfg=open(os.path.join(REF,"hashes/config-fingerprint.txt")).read().strip()
cfg_same = r_cfg==v100_cfg

# §8.1 + counts + projection + expected bytes + fixture required fields
req={"fixture_id","group","modality","validation_record","artifact","expected","authoritative"}
n=0; PH=re.compile(r"\b(TBD|TODO|FIXME|PLACEHOLDER|representative subset|to be emitted|boundary 0\.\d|oversized|depth65|fieldcount|maxstring)\b",re.I)
for p in allf:
    if p.startswith("corpus/"):
        o=rj(p); n+=1
        if not req.issubset(o): bad(p+" missing required fields")
        exp=o["expected"]; cats=[f["category"] for f in exp["findings"]]
        if out81(cats)!=exp["outcome"]: bad(p+" outcome")
        es=exp["evaluation_summary"]
        if es["evaluated_assertive"]+es["unevaluated_assertive"]!=es["total_assertive"]: bad(p+" count")
        pi=exp["projection_pi"]
        if sh((cj(pi)+"\n").encode())!=exp["projection_pi_sha256"]: bad(p+" projection")
        ep="expected/"+o["fixture_id"]+".expected.json"
        if rb(ep)!=(cj(exp)+"\n").encode(): bad(p+" expected-bytes")
        if not os.path.exists(os.path.join(PKG,"derivations/"+o["fixture_id"]+".json")): bad(p+" no derivation")
# placeholder scan over normative (skip reports)
for p in allf:
    if p.startswith("reports/"): continue
    try: t=rb(p).decode()
    except: continue
    for m in PH.finditer(t): bad(f"placeholder '{m.group(0)}' in {p}")
# sha256sums
for ln in rb("hashes/sha256sums.txt").decode().splitlines():
    if not ln.strip(): continue
    h,pp=ln.split("  ",1)
    if pp=="hashes/sha256sums.txt": continue
    if sh(rb(pp))!="sha-256:"+h: bad("sha256sums "+pp)

res={"fixtures":n,"config_fingerprint_unchanged_vs_v100":cfg_same,"resource_root":r_res,"schema_root":r_sch,
     "corpus_root":r_cor,"config_fingerprint":r_cfg,"package_root":r_pkg,"failures":FAIL}
json.dump(res,open(os.path.join(BASE,"pkg-validation.json"),"w"),indent=1)
print("packaging: fixtures",n,"| config_fp unchanged vs v1.0.0:",cfg_same,"| failures:",len(FAIL))
for f in FAIL[:40]: print("  x",f)
sys.exit(1 if FAIL else 0)
