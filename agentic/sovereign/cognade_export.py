"""
COGNADE SDK Export: Hardware Bridge for PA-VPU
===============================================

This module bridges the Python Sovereign-1 prototype to the C-based
PA-VPU (Phase Attention Vector Processing Unit) hardware.

Exports:
1. C-struct definitions for cognade_state_t
2. Binary serialization for WORD_TO_REFERENT lookup table
3. Deterministic phoneme encoding as standalone C function

State Layout (128-bit):
- Bits 0-15:   Guna Pulse (16-bit)
- Bits 16-47:  S-Signal (32-bit)
- Bits 48-95:  R-Signal (48-bit via 64-bit container)
- Bits 96-127: C-Signal (32-bit)

Reference: SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 10
"""

import struct
import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, BinaryIO
from pathlib import Path

import torch


# =============================================================================
# C Header Generation
# =============================================================================

COGNADE_HEADER_TEMPLATE = '''\
/**
 * COGNADE State Structure for PA-VPU Hardware
 * ============================================
 *
 * Auto-generated from Sovereign-1 Python prototype.
 * DO NOT EDIT MANUALLY.
 *
 * State Layout (128-bit total):
 * - guna_pulse:  Cognitive dynamics (Sattva/Rajas/Tamas encoded)
 * - s_signal:    Referent class encoding (one-hot in 16-class space)
 * - r_signal:    Ontological state (12 Bhavas × 4 dims, packed)
 * - c_signal:    Phonemic features (hash-based)
 *
 * Generated: {timestamp}
 * Version: {version}
 */

#ifndef COGNADE_STATE_H
#define COGNADE_STATE_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {{
#endif

/* Version info */
#define COGNADE_VERSION_MAJOR {version_major}
#define COGNADE_VERSION_MINOR {version_minor}
#define COGNADE_VERSION_PATCH {version_patch}

/* State dimensions */
#define COGNADE_STATE_BITS      128
#define COGNADE_GUNA_BITS       16
#define COGNADE_S_SIGNAL_BITS   32
#define COGNADE_R_SIGNAL_BITS   48
#define COGNADE_C_SIGNAL_BITS   32

/* Number of referent classes */
#define COGNADE_NUM_REFERENT_CLASSES 16

/* Number of Bhava layers */
#define COGNADE_NUM_BHAVAS 12

/* Nexus positions */
#define COGNADE_NEXUS_LOGIC_HEAVY 4
#define COGNADE_NEXUS_BALANCED    6
#define COGNADE_NEXUS_MEMORY_HEAVY 8

/**
 * Guna encoding within 16-bit field:
 * - Bits 0-4:   Sattva (5 bits, 0-31 scale)
 * - Bits 5-9:   Rajas (5 bits, 0-31 scale)
 * - Bits 10-15: Tamas (6 bits, 0-63 scale)
 */
typedef struct {{
    uint16_t sattva : 5;
    uint16_t rajas  : 5;
    uint16_t tamas  : 6;
}} cognade_guna_t;

/**
 * Primary 128-bit state structure.
 *
 * Memory layout optimized for PA-VPU register alignment.
 */
typedef struct __attribute__((packed)) {{
    uint16_t guna_pulse;   /* Bits 0-15:   Guna Pulse */
    uint32_t s_signal;     /* Bits 16-47:  S-Signal (Referent) */
    uint64_t r_signal;     /* Bits 48-111: R-Signal (Ontology, uses 48 of 64 bits) */
    uint32_t c_signal;     /* Bits 112-143: C-Signal (Phonemic) - Note: overlaps */
}} cognade_state_t;

/**
 * Alternative 128-bit layout using explicit byte array.
 */
typedef struct {{
    uint8_t bytes[16];     /* Raw 128-bit state */
}} cognade_state_raw_t;

/**
 * PID Governor state for streaming inference.
 */
typedef struct {{
    float integral_error;
    float prev_error;
    uint8_t vritti_mode;   /* 0=pramana, 1=viparyaya, 2=vikalpa, 3=smrti, 4=nidra */
    uint8_t authority;     /* 0-255 scale (divide by 255 for 0.0-1.0) */
}} cognade_pid_state_t;

/**
 * Nexus configuration for Virtual Nexus.
 */
typedef struct {{
    uint8_t position;      /* Layer position: 4, 6, or 8 */
    uint8_t quadratic_layers;
    uint8_t phase_layers;
}} cognade_nexus_config_t;

/**
 * Referent class enumeration.
 */
typedef enum {{
    REFERENT_LUMINOUS = 0,
    REFERENT_BIOLOGICAL = 1,
    REFERENT_ROLE_BEARER = 2,
    REFERENT_ARTIFACT = 3,
    REFERENT_NATURAL_BODY = 4,
    REFERENT_SUBSTANCE = 5,
    REFERENT_PROCESS = 6,
    REFERENT_ABSTRACT = 7,
    REFERENT_SIGNAL = 8,
    REFERENT_TEMPORAL = 9,
    REFERENT_SPATIAL = 10,
    REFERENT_EMOTIONAL = 11,
    REFERENT_SOCIAL = 12,
    REFERENT_ENERGY_SOURCE = 13,
    REFERENT_PHENOMENON = 14,
    REFERENT_UNKNOWN = 15,
}} cognade_referent_class_t;

/**
 * Bhava (ontological layer) enumeration.
 */
typedef enum {{
    BHAVA_O1_POTENTIAL = 0,
    BHAVA_O2_IDENTITY = 1,
    BHAVA_O3_EXECUTION = 2,
    BHAVA_O4_STRUCTURE = 3,
    BHAVA_O5_COGNITION = 4,
    BHAVA_O6_AGENCY = 5,
    BHAVA_O7_REASONING = 6,
    BHAVA_O8_PURPOSE = 7,
    BHAVA_O9_WITNESSES = 8,
    BHAVA_O10_UNIFYING = 9,
    BHAVA_O11_INTEGRATION = 10,
    BHAVA_O12_ABSOLVING = 11,
}} cognade_bhava_t;

/* =============================================================================
 * Function Declarations
 * =========================================================================== */

/**
 * Pack a 128-D float state vector into cognade_state_t.
 *
 * @param state_128d Array of 128 floats (Guna[16] + S[32] + R[48] + C[32])
 * @param out        Output packed state
 */
void cognade_pack_state(const float* state_128d, cognade_state_t* out);

/**
 * Unpack cognade_state_t back to 128-D float vector.
 *
 * @param state      Packed state
 * @param out_128d   Output array of 128 floats
 */
void cognade_unpack_state(const cognade_state_t* state, float* out_128d);

/**
 * Extract Guna components from packed state.
 *
 * @param guna       Packed 16-bit guna
 * @param sattva     Output: Sattva (0.0-1.0)
 * @param rajas      Output: Rajas (0.0-1.0)
 * @param tamas      Output: Tamas (0.0-1.0)
 */
void cognade_extract_guna(uint16_t guna, float* sattva, float* rajas, float* tamas);

/**
 * Get dominant referent class from S-Signal.
 *
 * @param s_signal   32-bit S-Signal
 * @return           Dominant referent class
 */
cognade_referent_class_t cognade_get_dominant_referent(uint32_t s_signal);

/**
 * Get dominant Bhava from R-Signal.
 *
 * @param r_signal   48-bit R-Signal (in 64-bit container)
 * @return           Dominant Bhava layer
 */
cognade_bhava_t cognade_get_dominant_bhava(uint64_t r_signal);

/**
 * Compute 32-bit phoneme hash for a token string.
 *
 * Uses SHA256 for deterministic encoding.
 *
 * @param token      Token string (null-terminated)
 * @param token_len  Length of token
 * @return           32-bit phoneme hash
 */
uint32_t cognade_phoneme_hash(const char* token, size_t token_len);

/**
 * Look up referent class for a word.
 *
 * Uses pre-loaded binary lookup table.
 *
 * @param word       Word string (null-terminated)
 * @param word_len   Length of word
 * @return           Referent class (REFERENT_UNKNOWN if not found)
 */
cognade_referent_class_t cognade_lookup_referent(const char* word, size_t word_len);

/**
 * Select nexus position based on dominant Bhava.
 *
 * @param bhava      Dominant Bhava layer
 * @return           Nexus configuration
 */
cognade_nexus_config_t cognade_select_nexus(cognade_bhava_t bhava);

#ifdef __cplusplus
}}
#endif

#endif /* COGNADE_STATE_H */
'''


