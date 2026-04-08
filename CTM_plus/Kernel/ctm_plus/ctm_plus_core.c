// SPDX-License-Identifier: GPL-2.0
/*
 * CTM+ Core Algorithm Implementation
 *
 * Implements the core CTM+ memory tiering logic:
 * - Smart victim selection with O(k) sampling
 * - ARC-style dual shadow tiers for adaptive p
 * - Neighbor tracking for cluster protection
 * - Transition tracking for reuse prediction
 */

#include <linux/kernel.h>
#include <linux/slab.h>
#include <linux/random.h>
#include <linux/math64.h>
#include "ctm_plus.h"

/* Fixed-point math helpers (scale = 100) */
#define FP_SCALE 100
#define FP_MUL(a, b) (((a) * (b)) / FP_SCALE)
#define FP_DIV(a, b) (((a) * FP_SCALE) / (b))

/* Hash function for transition tracker */
static inline unsigned int ctm_hash_pfn(unsigned long pfn, unsigned int bits)
{
    return hash_long(pfn, bits);
}

/* ========== Page State Management ========== */

static struct ctm_page_state *ctm_find_page(struct ctm_controller *ctrl,
                                            unsigned long pfn)
{
    struct rb_node *node = ctrl->page_tree.rb_node;

    while (node) {
        struct ctm_page_state *page = rb_entry(node, struct ctm_page_state, node);

        if (pfn < page->pfn)
            node = node->rb_left;
        else if (pfn > page->pfn)
            node = node->rb_right;
        else
            return page;
    }
    return NULL;
}

static struct ctm_page_state *ctm_alloc_page(struct ctm_controller *ctrl,
                                             unsigned long pfn)
{
    struct ctm_page_state *page;
    struct rb_node **link = &ctrl->page_tree.rb_node;
    struct rb_node *parent = NULL;

    page = kzalloc(sizeof(*page), GFP_ATOMIC);
    if (!page)
        return NULL;

    page->pfn = pfn;
    page->coherence = 50;  /* Default 0.5 */
    INIT_LIST_HEAD(&page->lru_list);

    /* Insert into RB tree */
    while (*link) {
        struct ctm_page_state *entry = rb_entry(*link, struct ctm_page_state, node);
        parent = *link;

        if (pfn < entry->pfn)
            link = &(*link)->rb_left;
        else
            link = &(*link)->rb_right;
    }

    rb_link_node(&page->node, parent, link);
    rb_insert_color(&page->node, &ctrl->page_tree);

    return page;
}

static void ctm_free_page(struct ctm_controller *ctrl, struct ctm_page_state *page)
{
    rb_erase(&page->node, &ctrl->page_tree);
    list_del(&page->lru_list);
    kfree(page);
}

/* ========== Shadow Tier (Ghost Cache) ========== */

static void ctm_shadow_record(struct ctm_controller *ctrl, unsigned long pfn,
                              bool from_tier0)
{
    struct ctm_shadow_entry *entry;
    struct list_head *shadow = from_tier0 ? &ctrl->shadow_b1 : &ctrl->shadow_b2;
    unsigned int *size = from_tier0 ? &ctrl->shadow_b1_size : &ctrl->shadow_b2_size;

    entry = kzalloc(sizeof(*entry), GFP_ATOMIC);
    if (!entry)
        return;

    entry->pfn = pfn;
    entry->evict_time = ctrl->access_counter;
    entry->from_tier0 = from_tier0;

    list_add_tail(&entry->list, shadow);
    (*size)++;

    /* Trim if too large */
    while (*size > CTM_SHADOW_MAX_SIZE) {
        struct ctm_shadow_entry *old = list_first_entry(shadow,
                                        struct ctm_shadow_entry, list);
        list_del(&old->list);
        kfree(old);
        (*size)--;
    }
}

static bool ctm_shadow_check(struct ctm_controller *ctrl, unsigned long pfn,
                             bool *was_in_b1)
{
    struct ctm_shadow_entry *entry, *tmp;

    /* Check B1 (evicted from tier0) */
    list_for_each_entry_safe(entry, tmp, &ctrl->shadow_b1, list) {
        if (entry->pfn == pfn) {
            list_del(&entry->list);
            kfree(entry);
            ctrl->shadow_b1_size--;
            *was_in_b1 = true;
            return true;
        }
    }

    /* Check B2 (evicted from tier1) */
    list_for_each_entry_safe(entry, tmp, &ctrl->shadow_b2, list) {
        if (entry->pfn == pfn) {
            list_del(&entry->list);
            kfree(entry);
            ctrl->shadow_b2_size--;
            *was_in_b1 = false;
            return true;
        }
    }

    return false;
}

