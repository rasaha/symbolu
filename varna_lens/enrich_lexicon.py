#!/usr/bin/env python3
"""Enrich lexicon_authoritative.json with source literature as NON-SCORING metadata.

NOTE (schema migration): the two reading fields were later renamed `positive`→`liberating_state` and
`negative`→`binding_state` by `migrate_ontology.py`. This historical script still references the old
names; the design below is unchanged in spirit (the expanded_properties metadata never affects the reading).

Design (per the agreed contract): keep the two reading states as the ONLY reading axis (the deterministic
engine reads binding_state=worldly→leading_vritti, liberating_state=counter→counter_vritti — untouched here). Add an
`expanded_properties` block per consonant carrying the authoritative acoustic-root literature (vṛtti,
cosmic/elemental functions, imagery, etymology, semantic extensions, deity links, source quote). These
ENRICH interpretation only; they must NOT change the polarity score. Re-runnable: merges idempotently.
"""
import json, pathlib

PATH = pathlib.Path(__file__).with_name("lexicon_authoritative.json")

# key -> expanded_properties (only sub-keys the source provides). Source: P.R. Sarkar, acoustic-roots
# discourses (Varṇa Vijñāna), as supplied by the project owner.
ENRICH = {
 "ka": {
   "vrtti": {"name": "Āśā", "english": "hope / forward-seeking desire", "type": "abhiipśātmaka"},
   "acoustic_roots": ["Kārya Brahma (the expressed/manifested universe; controller of the living world)",
                      "creation / expression", "Saṃvṛtti Bodhicitta (Buddhist name for the created world)"],
   "elemental": "flowing water (ka = water; va = water in general)",
   "etymology": "kae + ḍa = 'that which produces sound'; the roar of rivers/springs inspired the hope of survival",
   "semantic_extensions": ["kac = glossy", "ka / keśa = hair grown on the head",
                           "keśa = ka + īśa = hair, also Nārāyaṇa",
                           "kāpālika = 'kaṃ saṃvṛtti bodhicittaṃ pālayati' = one who serves the living & non-living world"],
   "deity_links": ["Śiva (Vyomakeśa / Khakuntala — hair toward the sky; Dhurjaṭī)", "Nārāyaṇa (via keśa)"],
   "mantra_note": "kriiṃ = ka (Kārya Brahma) + ra (luminous factor); bīja of Kālī / Bhrāmarī Tārā",
   "domain_tags": ["hope", "manifestation", "creation", "expression", "flowing_water", "survival_signal",
                   "sound", "hair", "gloss", "karya_brahma"],
   "source_quote": "Ka is the acoustic root of the abhiipśātmaka áshá vrtti. It is also the acoustic root of Kárya Brahma [the expressed universe]. … Ka (kae + d́a) etymologically means 'that which produces sound'. It also means 'water'.",
 },
 "kha": {
   "vrtti": {"name": "Cintā", "english": "worry / impersonal, objective thought", "type": "vishuddha saṃvedanātmaka"},
   "acoustic_roots": ["the crude aspects of heaven (the transcendent sphere of heaven is kṣa)"],
   "note": "kha means 'sky' but is NOT the acoustic root of sky (that is ha); ka + ha = kha, so kha follows ka",
   "domain_tags": ["worry", "impersonal_thought", "crude_heaven"],
   "source_quote": "The acoustic root of áshá vrtti is ka, and that of cintá vrtti [the propensity of worry] is kha. … Impersonal thoughts are symbolized by the acoustic root kha.",
 },
 "ga": {
   "vrtti": {"name": "Ceṣṭā", "english": "effort / striving to arouse dormant potential"},
   "note": "the main cause of mundane development and spiritual elevation; acts in physical, psychic and spiritual spheres",
   "domain_tags": ["effort", "striving", "development", "elevation"],
   "source_quote": "The effort made to arouse one's dormant potentiality is called ceśt́á. … Ga, being the acoustic root of ceśt́á vrtti, plays an important role in the physical, psychic and spiritual spheres.",
 },
 "gha": {
   "vrtti": {"name": "Mamatā", "english": "love / attachment (bound by time, space, individuality)"},
   "imagery": "the mother who sacrifices for her child yet slices kai fish without feeling; the cow who suckles then later kicks her calf — mamatā limited by relative factors; only humans can transcend it",
   "domain_tags": ["attachment", "love", "mine-ness", "relativity"],
   "source_quote": "Mamatá, the vrtti of love and attachment …, is related to time, space and individuality. … Gha is the acoustic root of mamatá vrtti.",
 },
 "nga": {
   "vrtti": {"name": "Dambha", "english": "vanity"},
   "history": "Vashiṣṭha is said to have learned uṋa (and the Tārā cult of Vāmācāra Tantra) from China; uṋa is used across Indo-Chinese languages",
   "domain_tags": ["vanity", "pride"],
   "source_quote": "Uṋa is the acoustic root of dambha vrtti [the propensity of vanity].",
 },
 "ca": {
   "vrtti": {"name": "Viveka", "english": "conscience / discrimination"},
   "domain_tags": ["conscience", "discrimination"],
   "source_quote": "Ca is the acoustic root of viveka [conscience].",
 },
 "cha": {
   "vrtti": {"name": "Vikalatā", "english": "nervous breakdown"},
   "note": "a mind that had been functioning properly starts malfunctioning or stops altogether",
   "domain_tags": ["nervous_breakdown", "collapse"],
   "source_quote": "Cha is the acoustic root of vikalatáh vrtti [nervous breakdown].",
 },
 "ja": {
   "vrtti": {"name": "Ahaṃkāra", "english": "ego / inflated I-feeling"},
   "imagery": "Aurangzeb: 'Since I was there, I controlled the situation … had I not been there the world would have met its destruction' — an expression of ahaṃkāra",
   "domain_tags": ["ego", "I-feeling", "inflation"],
   "source_quote": "Ja is the acoustic root of ahaḿkára vrtti (ego). The ego becomes inflated when one allows one's 'I' feeling to take a predominant role.",
 },
 "jha": {
   "vrtti": {"name": "Lolupatā / Lobha / Lolatā", "english": "greed / avarice"},
   "etymology": "Bengali nolá (greedy fascination of a cat/dog) derives from lola / lolatā",
   "domain_tags": ["greed", "avarice", "craving_fascination"],
   "source_quote": "Jha is the acoustic root of lolupatá, lobha [greed] and lolatá [avarice] vrttis.",
 },
 "nya": {
   "vrtti": {"name": "Kapaṭatā", "english": "hypocrisy"},
   "note": "Sanskrit pāṣaṇḍa / Hindi pākhaṇḍī = hypocrite; three forms: (1) cheating to serve one's purpose, (2) dominating to hide one's ignorance, (3) condemning sins one secretly commits",
   "domain_tags": ["hypocrisy", "deceit"],
   "source_quote": "Ina is the acoustic root of kapat́atá vrtti [hypocrisy].",
 },
 "tta": {
   "vrtti": {"name": "Vitarka", "english": "overstating one's case (garrulousness + bad temper)"},
   "note": "NOT mere debating, and NOT kaṣāya (harsh speech to hurt); its opposite is pramita vāk (balanced, only-relevant speech). Howrah-station example.",
   "domain_tags": ["overstatement", "garrulousness", "bad_temper"],
   "source_quote": "T́a is the acoustic root of vitarka vrtti [overstating one's case]. … Vitarka is a combination of a bad temper and garrulousness.",
 },
 "ttha": {
   "vrtti": {"name": "Anutāpa", "english": "repentance"},
   "etymology": "N. India paschāttāpa; anu / paschāt = 'later/after', tāpa = 'heat'",
   "domain_tags": ["repentance", "remorse"],
   "source_quote": "T́ha is the acoustic root of anutápa vrtti [repentance].",
 },
 "dda": {
   "vrtti": {"name": "Lajjā", "english": "shyness"},
   "domain_tags": ["shyness"],
   "source_quote": "D́a is the acoustic root of lajjá vrtti [the propensity of shyness].",
 },
 "ddha": {
   "vrtti": {"name": "Piśunatā", "english": "senseless / sadistic cruelty"},
   "imagery": "slow, cruel killing (chopping legs, then tail, then head); the half-chopped live tortoise crawling away — contrary to Neohumanism",
   "domain_tags": ["sadistic_cruelty", "torture"],
   "source_quote": "Senseless, sadistic killing is called pishunatá vrtti.",
 },
 "nna": {
   "vrtti": {"name": "Īrṣyā", "english": "envy"},
   "domain_tags": ["envy"],
   "source_quote": "Ńa is the acoustic root of iirśá vrtti [the propensity of envy].",
 },
 "ta": {
   "vrtti": {"name": "Jāḍya / Nidrā", "english": "staticity, long/deep sleep, intellectual dullness, spiritual inertness"},
   "etymology": "Tantra = 'taṃ jāḍyāt tārayet' (liberates from staticity); root tan = 'to expand' (taṃ vistāreṇa tārayet)",
   "domain_tags": ["inertia", "sleep", "dullness", "staticity"],
   "source_quote": "Ta is the acoustic root of staticity, long sleep and deep sleep. … That which brings about the cessation of dullness and staticity is called Tantra.",
 },
 "tha": {
   "vrtti": {"name": "Viṣāda", "english": "melancholy"},
   "domain_tags": ["melancholy", "dejection"],
   "source_quote": "Tha is the acoustic root of viśada vrtti, of melancholy.",
 },
 "da": {
   "vrtti": {"name": "Krodha / Karkaśatā", "english": "peevishness / irritability"},
   "note": "speak nicely to a peevish person and they react adversely; speak harshly and they take it calmly",
   "domain_tags": ["peevishness", "irritability"],
   "source_quote": "Da is the acoustic root of peevishness.",
 },
 "dha": {
   "vrtti": {"name": "Tṛṣṇā", "english": "thirst for acquisition (wealth, name, fame, power, prestige)"},
   "note": "not thirst for water; cure = divert all thought toward Parama Puruṣa",
   "domain_tags": ["craving", "acquisition", "ambition"],
   "source_quote": "Dha is the acoustic root of thirst for acquisition. This limitless craving … is called trśńa in Sanskrit.",
 },
 "na": {
   "vrtti": {"name": "Moha", "english": "blind attachment / infatuation"},
   "note": "four types: deśagata (geo-sentiment), kālagata (time), idea-bound, ādhāragata (object); cure = ideation of indifference + Parama Puruṣa",
   "domain_tags": ["blind_attachment", "infatuation", "delusion"],
   "source_quote": "Na is the acoustic root of moha vrtti [blind attachment or infatuation].",
 },
 "pa": {
   "vrtti": {"name": "Ghṛṇā", "english": "hatred / revulsion (a fetter / pāśa)"},
   "note": "one of 8 pāśas (ghṛṇā, śaṅkā, bhaya, lajjā, jugupsā, kula, śīla, māna); mainly tied to the moha ripu; root pat/patati = downward fall vs ūrdhva-gati / anurakti (devotion). The 6 ripus: kāma, krodha, lobha, mada, moha, mātsarya.",
   "domain_tags": ["hatred", "revulsion", "fetter", "downfall"],
   "source_quote": "Pa is the acoustic root of ghrńá vrtti [the propensity of hatred or revulsion]. … Pa is the acoustic root of the fetter of hatred.",
 },
 "pha": {
   "vrtti": {"name": "Bhaya", "english": "fear"},
   "note": "generally born of more than one factor, but mainly from the moha ripu",
   "domain_tags": ["fear"],
   "source_quote": "Pha is the acoustic root of bhaya vrtti [the propensity of fear].",
 },
 "ba": {
   "vrtti": {"name": "Avajñā", "english": "indifference (neglecting something of value)"},
   "note": "distinguished from upekṣā (ignoring the truly unacceptable); related to avahelā; maitrī–karuṇā–muditā–upekṣā verse on the four attitudes",
   "domain_tags": ["indifference", "neglect"],
   "source_quote": "Ba is the acoustic root of avajiṋá vrtti [indifference]. … when one neglects something which may actually have some value, that is called avajiṋá.",
 },
 "bha": {
   "vrtti": {"name": "Mūrcchā", "english": "deluded obsession (loss of common sense under a ripu's spell)"},
   "note": "NOT senselessness; cure = pratyāhāra yoga, or kīrtana / devotional song",
   "domain_tags": ["deluded_obsession", "hypnotic_spell"],
   "source_quote": "Bha is the acoustic root of the múrcchá vrtti. … it means to lose one's common sense under the hypnotic spell of a particular ripu.",
 },
 "ma": {
   "vrtti": {"name": "Praṇāśa + Praśraya", "english": "annihilation; and giving latitude / indulgence (Hindi baṛhvā denā)"},
   "domain_tags": ["annihilation", "indulgence", "latitude"],
   "source_quote": "Ma is the acoustic root of prańásha [annihilation]. It is also the acoustic root of prashraya vrtti – giving latitude [indulgence].",
 },
 "ya": {
   "vrtti": {"name": "Aviśvāsa", "english": "lack of confidence (in oneself and others)"},
   "elemental": "constant movement (like the movement of air)",
   "note": "such people say to the end 'Shall I be able to do it?' and can accomplish nothing great",
   "domain_tags": ["lack_of_confidence", "movement", "air"],
   "source_quote": "Ya is the acoustic root of avishvása vrtti [lack of confidence], and is also the acoustic root of constant movement (like the movement of air).",
 },
 "ra": {
   "vrtti": {"name": "Agnitattva / Prāṇaśakti (vitality) + Sarvanāśa (annihilation-thought)",
             "english": "vitality / fire; and the defeatist thought 'everything is gone, I am undone'"},
   "elemental": "agnitattva (fire); the monosyllable 'ra' means fire",
   "note": "sarvanāśa cured by guru mantra auto-suggestion 'Parama Puruṣa is mine / I am destined to win'",
   "mantra_note": "Raṃ bījaṃ shikhinaṃ dhyāyet, trikoṇam-aruṇaprabham (meditate on the bīja Raṃ, triangular, fire-red)",
   "domain_tags": ["vitality", "fire", "agnitattva", "annihilation_thought", "defeat", "luminous_factor"],
   "source_quote": "Ra is the acoustic root of agnitattva or práńashakti – vitality. … It is also the acoustic root of sarvanásha [the thought of annihilation]. … the monosyllabic word ra means 'fire'.",
 },
 "la": {
   "vrtti": {"name": "Krūratā", "english": "cruelty (countered by compassion)"},
   "elemental": "kṣititattva (the solid factor)",
   "mantra_note": "Laṃ bījaṃ dharaṇīṃ dhyāyet, caturāsrāṃ supītābhām (meditate on bīja Laṃ, square, golden — the earth factor)",
   "domain_tags": ["cruelty", "solid_factor", "earth"],
   "source_quote": "La is the acoustic root of kruratá vrtti [cruelty]. … La is also the acoustic root of kśititattva, the solid factor.",
 },
 "va": {
   "vrtti": {"name": "Dharma", "english": "ensconcement in one's original stance; movement toward Parama Puruṣa"},
   "elemental": "jalatattva (the liquid factor — any liquid, not only water)",
   "deity_links": ["Varuṇa Deva (the mythological rain-god)"],
   "note": "Dhriyate dharma ityāhuḥ — 'dharma is that which sustains'; humanity cannot sprout except in the soil of dharma",
   "domain_tags": ["dharma", "original_stance", "liquid_factor", "water", "sustaining"],
   "source_quote": "Va is the acoustic root of dharma. … Va is also the acoustic root of jalatattva [the liquid factor], and the acoustic root of the rain-god Varuńa Deva.",
 },
 "sha": {
   "vrtti": {"name": "Rajoguṇa + Artha", "english": "the mutative principle; and artha (psychic longing — temporary cessation of worldly wants)"},
   "note": "shra = mutative principle + vitality (ra); shra + ṅīṣ = shrii (hence 'Śrī' before a name, a blessing on dynamism)",
   "domain_tags": ["rajoguna", "mutative", "artha", "dynamism"],
   "source_quote": "Sha is the acoustic root of rajoguńa [the mutative principle]. It is also the acoustic root of artha [psychic longing].",
 },
 "ssa": {
   "vrtti": {"name": "Tamoguṇa + Kāma", "english": "the static principle; and kāma (all physical/worldly desires — wealth, fame, position)"},
   "note": "one of the four vargas (dharma=va, artha=sha, kāma=ṣa, mokṣa=sa)",
   "domain_tags": ["tamoguna", "static", "kama", "worldly_desire"],
   "source_quote": "Śa is the acoustic root of tamoguńa [the static principle], and is also the acoustic root of all kinds of worldly desires … káma.",
 },
 "sa": {
   "vrtti": {"name": "Mokṣa + Sattvaguṇa", "english": "liberation (unqualified); and the sentient principle"},
   "note": "completes the four vargas: va=dharma, sha=artha, ṣa=kāma, sa=mokṣa; and the three guṇas: sha=rajas, ṣa=tamas, sa=sattva",
   "domain_tags": ["moksa", "liberation", "sattvaguna", "sentient"],
   "source_quote": "Sa is the acoustic root of mokśa [salvation, unqualified liberation]. … sa is the acoustic root of sattvaguńa [the sentient principle].",
 },
 "ha": {
   "vrtti": {"name": "Parā-vidyā", "english": "intuitional science; ethereal factor, daytime, the sun, svarloka"},
   "note": "opposite of ṭha (night, moon, bhūvarloka, kāmamaya kośa); ha + ao = hao (Śiva in tāṇḍava dance); Śiva as preceptor = aeṃ (also bīja of the guru and of Sarasvatī)",
   "domain_tags": ["ether", "day", "sun", "svarloka", "para_vidya", "intuition"],
   "source_quote": "Ha is the acoustic root of the ethereal factor, of daytime, of the sun, of svarloka, and of parávidyá [intuitional science].",
 },
 "ksha": {
   "vrtti": {"name": "Aparā-vidyā", "english": "mundane knowledge / material science"},
   "note": "also the acoustic root of the transcendent sphere of heaven (vs kha = crude heaven)",
   "domain_tags": ["mundane_knowledge", "material_science"],
   "source_quote": "Kśa is the acoustic root of mundane knowledge, and is also the acoustic root of material science.",
 },
}


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    cons = data["consonants"]
    added = 0
    for k, ep in ENRICH.items():
        if k in cons:
            cons[k]["expanded_properties"] = ep
            added += 1
    data["_expanded_properties_note"] = (
        "expanded_properties = source acoustic-root literature (P.R. Sarkar, Varṇa Vijñāna) as INTERPRETIVE "
        "METADATA only. It enriches reading/authoring but does NOT affect the polarity score, which uses "
        "ONLY positive/negative. Scoring fields: positive, negative. Metadata fields: expanded_properties, "
        "source_vritti, source_notes."
    )
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"enriched {added}/{len(cons)} consonants with expanded_properties; scoring fields untouched.")


if __name__ == "__main__":
    main()
