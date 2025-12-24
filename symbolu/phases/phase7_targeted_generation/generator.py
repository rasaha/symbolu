"""
Phase-7 Targeted Generation - Candidate Sequence Generator

Generates valid varna sequences according to Phase-6 grammar:
- Consonant-initial
- Only valid varnas
- Deterministic enumeration order

Two enumeration modes:
- Length-first: all length 1, then length 2, etc. (default)
- Lexicographic: pure lexicographic order for early termination optimization
"""

from typing import Iterator, Tuple, FrozenSet, Optional, List
import itertools

from .types import GenerationConfig


def generate_candidates(
    config: GenerationConfig,
) -> Iterator[Tuple[str, ...]]:
    """
    Generate candidate varna sequences.

    Produces valid sequences according to Phase-6 grammar:
        - Consonant-initial
        - Only valid varnas
        - Up to max_sequence_length

    Args:
        config: Generation configuration

    Yields:
        Tuples of varna tokens (immutable sequences)

    Notes:
        - Enumeration order is deterministic (lexicographic)
        - If max_candidates is set, stops after that many
        - Does not filter by target (that's scoring's job)
    """
    consonants = sorted(config.consonant_set)
    vowels = sorted(config.vowel_set)
    all_tokens = consonants + vowels
    max_len = config.max_sequence_length
    max_candidates = config.max_candidates

    count = 0

    # Generate sequences of each length
    for length in range(1, max_len + 1):
        # First token must be consonant
        for first_consonant in consonants:
            if length == 1:
                yield (first_consonant,)
                count += 1
                if max_candidates is not None and count >= max_candidates:
                    return
            else:
                # Remaining tokens can be any valid token
                for remaining in itertools.product(all_tokens, repeat=length - 1):
                    sequence = (first_consonant,) + remaining
                    # Validate: vowels must follow consonants
                    if _is_valid_sequence(sequence, config.consonant_set, config.vowel_set):
                        yield sequence
                        count += 1
                        if max_candidates is not None and count >= max_candidates:
                            return


def _is_valid_sequence(
    sequence: Tuple[str, ...],
    consonants: FrozenSet[str],
    vowels: FrozenSet[str],
) -> bool:
    """
    Check if sequence is valid according to Phase-6 grammar.

    Rules:
    - First token must be consonant
    - Vowels can follow consonants
    - Consonants can follow anything
    """
    if not sequence:
        return False

    # First must be consonant
    if sequence[0] not in consonants:
        return False

    # Check each token
    has_active_consonant = True  # First token is consonant
    for i, token in enumerate(sequence):
        if token in consonants:
            has_active_consonant = True
        elif token in vowels:
            if not has_active_consonant:
                return False
            # Vowel is valid after consonant
        else:
            # Unknown token
            return False

    return True


def count_candidate_space(config: GenerationConfig) -> int:
    """
    Calculate size of candidate space without generating.

    Args:
        config: Generation configuration

    Returns:
        Number of valid sequences in space

    Notes:
        This is an approximation that may overcount slightly
        due to vowel-must-follow-consonant rule.
    """
    n_consonants = len(config.consonant_set)
    n_vowels = len(config.vowel_set)
    n_all = n_consonants + n_vowels
    max_len = config.max_sequence_length

    # For each length L:
    # First token: n_consonants choices
    # Remaining L-1 tokens: n_all choices each (approximately)
    # Actual count is less due to grammar constraints

    total = 0
    for length in range(1, max_len + 1):
        if length == 1:
            total += n_consonants
        else:
            # Upper bound: first is consonant, rest is anything
            total += n_consonants * (n_all ** (length - 1))

    if config.max_candidates is not None:
        return min(total, config.max_candidates)
    return total


