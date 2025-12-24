"""
Phoneme Space Benchmarks

Measures:
1. Phoneme embedding quality (linguistic validity)
2. Guna mapping accuracy (theoretical consistency)
3. 12D → 10D projection fidelity (dimensional reduction quality)

Run: python -m benchmarks.phoneme_space_benchmark
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from symbolu.guna_modulation.phoneme_space import (
    enable_phoneme_space,
    get_phoneme, get_phoneme_guna, get_phoneme_embedding,
    phoneme_similarity, phoneme_distance,
    compute_affinity, project_phoneme,
    analyze_sequence, guna_profile,
    IPA_INVENTORY, PhonemeType,
    Place, Manner, Voicing, Height, Backness,
)


@dataclass
class BenchmarkResult:
    """Result from a single benchmark."""
    name: str
    score: float  # 0-1, higher is better
    max_score: float
    details: Dict[str, float]
    passed: bool


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results."""
    results: List[BenchmarkResult]

    @property
    def total_score(self) -> float:
        return sum(r.score for r in self.results)

    @property
    def max_total(self) -> float:
        return sum(r.max_score for r in self.results)

    @property
    def percentage(self) -> float:
        return (self.total_score / self.max_total) * 100 if self.max_total > 0 else 0


# =============================================================================
# BENCHMARK 1: PHONEME EMBEDDING QUALITY
# =============================================================================

def benchmark_embedding_quality() -> BenchmarkResult:
    """
    Measures how well embeddings capture linguistic relationships.

    Tests:
    - Voicing minimal pairs (p/b, t/d, k/g) should be similar
    - Place minimal pairs should be similar
    - Manner classes should cluster
    - Vowel space should be organized
    - Consonant-vowel distinction should be clear
    """
    details = {}
    tests_passed = 0
    total_tests = 0

    # Test 1: Voicing minimal pairs (should be highly similar)
    voicing_pairs = [('p', 'b'), ('t', 'd'), ('k', 'g'), ('f', 'v'), ('s', 'z')]
    voicing_sims = []
    for p1, p2 in voicing_pairs:
        sim = phoneme_similarity(p1, p2)
        if sim is not None:
            voicing_sims.append(sim)

    voicing_avg = sum(voicing_sims) / len(voicing_sims) if voicing_sims else 0
    details['voicing_pairs_similarity'] = voicing_avg
    if voicing_avg > 0.85:
        tests_passed += 1
    total_tests += 1

    # Test 2: Place minimal pairs (same manner, different place)
    place_pairs = [('p', 't'), ('t', 'k'), ('m', 'n'), ('f', 's')]
    place_sims = []
    for p1, p2 in place_pairs:
        sim = phoneme_similarity(p1, p2)
        if sim is not None:
            place_sims.append(sim)

    place_avg = sum(place_sims) / len(place_sims) if place_sims else 0
    details['place_pairs_similarity'] = place_avg
    if place_avg > 0.75:
        tests_passed += 1
    total_tests += 1

    # Test 3: Manner class clustering (stops should be similar to stops)
    stops = ['p', 't', 'k', 'b', 'd', 'g']
    fricatives = ['f', 's', 'ʃ', 'v', 'z']

    # Intra-class similarity
    stop_sims = []
    for i, s1 in enumerate(stops):
        for s2 in stops[i+1:]:
            sim = phoneme_similarity(s1, s2)
            if sim is not None:
                stop_sims.append(sim)

    fric_sims = []
    for i, f1 in enumerate(fricatives):
        for f2 in fricatives[i+1:]:
            sim = phoneme_similarity(f1, f2)
            if sim is not None:
                fric_sims.append(sim)

    intra_class_avg = (sum(stop_sims) + sum(fric_sims)) / (len(stop_sims) + len(fric_sims)) if (stop_sims or fric_sims) else 0
    details['manner_intra_class_similarity'] = intra_class_avg
    if intra_class_avg > 0.80:
        tests_passed += 1
    total_tests += 1

    # Test 4: Vowel organization (cardinal vowels form triangle)
    vowel_sims = []
    cardinal_vowels = ['a', 'i', 'u']
    for i, v1 in enumerate(cardinal_vowels):
        for v2 in cardinal_vowels[i+1:]:
            sim = phoneme_similarity(v1, v2)
            if sim is not None:
                vowel_sims.append(sim)

    vowel_avg = sum(vowel_sims) / len(vowel_sims) if vowel_sims else 0
    details['vowel_triangle_similarity'] = vowel_avg
    # Vowels should be similar (all voiced, open) but distinct
    if 0.60 < vowel_avg < 0.95:
        tests_passed += 1
    total_tests += 1

    # Test 5: Consonant-vowel distinction
    consonants = ['p', 't', 'k', 's', 'm', 'n']
    vowels = ['a', 'i', 'u', 'e', 'o']

    cv_sims = []
    for c in consonants:
        for v in vowels:
            sim = phoneme_similarity(c, v)
            if sim is not None:
                cv_sims.append(sim)

    cv_avg = sum(cv_sims) / len(cv_sims) if cv_sims else 0
    details['consonant_vowel_distinction'] = 1.0 - cv_avg  # Lower similarity = better distinction
    if cv_avg < 0.75:  # Should be less similar
        tests_passed += 1
    total_tests += 1

    # Test 6: Self-similarity should be 1.0
    self_sims = []
    for symbol in ['a', 'p', 't', 'i', 's']:
        sim = phoneme_similarity(symbol, symbol)
        if sim is not None:
            self_sims.append(sim)

    self_avg = sum(self_sims) / len(self_sims) if self_sims else 0
    details['self_similarity'] = self_avg
    if self_avg > 0.99:
        tests_passed += 1
    total_tests += 1

    score = tests_passed / total_tests if total_tests > 0 else 0

    return BenchmarkResult(
        name="Phoneme Embedding Quality",
        score=score,
        max_score=1.0,
        details=details,
        passed=tests_passed >= 5
    )


