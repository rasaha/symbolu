"""
Long-context workload generators for 32K-128K+ token benchmarking.

Unlike the short-context generators in kv_cache_simulator.py (which use O(n²)
sequential attention), these generators produce realistic sparse attention
patterns that are computationally feasible at 100K+ tokens.

Workload patterns modeled:
  1. Sleeping Tokens: tokens accessed early, dormant for 50K+ positions,
     then suddenly critical (multi-hop retrieval, backreferences)
  2. Needle-in-Haystack: uniform document with embedded "needles" that
     get high attention during query phase
  3. Multi-Document QA: multiple documents + queries that cross-reference
     specific passages across documents
  4. Streaming Conversation: accumulating multi-turn context with
     recency bias but periodic callbacks to early turns
  5. Code Generation: hierarchical structure with function/class
     definitions referenced long-range from call sites
"""

import math
import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LongContextConfig:
    """Configuration for long-context workload generation."""
    seq_len: int = 65536
    seed: int = 42

    # Attention patterns
    sink_tokens: int = 8           # BOS + system prompt tokens
    recent_window: int = 2048      # Sliding window for local attention
    sparse_sample_rate: float = 0.02  # Fraction of context sampled per step

    # Sleeping token parameters
    num_sleepers: int = 64         # Tokens that "wake up" after long dormancy
    min_sleep_distance: int = 8192 # Minimum gap before sleeper is reaccessed
    max_sleep_distance: int = 65536

    # Needle parameters
    num_needles: int = 32          # Important facts embedded in document
    needle_attention_boost: float = 15.0

    # Multi-document parameters
    num_documents: int = 5
    queries_per_document: int = 10
    cross_doc_reference_rate: float = 0.15  # Fraction of queries referencing other docs


