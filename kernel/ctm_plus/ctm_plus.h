/* SPDX-License-Identifier: GPL-2.0 */
/*
 * CTM+ (Coherence-Tier Memory Plus) Kernel Module
 *
 * A smart memory tiering controller that optimizes page placement
 * between fast (Tier 0) and slow (Tier 1) memory tiers.
 *
 * Core components:
 * - Phase Integrator: Learns access patterns
 * - USE Coherence: Computes pairwise phase correlation
 * - Dual Shadow Tier: ARC-like ghost caches with adaptive p
 * - Smart Victim Selection: Pre-eviction scoring
 */

#ifndef _CTM_PLUS_H
#define _CTM_PLUS_H

#include <linux/types.h>
#include <linux/list.h>
#include <linux/rbtree.h>
#include <linux/spinlock.h>
#include <linux/workqueue.h>

/* Configuration defaults */
#define CTM_VICTIM_SAMPLE_SIZE      48
#define CTM_PROMOTION_THRESHOLD     30  /* 0.3 * 100 for integer math */
#define CTM_LOOP_PIN_REUSE_THRESH   40  /* 0.4 * 100 */
#define CTM_LOOP_PIN_NEIGHBOR_THRESH 30  /* 0.3 * 100 */
#define CTM_SHADOW_MAX_SIZE         1024
#define CTM_NEIGHBOR_WINDOW         16
#define CTM_NEIGHBOR_TOP_K          8

/* Page state flags */
#define CTM_PAGE_IN_TIER0   BIT(0)
#define CTM_PAGE_IN_TIER1   BIT(1)
#define CTM_PAGE_HOT        BIT(2)
#define CTM_PAGE_PINNED     BIT(3)

/**
 * struct ctm_page_state - Per-page tracking state
 * @node: RB tree node for fast lookup
 * @lru_list: LRU list linkage
 * @pfn: Page frame number
 * @flags: Page state flags
 * @access_count: Total access count
 * @last_access_time: Timestamp of last access
 * @phase: Learned phase value (fixed-point, scaled by 1000)
 * @amplitude: Access amplitude (fixed-point)
 * @coherence: Coherence score (fixed-point)
 * @reuse_score: Predicted reuse probability (fixed-point)
 */
struct ctm_page_state {
    struct rb_node node;
    struct list_head lru_list;
    unsigned long pfn;
    unsigned int flags;
    unsigned int access_count;
    u64 last_access_time;
    s32 phase;          /* Fixed-point: value * 1000 */
    u32 amplitude;      /* Fixed-point: value * 100 */
    u32 coherence;      /* Fixed-point: value * 100 */
    u32 reuse_score;    /* Fixed-point: value * 100 */
};

/**
 * struct ctm_shadow_entry - Ghost cache entry for regret tracking
 * @list: FIFO list linkage
 * @pfn: Page frame number
 * @evict_time: When page was evicted
 * @from_tier0: Was evicted from tier0 (B1) or tier1 (B2)
 */
struct ctm_shadow_entry {
    struct list_head list;
    unsigned long pfn;
    u64 evict_time;
    bool from_tier0;
};

/**
 * struct ctm_neighbor_tracker - Co-occurrence tracking
 * @recent: Circular buffer of recent page accesses
 * @recent_idx: Current index in circular buffer
 * @cooccur_tree: RB tree of co-occurrence counts
 */
struct ctm_neighbor_tracker {
    unsigned long recent[CTM_NEIGHBOR_WINDOW];
    int recent_idx;
    struct rb_root cooccur_tree;
};

/**
 * struct ctm_transition_tracker - Markov transition model
 * @transitions: Hash table of page transitions
 * @last_page: Last accessed page
 */
struct ctm_transition_tracker {
    struct hlist_head *transitions;
    unsigned long last_page;
    unsigned int hash_bits;
};