# =============================================================================
# BENCHMARK 2: GUNA MAPPING ACCURACY
# =============================================================================

def benchmark_guna_mapping() -> BenchmarkResult:
    """
    Measures theoretical consistency of Guna mappings.

    Tests:
    - Vowels should be Sattva-dominant (clarity, openness)
    - Stops should be Tamas-dominant (obstruction)
    - Fricatives should have high Rajas (turbulence)
    - Voiced sounds should have more Rajas than voiceless
    - Sonorants should be more Sattvic than obstruents
    - Guna should be normalized (sum to 1)
    """
    details = {}
    tests_passed = 0
    total_tests = 0

    # Test 1: Vowels are Sattva-dominant
    vowels = ['a', 'i', 'u', 'e', 'o']
    vowel_sattva_dominant = 0
    for v in vowels:
        guna = get_phoneme_guna(v)
        if guna and guna.dominant_guna == 'sattva':
            vowel_sattva_dominant += 1

    vowel_sattva_rate = vowel_sattva_dominant / len(vowels)
    details['vowels_sattva_dominant'] = vowel_sattva_rate
    if vowel_sattva_rate >= 0.8:
        tests_passed += 1
    total_tests += 1

    # Test 2: Stops are Tamas-dominant
    stops = ['p', 't', 'k']  # voiceless stops (pure obstruction)
    stop_tamas_dominant = 0
    for s in stops:
        guna = get_phoneme_guna(s)
        if guna and guna.dominant_guna == 'tamas':
            stop_tamas_dominant += 1

    stop_tamas_rate = stop_tamas_dominant / len(stops)
    details['stops_tamas_dominant'] = stop_tamas_rate
    if stop_tamas_rate >= 0.8:
        tests_passed += 1
    total_tests += 1

    # Test 3: Fricatives have high Rajas
    fricatives = ['f', 's', 'ʃ']
    fric_rajas_scores = []
    for f in fricatives:
        guna = get_phoneme_guna(f)
        if guna:
            fric_rajas_scores.append(guna.rajas)

    fric_rajas_avg = sum(fric_rajas_scores) / len(fric_rajas_scores) if fric_rajas_scores else 0
    details['fricatives_rajas_avg'] = fric_rajas_avg
    if fric_rajas_avg > 0.35:
        tests_passed += 1
    total_tests += 1

    # Test 4: Voiced > Voiceless in Rajas
    voiced_rajas = []
    voiceless_rajas = []
    pairs = [('p', 'b'), ('t', 'd'), ('k', 'g'), ('f', 'v'), ('s', 'z')]
    for voiceless, voiced in pairs:
        guna_vl = get_phoneme_guna(voiceless)
        guna_v = get_phoneme_guna(voiced)
        if guna_vl and guna_v:
            voiceless_rajas.append(guna_vl.rajas)
            voiced_rajas.append(guna_v.rajas)

    voiced_rajas_avg = sum(voiced_rajas) / len(voiced_rajas) if voiced_rajas else 0
    voiceless_rajas_avg = sum(voiceless_rajas) / len(voiceless_rajas) if voiceless_rajas else 0
    details['voiced_rajas_avg'] = voiced_rajas_avg
    details['voiceless_rajas_avg'] = voiceless_rajas_avg
    if voiced_rajas_avg > voiceless_rajas_avg:
        tests_passed += 1
    total_tests += 1

    # Test 5: Sonorants more Sattvic than obstruents
    sonorants = ['m', 'n', 'l', 'w', 'j']
    obstruents = ['p', 't', 'k', 'f', 's']

    sonorant_sattva = []
    for s in sonorants:
        guna = get_phoneme_guna(s)
        if guna:
            sonorant_sattva.append(guna.sattva)

    obstruent_sattva = []
    for o in obstruents:
        guna = get_phoneme_guna(o)
        if guna:
            obstruent_sattva.append(guna.sattva)

    son_sattva_avg = sum(sonorant_sattva) / len(sonorant_sattva) if sonorant_sattva else 0
    obs_sattva_avg = sum(obstruent_sattva) / len(obstruent_sattva) if obstruent_sattva else 0
    details['sonorant_sattva_avg'] = son_sattva_avg
    details['obstruent_sattva_avg'] = obs_sattva_avg
    if son_sattva_avg > obs_sattva_avg:
        tests_passed += 1
    total_tests += 1

    # Test 6: Guna normalization (sum to 1)
    normalization_errors = []
    for symbol in list(IPA_INVENTORY.keys())[:20]:
        guna = get_phoneme_guna(symbol)
        if guna:
            total = guna.sattva + guna.rajas + guna.tamas
            normalization_errors.append(abs(total - 1.0))

    avg_norm_error = sum(normalization_errors) / len(normalization_errors) if normalization_errors else 1
    details['normalization_error'] = avg_norm_error
    if avg_norm_error < 0.01:
        tests_passed += 1
    total_tests += 1

    score = tests_passed / total_tests if total_tests > 0 else 0

    return BenchmarkResult(
        name="Guna Mapping Accuracy",
        score=score,
        max_score=1.0,
        details=details,
        passed=tests_passed >= 5
    )