class LongContextWorkloadGenerator:
    """
    Generates realistic long-context KV cache access workloads.

    All workloads produce a list of (position, token_type, attention_weight)
    tuples suitable for the KVCacheSimulator and TurboQuantCTMSimulator.
    """

    def __init__(self, config: LongContextConfig):
        self.config = config
        self.rng = random.Random(config.seed)

    def sleeping_tokens(self, num_accesses: Optional[int] = None) -> list:
        """
        Workload with "sleeping" tokens that wake up after long dormancy.

        Pattern:
        - Phase 1 (0-20%): Document ingestion, all tokens accessed once
        - Phase 2 (20-80%): Steady generation with local attention
        - Phase 3 (80-100%): Retrieval bursts — sleeping tokens from phase 1
          suddenly get high attention as the model backreferences

        This is the hardest workload for LRU: the sleeping tokens haven't
        been accessed for 50K+ positions, so LRU evicts them, but they're
        about to become critical.
        """
        cfg = self.config
        seq_len = cfg.seq_len
        n = num_accesses or seq_len * 3

        accesses = []

        # Choose sleeping token positions (scattered in first 20% of context)
        sleeper_zone_end = seq_len // 5
        sleeper_positions = sorted(
            self.rng.sample(range(cfg.sink_tokens, sleeper_zone_end), cfg.num_sleepers)
        )
        sleeper_set = set(sleeper_positions)

        # Phase 1: Document ingestion (0 to 20% of accesses)
        phase1_end = n // 5
        for t in range(min(phase1_end, seq_len)):
            token_type = self._token_type(t, sleeper_set)
            # During ingestion, sparse attention to prior context
            attn = self._sparse_attention_weight(t, seq_len)
            accesses.append((t, token_type, attn))

        # Phase 2: Steady generation (20% to 80%)
        # Local attention with recency bias + sinks
        phase2_end = 4 * n // 5
        for step in range(phase1_end, phase2_end):
            current_pos = min(seq_len - 1, sleeper_zone_end + (step - phase1_end))

            # Attend to sinks
            for s in range(min(cfg.sink_tokens, seq_len)):
                accesses.append((s, "bos" if s == 0 else "instruction", 0.05))

            # Attend to recent window (sparse sample)
            window_start = max(0, current_pos - cfg.recent_window)
            n_sample = max(1, int(cfg.recent_window * cfg.sparse_sample_rate))
            if current_pos > window_start:
                sampled = self.rng.sample(
                    range(window_start, current_pos),
                    min(n_sample, current_pos - window_start),
                )
                for pos in sampled:
                    token_type = self._token_type(pos, sleeper_set)
                    accesses.append((pos, token_type, 0.02))

            # Occasional random long-range access (non-sleeper)
            if self.rng.random() < 0.01 and current_pos > cfg.recent_window:
                far_pos = self.rng.randint(cfg.sink_tokens, window_start)
                accesses.append((far_pos, "regular", 0.005))

            # Early termination if we've generated enough
            if len(accesses) >= phase2_end:
                break

        # Phase 3: Retrieval bursts (80% to 100%)
        # Sleeping tokens wake up with high attention
        retrieval_steps = n - phase2_end
        sleepers_per_burst = max(1, cfg.num_sleepers // max(1, retrieval_steps // 20))

        for step in range(retrieval_steps):
            current_pos = seq_len - 1

            # Always attend to sinks
            accesses.append((0, "bos", 0.05))

            # Recent window (still active)
            window_start = max(0, current_pos - cfg.recent_window // 2)
            n_sample = max(1, int(cfg.recent_window * cfg.sparse_sample_rate * 0.5))
            if current_pos > window_start:
                sampled = self.rng.sample(
                    range(window_start, current_pos),
                    min(n_sample, current_pos - window_start),
                )
                for pos in sampled:
                    accesses.append((pos, "regular", 0.01))

            # WAKE UP sleepers — high attention burst
            burst_sleepers = self.rng.sample(
                sleeper_positions,
                min(sleepers_per_burst, len(sleeper_positions)),
            )
            for sp in burst_sleepers:
                accesses.append((
                    sp,
                    "entity",  # Sleepers are important entities
                    0.1 * cfg.needle_attention_boost,
                ))

            if len(accesses) >= n:
                break

        return accesses[:n]

    def needle_in_haystack(self, num_accesses: Optional[int] = None) -> list:
        """
        Needle-in-a-Haystack workload.

        A long document with embedded "needles" (facts/entities) at specific
        positions. After document ingestion, queries arrive that require
        retrieving specific needles from various depths.

        Tests whether the eviction policy preserves tokens at arbitrary
        depths in the context, not just recent or frequent ones.
        """
        cfg = self.config
        seq_len = cfg.seq_len
        n = num_accesses or seq_len * 2

        accesses = []

        # Place needles at various depths (uniform distribution)
        needle_positions = sorted(
            self.rng.sample(
                range(cfg.sink_tokens, seq_len - cfg.recent_window),
                min(cfg.num_needles, seq_len - cfg.sink_tokens - cfg.recent_window),
            )
        )
        needle_set = set(needle_positions)

        # Phase 1: Document ingestion (first seq_len accesses, sparse)
        # Process document sequentially but with sparse backward attention
        ingestion_len = min(n // 2, seq_len)
        for t in range(ingestion_len):
            token_type = "entity" if t in needle_set else self._token_type(t, set())
            attn = 0.01
            # Needles get slightly higher attention during ingestion
            if t in needle_set:
                attn = 0.05
            accesses.append((t, token_type, attn))

            # Sparse backward attention during ingestion
            if t > 0 and t % 64 == 0:
                n_back = min(8, t)
                back_positions = self.rng.sample(range(t), n_back)
                for bp in back_positions:
                    bt = "entity" if bp in needle_set else "regular"
                    accesses.append((bp, bt, 0.005))

        # Phase 2: Query phase — retrieve needles from various depths
        queries_remaining = n - len(accesses)
        queries = max(1, queries_remaining // (cfg.num_needles * 5))

        for q in range(queries):
            # Each query targets 1-3 needles
            num_targets = self.rng.randint(1, min(3, len(needle_positions)))
            target_needles = self.rng.sample(needle_positions, num_targets)

            # Query tokens attend to:
            # 1. Sinks (always)
            accesses.append((0, "bos", 0.04))
            for s in range(1, min(cfg.sink_tokens, seq_len)):
                accesses.append((s, "instruction", 0.03))

            # 2. Target needles (HIGH attention)
            for np_ in target_needles:
                accesses.append((
                    np_, "entity",
                    cfg.needle_attention_boost * 0.1,
                ))
                # Also attend to neighbors of needle (context window around it)
                for offset in [-2, -1, 1, 2]:
                    neighbor = np_ + offset
                    if 0 <= neighbor < seq_len:
                        accesses.append((neighbor, "regular", 0.02))

            # 3. Recent window
            n_recent = max(1, int(cfg.recent_window * cfg.sparse_sample_rate))
            recent_start = max(0, seq_len - cfg.recent_window)
            if seq_len > recent_start:
                sampled = self.rng.sample(
                    range(recent_start, seq_len),
                    min(n_recent, seq_len - recent_start),
                )
                for pos in sampled:
                    accesses.append((pos, "regular", 0.01))

            # 4. Random non-needle tokens (noise)
            for _ in range(3):
                rp = self.rng.randint(cfg.sink_tokens, seq_len - 1)
                if rp not in needle_set:
                    accesses.append((rp, "regular", 0.002))

            if len(accesses) >= n:
                break

        return accesses[:n]

    def multi_document_qa(self, num_accesses: Optional[int] = None) -> list:
        """
        Multi-document QA with cross-references.

        Multiple documents loaded sequentially, followed by queries that
        reference specific passages — sometimes across documents. Tests
        the system's ability to maintain access to widely-separated regions
        of the context simultaneously.
        """
        cfg = self.config
        seq_len = cfg.seq_len
        n = num_accesses or seq_len * 2

        accesses = []
        num_docs = cfg.num_documents
        doc_len = (seq_len - cfg.sink_tokens) // num_docs

        # Build document boundaries and key passages
        doc_starts = []
        doc_key_passages = {}  # doc_idx -> list of (start, end) key passage ranges

        for d in range(num_docs):
            start = cfg.sink_tokens + d * doc_len
            doc_starts.append(start)

            # Each document has 3-5 key passages
            num_passages = self.rng.randint(3, 6)
            passages = []
            for _ in range(num_passages):
                p_start = start + self.rng.randint(0, max(1, doc_len - 50))
                p_end = min(p_start + self.rng.randint(5, 20), start + doc_len)
                passages.append((p_start, p_end))
            doc_key_passages[d] = passages

        # Phase 1: Document ingestion
        ingestion_budget = n // 2
        tokens_per_step = max(1, seq_len // ingestion_budget)

        for pos in range(0, seq_len, tokens_per_step):
            # Determine which document this token belongs to
            doc_idx = min(num_docs - 1, max(0, (pos - cfg.sink_tokens) // doc_len))
            is_key = any(s <= pos < e for s, e in doc_key_passages.get(doc_idx, []))

            token_type = "entity" if is_key else self._token_type(pos, set())
            attn = 0.03 if is_key else 0.005
            accesses.append((pos, token_type, attn))

            if len(accesses) >= ingestion_budget:
                break

        # Phase 2: Queries
        query_budget = n - len(accesses)
        queries_count = cfg.queries_per_document * num_docs

        for q in range(queries_count):
            # Primary document for this query
            primary_doc = q % num_docs
            primary_passages = doc_key_passages[primary_doc]

            # Sinks
            accesses.append((0, "bos", 0.04))

            # Attend to primary document passages
            for p_start, p_end in primary_passages:
                target = self.rng.randint(p_start, max(p_start + 1, p_end))
                accesses.append((target, "entity", 0.08))

            # Cross-document reference
            if self.rng.random() < cfg.cross_doc_reference_rate:
                other_doc = self.rng.choice(
                    [d for d in range(num_docs) if d != primary_doc]
                )
                other_passages = doc_key_passages[other_doc]
                if other_passages:
                    xref = self.rng.choice(other_passages)
                    target = self.rng.randint(xref[0], max(xref[0] + 1, xref[1]))
                    accesses.append((target, "entity", 0.12))

            # Recent context
            n_recent = max(1, int(cfg.recent_window * cfg.sparse_sample_rate * 0.5))
            recent_start = max(0, seq_len - cfg.recent_window)
            if seq_len > recent_start:
                for pos in self.rng.sample(
                    range(recent_start, seq_len),
                    min(n_recent, seq_len - recent_start),
                ):
                    accesses.append((pos, "regular", 0.01))

            if len(accesses) >= n:
                break

        return accesses[:n]

    def streaming_conversation(
        self,
        num_turns: int = 50,
        tokens_per_turn: int = 512,
        callback_rate: float = 0.08,
        num_accesses: Optional[int] = None,
    ) -> list:
        """
        Long streaming conversation with periodic callbacks to early turns.

        Simulates a multi-turn conversation where:
        - Each turn adds new tokens and attends to recent context
        - Periodically, the model callbacks to early turns (user referenced
          something from the beginning of the conversation)
        - System prompt tokens always get attention (sinks)
        """
        cfg = self.config
        seq_len = min(cfg.seq_len, num_turns * tokens_per_turn + cfg.sink_tokens)
        n = num_accesses or seq_len * 2

        accesses = []
        turn_starts = []

        for turn in range(num_turns):
            turn_start = cfg.sink_tokens + turn * tokens_per_turn
            turn_end = min(turn_start + tokens_per_turn, seq_len)
            turn_starts.append(turn_start)

            if turn_start >= seq_len:
                break

            # Each new token in this turn
            for pos in range(turn_start, turn_end):
                token_type = self._token_type(pos, set())

                # Always attend to sinks
                accesses.append((0, "bos", 0.05))

                # Attend to current turn (high attention)
                n_intra = min(8, pos - turn_start)
                if n_intra > 0:
                    for ip in self.rng.sample(
                        range(turn_start, pos), min(n_intra, pos - turn_start)
                    ):
                        accesses.append((ip, "regular", 0.04))

                # Attend to previous turn (moderate)
                if turn > 0:
                    prev_start = turn_starts[turn - 1]
                    prev_end = turn_starts[turn - 1] + tokens_per_turn
                    n_prev = min(4, prev_end - prev_start)
                    for pp in self.rng.sample(
                        range(prev_start, min(prev_end, seq_len)),
                        min(n_prev, min(prev_end, seq_len) - prev_start),
                    ):
                        accesses.append((pp, "regular", 0.02))

                # Callback to early turns (rare but important)
                if self.rng.random() < callback_rate and turn > 3:
                    # Reference a random early turn
                    early_turn = self.rng.randint(0, min(turn // 2, len(turn_starts) - 1))
                    early_start = turn_starts[early_turn]
                    early_pos = early_start + self.rng.randint(
                        0, min(tokens_per_turn, seq_len - early_start) - 1
                    )
                    accesses.append((early_pos, "entity", 0.08))

                # Self token
                accesses.append((pos, token_type, 0.01))

                if len(accesses) >= n:
                    break
            if len(accesses) >= n:
                break

        return accesses[:n]

    def code_generation(self, num_accesses: Optional[int] = None) -> list:
        """
        Code generation workload with hierarchical long-range references.

        Simulates:
        - Import statements (positions 0-50): referenced from everywhere
        - Class definitions (positions 50-5000): referenced from methods
        - Function bodies: reference their class + imports + other functions
        - Long-range call sites: functions defined early called from code
          written 40K+ tokens later

        Tests hierarchical long-range dependencies typical of code LLMs.
        """
        cfg = self.config
        seq_len = cfg.seq_len
        n = num_accesses or seq_len * 2

        accesses = []

        # Structure: imports | class_defs | function_bodies | main_code
        # Scale zones to seq_len so it works at any size
        import_end = min(50, seq_len // 10)
        class_end = min(5000, seq_len // 4)
        func_start = class_end
        func_end = seq_len // 2
        import_zone = (0, max(1, import_end))
        class_zone = (import_end, max(import_end + 1, class_end))
        func_zone = (func_start, max(func_start + 1, func_end))
        main_zone = (func_end, seq_len)

        # Define function entry points (scattered through func_zone)
        func_range = max(1, func_zone[1] - func_zone[0])
        num_functions = min(100, func_range // max(1, func_range // 50))
        num_functions = max(1, min(num_functions, func_range))
        func_positions = sorted(
            self.rng.sample(
                range(func_zone[0], func_zone[1]),
                num_functions,
            )
        )
        func_set = set(func_positions)

        # Define class entry points
        class_range = max(1, class_zone[1] - class_zone[0])
        num_classes = max(1, min(20, class_range // max(1, class_range // 10)))
        num_classes = min(num_classes, class_range)
        class_positions = sorted(
            self.rng.sample(
                range(class_zone[0], class_zone[1]),
                num_classes,
            )
        )

        # Phase 1: Write code (ingestion)
        ingestion_budget = n * 2 // 3
        step_size = max(1, seq_len // ingestion_budget)

        for pos in range(0, seq_len, step_size):
            # Token type based on zone
            if import_zone[0] <= pos < import_zone[1]:
                token_type = "code"
                attn = 0.03
            elif pos in func_set:
                token_type = "entity"  # Function definition
                attn = 0.05
            elif pos in class_positions:
                token_type = "entity"  # Class definition
                attn = 0.06
            else:
                token_type = "code"
                attn = 0.005

            accesses.append((pos, token_type, attn))

            # Code references during writing
            # Reference imports frequently
            if self.rng.random() < 0.05 and import_zone[1] > import_zone[0]:
                ip = self.rng.randint(import_zone[0], import_zone[1] - 1)
                accesses.append((ip, "code", 0.02))

            # Reference class defs from function bodies
            if pos >= func_zone[0] and self.rng.random() < 0.08 and class_positions:
                cp = self.rng.choice(class_positions)
                accesses.append((cp, "entity", 0.04))

            # Reference other functions (call sites)
            if pos >= main_zone[0] and self.rng.random() < 0.1 and func_positions:
                fp = self.rng.choice(func_positions)
                accesses.append((fp, "entity", 0.06))

            if len(accesses) >= ingestion_budget:
                break

        # Phase 2: Code completion / execution — heavy long-range references
        completion_budget = n - len(accesses)

        for step in range(completion_budget):
            current_pos = main_zone[0] + self.rng.randint(
                0, max(1, main_zone[1] - main_zone[0] - 1)
            )

            # Always reference imports
            if import_zone[1] > import_zone[0]:
                ip = self.rng.randint(import_zone[0], import_zone[1] - 1)
                accesses.append((ip, "code", 0.03))

            # Reference function definitions (long-range!)
            if func_positions:
                # Zipfian selection — some functions referenced much more
                idx = min(
                    int(abs(self.rng.gauss(0, len(func_positions) / 3))),
                    len(func_positions) - 1,
                )
                fp = func_positions[idx]
                accesses.append((fp, "entity", 0.08))

            # Reference class
            if class_positions and self.rng.random() < 0.3:
                cp = self.rng.choice(class_positions)
                accesses.append((cp, "entity", 0.05))

            # Local context
            window_start = max(0, current_pos - cfg.recent_window // 4)
            n_local = min(4, current_pos - window_start)
            if n_local > 0:
                for lp in self.rng.sample(
                    range(window_start, current_pos),
                    min(n_local, current_pos - window_start),
                ):
                    accesses.append((lp, "code", 0.01))

            if len(accesses) >= n:
                break

        return accesses[:n]

    def _token_type(self, position: int, special_set: set) -> str:
        """Assign token type."""
        if position == 0:
            return "bos"
        if position in special_set:
            return "entity"
        if position < 10 and self.rng.random() < 0.3:
            return "instruction"
        r = self.rng.random()
        if r < 0.04:
            return "entity"
        if r < 0.07:
            return "number"
        if r < 0.15:
            return "punctuation"
        return "regular"

    def _sparse_attention_weight(self, position: int, seq_len: int) -> float:
        """Compute a sparse attention weight for document ingestion."""
        if position < self.config.sink_tokens:
            return 0.05
        # Mild recency bias during ingestion
        return 0.005 + 0.01 * (position / max(1, seq_len))