static void ctm_update_adaptive_p(struct ctm_controller *ctrl, bool hit_in_b1)
{
    unsigned int delta;

    /* ARC-style p adaptation */
    if (hit_in_b1) {
        /* Hit in B1: increase p (favor recency) */
        delta = ctrl->shadow_b2_size > ctrl->shadow_b1_size ?
                FP_DIV(ctrl->shadow_b2_size, ctrl->shadow_b1_size) : FP_SCALE;
        ctrl->adaptive_p = min(ctrl->adaptive_p + delta, 100u);
    } else {
        /* Hit in B2: decrease p (favor frequency) */
        delta = ctrl->shadow_b1_size > ctrl->shadow_b2_size ?
                FP_DIV(ctrl->shadow_b1_size, ctrl->shadow_b2_size) : FP_SCALE;
        ctrl->adaptive_p = ctrl->adaptive_p > delta ? ctrl->adaptive_p - delta : 0;
    }
}

/* ========== Neighbor Tracking ========== */

static void ctm_neighbor_record(struct ctm_controller *ctrl, unsigned long pfn)
{
    int i;

    /* Record co-occurrences with recent pages */
    for (i = 0; i < CTM_NEIGHBOR_WINDOW; i++) {
        unsigned long recent = ctrl->neighbor.recent[i];
        if (recent && recent != pfn) {
            /*
             * Update coherence score of neighbor page.
             * Pages co-occurring frequently get higher coherence,
             * protecting them from eviction as a cluster.
             */
            struct ctm_page_state *neighbor = ctm_find_page(ctrl, recent);
            if (neighbor) {
                unsigned int new_coh = neighbor->coherence + 5;
                neighbor->coherence = min(new_coh, 100u);
            }
        }
    }

    /* Add to recent buffer */
    ctrl->neighbor.recent[ctrl->neighbor.recent_idx] = pfn;
    ctrl->neighbor.recent_idx = (ctrl->neighbor.recent_idx + 1) % CTM_NEIGHBOR_WINDOW;
}

static unsigned int ctm_get_neighbor_hotness(struct ctm_controller *ctrl,
                                             unsigned long pfn)
{
    /* Simplified: check how many recent neighbors are in tier0 */
    int i, in_tier0 = 0, total = 0;

    for (i = 0; i < CTM_NEIGHBOR_WINDOW; i++) {
        unsigned long neighbor = ctrl->neighbor.recent[i];
        if (neighbor && neighbor != pfn) {
            struct ctm_page_state *page = ctm_find_page(ctrl, neighbor);
            if (page) {
                total++;
                if (page->flags & CTM_PAGE_IN_TIER0)
                    in_tier0++;
            }
        }
    }

    return total ? FP_DIV(in_tier0 * FP_SCALE, total) : 0;
}

/* ========== Transition Tracking ========== */

static void ctm_transition_record(struct ctm_controller *ctrl, unsigned long pfn)
{
    /* Record transition from last_page to pfn */
    if (ctrl->transition.last_page && ctrl->transition.last_page != pfn) {
        /*
         * Boost reuse_score of the target page when it follows
         * a known predecessor — indicates a repeating access pattern.
         */
        struct ctm_page_state *page = ctm_find_page(ctrl, pfn);
        if (page) {
            unsigned int new_reuse = page->reuse_score + 10;
            page->reuse_score = min(new_reuse, 100u);
        }
    }
    ctrl->transition.last_page = pfn;
}

static unsigned int ctm_get_reuse_score(struct ctm_controller *ctrl,
                                        unsigned long pfn)
{
    /* Simplified: return based on access count */
    struct ctm_page_state *page = ctm_find_page(ctrl, pfn);
    if (!page)
        return 0;

    /* Higher access count = higher reuse probability, capped at 100 */
    return min(min(page->access_count, 10u) * 10, 100u);
}

/* ========== Victim Selection ========== */

/**
 * ctm_score_page - Compute victim score for a page.
 *
 * Weighted scoring with 5 base signals + optional compression quality hint.
 * Lower score = evict first. Higher score = more valuable = keep.
 *
 * Base signals (matching CUDA compute_victim_score):
 *   40% recency + 30% frequency + 15% reuse + 10% coherence - 10% neighbor
 *
 * Compression quality signal (when enable_compression_hints is set):
 *   Pages with poor GPU compression quality (low cosine_similarity) get a
 *   score boost because evicting them loses more information — the GPU's
 *   compressed representation for those pages is less faithful.
 */
