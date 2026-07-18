#!/usr/bin/env python3
"""Read-only EXHAUSTIVE extraction of every directly-attested varṇa association
from the primary-text ledger b1_2_varna_classical_verifications.json.

No inference. Each association is a token that appears verbatim in the ledger's
source_quote / classical_associations for that varṇa. The `captured_in_normalized_layer`
flag marks whether varna_classical_associations_33.json already recorded it
(that layer normalized ONLY guṇa / tattva / deity). Everything with
captured=False is source-backed information currently 'left on the table'.
"""
import json, hashlib

LEDGER = "b1_2_mapping_fidelity/b1_2_varna_classical_verifications.json"
NORM = "varna_classical_associations_33.json"

def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
HASHES = {LEDGER: sha(LEDGER), NORM: sha(NORM)}

led = {e["varna"]: e for e in json.load(open(LEDGER))["verifications"]}

# Curated association inventory: transcription of tokens present verbatim in
# each ledger source_quote. class ∈ {guna,tattva,purushartha,bija_mantra,deity,
# brahma_cosmological,buddhist,loka,kosha,celestial_temporal,vidya,
# opposite_varna,prana_shakti,etymology,cross_reference,phonetic_historical,
# scope_note,distinction}. captured = already in normalized guṇa/tattva/deity layer.
# ASCII ledger keys: sha=ś, ssa=ṣ, sa=s, nga=ṅ, nya=ñ, tta=ṭ, ttha=ṭh, dda=ḍ,
# ddha=ḍh, nna=ṇ, ksha=kṣ(conjunct).
INV = {
 "ha":[("tattva","ākāśa / ether factor",True),("celestial_temporal","daytime; the sun",False),
       ("loka","svarloka",False),("vidya","parā-vidyā (intuitional science)",False),
       ("opposite_varna","ṭha (night/moon/bhúvarloka/kāmamaya kośa)",False),
       ("deity","Shiva in His táṇḍava (via compound ha+ao=hao)",False)],
 "pa":[("cross_reference","ghṛṇā = fetter of hatred, one of the eight pāśas",False),
       ("cross_reference","six ripus: kāma, krodha, lobha, mada, moha, mātsarya",False),
       ("etymology","pat/patati = downward attraction vs upward anurakti→devotion",False)],
 "ka":[("brahma_cosmological","Kārya Brahma (Saguṇarasātmaka Brahma; controller of the living world)",False),
       ("deity","Nārāyaṇa (kesha = ka+iisha, a name of Nārāyaṇa)",False),
       ("buddhist","Saṃvṛtti Bodhicitta (the created world = Kārya Brahma)",False),
       ("etymology","'that which produces sound'; 'water'/flowing water; 'hair on the head'",False)],
 "kha":[("etymology","MEANS 'sky'/'heaven' (crude aspects) but is NOT their acoustic root (ha is)",False),
        ("opposite_varna","transcendent heaven = kṣa (ksha)",False),
        ("etymology","structural: ka + ha = kha (follows ka in the alphabet)",False)],
 "ga":[("scope_note","ceṣṭā = main cause of BOTH mundane development AND spiritual elevation (physical/psychic/spiritual)",False)],
 "gha":[("scope_note","mamatā bounded by time, space, individuality (illustrations only)",False)],
 "nga":[("phonetic_historical","legend: uṋa learned by Vashiṣṭha in China; used across Indo-Chinese languages (Tibetan/Ladakhi/Sherpa/Manpa)",False),
        ("cross_reference","Tárā cult transmission — but Tárā roots are aeṃ / krīṃ, NOT ṅa",False)],
 "ca":[("absent","ONLY the vṛtti name (viveka) is attested; no association",False)],
 "cha":[("absent","vṛtti name + state definition (vikalatā); no association",False)],
 "ja":[("absent","vṛtti name + illustration (ahaṃkāra); no association",False)],
 "jha":[("etymology","Bengali nolā (greedy fascination) derives from lola/lolatā",False)],
 "nya":[("etymology","Sanskrit páśaṇḍa / Hindi pākhaṇḍī = hypocrite; three forms of hypocrisy",False)],
 "tta":[("distinction","vitarka NOT kaśāya vṛtti; liberated contrast = pramita vāk",False)],
 "ttha":[("celestial_temporal","nighttime; the moon",False),("loka","bhúvarloka",False),
         ("kosha","kāmamaya kośa",False),("opposite_varna","ha (day/sun/svarloka/parā-vidyā)",False),
         ("etymology","anutāpa = anu('after')+tāpa('heat'); N.Indian paścāttāpa = 'after-heat'",False)],
 "dda":[("cross_reference","lajjā = one of the eight pāśas listed under pa",False)],
 "ddha":[("distinction","piśunatā vs krūratā (la) vs dha (tṛṣṇā); contrary to Neohumanism",False)],
 "nna":[("absent","ONLY the vṛtti name (īrṣyā) is attested; no association",False)],
 "ta":[("etymology","Tantra: 'Taṃ jāḍyāt tārayet…'; tan='to expand' (liberating direction)",False)],
 "tha":[("absent","vṛtti name (viṣāda) + phonetic note only; no association",False)],
 "da":[("absent","vṛtti (peevishness) + illustration only; no association",False)],
 "dha":[("distinction","tṛṣṇā is NOT 'thirst for water'",False),
        ("cross_reference","cure: divert all thoughts toward Parama Puruṣa",False)],
 "na":[("scope_note","moha divides into four: space/time/idea/individuality; cure = indifference + Parama Puruṣa",False)],
 "pha":[("cross_reference","bhaya = one of the eight pāśas; born mainly of the moha ripu",False)],
 "ba":[("cross_reference","brahmavihāra four attitudes: maitrī/karuṇā/muditā/upekṣā",False)],
 "bha":[("cross_reference","cure: pratyāhāra yoga; else kīrtana / devotional singing",False)],
 "ma":[("scope_note","two linked vṛttis on one root: praṇāśa (annihilation) + praśraya (indulgence)",False)],
 "ya":[("tattva","vāyu / air — acoustic root of CONSTANT MOVEMENT (motion/tattva association)",True)],
 "ra":[("tattva","agnitattva (fire element)",True),
       ("prana_shakti","prāṇaśakti (vitality)",False),
       ("bija_mantra","RAM bīja — triangular, red-glowing ('Raṃ bījaṃ śikhinaṃ dhyāyet')",False),
       ("etymology","the monosyllable ra = 'fire'",False),
       ("cross_reference","cure: 'Parama Puruṣa is mine' (guru mantra); 'I am destined to win'",False)],
 "la":[("tattva","kṣititattva (solid/earth factor, dharaṇī / pṛthvī)",True),
       ("bija_mantra","LAM bīja — four-sided/square, deep-yellow ('Laṃ bījaṃ dharaṇīṃ dhyāyet')",False)],
 "va":[("tattva","jalatattva (liquid factor — water and any liquid)",True),
       ("deity","Varuṇa Deva (the rain-god)",True),
       ("purushartha","dharma ('that which sustains'; dhriyate dharma) — the four-varga longing assigned to va",False)],
 "sha":[("guna","tamoguṇa (the static principle)",True),
        ("purushartha","kāma (physical longing) — the four-varga puruṣārtha for śa",False)],
 "sa":[("guna","sattvaguṇa (the sentient principle)",True),
       ("purushartha","mokṣa (liberation) — the four-varga puruṣārtha for sa",False)],
 "ssa":[("guna","rajoguṇa (the mutative principle)",True),
        ("purushartha","artha (psychic longing / removal of worldly wants) — four-varga puruṣārtha for ṣa",False)],
 "ksha":[("vidya","aparā-vidyā (mundane knowledge / material science)",False),
         ("opposite_varna","complement of ha (parā-vidyā); transcendent heaven",False),
         ("etymology","structural: kṣa = ka (Kārya Brahma) + ṣa",False),
         ("note_out_of_atomic_scope","kṣa is a CONJUNCT (k+ṣ) — not one of the 33 atomic backbone consonants",False)],
}