/**
 * struct ctm_config - Runtime configuration
 * @victim_sample_size: Sample size for victim selection
 * @promotion_threshold: Min score to promote (scaled by 100)
 * @loop_pin_reuse_thresh: Reuse threshold for loop pinning
 * @loop_pin_neighbor_thresh: Neighbor threshold for loop pinning
 * @enable_smart_victim: Use smart victim selection vs LRU
 */
struct ctm_config {
    unsigned int victim_sample_size;
    unsigned int promotion_threshold;
    unsigned int loop_pin_reuse_thresh;
    unsigned int loop_pin_neighbor_thresh;
    bool enable_smart_victim;
};

/**
 * struct ctm_stats - Runtime statistics
 * @promotions: Total promotions from tier1 to tier0
 * @demotions: Total demotions from tier0 to tier1
 * @tier0_hits: Hits in tier0
 * @tier1_hits: Hits in tier1
 * @misses: Total misses
 * @smart_victim_selections: Times smart victim was used
 */
struct ctm_stats {
    atomic64_t promotions;
    atomic64_t demotions;
    atomic64_t tier0_hits;
    atomic64_t tier1_hits;
    atomic64_t misses;
    atomic64_t smart_victim_selections;
};

/**
 * struct ctm_controller - Main CTM+ controller
 * @lock: Spinlock for synchronization
 * @page_tree: RB tree of all tracked pages
 * @tier0_lru: LRU list for tier0 pages
 * @tier1_lru: LRU list for tier1 pages
 * @shadow_b1: Ghost cache for tier0 evictions
 * @shadow_b2: Ghost cache for tier1 evictions
 * @neighbor: Neighbor tracker
 * @transition: Transition tracker
 * @config: Runtime configuration
 * @stats: Statistics
 * @tier0_size: Current tier0 size
 * @tier0_capacity: Max tier0 capacity
 * @tier1_size: Current tier1 size
 * @tier1_capacity: Max tier1 capacity
 * @adaptive_p: ARC-style adaptive parameter (scaled by 100)
 * @access_counter: Global access counter
 * @slow_work: Workqueue for background coherence updates
 */
struct ctm_controller {
    spinlock_t lock;
    struct rb_root page_tree;
    struct list_head tier0_lru;
    struct list_head tier1_lru;
    struct list_head shadow_b1;
    struct list_head shadow_b2;
    unsigned int shadow_b1_size;
    unsigned int shadow_b2_size;
    struct ctm_neighbor_tracker neighbor;
    struct ctm_transition_tracker transition;
    struct ctm_config config;
    struct ctm_stats stats;
    unsigned int tier0_size;
    unsigned int tier0_capacity;
    unsigned int tier1_size;
    unsigned int tier1_capacity;
    unsigned int adaptive_p;  /* Scaled by 100, range [0, 100] */
    u64 access_counter;
    struct delayed_work slow_work;
};

/* Core API */
int ctm_init(struct ctm_controller *ctrl, unsigned int tier0_cap,
             unsigned int tier1_cap);
void ctm_destroy(struct ctm_controller *ctrl);

/* Access handling */
int ctm_on_access(struct ctm_controller *ctrl, unsigned long pfn,
                  bool is_write, bool *promoted, bool *demoted);

/* Page tier queries */
bool ctm_is_in_tier0(struct ctm_controller *ctrl, unsigned long pfn);
int ctm_get_tier(struct ctm_controller *ctrl, unsigned long pfn);

/* Configuration */
void ctm_set_config(struct ctm_controller *ctrl, struct ctm_config *config);
void ctm_get_config(struct ctm_controller *ctrl, struct ctm_config *config);

/* Statistics */
void ctm_get_stats(struct ctm_controller *ctrl, struct ctm_stats *stats);
void ctm_reset_stats(struct ctm_controller *ctrl);

/* Victim selection (for external memory managers) */
unsigned long ctm_select_victim(struct ctm_controller *ctrl);

/* sysfs interface */
extern struct attribute_group ctm_attr_group;

#endif /* _CTM_PLUS_H */