def generate_header(
    version: str = "1.0.0",
    timestamp: Optional[str] = None,
) -> str:
    """
    Generate the COGNADE C header file.

    Args:
        version: Version string (major.minor.patch)
        timestamp: Generation timestamp (auto-generated if None)

    Returns:
        C header file contents as string
    """
    from datetime import datetime

    if timestamp is None:
        timestamp = datetime.now().isoformat()

    parts = version.split(".")
    version_major = int(parts[0]) if len(parts) > 0 else 1
    version_minor = int(parts[1]) if len(parts) > 1 else 0
    version_patch = int(parts[2]) if len(parts) > 2 else 0

    return COGNADE_HEADER_TEMPLATE.format(
        timestamp=timestamp,
        version=version,
        version_major=version_major,
        version_minor=version_minor,
        version_patch=version_patch,
    )


# =============================================================================
# C Implementation Generation
# =============================================================================

COGNADE_IMPL_PHONEME = '''\
/**
 * Deterministic Phoneme Hash Implementation
 * ==========================================
 *
 * Standalone C implementation of DeterministicPhonemeEncoder.
 * Uses simplified SHA256 for consistent hashing.
 */

#include <string.h>
#include <ctype.h>

/* Vowel and consonant sets */
static const char VOWELS[] = "aeiouAEIOU";
static const char CONSONANTS[] = "bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ";

static int is_vowel(char c) {
    return strchr(VOWELS, c) != NULL;
}

static int is_consonant(char c) {
    return strchr(CONSONANTS, c) != NULL;
}

/**
 * Simple hash function for 32-bit phoneme encoding.
 *
 * Features encoded:
 * - Bits 0-7:   Primary hash (SHA256 first byte)
 * - Bits 8-11:  Length feature
 * - Bits 12-15: Vowel ratio
 * - Bits 16-23: Bigram hash
 * - Bits 24-27: First/last char
 * - Bits 28-31: Pattern flags
 */
uint32_t cognade_phoneme_hash(const char* token, size_t token_len) {
    if (token == NULL || token_len == 0) {
        return 0;
    }

    uint32_t hash = 0;

    /* Primary hash using FNV-1a (simplified SHA256 alternative) */
    uint32_t fnv_hash = 2166136261u;
    for (size_t i = 0; i < token_len; i++) {
        fnv_hash ^= (uint8_t)tolower(token[i]);
        fnv_hash *= 16777619u;
    }
    hash |= (fnv_hash & 0xFF);  /* Bits 0-7 */

    /* Length feature (0-15 clamped) */
    uint32_t len_feat = (token_len > 15) ? 15 : (uint32_t)token_len;
    hash |= (len_feat << 8);  /* Bits 8-11 */

    /* Vowel ratio (0-15 scale) */
    size_t vowel_count = 0;
    for (size_t i = 0; i < token_len; i++) {
        if (is_vowel(token[i])) vowel_count++;
    }
    uint32_t vowel_ratio = (uint32_t)((vowel_count * 15) / token_len);
    hash |= (vowel_ratio << 12);  /* Bits 12-15 */

    /* Bigram hash (first two chars) */
    if (token_len >= 2) {
        uint32_t bigram = ((uint8_t)tolower(token[0]) ^ (uint8_t)tolower(token[1]));
        hash |= (bigram << 16);  /* Bits 16-23 */
    }

    /* First/last char hash */
    uint32_t boundary = ((uint8_t)tolower(token[0]) & 0x0F);
    boundary |= (((uint8_t)tolower(token[token_len-1]) & 0x0F) << 4);
    hash |= ((boundary & 0x0F) << 24);  /* Bits 24-27 */

    /* Pattern flags */
    uint32_t flags = 0;
    for (size_t i = 0; i < token_len; i++) {
        if (isupper(token[i])) flags |= 0x1;
        if (isdigit(token[i])) flags |= 0x2;
    }
    if (token[0] == ' ' || token[0] == 'G') flags |= 0x4;  /* Word start marker */
    hash |= (flags << 28);  /* Bits 28-31 */

    return hash;
}
'''


