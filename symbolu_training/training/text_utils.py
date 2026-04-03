"""
Text Processing Utilities for Training
=======================================

Utilities for cleaning and preprocessing text data during training,
including WikiText artifact removal and text normalization.
"""

import re
from typing import Optional


def clean_wikitext_artifacts(text: str) -> str:
    """
    Clean Moses tokenization artifacts from WikiText-103/WikiText-2.

    WikiText uses Moses tokenization which escapes punctuation:
    - twenty @-@ one  ->  twenty-one
    - 3 @.@ 14        ->  3.14
    - 1 @,@ 000       ->  1,000

    Also removes Wikipedia-specific formatting:
    - = = Section = =  ->  Section
    - Empty lines and excessive whitespace

    These artifacts appear in model outputs when trained on raw WikiText.
    This function reverses the escaping for cleaner training/display.

    Args:
        text: Text containing potential WikiText artifacts

    Returns:
        Cleaned text with artifacts replaced
    """
    if not text:
        return text

    # Fix hyphens: @-@ -> -
    # Handles both spaced and unspaced variants
    text = re.sub(r'\s*@-@\s*', '-', text)

    # Fix periods: @.@ -> .
    text = re.sub(r'\s*@\.@\s*', '.', text)

    # Fix commas: @,@ -> ,
    text = re.sub(r'\s*@,@\s*', ',', text)

    # Fix semicolons: @;@ -> ; (less common but possible)
    text = re.sub(r'\s*@;@\s*', ';', text)

    # Fix colons: @:@ -> :
    text = re.sub(r'\s*@:@\s*', ':', text)

    # Fix exclamation: @!@ -> !
    text = re.sub(r'\s*@!@\s*', '!', text)

    # Fix question mark: @?@ -> ?
    text = re.sub(r'\s*@\?@\s*', '?', text)

    # V9.8.4: Remove Wikipedia section headers: = = Title = = -> Title
    # These appear as "= = = Heading = = =" in raw WikiText
    text = re.sub(r'(?:^|\n)\s*=+\s*=*\s*', '\n', text)  # Remove leading = = =
    text = re.sub(r'\s*=+\s*=*\s*(?=\n|$)', '', text)    # Remove trailing = = =

    # Remove empty lines and excessive newlines
    text = re.sub(r'\n\s*\n+', '\n\n', text)

    # Clean up stray @ symbols that might remain
    text = re.sub(r'\s*@\s*', ' ', text)

    # Remove <unk> tokens (WikiText replaces rare words with <unk>)
    # These pollute the vocabulary when tokenized by BPE (becomes <, unk, >)
    text = re.sub(r'\s*<unk>\s*', ' ', text)

    return text


def clean_generated_text(
    text: str,
    remove_wikitext_artifacts: bool = True,
    normalize_whitespace: bool = True,
    truncate_at_eos: bool = False,
    eos_tokens: Optional[list] = None,
) -> str:
    """
    Clean generated text for display or evaluation.

    Args:
        text: Raw generated text
        remove_wikitext_artifacts: Clean WikiText Moses tokenization artifacts
        normalize_whitespace: Collapse multiple spaces, strip leading/trailing
        truncate_at_eos: Stop at first end-of-sentence token
        eos_tokens: Custom EOS tokens (default: ['.', '!', '?'])

    Returns:
        Cleaned text
    """
    if not text:
        return text

    if remove_wikitext_artifacts:
        text = clean_wikitext_artifacts(text)

    if normalize_whitespace:
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

    if truncate_at_eos:
        eos = eos_tokens or ['.', '!', '?']
        # Find first EOS token and truncate after it
        first_eos = len(text)
        for token in eos:
            pos = text.find(token)
            if pos != -1 and pos < first_eos:
                first_eos = pos
        if first_eos < len(text):
            text = text[:first_eos + 1]

    return text


def estimate_token_quality(text: str) -> dict:
    """
    Estimate quality metrics for generated text.

    Returns metrics that can help diagnose training issues:
    - artifact_count: Number of WikiText artifacts found
    - repetition_score: Ratio of repeated n-grams
    - unique_ratio: Ratio of unique tokens to total

    Args:
        text: Text to analyze

    Returns:
        Dictionary of quality metrics
    """
    if not text:
        return {
            'artifact_count': 0,
            'repetition_score': 0.0,
            'unique_ratio': 0.0,
        }

    # Count WikiText artifacts
    artifact_patterns = [r'@-@', r'@\.@', r'@,@', r'@;@', r'@:@', r'@!@', r'@\?@']
    artifact_count = sum(len(re.findall(p, text)) for p in artifact_patterns)

    # Compute repetition (3-gram)
    words = text.split()
    if len(words) >= 3:
        trigrams = [tuple(words[i:i+3]) for i in range(len(words) - 2)]
        unique_trigrams = len(set(trigrams))
        total_trigrams = len(trigrams)
        repetition_score = 1.0 - (unique_trigrams / max(total_trigrams, 1))
    else:
        repetition_score = 0.0

    # Unique token ratio
    tokens = text.split()
    unique_ratio = len(set(tokens)) / max(len(tokens), 1)

    return {
        'artifact_count': artifact_count,
        'repetition_score': repetition_score,
        'unique_ratio': unique_ratio,
    }