static unsigned int ctm_score_page(struct ctm_controller *ctrl,
                                   struct ctm_page_state *page,
                                   u64 min_time, u64 time_range)
{
    unsigned int score, recency_rank, frequency, reuse, coherence, neighbor_hot;

    /* Recency (fixed-point) */
    {
        u64 delta = page->last_access_time - min_time;
        if (delta > div64_u64(ULLONG_MAX, FP_SCALE))
            recency_rank = (unsigned int)div64_u64(delta, time_range) * FP_SCALE;
        else
            recency_rank = (unsigned int)div64_u64(delta * FP_SCALE, time_range);
    }
    frequency = min(min(page->access_count, 10u) * 10, 100u);
    reuse = ctm_get_reuse_score(ctrl, page->pfn);
    coherence = page->coherence;
    neighbor_hot = ctm_get_neighbor_hotness(ctrl, page->pfn);

    /* Weighted score (lower = evict first) */
    score = FP_MUL(40, recency_rank) +
            FP_MUL(30, frequency) +
            FP_MUL(15, reuse) +
            FP_MUL(10, coherence);

    /* Subtract neighbor protection */
    if (score > FP_MUL(10, neighbor_hot))
        score -= FP_MUL(10, neighbor_hot);

    /* Partition penalty based on adaptive p */
    if (ctrl->adaptive_p > 50 && frequency < 30)
        score = score > 10 ? score - 10 : 0;
    else if (ctrl->adaptive_p < 50 && recency_rank < 30)
        score = score > 10 ? score - 10 : 0;

    /*
     * Compression quality hint from GPU (quality-aware eviction).
     *
     * Pages with low compression_quality (poorly compressed on GPU) get
     * a score boost. Evicting them from fast memory is more costly because
     * their compressed representation loses more information.
     *
     * compression_quality is 0-100 (cosine_sim * 100).
     * quality_penalty = 100 - compression_quality (high when quality is poor).
     */
    if (ctrl->config.enable_compression_hints &&
        (page->flags & CTM_PAGE_GPU_COMPRESSED)) {
        unsigned int quality_penalty = 100 - page->compression_quality;
        score += FP_MUL(ctrl->config.weight_compression_quality, quality_penalty);
    }

    return score;
}

static struct ctm_page_state *ctm_select_victim_smart(struct ctm_controller *ctrl)
{
    struct ctm_page_state *victim = NULL, *page;
    struct list_head *pos;
    unsigned int best_score = UINT_MAX;
    unsigned int sample_count = 0;
    unsigned int sample_target = ctrl->config.victim_sample_size;
    u64 time_range, min_time = ULLONG_MAX, max_time = 0;

    /* Find time range */
    list_for_each(pos, &ctrl->tier0_lru) {
        page = list_entry(pos, struct ctm_page_state, lru_list);
        if (page->last_access_time < min_time)
            min_time = page->last_access_time;
        if (page->last_access_time > max_time)
            max_time = page->last_access_time;
    }
    time_range = max_time - min_time;
    if (!time_range)
        time_range = 1;

    /* Sample and score pages */
    list_for_each(pos, &ctrl->tier0_lru) {
        unsigned int score;

        page = list_entry(pos, struct ctm_page_state, lru_list);

        /* Random sampling (simplified) */
        if (sample_count >= sample_target && get_random_u32() % 4 != 0)
            continue;

        sample_count++;

        score = ctm_score_page(ctrl, page, min_time, time_range);

        if (score < best_score) {
            best_score = score;
            victim = page;
        }
    }

    if (victim)
        atomic64_inc(&ctrl->stats.smart_victim_selections);

    return victim;
}

/**
 * ctm_select_cxl_victim_smart - Select a victim from the CXL tier.
 *
 * When the CXL tier is full and a new page needs to be demoted from tier0,
 * we first evict the lowest-scoring page from CXL to tier1.
 */
static struct ctm_page_state *ctm_select_cxl_victim_smart(
    struct ctm_controller *ctrl)
{
    struct ctm_page_state *victim = NULL, *page;
    struct list_head *pos;
    unsigned int best_score = UINT_MAX;
    unsigned int sample_count = 0;
    unsigned int sample_target = ctrl->config.victim_sample_size;
    u64 time_range, min_time = ULLONG_MAX, max_time = 0;