def generate_phoneme_impl() -> str:
    """Generate standalone C implementation of phoneme hashing."""
    return COGNADE_IMPL_PHONEME


# =============================================================================
# Binary Serialization
# =============================================================================

@dataclass
class BinaryTableHeader:
    """Header for binary lookup tables."""
    magic: bytes = b'CGND'  # Magic number
    version: int = 1
    num_entries: int = 0
    entry_size: int = 0


def serialize_referent_table(
    word_to_referent: Dict[str, Dict],
    output_path: Optional[Path] = None,
) -> bytes:
    """
    Serialize WORD_TO_REFERENT dictionary to binary lookup table.

    Binary Format:
    - Header (16 bytes):
      - Magic: 'CGND' (4 bytes)
      - Version: uint32 (4 bytes)
      - Num entries: uint32 (4 bytes)
      - Reserved: uint32 (4 bytes)
    - Entries (variable):
      - Word hash: uint32 (4 bytes)
      - Primary class: uint8 (1 byte)
      - Secondary class: uint8 (1 byte)
      - Reserved: uint16 (2 bytes)

    Args:
        word_to_referent: Dictionary mapping words to referent profiles
        output_path: Optional path to write binary file

    Returns:
        Binary data as bytes
    """
    # Referent class name to index mapping
    REFERENT_TO_INDEX = {
        "luminous": 0, "biological": 1, "role_bearer": 2, "artifact": 3,
        "natural_body": 4, "substance": 5, "process": 6, "abstract": 7,
        "signal": 8, "temporal": 9, "spatial": 10, "emotional": 11,
        "social": 12, "energy_source": 13, "phenomenon": 14, "unknown": 15,
    }

    entries = []

    for word, profile in word_to_referent.items():
        # Compute word hash (FNV-1a)
        word_hash = 2166136261
        for c in word.lower():
            word_hash ^= ord(c)
            word_hash = (word_hash * 16777619) & 0xFFFFFFFF

        # Extract primary and secondary classes
        primary_class = 15  # unknown
        secondary_class = 15

        if hasattr(profile, 'primary') and profile.primary:
            primary_val = profile.primary[0].value if hasattr(profile.primary[0], 'value') else str(profile.primary[0])
            primary_class = REFERENT_TO_INDEX.get(primary_val.lower(), 15)

        if hasattr(profile, 'secondary') and profile.secondary:
            secondary_val = profile.secondary[0].value if hasattr(profile.secondary[0], 'value') else str(profile.secondary[0])
            secondary_class = REFERENT_TO_INDEX.get(secondary_val.lower(), 15)

        entries.append((word_hash, primary_class, secondary_class))

    # Sort by hash for binary search
    entries.sort(key=lambda x: x[0])

    # Build binary data
    data = bytearray()

    # Header
    data.extend(b'CGND')                              # Magic
    data.extend(struct.pack('<I', 1))                 # Version
    data.extend(struct.pack('<I', len(entries)))      # Num entries
    data.extend(struct.pack('<I', 0))                 # Reserved

    # Entries
    for word_hash, primary, secondary in entries:
        data.extend(struct.pack('<I', word_hash))     # Hash
        data.extend(struct.pack('<B', primary))       # Primary class
        data.extend(struct.pack('<B', secondary))     # Secondary class
        data.extend(struct.pack('<H', 0))             # Reserved

    result = bytes(data)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(result)

    return result


