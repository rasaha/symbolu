# HIDDEN_EVALUATION_LOCK — Exploratory Resolver Study v0.1

**Lock version:** `v0.1`  
**Combined lock hash:** `d31c20580cda4beddc665a86e49db75fe61052552d29f5f2d4b36adfd8d797ec`  
**Manifest hash:** `b7cc359cf7735ef9102c03524e66909d62a697fc34804821d71c5da15f0f3106`

This lock is computed BEFORE the first hidden evaluation. Every artifact that
could influence the hidden result is content-hashed below. Per the
preregistration, any post-lock edit to a locked file invalidates prior hidden
runs, bumps the lock version, and forces a full rerun (disclosed).

## Manifest (frozen parameters)
```json
{
  "study": "Exploratory Resolver Study v0.1",
  "resolver_under_test": "HybridRelationshipResolver Experimental v0.1",
  "corpus": "Hidden Relationship Corpus Pilot v0.2 (22 seed + 38 pilot = 60)",
  "comparator_run_order": [
    "null",
    "always_abstain",
    "frozen",
    "rule",
    "graph_traversal",
    "hybrid_relationship"
  ],
  "ablations": [
    "A0_full",
    "A1_no_semantic",
    "A2_no_traversal",
    "A3_no_governance_rules",
    "A4_no_confidence_abstain",
    "A5_no_provenance",
    "A6_discovery_only",
    "A7_modeG_gold_graph",
    "A8_modeP_gold_governance"
  ],
  "abstention_threshold_tau": 0.5,
  "bootstrap_seed": 20240601,
  "bootstrap_iters": 10000,
  "ci_alpha": 0.05,
  "primary_endpoint": "hidden_owner_clean_macro = mean(discovery_f1, classification_accuracy, governance_accuracy_modeG, packet_realization_accuracy_modeP, selective_accuracy)",
  "practical_significance_threshold": 0.03,
  "non_inferiority_margins": {
    "discovery_precision_decrease": 0.05,
    "governance_modeG_decrease": 0.03,
    "packet_modeP_decrease": 0.03,
    "selective_decrease": 0.03,
    "false_abstention_increase": 0.05,
    "missed_abstention_increase": 0.05,
    "coverage_decrease": 0.1,
    "unsafe_answers_increase": "any",
    "determinism": "must hold"
  },
  "repetitions": 2,
  "byte_identical_required": true
}
```

## Experiment source hashes (SHA-256)
| file | sha256 |
|---|---|
| `hybrid_resolver.py` | `a2bb9803f0d180dd80a0f3c7806247dde284b9830240a44095fdd4632b887add` |
| `EXPERIMENT_PREREGISTRATION.md` | `4048942d804e4ed2468f60f95255c9b796c3d10e3abc47ee7e50a00928c6f0f6` |
| `stats.py` | `03ca5b37b5da45dce5c43f80e2a82299895665f219d847ba6f6751976fc82cd3` |
| `hidden_metrics.py` | `b878994f23a312de2d09d008661c52f3b19cbb6b913cd8b98b683388f3e90228` |
| `hidden_data.py` | `a32119d1b4bf84f8f871d88f2b52b704da2ff25ef9840191710b7bfe10973813` |
| `run_experiment.py` | `c7335f1d8a24d85d7a3cdecabac54fc536cad1eb3746766ee1a1717dd9e45274` |
| `lock.py` | `917ad4a8791098f2f675c3582837abd333da39eb3b7235925efd8ffa4e58ef06` |

## Frozen-dependency hashes (must be unchanged)
| file | sha256 |
|---|---|
| `resolution/resolvers.py` | `a5eba70cf0b2f4a564ed848a93cb5e4d1006bf87e5e7e6afff619d8d99c0ef53` |
| `resolution/parse.py` | `f84657b904255b1071d8705eb5be629d1e70671355177c52e22bb8dafebf8f47` |
| `resolution/graph.py` | `db7309356ddb1ab1599d3526e85618a8c734310ce3dd3ed3640b816776e3c645` |
| `resolution/gold.py` | `f85ffb18fc76e343e0ae6195882d76b21c5e634978f0dc241e0df66498ee4bbd` |
| `resolution/modes.py` | `25400ec8d24bf077616106e38fb25c1779a49a31a3c7c7bf0df34b00b71ca0e4` |
| `measurement/stage_metrics.py` | `e105714cfa3d5785303c0219e035b194a2cc219391deb574b9455aea920c1419` |
| `measurement/abstention.py` | `874becf768ea33c0156df97e4a522b76722d264ac39a4920de2a6f500cd235f2` |
| `measurement/gold_graph.py` | `9125017a3c2e9ad7ff5339090c893e97ba22c221af464da9c8ea9cd8f35f7f4a` |
| `audit/adversarial.py` | `886c4122bc6935c8c3786d4d9e8ffde771cc871b1e5b2b1f440d7749ae51c4b2` |
| `hidden_corpus/corpus.py` | `e9bc51cf8f0ed1ea8f9ac3379f88121a3ed43cddf99ce1cc91acd083f38482b1` |
| `hidden_corpus/annotations.py` | `8aee8fe56782121a66602412effdf4f566c21a743377071b52eb2a9f87191524` |
| `curation/pilot_corpus.py` | `e48884305d758891852794b5255de11aefd2052901a8bee0400a10f2c149f639` |
| `curation/pilot_annotations.py` | `c999dcb1c5b2aec780553915db7414997a3fd4fa7e6367e0ac1dd5f071735dca` |

## Discipline
- No per-case hidden failure was inspected before this lock.
- Thresholds (τ=0.5) and non-inferiority margins were selected on the
  visible corpus and are frozen here.
- Two byte-identical repetitions are required for the run to count.