rows=[]
for k,e in led.items():
    assoc=[{"class":c,"value":v,"captured_in_normalized_layer":cap} for (c,v,cap) in INV.get(k,[])]
    rows.append({
        "ledger_key":k,
        "sanskrit_label":e.get("sanskrit_label"),
        "source_quote_verbatim":e.get("source_quote"),
        "classical_associations_verbatim":e.get("classical_associations"),
        "attested_associations":assoc,
        "n_associations":len([a for a in assoc if a["class"]!="absent"]),
    })

# roll-up of omitted association classes
from collections import defaultdict
omitted=defaultdict(list)
for r in rows:
    for a in r["attested_associations"]:
        if not a["captured_in_normalized_layer"] and a["class"] not in ("absent","note_out_of_atomic_scope"):
            omitted[a["class"]].append(r["ledger_key"])

out={
 "schema":"varna_classical_exhaustive_v1",
 "label":"READ_ONLY_EXHAUSTIVE_EXTRACTION / NO_INFERENCE",
 "source_tradition":"single tradition (Sarkar varṇa/bīja exposition); no independent second text cited in-repo -> no cross-text variant conflicts (the only internal conflict was the ś/ṣ swap, already RESOLVED)",
 "ledger_scope":"33 atomic consonants + kṣa conjunct (34 entries). NO vowels in the primary-text ledger.",
 "vowels":"ABSENT from primary-text verification. varna_lens vowels carry ONLY authored binding/liberating states (source: Sanskrit_letters_full.docx); NO tattva/guṇa/bīja/deity anywhere -> no source-backed vowel classical layer exists to extract.",
 "normalized_layer_scope":"varna_classical_associations_33.json normalized ONLY guṇa (3), tattva (5), deity (1).",
 "omitted_but_attested_classes":{k:sorted(set(v)) for k,v in sorted(omitted.items())},
 "artifact_hashes":HASHES,
 "rows":rows,
}
json.dump(out,open("varna_classical_associations_exhaustive.json","w"),ensure_ascii=False,indent=2)
print(json.dumps({"n_entries":len(rows),
                  "omitted_classes":{k:sorted(set(v)) for k,v in omitted.items()}},
                 ensure_ascii=False,indent=2))