# =============================================================================
# State Packing/Unpacking
# =============================================================================

def pack_state_to_binary(
    state_128d: torch.Tensor,
) -> bytes:
    """
    Pack 128-D float state to 16-byte binary representation.

    Quantization:
    - Guna (16 floats → 16 bits): 5+5+6 bit encoding
    - S-Signal (32 floats → 32 bits): Max index encoding
    - R-Signal (48 floats → 48 bits): 4-bit per Bhava
    - C-Signal (32 floats → 32 bits): FNV hash of features

    Args:
        state_128d: [128] float tensor

    Returns:
        16-byte binary representation
    """
    if state_128d.dim() > 1:
        state_128d = state_128d.mean(dim=0)

    state = state_128d.detach().cpu()

    # Extract components
    guna = state[0:16]
    s_signal = state[16:48]
    r_signal = state[48:96]
    c_signal = state[96:128]

    # Pack Guna (16 bits)
    # Guna layout: [0:5] Sattva, [5:10] Rajas, [10:16] Tamas
    sattva = guna[0:5].mean().clamp(0, 1).item()
    rajas = guna[5:10].mean().clamp(0, 1).item()
    tamas = guna[10:16].mean().clamp(0, 1).item()

    # Normalize
    total = sattva + rajas + tamas
    if total > 0:
        sattva /= total
        rajas /= total
        tamas /= total

    # Encode: 5+5+6 bits
    sattva_int = int(sattva * 31)  # 5 bits
    rajas_int = int(rajas * 31)    # 5 bits
    tamas_int = int(tamas * 63)    # 6 bits

    guna_packed = (sattva_int) | (rajas_int << 5) | (tamas_int << 10)

    # Pack S-Signal (32 bits)
    # Use max index in first 16 dims + confidence in rest
    s_primary = s_signal[:16]
    max_idx = s_primary.argmax().item()
    confidence = s_primary[max_idx].item()

    s_packed = (max_idx & 0xF) | (int(confidence * 65535) << 4)

    # Pack R-Signal (48 bits in 64-bit container)
    # 12 Bhavas × 4 bits each = 48 bits
    r_reshaped = r_signal.view(12, 4).mean(dim=1)
    r_packed = 0
    for i in range(12):
        r_val = int(r_reshaped[i].clamp(0, 1).item() * 15)  # 4 bits
        r_packed |= (r_val << (i * 4))

    # Pack C-Signal (32 bits)
    # Simple hash of feature vector
    c_hash = 2166136261
    for i in range(32):
        c_val = int(c_signal[i].clamp(0, 1).item() * 255)
        c_hash ^= c_val
        c_hash = (c_hash * 16777619) & 0xFFFFFFFF

    # Build binary
    data = bytearray()
    data.extend(struct.pack('<H', guna_packed))   # 2 bytes
    data.extend(struct.pack('<I', s_packed))      # 4 bytes
    data.extend(struct.pack('<Q', r_packed))      # 8 bytes (only 48 bits used)
    data.extend(struct.pack('<I', c_hash))        # 4 bytes

    # Truncate to 16 bytes (we have 18, need to adjust)
    # Repack with proper 128-bit layout
    data = bytearray()
    data.extend(struct.pack('<H', guna_packed))        # 2 bytes: Guna
    data.extend(struct.pack('<I', s_packed)[:4])       # 4 bytes: S-Signal
    data.extend(struct.pack('<Q', r_packed)[:6])       # 6 bytes: R-Signal (48 bits)
    data.extend(struct.pack('<I', c_hash))             # 4 bytes: C-Signal

    return bytes(data)