def validate_sequence(
    sequence: Tuple[str, ...],
    config: GenerationConfig,
) -> bool:
    """
    Check if sequence is valid according to Phase-6 grammar.

    Args:
        sequence: Candidate sequence
        config: Generation configuration

    Returns:
        True if valid, False otherwise
    """
    if not sequence:
        return False

    # Check all tokens are valid
    valid_tokens = config.consonant_set | config.vowel_set
    for token in sequence:
        if token not in valid_tokens:
            return False

    return _is_valid_sequence(sequence, config.consonant_set, config.vowel_set)


def generate_candidates_lexicographic(
    config: GenerationConfig,
) -> Iterator[Tuple[str, ...]]:
    """
    Generate candidate varna sequences in pure lexicographic order.

    This generator produces sequences in lexicographic order (like dictionary order)
    rather than length-first order. This is required for early termination (H1)
    to produce the same results as exhaustive search when ranking ties by
    lexicographic order.

    Args:
        config: Generation configuration

    Yields:
        Tuples of varna tokens in lexicographic order

    Notes:
        - Uses depth-first traversal of the sequence tree
        - ('ba',) < ('ba', 'a') < ('ba', 'a', 'a') < ('ba', 'ba') < ('ka',)
        - Required for H1 early termination to work correctly
    """
    consonants = sorted(config.consonant_set)
    vowels = sorted(config.vowel_set)
    all_tokens = sorted(set(consonants) | set(vowels))  # Lexicographically sorted
    max_len = config.max_sequence_length
    max_candidates = config.max_candidates

    count = 0

    def generate_from_prefix(
        prefix: Tuple[str, ...],
        has_active_consonant: bool,
    ) -> Iterator[Tuple[str, ...]]:
        """Recursively generate sequences with given prefix."""
        nonlocal count

        # Yield current prefix if it's valid (non-empty)
        if prefix:
            yield prefix
            count += 1
            if max_candidates is not None and count >= max_candidates:
                return

        # Don't extend if we've reached max length
        if len(prefix) >= max_len:
            return

        # Extend with each valid token in lexicographic order
        for token in all_tokens:
            if token in config.consonant_set:
                # Consonant can always follow
                new_has_active = True
                new_prefix = prefix + (token,)
                yield from generate_from_prefix(new_prefix, new_has_active)
                if max_candidates is not None and count >= max_candidates:
                    return
            elif token in config.vowel_set:
                # Vowel can only follow consonant (has_active_consonant)
                if has_active_consonant:
                    new_prefix = prefix + (token,)
                    yield from generate_from_prefix(new_prefix, has_active_consonant)
                    if max_candidates is not None and count >= max_candidates:
                        return

    # Start with each consonant (first token must be consonant)
    for first_consonant in consonants:
        yield from generate_from_prefix((first_consonant,), True)
        if max_candidates is not None and count >= max_candidates:
            return


def generate_candidates_filtered(
    config: GenerationConfig,
    exclude_sequences: Optional[FrozenSet[Tuple[str, ...]]] = None,
    prefix: Optional[Tuple[str, ...]] = None,
    suffix: Optional[Tuple[str, ...]] = None,
    lexicographic: bool = False,
) -> Iterator[Tuple[str, ...]]:
    """
    Generate candidates with compositional filtering.

    Args:
        config: Generation configuration
        exclude_sequences: Sequences to exclude (for exclusion chains)
        prefix: Required prefix (for STARTS_WITH constraint)
        suffix: Required suffix (for ENDS_WITH constraint)
        lexicographic: If True, use lexicographic order (for early termination)

    Yields:
        Filtered candidate sequences
    """
    # Choose generator based on order preference
    if lexicographic:
        base_generator = generate_candidates_lexicographic(config)
    else:
        base_generator = generate_candidates(config)

    for seq in base_generator:
        # Apply exclusion filter
        if exclude_sequences is not None and seq in exclude_sequences:
            continue

        # Apply prefix filter
        if prefix is not None:
            if len(seq) < len(prefix):
                continue
            if seq[:len(prefix)] != prefix:
                continue

        # Apply suffix filter
        if suffix is not None:
            if len(seq) < len(suffix):
                continue
            if seq[-len(suffix):] != suffix:
                continue

        yield seq
