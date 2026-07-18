import json, hashlib, copy
src="frozen/varna_native_stage1_merged_v2.json"
v2=json.load(open(src))
v2_hash=hashlib.sha256(open(src,'rb').read()).hexdigest()
v3=copy.deepcopy(v2)

rows={r["canonical_parser_unit"]:r for r in v3["rows"]}
S, SS = rows["ś"], rows["ṣ"]

CORR_NOTE=("CORRECTED (v3): ś=rajoguṇa+artha, ṣ=tamoguṇa+kāma per primary source "
           "(P.R. Sarkar, 'The Acoustic Roots of the Indo-Aryan Alphabet'). Reverses the mis-decoded "
           "ś/ṣ swap that entered via b1_2_varna_classical_verifications → v3.1 "
           "(Sarkar 'sha'=ś read as retroflex ṣ). See VARNA_PRIMARY_SOURCE_RECONCILIATION_AUDIT.md.")

# swap the pole CONTENT (meaning + its attestation) between ś and ṣ
for fld in ("binding_vritti","liberating_vritti","binding_pole_provenance","liberating_pole_provenance"):
    S[fld], SS[fld] = SS[fld], S[fld]

# re-source both to the primary-source correction; primary-source romanization: ś='sha', ṣ="s'a"
for r,key in ((S,"sha"),(SS,"s'a")):
    r["source_artifact"]="varna_acoustic_roots_primary_source.json (corrects v3.1 ś/ṣ swap)"
    r["source_key"]=key
    r["empirical_status_note"]=CORR_NOTE

# versioning metadata
v3["schema_version"]="native_merged_v3"
v3["supersedes"]={"artifact":"varna_native_stage1_merged_v2.json","sha256":v2_hash,
    "change_class":"CORRECTION_SIBILANT_SWAP",
    "correction":"swapped ś<->ṣ binding/liberating pole content to match primary source (ś=rajoguṇa+artha, ṣ=tamoguṇa+kāma)",
    "rows_changed":["ś","ṣ"],
    "vowel_additions_from_v2_retained":True}
# consonant pole content changed -> no longer matches v3.1 (which carries the swap)
v3["consonant_pole_content_hash_matches_v31"]=False
recipe="sha256 of json.dumps([[unit,binding_vritti,liberating_vritti] for consonant rows in file order], ensure_ascii=False)"
cons=[[r["canonical_parser_unit"],r["binding_vritti"],r["liberating_vritti"]]
      for r in v3["rows"] if r["category"]=="consonant"]
v3["consonant_pole_content_hash"]=hashlib.sha256(json.dumps(cons,ensure_ascii=False).encode()).hexdigest()
v3["consonant_pole_content_hash_recipe"]=recipe

# VERIFY: only ś and ṣ rows differ v2->v3
diffs=[a["canonical_parser_unit"] for a,b in zip(v2["rows"],v3["rows"]) if a!=b]
assert set(diffs)=={"ś","ṣ"}, f"unexpected row diffs: {diffs}"
assert "artha" in S["binding_vritti"] and "rajasic" in S["binding_vritti"], "ś not corrected to artha/rajas"
assert "kāma" in SS["binding_vritti"] and "tamasic" in SS["binding_vritti"], "ṣ not corrected to kāma/tamas"
# vowel additions from v2 retained
assert rows["ṛ"]["liberating_vritti"].startswith("freedom"), "vowel additions lost"

out="frozen/varna_native_stage1_merged_v3.json"
json.dump(v3,open(out,"w"),ensure_ascii=False,indent=2)
v3_hash=hashlib.sha256(open(out,'rb').read()).hexdigest()
print("v2 sha256:", v2_hash)
print("v3 sha256:", v3_hash)
print("rows changed (must be ś, ṣ):", sorted(diffs))
print()
print("ś now  -> binding:", S["binding_vritti"][:70])
print("ṣ now  -> binding:", SS["binding_vritti"][:70])