    /* Find time range in CXL tier */
    list_for_each(pos, &ctrl->cxl_lru) {
        page = list_entry(pos, struct ctm_page_state, lru_list);
        if (page->last_access_time < min_time)
            min_time = page->last_access_time;
        if (page->last_access_time > max_time)
            max_time = page->last_access_time;
    }
    time_range = max_time - min_time;
    if (!time_range)
        time_range = 1;

    list_for_each(pos, &ctrl->cxl_lru) {
        unsigned int score;

        page = list_entry(pos, struct ctm_page_state, lru_list);

        if (sample_count >= sample_target && get_random_u32() % 4 != 0)
            continue;

        sample_count++;

        score = ctm_score_page(ctrl, page, min_time, time_range);

        if (score < best_score) {
            best_score = score;
            victim = page;
        }
    }

    return victim;
}

static struct ctm_page_state *ctm_select_victim_lru(struct ctm_controller *ctrl)
{
    if (list_empty(&ctrl->tier0_lru))
        return NULL;

    return list_first_entry(&ctrl->tier0_lru, struct ctm_page_state, lru_list);
}

unsigned long ctm_select_victim(struct ctm_controller *ctrl)
{
    struct ctm_page_state *victim;
    unsigned long flags;

    spin_lock_irqsave(&ctrl->lock, flags);

    if (list_empty(&ctrl->tier0_lru)) {
        spin_unlock_irqrestore(&ctrl->lock, flags);
        return ULONG_MAX;  /* No victim available */
    }

    if (ctrl->config.enable_smart_victim)
        victim = ctm_select_victim_smart(ctrl);
    else
        victim = ctm_select_victim_lru(ctrl);

    spin_unlock_irqrestore(&ctrl->lock, flags);

    return victim ? victim->pfn : ULONG_MAX;
}
EXPORT_SYMBOL_GPL(ctm_select_victim);

/* ========== Main Access Handler ========== */

/**
 * ctm_demote_tier0_victim - Demote a tier0 page to CXL or tier1.
 *
 * When CXL tier is enabled: tier0 -> CXL (warm tier)
 * When CXL tier is full or disabled: tier0 -> tier1
 *
 * This implements the 3-tier demotion path matching the CUDA
 * IntegratedController logic.
 */
static void ctm_demote_tier0_victim(struct ctm_controller *ctrl,
                                    struct ctm_page_state *victim)
{
    victim->flags &= ~CTM_PAGE_IN_TIER0;

    if (ctrl->config.enable_cxl_tier &&
        ctrl->cxl_size < ctrl->cxl_capacity) {
        /* Demote to CXL warm tier */
        victim->flags |= CTM_PAGE_IN_CXL;
        list_move_tail(&victim->lru_list, &ctrl->cxl_lru);
        ctrl->tier0_size--;
        ctrl->cxl_size++;
        atomic64_inc(&ctrl->stats.cxl_demotions);
    } else if (ctrl->config.enable_cxl_tier &&
               ctrl->cxl_size >= ctrl->cxl_capacity) {
        /* CXL full — evict from CXL to tier1 first, then demote to CXL */
        struct ctm_page_state *cxl_victim = ctm_select_cxl_victim_smart(ctrl);
        if (cxl_victim) {
            cxl_victim->flags &= ~CTM_PAGE_IN_CXL;
            cxl_victim->flags |= CTM_PAGE_IN_TIER1;
            list_move_tail(&cxl_victim->lru_list, &ctrl->tier1_lru);
            ctrl->cxl_size--;
            ctrl->tier1_size++;
            atomic64_inc(&ctrl->stats.demotions);
        }
        victim->flags |= CTM_PAGE_IN_CXL;
        list_move_tail(&victim->lru_list, &ctrl->cxl_lru);
        ctrl->tier0_size--;
        ctrl->cxl_size++;
        atomic64_inc(&ctrl->stats.cxl_demotions);
    } else {
        /* No CXL — demote directly to tier1 */
        victim->flags |= CTM_PAGE_IN_TIER1;
        list_move_tail(&victim->lru_list, &ctrl->tier1_lru);
        ctrl->tier0_size--;
        ctrl->tier1_size++;
        atomic64_inc(&ctrl->stats.demotions);
    }

    ctm_shadow_record(ctrl, victim->pfn, true);
}

