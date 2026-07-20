# HIDDEN_EVALUATION_LOCK_V2 — Proposal Validation Experiment v0.1

**Lock version:** `v0.2`  
**Combined lock hash:** `a15f4aa24a906602d300863efe1e5aac38d776a78c1e0ca2c27769a708cc07ce`  
**Manifest hash:** `505e11f8709ae4e15d1ec597cc7cca58d9b5f22ff2db94b8ca93ffcf9dab27e7`

Computed BEFORE the first hidden evaluation of v0.2. The v0.1 experiment and all
frozen platform artifacts are hashed here to prove they are unchanged.

## Manifest
```json
{
  "study": "Proposal Validation Experiment v0.1",
  "resolver_under_test": "HybridRelationshipResolver Experimental v0.2",
  "ablation_order": [
    "V0_none",
    "V1_dedupe_only",
    "V2_evidence_only",
    "V3_authority_temporal",
    "V4_full"
  ],
  "floor_lexical": 0.6,
  "floor_structural": 0.5,
  "primary_endpoint": "recover discovery precision with recall loss <= 0.03 vs V0",
  "recall_loss_margin": 0.03,
  "order_sensitive_types": [
    "supersedes",
    "amends",
    "effective_after"
  ],
  "destination_required_types": [
    "supersedes",
    "amends",
    "overrides",
    "governs_over",
    "exception_to",
    "conflicts_with",
    "effective_after"
  ],
  "bootstrap_seed": 20240601,
  "bootstrap_iters": 10000,
  "repetitions": 2,
  "byte_identical_required": true,
  "note": "v0.1 experiment and all frozen platform artifacts are unchanged."
}
```

## v0.2 source hashes (SHA-256)
| file | sha256 |
|---|---|
| `validator.py` | `257ed63c0a35b6140b957188a479f32e1ca6ebef0db8bae45099fd5e83da89dc` |
| `hybrid_resolver_v2.py` | `620e82c76d7f35932fc9c40af2241d4749d6dac1400b35faf2708529cbaa5a8e` |
| `run_validation_experiment.py` | `52551201b602a0cb6cde530d153cacc453822ac18f532a05ecdd1f94898aa19d` |
| `lock_v2.py` | `269317042206f1f1bdd264901c582e850654751718edd3a7207bdc9515355eca` |
| `PROPOSAL_VALIDATION_PREREGISTRATION.md` | `67d0156185cbe33df822746e1a43b66b16fbb4a33b76dbb045c13c659e8b0297` |
| `VALIDATION_RULEBOOK.md` | `d00e5a2af27fc526db3f0ef7347a011f86ee3f3be47680efdb788f78064e989d` |
| `CONFIDENCE_VECTOR_SPEC.md` | `5b313ad00a8cff6338b04a5465e5ade0e3e2110b7aa26cd0e017905e90acf733` |

## Frozen-dependency hashes (must be unchanged)
| file | sha256 |
|---|---|
| `experiment/hybrid_resolver.py` | `a2bb9803f0d180dd80a0f3c7806247dde284b9830240a44095fdd4632b887add` |
| `experiment/hidden_data.py` | `a32119d1b4bf84f8f871d88f2b52b704da2ff25ef9840191710b7bfe10973813` |
| `experiment/hidden_metrics.py` | `b878994f23a312de2d09d008661c52f3b19cbb6b913cd8b98b683388f3e90228` |
| `experiment/stats.py` | `03ca5b37b5da45dce5c43f80e2a82299895665f219d847ba6f6751976fc82cd3` |
| `resolution/resolvers.py` | `a5eba70cf0b2f4a564ed848a93cb5e4d1006bf87e5e7e6afff619d8d99c0ef53` |
| `resolution/parse.py` | `f84657b904255b1071d8705eb5be629d1e70671355177c52e22bb8dafebf8f47` |
| `resolution/graph.py` | `db7309356ddb1ab1599d3526e85618a8c734310ce3dd3ed3640b816776e3c645` |
| `measurement/stage_metrics.py` | `e105714cfa3d5785303c0219e035b194a2cc219391deb574b9455aea920c1419` |
| `measurement/abstention.py` | `874becf768ea33c0156df97e4a522b76722d264ac39a4920de2a6f500cd235f2` |
| `hidden_corpus/corpus.py` | `e9bc51cf8f0ed1ea8f9ac3379f88121a3ed43cddf99ce1cc91acd083f38482b1` |
| `hidden_corpus/annotations.py` | `8aee8fe56782121a66602412effdf4f566c21a743377071b52eb2a9f87191524` |
| `curation/pilot_corpus.py` | `e48884305d758891852794b5255de11aefd2052901a8bee0400a10f2c149f639` |
| `curation/pilot_annotations.py` | `c999dcb1c5b2aec780553915db7414997a3fd4fa7e6367e0ac1dd5f071735dca` |

## Discipline
- Validator rules and floors (lexical 0.6, structural 0.5) were selected on the
  visible corpus so that V4 rejects zero correct visible edges; frozen here.
- No hidden per-case failure was inspected before this lock.
- Two byte-identical repetitions are required.
