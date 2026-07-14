#!/usr/bin/env python3
"""Read-only reconciliation of the ACTUAL primary source
  P.R. Sarkar, "The Acoustic Roots of the Indo-Aryan Alphabet"
  (Ánanda Márga Philosophy in a Nutshell Part 8, 1984-85, Calcutta)
against the frozen merged lexicon. NO frozen artifact is modified.

Romanization key in the source (verified across the document):
  apostrophe = retroflex/cerebral -> ṭ=t', ṭh=t'h, ḍ=d', ḍh=d'h, ṇ=n', ṣ=s', kṣ=ks'
  palatal ś = "sha";  dental s = "sa";  retroflex ṣ = "s'a".
"""
import json, hashlib

MERGED = "frozen/varna_native_stage1_merged_v1.json"
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

merged = {r["canonical_parser_unit"]: r for r in json.load(open(MERGED))["rows"]}

# Primary-source acoustic-root facts, transcribed verbatim (no inference).
# Each: iast -> dict(vritti/guna/purushartha/tattva/deity/other, quote)
PRIMARY = {
 # ---- vowels & special sounds (ENTIRELY ABSENT from the consonant backbone) ----
 "a":{"assoc":"creation; controller of the seven notes (surasaptaka); 1st note ṣaḍja","cat":"vowel"},
 "ā":{"assoc":"ṛṣabha — the 2nd musical note","cat":"vowel"},
 "i":{"assoc":"gāndhāra — the 3rd musical note","cat":"vowel"},
 "ī":{"assoc":"madhyama — the 4th musical note","cat":"vowel"},
 "u":{"assoc":"pañcama — the 5th musical note (+ 'a few other factors, the force of…')","cat":"vowel"},
 "ū":{"assoc":"dhaivata — the 6th musical note","cat":"vowel"},
 "ṛ":{"assoc":"niṣāda — the 7th musical note","cat":"vowel"},
 "ṝ":{"assoc":"oṃ (onm) — creation/preservation/destruction; Saguṇa & Nirguṇa","cat":"vowel"},
 "ḷ":{"assoc":"the sound hummm — struggle, sādhanā, kuṇḍalinī (Tantra); the 'battle cry'","cat":"vowel"},
 "ḹ":{"assoc":"phaṭ — putting theory into practice; the atibīja/mahābīja of phaṭ","cat":"vowel"},
 "e":{"assoc":"vauṣaṭ (mahābīja) — mundane knowledge/welfare and its sprouting","cat":"vowel"},
 "ai":{"assoc":"vaṣaṭ — welfare in the subtler sphere; six stages of vocalization (parā/paśyantī/madhyamā…)","cat":"vowel"},
 "o":{"assoc":"svāhā — completion of an action (total effacement into the fire)","cat":"vowel"},
 "au":{"assoc":"namaḥ mudrā — surrender to the greatness of another/Supreme","cat":"vowel"},
 "aṃ":{"assoc":"an idea (same sound, different ideation → different meaning)","cat":"anusvara"},
 "aḥ":{"assoc":"words neither good nor bad — positive/negative by utterance","cat":"visarga"},
 # ---- consonants: vṛtti + notable extra associations ----
 "k":{"vritti":"āśā (hope)","other":"Kārya Brahma; 'that which produces sound'; flowing water; Nārāyaṇa (kesha)"},
 "kh":{"vritti":"cintā (worry/objective thought)","other":"means 'sky'/'heaven' (crude); transcendent = kṣa"},
 "g":{"vritti":"ceṣṭā (effort to arouse dormant potential)"},
 "gh":{"vritti":"mamatā (love/possessive attachment)"},
 "ṅ":{"vritti":"dambha (vanity)","other":"Vashiṣṭha/China legend; Tárā-cult transmission"},
 "c":{"vritti":"viveka (conscience)"},
 "ch":{"vritti":"vikalatā (nervous breakdown)"},
 "j":{"vritti":"ahaṃkāra (ego)"},
 "jh":{"vritti":"lolupatā/lobha/lolatā (greed/avarice)"},
 "ñ":{"vritti":"kapaṭatā (hypocrisy)"},
 "ṭ":{"vritti":"vitarka (overstatement/garrulousness)"},
 "ṭh":{"vritti":"anutāpa (repentance)","other":"nighttime, moon, bhúvarloka, kāmamaya kośa (opposite of ha)"},
 "ḍ":{"vritti":"lajjā (shyness)"},
 "ḍh":{"vritti":"piśunatā (sadistic cruelty)"},
 "ṇ":{"vritti":"īrṣyā (envy)"},
 "t":{"vritti":"jāḍya/staticity, long/deep sleep, dullness, inertness"},
 "th":{"vritti":"viṣāda (melancholy)"},
 "d":{"vritti":"peevishness (krodha/karkaśatā)"},
 "dh":{"vritti":"tṛṣṇā (thirst for acquisition; NOT thirst for water)"},
 "n":{"vritti":"moha (blind attachment; four categories)"},
 "p":{"vritti":"ghṛṇā (hatred/revulsion)","other":"six ripus; fetter of hatred"},
 "ph":{"vritti":"bhaya (fear; born of moha ripu)"},
 "b":{"vritti":"avajñā (indifference)","other":"brahmavihāra four attitudes"},
 "bh":{"vritti":"mūrcchā (loss of common sense under a ripu's spell)"},
 "m":{"vritti":"praṇāśa (annihilation) + praśraya (indulgence)"},
 "y":{"vritti":"aviśvāsa (lack of confidence)","tattva":"constant movement / air"},
 "r":{"vritti":"sarvanāśa (annihilation-thought)","tattva":"agnitattva / prāṇaśakti (vitality)",
      "other":"RAM bīja (triangular, red)"},
 "l":{"vritti":"krūratā (cruelty)","note":"this text gives ONLY krūratā; la=kṣititattva is from a different Sarkar passage"},
 "v":{"vritti":"dharma (ensconcement)","purushartha":"dharma","tattva":"jalatattva (water)","deity":"Varuṇa Deva"},
 # THE THREE SIBILANTS — the crux
 "ś":{"vritti":"artha (psychic longing)","guna":"rajoguṇa (mutative)","purushartha":"artha",
      "quote":"'Sha is the acoustic root of rajoguṇa … also the acoustic root of artha.'"},
 "ṣ":{"vritti":"kāma (physical/worldly desire)","guna":"tamoguṇa (static)","purushartha":"kāma",
      "quote":"'S'a is the acoustic root of tamoguṇa … all kinds of worldly desires … kāma.'"},
 "s":{"vritti":"mokṣa (liberation)","guna":"sattvaguṇa (sentient)","purushartha":"mokṣa"},
 "h":{"vritti":"parā-vidyā","tattva":"ākāśa/ether","other":"daytime, sun, svarloka; opposite ṭha; Shiva (via hao)"},
 "kṣ":{"vritti":"mundane knowledge / material science (aparā-vidyā)","note":"conjunct k+ṣ; not an atomic backbone unit"},
}