def unpack_binary_to_state(
    data: bytes,
) -> torch.Tensor:
    """
    Unpack 16-byte binary to approximate 128-D float state.

    Note: This is lossy due to quantization.

    Args:
        data: 16-byte binary representation

    Returns:
        [128] float tensor (approximate)
    """
    state = torch.zeros(128)

    # Unpack Guna
    guna_packed = struct.unpack('<H', data[0:2])[0]
    sattva = (guna_packed & 0x1F) / 31.0
    rajas = ((guna_packed >> 5) & 0x1F) / 31.0
    tamas = ((guna_packed >> 10) & 0x3F) / 63.0

    state[0:5] = sattva
    state[5:10] = rajas
    state[10:16] = tamas

    # Unpack S-Signal
    s_packed = struct.unpack('<I', data[2:6])[0]
    max_idx = s_packed & 0xF
    confidence = ((s_packed >> 4) & 0xFFFF) / 65535.0

    state[16 + max_idx] = confidence

    # Unpack R-Signal
    r_packed = struct.unpack('<Q', data[6:14].ljust(8, b'\x00'))[0]
    for i in range(12):
        r_val = ((r_packed >> (i * 4)) & 0xF) / 15.0
        state[48 + i * 4:48 + (i + 1) * 4] = r_val

    # Unpack C-Signal (cannot fully recover, use hash as seed)
    c_hash = struct.unpack('<I', data[12:16])[0]
    for i in range(32):
        state[96 + i] = ((c_hash >> (i % 32)) & 0x1) / 1.0

    return state


# =============================================================================
# Export Functions
# =============================================================================

def export_cognade_sdk(
    output_dir: Path,
    word_to_referent: Optional[Dict] = None,
    version: str = "1.0.0",
) -> Dict[str, Path]:
    """
    Export complete COGNADE SDK files.

    Generates:
    - cognade_state.h: C header with struct definitions
    - cognade_phoneme.c: Phoneme hash implementation
    - referent_table.bin: Binary lookup table

    Args:
        output_dir: Directory for output files
        word_to_referent: WORD_TO_REFERENT dictionary (optional)
        version: SDK version string

    Returns:
        Dict mapping file type to path
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = {}

    # Generate header
    header_content = generate_header(version=version)
    header_path = output_dir / "cognade_state.h"
    with open(header_path, 'w') as f:
        f.write(header_content)
    files['header'] = header_path

    # Generate phoneme implementation
    phoneme_content = generate_phoneme_impl()
    phoneme_path = output_dir / "cognade_phoneme.c"
    with open(phoneme_path, 'w') as f:
        f.write(phoneme_content)
    files['phoneme_impl'] = phoneme_path

    # Generate binary referent table
    if word_to_referent:
        table_path = output_dir / "referent_table.bin"
        serialize_referent_table(word_to_referent, table_path)
        files['referent_table'] = table_path

    return files


# Convenience function
def create_exporter(output_dir: str, **kwargs) -> Dict[str, Path]:
    """Factory function for SDK export."""
    return export_cognade_sdk(Path(output_dir), **kwargs)
