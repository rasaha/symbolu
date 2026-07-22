# PSE Varṇa Tool — Old vs New Mapping Regression

`GENERATED — varna_lens/tools/regression_old_vs_new.py` · deterministic · no LLM

- **OLD**: `varna_lens/lexicon_authoritative.json` (retained as comparison artifact only)
- **NEW**: `varna_lens/lexicon_b1_12.json` (B1.12 frozen substrate → default runtime)
- Corpus: 24 words (English hybrid/g2p + IAST Sanskrit)

## Summary

- Drive/gloss (`essence_short`) changed: **24/24** words (expected — this IS the mapping-source swap).
- Structural fields changed (valence, trajectory roles, controlling element, tone, deterministic reflection, honesty): **0** field-diffs.
- New abstentions (varṇa unmapped in B1.12, e.g. `ksha`): **0** words.
- Honesty violations introduced: **0**.

## Structural changes (should be minimal — architecture is unchanged)

**None.** Every structural field (valence, trajectory roles, controlling element, tone, deterministic reflection, honesty_ok) is byte-identical old→new. Only the varṇa→drive gloss payload changed, confirming the swap is isolated to the symbolic substrate.

## New abstentions (explicit, surfaced — never silent)

None in this corpus.

## Drive/gloss changes (per word) — recorded, not judged

| word | old essence_short | new essence_short |
|---|---|---|
| river | `−Sarvanāśa⤳Prāṇaśakti / Agnitattva → +I-ness, doing self → +Dharma / J` | `−sarvanāśa — the defeatist annihilation-thought⤳prāṇaśakti — the fire ` |
| kill | `−Āśā⤳Nirāśā → +I-ness, doing self → −Krūratā⤳Karuṇā / Sneha` | `−āśā as grasping / clinging hope — goaded toward a specific outcome or` |
| compassion | `−Āśā⤳Nirāśā → +Completion, closure → −Praśraya / Praṇāśa⤳Anuśāsana → +` | `−āśā as grasping / clinging hope — goaded toward a specific outcome or` |
| freedom | `−Bhaya⤳Abhaya → +Prāṇaśakti / Agnitattva → +Specialization of self → +` | `−bhaya — fear: collapse or flight before danger; the shrinking, dread ` |
| temple | `−Vitarka⤳Maunam / Yathārthatā → +Practical thought, benefit → −Praśray` | `−vitarka — overstating one's case to the point of garrulousness; bad-t` |
| wife | `−Adharma⤳Dharma / Jalatattva → +I-ness, doing self → −Bhaya⤳Abhaya` | `−ensconcement gone rigid — over-holding, clinging to one's holding; st` |
| poison | `−Ghṛṇā⤳Maitrī / Sneha → +Completion, closure → +Mokṣa / Sattvaguṇa → +` | `−ghṛṇā — the fetter of hatred / revulsion: hatred arising⤳the upward t` |
| knife | `−Īrṣyā⤳Muditā → +I-ness, doing self → −Bhaya⤳Abhaya` | `−envy — the sting at another's success; covetous resentment at another` |
| happy | `−Avidyā / Rātri⤳Parā-vidyā → +Birth of cognition / raw potential → +Ma` | `−outward / visible vision — fixation on the manifest, physically-seen,` |
| courage | `−Āśā⤳Nirāśā → +Completion, closure → −Birth of cognition / raw potenti` | `−āśā as grasping / clinging hope — goaded toward a specific outcome or` |
| xozence | `−Āśā⤳Nirāśā → +Transmutation of desire / grounded containment → +Compl` | `−āśā as grasping / clinging hope — goaded toward a specific outcome or` |
| cognade | `−Aviveka⤳Viveka → +Completion, closure → −Ceṣṭā⤳Sthiti → +Viveka → +Bi` | `−viveka distorted — discernment hardening into judgmentalism / separat` |
| kāla | `−Āśā⤳Nirāśā → +Ongoing thought / expansion → +Karuṇā / Sneha   ⟹ [+Bir` | `−āśā as grasping / clinging hope — goaded toward a specific outcome or` |
| karma | `−Āśā⤳Nirāśā → +Birth of cognition / raw potential → −Sarvanāśa⤳Prāṇaśa` | `−āśā as grasping / clinging hope — goaded toward a specific outcome or` |
| dama | `−Lajjā⤳Nirbhayatā / Svīkāra → +Birth of cognition / raw potential → +A` | `−lajjā as inhibition — action held back by others' regard; shrinking, ` |
| akrodha | `−Birth of cognition / raw potential → −Āśā⤳Nirāśā → +Prāṇaśakti / Agni` | `−Birth of cognition / raw potential → −āśā as grasping / clinging hope` |
| garva | `−Ceṣṭā⤳Sthiti → +Birth of cognition / raw potential → −Sarvanāśa⤳Prāṇa` | `−restless striving that cannot stop — effort compulsively driven on, u` |
| sneha | `−Escapism⤳Mokṣa / Sattvaguṇa → +Viveka → +Practical thought, benefit →` | `−the sentient / sattvic impulse clung to — clarity, purity or harmony ` |
| dhṛti | `−Tṛṣṇā⤳Nivṛtti / Tuṣṭi → +Jāgaraṇa   ⟹ [+I-ness, doing self]` | `−tṛṣṇā — limitless thirst to acquire: unquenchable craving for wealth,` |
| kleśa | `−Āśā⤳Nirāśā → +Karuṇā / Sneha → +Practical thought, benefit → +Directe` | `−āśā as grasping / clinging hope — goaded toward a specific outcome or` |
| śānti | `−Restless acquisition / material greed⤳Directed energy / purposeful ma` | `−artha as possessive acquisition — worldly purpose pursued and possess` |
| ṣaṭ | `−Kāma / Tamoguṇa⤳Transmutation of desire / grounded containment → +Bir` | `−kāma — worldly / physical desire and longing: grasping for wealth, op` |
| kṣamā | `−Āśā⤳Nirāśā → +Transmutation of desire / grounded containment → +Birth` | `−āśā as grasping / clinging hope — goaded toward a specific outcome or` |
| yoga | `−Aviśvāsa⤳Viśvāsa → +Completion, closure → +Sthiti   ⟹ [+Birth of cogn` | `−aviśvāsa — self-doubt that cannot commit: lack of confidence and wave` |

*Old glosses are short two-pole labels (e.g. `Hope`/`Detach`); new glosses are the B1.12 binding/liberating vṛtti prose (verbatim). `_short()` truncates each at the first `(`.*