int ctm_on_access(struct ctm_controller *ctrl, unsigned long pfn,
                  bool is_write, bool *promoted, bool *demoted)
{
    struct ctm_page_state *page;
    unsigned long flags;
    bool in_tier0, in_cxl, in_tier1;
    int ret = 0;

    *promoted = false;
    *demoted = false;

    spin_lock_irqsave(&ctrl->lock, flags);

    ctrl->access_counter++;

    /* Track neighbors and transitions */
    ctm_neighbor_record(ctrl, pfn);
    ctm_transition_record(ctrl, pfn);

    /* Find or create page state */
    page = ctm_find_page(ctrl, pfn);
    if (!page) {
        page = ctm_alloc_page(ctrl, pfn);
        if (!page) {
            ret = -ENOMEM;
            goto out;
        }
    }

    /* Update page state */
    page->access_count++;
    page->last_access_time = ctrl->access_counter;

    in_tier0 = page->flags & CTM_PAGE_IN_TIER0;
    in_cxl   = page->flags & CTM_PAGE_IN_CXL;
    in_tier1 = page->flags & CTM_PAGE_IN_TIER1;

    if (in_tier0) {
        /* Case 1: Hit in Tier 0 (fastest) - update LRU */
        atomic64_inc(&ctrl->stats.tier0_hits);
        list_move_tail(&page->lru_list, &ctrl->tier0_lru);

    } else if (in_cxl) {
        /* Case 2: Hit in CXL warm tier - consider promotion to tier0 */
        unsigned int reuse_score, combined_score;
        bool should_promote = false;

        atomic64_inc(&ctrl->stats.cxl_hits);

        reuse_score = ctm_get_reuse_score(ctrl, pfn);
        combined_score = FP_MUL(50, reuse_score) +
                         FP_MUL(30, page->coherence) +
                         FP_MUL(20, (unsigned int)min(page->access_count, 10u) * 10);

        should_promote = combined_score > ctrl->config.cxl_promotion_threshold ||
                         page->access_count > 3;

        if (should_promote) {
            if (ctrl->tier0_size < ctrl->tier0_capacity) {
                /* Promote CXL -> tier0 */
                page->flags &= ~CTM_PAGE_IN_CXL;
                page->flags |= CTM_PAGE_IN_TIER0;
                list_move_tail(&page->lru_list, &ctrl->tier0_lru);
                ctrl->cxl_size--;
                ctrl->tier0_size++;
                atomic64_inc(&ctrl->stats.cxl_promotions);
                *promoted = true;
            } else {
                /* tier0 full — evict victim, then promote */
                struct ctm_page_state *victim;

                victim = ctrl->config.enable_smart_victim ?
                    ctm_select_victim_smart(ctrl) :
                    ctm_select_victim_lru(ctrl);

                if (victim) {
                    ctm_demote_tier0_victim(ctrl, victim);
                    *demoted = true;

                    page->flags &= ~CTM_PAGE_IN_CXL;
                    page->flags |= CTM_PAGE_IN_TIER0;
                    list_move_tail(&page->lru_list, &ctrl->tier0_lru);
                    ctrl->cxl_size--;
                    ctrl->tier0_size++;
                    atomic64_inc(&ctrl->stats.cxl_promotions);
                    *promoted = true;
                }
            }
        } else {
            /* Just update LRU in CXL tier */
            list_move_tail(&page->lru_list, &ctrl->cxl_lru);
        }

    } else if (in_tier1) {
        /* Case 3: Hit in Tier 1 - consider promotion */
        unsigned int reuse_score, neighbor_hot, combined_score;
        bool should_promote = false;

        atomic64_inc(&ctrl->stats.tier1_hits);

        reuse_score = ctm_get_reuse_score(ctrl, pfn);
        neighbor_hot = ctm_get_neighbor_hotness(ctrl, pfn);

        /* Loop pinning: fast-track if reuse and neighbors are hot */
        if (reuse_score > ctrl->config.loop_pin_reuse_thresh &&
            neighbor_hot > ctrl->config.loop_pin_neighbor_thresh) {
            should_promote = true;
        } else {
            combined_score = FP_MUL(50, reuse_score) +
                            FP_MUL(30, page->coherence) +
                            FP_MUL(20, neighbor_hot);
            should_promote = combined_score > ctrl->config.promotion_threshold;
        }

        if (should_promote) {
            /*
             * With CXL enabled: promote tier1 -> CXL (not directly to tier0)
             * Without CXL: promote tier1 -> tier0 (original behavior)
             */
            if (ctrl->config.enable_cxl_tier) {
                /* Promote to CXL warm tier */
                if (ctrl->cxl_size < ctrl->cxl_capacity) {
                    page->flags &= ~CTM_PAGE_IN_TIER1;
                    page->flags |= CTM_PAGE_IN_CXL;
                    list_move_tail(&page->lru_list, &ctrl->cxl_lru);
                    ctrl->tier1_size--;
                    ctrl->cxl_size++;
                    atomic64_inc(&ctrl->stats.promotions);
                    *promoted = true;
                } else {
                    /* CXL full — evict CXL victim to tier1, promote to CXL */
                    struct ctm_page_state *cxl_victim;
                    cxl_victim = ctm_select_cxl_victim_smart(ctrl);
                    if (cxl_victim) {
                        cxl_victim->flags &= ~CTM_PAGE_IN_CXL;
                        cxl_victim->flags |= CTM_PAGE_IN_TIER1;
                        list_move_tail(&cxl_victim->lru_list, &ctrl->tier1_lru);
                        ctrl->cxl_size--;
                        ctrl->tier1_size++;
                    }
                    page->flags &= ~CTM_PAGE_IN_TIER1;
                    page->flags |= CTM_PAGE_IN_CXL;
                    list_move_tail(&page->lru_list, &ctrl->cxl_lru);
                    ctrl->tier1_size--;
                    ctrl->cxl_size++;
                    atomic64_inc(&ctrl->stats.promotions);
                    *promoted = true;
                }
            } else if (ctrl->tier0_size < ctrl->tier0_capacity) {
                /* No CXL — promote directly to tier0 */
                page->flags &= ~CTM_PAGE_IN_TIER1;
                page->flags |= CTM_PAGE_IN_TIER0;
                list_move_tail(&page->lru_list, &ctrl->tier0_lru);
                ctrl->tier0_size++;
                ctrl->tier1_size--;
                atomic64_inc(&ctrl->stats.promotions);
                *promoted = true;
            } else {
                /* tier0 full — evict and promote */
                struct ctm_page_state *victim;
                victim = ctrl->config.enable_smart_victim ?
                    ctm_select_victim_smart(ctrl) :
                    ctm_select_victim_lru(ctrl);

                if (victim) {
                    ctm_demote_tier0_victim(ctrl, victim);
                    *demoted = true;

                    page->flags &= ~CTM_PAGE_IN_TIER1;
                    page->flags |= CTM_PAGE_IN_TIER0;
                    list_move_tail(&page->lru_list, &ctrl->tier0_lru);
                    ctrl->tier0_size++;
                    ctrl->tier1_size--;
                    atomic64_inc(&ctrl->stats.promotions);
                    *promoted = true;
                }
            }
        } else {
            /* Just update LRU in tier1 */
            list_move_tail(&page->lru_list, &ctrl->tier1_lru);
        }

    } else {
        /* Case 4: Miss - check shadow tiers and admit */
        bool was_in_b1 = false;

        atomic64_inc(&ctrl->stats.misses);

        if (ctm_shadow_check(ctrl, pfn, &was_in_b1)) {
            ctm_update_adaptive_p(ctrl, was_in_b1);
        }

        /* Admit to tier0 if space available */
        if (ctrl->tier0_size < ctrl->tier0_capacity) {
            page->flags |= CTM_PAGE_IN_TIER0;
            list_add_tail(&page->lru_list, &ctrl->tier0_lru);
            ctrl->tier0_size++;
            *promoted = true;
        } else {
            /* Evict from tier0 and admit */
            struct ctm_page_state *victim;
            victim = ctrl->config.enable_smart_victim ?
                ctm_select_victim_smart(ctrl) :
                ctm_select_victim_lru(ctrl);

            if (victim) {
                ctm_demote_tier0_victim(ctrl, victim);
                *demoted = true;
            }

            page->flags |= CTM_PAGE_IN_TIER0;
            list_add_tail(&page->lru_list, &ctrl->tier0_lru);
            ctrl->tier0_size++;
            *promoted = true;
        }
    }

out:
    spin_unlock_irqrestore(&ctrl->lock, flags);
    return ret;
}
EXPORT_SYMBOL_GPL(ctm_on_access);

