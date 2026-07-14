import json, hashlib, copy
src="frozen/varna_native_stage1_merged_v1.json"
v1=json.load(open(src))
v1_hash=hashlib.sha256(open(src,'rb').read()).hexdigest()

ADD={
 "ṛ":{"lib":"freedom / liberation — the unbound, self-established state",
      "bind":"rootlessness / escapism — flight that will not commit or take form",
      "note":"RESONANCE_LAYER (development-only); source varna_vocalic_resonance_tags.json. NOTE: ṛ (ऋ) ≠ Ra (र); Ra = annihilation (sarvanāśa); ṛ carries no such affliction — its resonance is freedom."},
 "ṝ":{"lib":"totality / oṃ (praṇava) — creation-preservation-destruction + transmutation",
      "bind":"dissolution / self-loss — totality that engulfs the individual",
      "note":"RESONANCE_LAYER (development-only); core oṃ is Sarkar-attested (Acoustic Roots); binding shadow derived; source varna_vocalic_resonance_tags.json"},
 "l̥":{"lib":"arrangement / formation (√kḷp — to fit, arrange, form)",
      "bind":"rigid contrivance / over-fitting / forced ordering",
      "note":"RESONANCE_LAYER (development-only); core from √kḷp corpus (differs from Sarkar's hummm); source varna_vocalic_resonance_tags.json"},
 "l̥̄":{"lib":"explosion / breakthrough (phaṭ — sudden manifestation, removal of lethargy)",
       "bind":"destructive outburst / rash discharge / premature shattering",
       "note":"RESONANCE_LAYER (development-only); core phaṭ is Sarkar-attested; NO attested word contains ḹ; source varna_vocalic_resonance_tags.json"},
}

v2=copy.deepcopy(v1)
changed=[]
for r in v2["rows"]:
    u=r["canonical_parser_unit"]
    if u in ADD:
        a=ADD[u]
        r["source_artifact"]="varna_vocalic_resonance_tags.json"
        r["source_key"]=r["iast"]
        r["binding_vritti"]=a["bind"]
        r["liberating_vritti"]=a["lib"]
        r["binding_pole_provenance"]="AUTHORED_PROVISIONAL"
        r["liberating_pole_provenance"]="AUTHORED_PROVISIONAL"
        r["activation_scope"]="DEVELOPMENT_ONLY"
        r["empirical_status_note"]=a["note"]
        changed.append(u)

# versioning metadata (additions only)
v2["schema_version"]="native_merged_v2"
v2["supersedes"]={"artifact":"varna_native_stage1_merged_v1.json","sha256":v1_hash,
    "change_class":"ADDITIONS_ONLY",
    "additions":"filled the 4 previously-empty vocalic rows (ṛ, ṝ, ḷ, ḹ) from the vocalic resonance layer",
    "no_existing_mapping_modified":True,
    "consonant_backbone_unchanged":True}

# VERIFY: only the 4 target rows differ; all else identical
diffs=[]
for a,b in zip(v1["rows"],v2["rows"]):
    if a!=b: diffs.append(a["canonical_parser_unit"])
assert set(diffs)==set(ADD.keys()), f"unexpected diffs: {diffs}"
# consonants byte-identical
cons_v1=[r for r in v1["rows"] if r["category"]=="consonant"]
cons_v2=[r for r in v2["rows"] if r["category"]=="consonant"]
assert cons_v1==cons_v2, "consonant rows changed!"

out="frozen/varna_native_stage1_merged_v2.json"
with open(out,"w") as f:
    json.dump(v2,f,ensure_ascii=False,indent=2)
v2_hash=hashlib.sha256(open(out,'rb').read()).hexdigest()
print("v1 sha256:", v1_hash)
print("v2 sha256:", v2_hash)
print("rows changed (must be exactly the 4 vowels):", sorted(changed))
print("consonant rows identical:", cons_v1==cons_v2)
print("total rows:", len(v2["rows"]))