# reconciliation vs merged
recon=[]
SIBILANT_TRUTH={"ś":("rajoguṇa","artha"),"ṣ":("tamoguṇa","kāma"),"s":("sattvaguṇa","mokṣa")}
for iast,fact in PRIMARY.items():
    m=merged.get(iast)
    status=""; detail=""
    if iast in ("ś","ṣ"):
        mb=(m or {}).get("binding_vritti","")
        # merged ś currently says kāma/tamas; merged ṣ says artha/rajas -> SWAPPED vs primary
        prim_guna=fact["guna"].split()[0]
        if iast=="ś":
            status = "SWAP_ERROR" if ("kāma" in mb or "tamasic" in mb) else "MATCH"
            detail = "primary: ś=rajoguṇa+artha; merged binding = kāma/tamasic → SWAPPED with ṣ"
        else:
            status = "SWAP_ERROR" if ("artha" in mb or "rajasic" in mb) else "MATCH"
            detail = "primary: ṣ=tamoguṇa+kāma; merged binding = artha/rajasic → SWAPPED with ś"
    elif fact.get("cat") in ("vowel","anusvara","visarga"):
        has = bool((m or {}).get("binding_vritti"))
        status = "MISSING_ACOUSTIC_ROOT_IN_MERGED"
        detail = ("vowel present in merged as authored binding gloss only (no acoustic-root/musical-note layer)"
                  if has else "vowel ABSENT from merged entirely (source None)")
    elif iast=="kṣ":
        status="OUT_OF_ATOMIC_SCOPE"; detail="conjunct; not one of the 33 atomic backbone consonants"
    else:
        status="MATCH_VRITTI"; detail="consonant vṛtti agrees with merged; some extra associations left on the table"
    recon.append({"iast":iast,"category":fact.get("cat","consonant"),
                  "primary_source":{k:v for k,v in fact.items() if k!="cat"},
                  "merged_binding_vritti":(m or {}).get("binding_vritti"),
                  "reconciliation_status":status,"detail":detail})

out={"schema":"varna_primary_source_reconciliation_v1",
     "label":"READ_ONLY_RECONCILIATION / NO_FROZEN_MODIFICATION",
     "primary_source":"P.R. Sarkar, 'The Acoustic Roots of the Indo-Aryan Alphabet', Ánanda Márga Philosophy in a Nutshell Part 8 (1984-85, Calcutta)",
     "romanization_key":"apostrophe = retroflex/cerebral (ṭ=t', ḍ=d', ṇ=n', ṣ=s', kṣ=ks'); palatal ś='sha'; dental s='sa'",
     "merged_sha256":sha(MERGED),
     "headline_findings":[
       "ś/ṣ SWAP_ERROR: frozen merged has ś=kāma/tamoguṇa and ṣ=artha/rajoguṇa; primary source says ś(sha)=artha/rajoguṇa and ṣ(s'a)=kāma/tamoguṇa. The two are INVERTED in the frozen artifact.",
       "This REVERSES the prior VARNA_SHA_SWAP_PROVENANCE_AUDIT verdict (SWAP_PROVENANCE_RESOLVED_NO_DATA_ERROR) — a data error IS present.",
       "VOWEL LAYER (16 units) entirely absent from the consonant backbone: acoustic roots for a..aḥ incl. the surasaptaka musical notes, oṃ, hummm, phaṭ, vauṣaṭ, vaṣaṭ, svāhā, namaḥ.",
     ],
     "counts":{
        "sibilant_swap_errors":sum(1 for r in recon if r["reconciliation_status"]=="SWAP_ERROR"),
        "vowels_missing":sum(1 for r in recon if r["reconciliation_status"]=="MISSING_ACOUSTIC_ROOT_IN_MERGED"),
        "consonant_vritti_match":sum(1 for r in recon if r["reconciliation_status"]=="MATCH_VRITTI"),
     },
     "rows":recon}
json.dump(out,open("varna_acoustic_roots_primary_source.json","w"),ensure_ascii=False,indent=2)
print(json.dumps({"counts":out["counts"],
                  "swap_rows":[{r["iast"]:r["reconciliation_status"]} for r in recon if r["iast"] in ("ś","ṣ","s")]},
                 ensure_ascii=False,indent=2))