/* ========== Initialization ========== */

int ctm_init(struct ctm_controller *ctrl, unsigned int tier0_cap,
             unsigned int tier1_cap)
{
    memset(ctrl, 0, sizeof(*ctrl));

    spin_lock_init(&ctrl->lock);
    ctrl->page_tree = RB_ROOT;
    INIT_LIST_HEAD(&ctrl->tier0_lru);
    INIT_LIST_HEAD(&ctrl->cxl_lru);
    INIT_LIST_HEAD(&ctrl->tier1_lru);
    INIT_LIST_HEAD(&ctrl->shadow_b1);
    INIT_LIST_HEAD(&ctrl->shadow_b2);

    ctrl->tier0_capacity = tier0_cap;
    ctrl->tier1_capacity = tier1_cap;
    ctrl->cxl_capacity = 0;  /* Disabled by default */
    ctrl->adaptive_p = 50;   /* Start balanced */

    /* Default configuration */
    ctrl->config.victim_sample_size = CTM_VICTIM_SAMPLE_SIZE;
    ctrl->config.promotion_threshold = CTM_PROMOTION_THRESHOLD;
    ctrl->config.loop_pin_reuse_thresh = CTM_LOOP_PIN_REUSE_THRESH;
    ctrl->config.loop_pin_neighbor_thresh = CTM_LOOP_PIN_NEIGHBOR_THRESH;
    ctrl->config.enable_smart_victim = true;
    ctrl->config.enable_cxl_tier = false;
    ctrl->config.enable_compression_hints = false;
    ctrl->config.weight_compression_quality = 5; /* 5% weight */
    ctrl->config.cxl_promotion_threshold = 40;   /* 0.40 scaled */

    return 0;
}
EXPORT_SYMBOL_GPL(ctm_init);