# =============================================================================
# BENCHMARK 3: 12D → 10D PROJECTION FIDELITY
# =============================================================================

def benchmark_projection_fidelity() -> BenchmarkResult:
    """
    Measures quality of dimensional projection.

    Current: 12D articulatory → 15D embedding (12 + 3 Guna)
    Target: 12D acoustic → 10D semantic

    Tests:
    - Information preservation (similar phonemes stay similar after projection)
    - Distinctive features preserved
    - Semantic clustering emerges
    - Layer activations are meaningful
    - Projection is stable (deterministic)
    """
    details = {}
    tests_passed = 0
    total_tests = 0

    # Test 1: Information preservation
    # Compare similarity before/after projection
    pairs = [('p', 'b'), ('a', 'i'), ('s', 'z'), ('m', 'n')]
    preservation_scores = []

    for p1, p2 in pairs:
        # Embedding similarity
        emb_sim = phoneme_similarity(p1, p2)

        # Projection similarity (via Guna)
        guna1 = get_phoneme_guna(p1)
        guna2 = get_phoneme_guna(p2)

        if guna1 and guna2 and emb_sim is not None:
            guna_sim = (
                guna1.sattva * guna2.sattva +
                guna1.rajas * guna2.rajas +
                guna1.tamas * guna2.tamas
            )
            # Preservation = correlation between embedding and projection similarity
            preservation_scores.append(min(emb_sim, guna_sim) / max(emb_sim, guna_sim) if max(emb_sim, guna_sim) > 0 else 0)

    preservation_avg = sum(preservation_scores) / len(preservation_scores) if preservation_scores else 0
    details['information_preservation'] = preservation_avg
    if preservation_avg > 0.6:
        tests_passed += 1
    total_tests += 1

    # Test 2: Distinctive features preserved
    # Voicing distinction should survive projection
    voicing_preserved = 0
    voicing_pairs = [('p', 'b'), ('t', 'd'), ('k', 'g')]
    for vl, v in voicing_pairs:
        guna_vl = get_phoneme_guna(vl)
        guna_v = get_phoneme_guna(v)
        if guna_vl and guna_v:
            # Voiced should have more Rajas
            if guna_v.rajas > guna_vl.rajas:
                voicing_preserved += 1

    voicing_rate = voicing_preserved / len(voicing_pairs)
    details['voicing_distinction_preserved'] = voicing_rate
    if voicing_rate >= 0.66:
        tests_passed += 1
    total_tests += 1

    # Test 3: Semantic clustering (vowels cluster, consonants cluster)
    vowels = ['a', 'i', 'u']
    consonants = ['p', 't', 'k']

    vowel_gunas = [get_phoneme_guna(v) for v in vowels]
    cons_gunas = [get_phoneme_guna(c) for c in consonants]

    # Compute centroid distance
    if all(vowel_gunas) and all(cons_gunas):
        v_centroid = (
            sum(g.sattva for g in vowel_gunas) / 3,
            sum(g.rajas for g in vowel_gunas) / 3,
            sum(g.tamas for g in vowel_gunas) / 3,
        )
        c_centroid = (
            sum(g.sattva for g in cons_gunas) / 3,
            sum(g.rajas for g in cons_gunas) / 3,
            sum(g.tamas for g in cons_gunas) / 3,
        )

        centroid_dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(v_centroid, c_centroid)))
        details['vowel_consonant_centroid_distance'] = centroid_dist
        if centroid_dist > 0.15:  # Should be separated
            tests_passed += 1
    total_tests += 1

    # Test 4: Layer activations are meaningful
    proj_a = project_phoneme('a')
    proj_p = project_phoneme('p')

    if proj_a and proj_p:
        # Vowel should have higher fusion (syllable nucleus)
        details['vowel_fusion'] = proj_a.fusion
        details['consonant_fusion'] = proj_p.fusion
        if proj_a.fusion > proj_p.fusion:
            tests_passed += 1
    total_tests += 1

    # Test 5: Projection stability (same input → same output)
    stability_checks = 0
    for symbol in ['a', 'p', 's']:
        proj1 = project_phoneme(symbol)
        proj2 = project_phoneme(symbol)
        if proj1 and proj2:
            if (proj1.signal == proj2.signal and
                proj1.embedding == proj2.embedding and
                proj1.guna_layer == proj2.guna_layer):
                stability_checks += 1

    stability_rate = stability_checks / 3
    details['projection_stability'] = stability_rate
    if stability_rate == 1.0:
        tests_passed += 1
    total_tests += 1

    # Test 6: Dimensionality reduction quality
    # Embedding is 15D, Guna is 3D - check variance preserved
    embeddings = []
    gunas = []
    for symbol in list(IPA_INVENTORY.keys())[:15]:
        emb = get_phoneme_embedding(symbol)
        guna = get_phoneme_guna(symbol)
        if emb and guna:
            embeddings.append(emb.vector)
            gunas.append([guna.sattva, guna.rajas, guna.tamas])

    if embeddings and gunas:
        # Compute variance in each space
        def variance(vectors):
            if not vectors:
                return 0
            means = [sum(v[i] for v in vectors) / len(vectors) for i in range(len(vectors[0]))]
            return sum(sum((v[i] - means[i]) ** 2 for i in range(len(v))) for v in vectors) / len(vectors)

        emb_var = variance(embeddings)
        guna_var = variance(gunas)

        # Normalized variance ratio
        var_ratio = guna_var / emb_var if emb_var > 0 else 0
        details['variance_ratio_15d_to_3d'] = var_ratio
        # Some variance should be preserved (not collapsed to point)
        if var_ratio > 0.01:
            tests_passed += 1
    total_tests += 1

    score = tests_passed / total_tests if total_tests > 0 else 0

    return BenchmarkResult(
        name="12D → 10D Projection Fidelity",
        score=score,
        max_score=1.0,
        details=details,
        passed=tests_passed >= 4
    )


