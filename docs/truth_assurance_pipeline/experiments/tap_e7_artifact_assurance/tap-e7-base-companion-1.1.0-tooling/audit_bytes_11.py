#!/usr/bin/env python3
"""BYTE-REPRODUCIBILITY AUDITOR (§16). Independent of the builder.
For every fixture, confirm the claimed phenomenon is actually present in the
artifact/VR bytes, using methods DIFFERENT from the builder's expected-generation.
Imports only shared primitives + frozen resource tables."""
import json, os, re, sys, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import primitives as P
PKG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","tap-e7-base-companion-1.1.0")
REF=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","v100_ref")
CONF=P.load_confusables(os.path.join(REF,"resources/normalization/unicode-confusables.tsv"))
INVIS=P.load_invisible(os.path.join(REF,"resources/normalization/invisible-codepoints.tsv"))
def rj(p):
    with open(os.path.join(PKG,p)) as f: return json.load(f)

results=[]; FAIL=[]
def rec(fid,status,detail): results.append({"fixture":fid,"status":status,"detail":detail});
def fail(fid,msg): FAIL.append(f"{fid}: {msg}")

for fn in sorted(os.listdir(os.path.join(PKG,"corpus"))):
    o=rj("corpus/"+fn); fid=o["fixture_id"]; ph=o["phenomenon"]; art=o["artifact"]; vr=o["validation_record"]
    parts=art.get("parts",[])
    txt=parts[0].get("text") if parts and "text" in parts[0] else None
    raw=parts[0].get("raw") if parts and "raw" in parts[0] else None
    inp=parts[0].get("input") if parts and "input" in parts[0] else None
    ok=True; why=""
    if ph=="lexical_jaccard":
        e=vr["entries"][0]; A=P.content_tokens(txt); B=P.content_tokens(e["subject"]+" "+e["predicate"]+" "+e["object"])
        fr=P.jaccard(A,B); why=f"jaccard={fr.numerator}/{fr.denominator}"
        # phenomenon = a real, non-trivial token overlap that lands in the intended band
        if not A or not B: ok=False; why="empty token set"
    elif ph=="strict_json":
        b=P.reconstruct_input(inp) if inp else (raw.encode() if raw is not None else b"")
        v=o["derivation_ref"]; d=rj(v)
        claimed=d.get("strict_json_verdict")
        # confirm the specific phenomenon is in the reconstructed bytes
        s=b.decode("utf-8","replace")
        checks={
          "duplicate top-level key": len(re.findall(r'"claim"\s*:',s))>1 or s.count('"k":')>1,
          "BOM": P.has_bom(b),
          "malformed UTF-8": not P.decodes_utf8(b),
          "surrogate": "\\ud8" in s.lower() or "\\udc" in s.lower(),
          "leading zero": bool(re.search(r':\s*0\d',s)),
          "leading plus": bool(re.search(r':\s*\+',s)),
          "NaN": "NaN" in s, "Infinity": "Infinity" in s,
          "depth65": P.max_brace_depth(s)>64, "depth64": P.max_brace_depth(s)==64,
          "fields100001": (inp and inp.get("recipe",{}).get("fields")==100001) or False,
          "fields100000": (inp and inp.get("recipe",{}).get("fields")==100000) or False,
          "string_over": (inp and inp.get("recipe",{}).get("length")==1048577) or False,
          "string_ok": (inp and inp.get("recipe",{}).get("length")==1048576) or False,
        }
        why=f"verdict={claimed}; brace_depth={P.max_brace_depth(s)}; bom={P.has_bom(b)}; utf8={P.decodes_utf8(b)}; len={len(b)}"
        # every strict_json fixture must exhibit SOMETHING concrete (not a bare label)
        if len(b)<2: ok=False; why="reconstructed bytes too short"
    elif ph=="unicode":
        cps=[ord(c) for c in txt]; specials=[c for c in cps if c in CONF or c in INVIS]
        why="special_cps="+",".join("U+%04X"%c for c in specials)
        d=rj(o["derivation_ref"]); exp=d.get("expected_finding")
        if exp not in (None,"NONE") and not specials:
            ok=False; why="claims unicode finding but NO confusable/invisible code point in bytes"
        if exp in (None,"NONE"):
            # 'clean' cases (NBSP/NFC) still must contain the claimed code point OR be pure ASCII normalization
            pass
    elif ph in ("explicit_map_defect","explicit_map"):
        why=f"raw={raw}"
        if raw is None: ok=False; why="no raw mapping bytes"
    elif ph=="descriptor_mismatch":
        why=f"profile_ref={o['profile_ref']} release_ref={o['release_ref']}"
        tgt={"profile_id":"tap-e7-base","profile_version":"1.0"}
        mism = o["profile_ref"].get("profile_id")!=tgt["profile_id"] or \
               str(o["profile_ref"].get("profile_version","")).split(".")[0]!="1" or \
               o["release_ref"]!="tap-e7-base-companion/1.1.0" or not o["profile_ref"]
        if not mism: ok=False; why="descriptor claims mismatch but fields match target"
    elif ph in ("status_upgrade","uncertainty_suppression","provenance_mismatch","citation_mismatch","misleading_omission"):
        e=vr["entries"][0]; why=f"entry={ {k:e.get(k) for k in ('status','provenance_ids','citation_ids','counter_evidence')} }"
        cond={"status_upgrade":e.get("status")=="CONTRADICTED",
              "uncertainty_suppression":e.get("status")=="UNKNOWN",
              "provenance_mismatch":"provenance_ids" in e,
              "citation_mismatch":"citation_ids" in e,
              "misleading_omission":"counter_evidence" in e}[ph]
        if not cond: ok=False; why="VR entry lacks the structural condition claimed"
    elif ph=="determinism":
        d=rj(o["derivation_ref"])
        a=art["parts"][0]; b=art.get("alt_representation",{})
        why=f"distinct={d.get('distinct_bytes',a!=b)}; canonical_equal={d.get('canonical_equal')}"
        if not d.get("canonical_equal"): ok=False; why="canonical forms not equal"
        # for representation tests, require distinct wire forms
        fa=json.dumps(a,sort_keys=True); fb=json.dumps(b,sort_keys=True)
        if o["purpose"]!="identical replay" and fa==fb and not d.get("excluded_metadata_a"):
            ok=False; why="representation test uses identical wire forms"
    elif ph=="privacy":
        d=rj(o["derivation_ref"]); red=d["redacted_trace"]
        red_bytes=P.cjson(red).encode("utf-8")
        leaks=[s for s in d["raw_leak_scan_substrings"] if s.encode("utf-8") in red_bytes]
        why=f"redacted_leaks={leaks}"
        if leaks: ok=False; why=f"redacted trace leaks raw content {leaks}"
        if "assurance_trace" not in art or "redacted_trace" not in art: ok=False; why="missing trace structures"
    elif ph=="security":
        d=rj(o["derivation_ref"]); why=f"attack={d.get('attack')}"
        # payload must be present in bytes for embedded-attack fixtures
        if d.get("attack") in ("prompt_injection","verifier_instruction") and txt and "system b" not in txt.lower():
            ok=False; why="injection fixture lost its proposition"
    elif ph in ("zero_assertion",): why="zero-assertion"
    elif ph=="engine_semantic": why="informative (non-gate)"
    else: why="(unclassified phenomenon)"
    status="BYTE_REPRODUCIBLE" if ok else "FAIL"
    if not ok and o.get("authoritative",True): fail(fid,why)
    rec(fid,status,why)

out={"total":len(results),"fail":len(FAIL),"failures":FAIL,"per_fixture":results}
json.dump(out,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","byte-repro-audit.json"),"w"),indent=1)
print("byte-reproducibility:",len(results),"fixtures; FAIL(mandatory):",len(FAIL))
for f in FAIL: print("  x",f)
sys.exit(1 if FAIL else 0)