void ctm_destroy(struct ctm_controller *ctrl)
{
    struct ctm_page_state *page, *tmp_page;
    struct ctm_shadow_entry *shadow, *tmp_shadow;
    struct rb_node *node;
    unsigned long flags;

    spin_lock_irqsave(&ctrl->lock, flags);

    /* Free all pages */
    for (node = rb_first(&ctrl->page_tree); node; ) {
        page = rb_entry(node, struct ctm_page_state, node);
        node = rb_next(node);
        rb_erase(&page->node, &ctrl->page_tree);
        kfree(page);
    }

    /* Free shadow entries */
    list_for_each_entry_safe(shadow, tmp_shadow, &ctrl->shadow_b1, list) {
        list_del(&shadow->list);
        kfree(shadow);
    }
    list_for_each_entry_safe(shadow, tmp_shadow, &ctrl->shadow_b2, list) {
        list_del(&shadow->list);
        kfree(shadow);
    }

    spin_unlock_irqrestore(&ctrl->lock, flags);
}
EXPORT_SYMBOL_GPL(ctm_destroy);

/* ========== Configuration & Stats ========== */

void ctm_set_config(struct ctm_controller *ctrl, struct ctm_config *config)
{
    unsigned long flags;

    spin_lock_irqsave(&ctrl->lock, flags);
    memcpy(&ctrl->config, config, sizeof(*config));
    spin_unlock_irqrestore(&ctrl->lock, flags);
}
EXPORT_SYMBOL_GPL(ctm_set_config);

void ctm_get_config(struct ctm_controller *ctrl, struct ctm_config *config)
{
    unsigned long flags;

    spin_lock_irqsave(&ctrl->lock, flags);
    memcpy(config, &ctrl->config, sizeof(*config));
    spin_unlock_irqrestore(&ctrl->lock, flags);
}
EXPORT_SYMBOL_GPL(ctm_get_config);

void ctm_get_stats(struct ctm_controller *ctrl, struct ctm_stats *stats)
{
    stats->promotions = atomic64_read(&ctrl->stats.promotions);
    stats->demotions = atomic64_read(&ctrl->stats.demotions);
    stats->tier0_hits = atomic64_read(&ctrl->stats.tier0_hits);
    stats->cxl_hits = atomic64_read(&ctrl->stats.cxl_hits);
    stats->tier1_hits = atomic64_read(&ctrl->stats.tier1_hits);
    stats->misses = atomic64_read(&ctrl->stats.misses);
    stats->smart_victim_selections = atomic64_read(&ctrl->stats.smart_victim_selections);
    stats->cxl_promotions = atomic64_read(&ctrl->stats.cxl_promotions);
    stats->cxl_demotions = atomic64_read(&ctrl->stats.cxl_demotions);
    stats->compression_hint_updates = atomic64_read(&ctrl->stats.compression_hint_updates);
}
EXPORT_SYMBOL_GPL(ctm_get_stats);