# =============================================================================
# MAIN BENCHMARK RUNNER
# =============================================================================

def run_all_benchmarks() -> BenchmarkSuite:
    """Run all phoneme space benchmarks."""
    enable_phoneme_space()

    results = [
        benchmark_embedding_quality(),
        benchmark_guna_mapping(),
        benchmark_projection_fidelity(),
    ]

    return BenchmarkSuite(results=results)


def print_results(suite: BenchmarkSuite):
    """Print formatted benchmark results."""
    print("\n" + "=" * 70)
    print("PHONEME SPACE BENCHMARK RESULTS")
    print("=" * 70)

    for result in suite.results:
        status = "✓ PASSED" if result.passed else "✗ FAILED"
        print(f"\n{result.name}: {result.score:.2%} [{status}]")
        print("-" * 50)
        for key, value in result.details.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")

    print("\n" + "=" * 70)
    print(f"TOTAL SCORE: {suite.total_score:.2f} / {suite.max_total:.2f} ({suite.percentage:.1f}%)")

    all_passed = all(r.passed for r in suite.results)
    print(f"STATUS: {'ALL BENCHMARKS PASSED ✓' if all_passed else 'SOME BENCHMARKS FAILED ✗'}")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    suite = run_all_benchmarks()
    success = print_results(suite)
    sys.exit(0 if success else 1)