void ctm_reset_stats(struct ctm_controller *ctrl)
{
    atomic64_set(&ctrl->stats.promotions, 0);
    atomic64_set(&ctrl->stats.demotions, 0);
    atomic64_set(&ctrl->stats.tier0_hits, 0);
    atomic64_set(&ctrl->stats.cxl_hits, 0);
    atomic64_set(&ctrl->stats.tier1_hits, 0);
    atomic64_set(&ctrl->stats.misses, 0);
    atomic64_set(&ctrl->stats.smart_victim_selections, 0);
    atomic64_set(&ctrl->stats.cxl_promotions, 0);
    atomic64_set(&ctrl->stats.cxl_demotions, 0);
    atomic64_set(&ctrl->stats.compression_hint_updates, 0);
}
EXPORT_SYMBOL_GPL(ctm_reset_stats);

bool ctm_is_in_tier0(struct ctm_controller *ctrl, unsigned long pfn)
{
    struct ctm_page_state *page;
    unsigned long flags;
    bool result = false;

    spin_lock_irqsave(&ctrl->lock, flags);
    page = ctm_find_page(ctrl, pfn);
    if (page)
        result = !!(page->flags & CTM_PAGE_IN_TIER0);
    spin_unlock_irqrestore(&ctrl->lock, flags);

    return result;
}
EXPORT_SYMBOL_GPL(ctm_is_in_tier0);

int ctm_get_tier(struct ctm_controller *ctrl, unsigned long pfn)
{
    struct ctm_page_state *page;
    unsigned long flags;
    int tier = -1;

    spin_lock_irqsave(&ctrl->lock, flags);
    page = ctm_find_page(ctrl, pfn);
    if (page) {
        if (page->flags & CTM_PAGE_IN_TIER0)
            tier = 0;
        else if (page->flags & CTM_PAGE_IN_CXL)
            tier = 1;  /* CXL is the warm tier between 0 and 2 */
        else if (page->flags & CTM_PAGE_IN_TIER1)
            tier = 2;
    }
    spin_unlock_irqrestore(&ctrl->lock, flags);

    return tier;
}
EXPORT_SYMBOL_GPL(ctm_get_tier);

unsigned int ctm_get_cxl_size(struct ctm_controller *ctrl)
{
    unsigned long flags;
    unsigned int size;

    spin_lock_irqsave(&ctrl->lock, flags);
    size = ctrl->cxl_size;
    spin_unlock_irqrestore(&ctrl->lock, flags);

    return size;
}
EXPORT_SYMBOL_GPL(ctm_get_cxl_size);

/**
 * ctm_set_compression_hint - Set GPU compression quality hint for a page.
 *
 * Called by the GPU driver or userspace (via sysfs) to inform the kernel
 * about how well the data on a physical page compressed under TurboQuant.
 *
 * Pages with low quality (poor compression) are more valuable to keep in
 * fast memory — the quality-aware victim scoring gives them a boost.
 *
 * @ctrl: CTM+ controller
 * @pfn: Page frame number
 * @quality: Compression quality 0-100 (cosine_similarity * 100)
 * @bits: TurboQuant bit-width (2/3/4, or 0 for uncompressed)
 */
int ctm_set_compression_hint(struct ctm_controller *ctrl, unsigned long pfn,
                             unsigned int quality, u8 bits)
{
    struct ctm_page_state *page;
    unsigned long flags;

    if (quality > 100)
        return -EINVAL;
    if (bits != 0 && bits != 2 && bits != 3 && bits != 4)
        return -EINVAL;

    spin_lock_irqsave(&ctrl->lock, flags);

    page = ctm_find_page(ctrl, pfn);
    if (!page) {
        spin_unlock_irqrestore(&ctrl->lock, flags);
        return -ENOENT;
    }

    page->compression_quality = quality;
    page->compression_bits = bits;

    if (bits > 0)
        page->flags |= CTM_PAGE_GPU_COMPRESSED;
    else
        page->flags &= ~CTM_PAGE_GPU_COMPRESSED;

    atomic64_inc(&ctrl->stats.compression_hint_updates);

    spin_unlock_irqrestore(&ctrl->lock, flags);
    return 0;
}
EXPORT_SYMBOL_GPL(ctm_set_compression_hint);
