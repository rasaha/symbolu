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

    /* Higher access count = higher reuse probability */
    return min(page->access_count * 10, 100u);
}

/* ========== Victim Selection ========== */

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
        unsigned int score, recency_rank, frequency, reuse, coherence, neighbor_hot;

        page = list_entry(pos, struct ctm_page_state, lru_list);

        /* Random sampling (simplified) */
        if (sample_count >= sample_target && get_random_u32() % 4 != 0)
            continue;

        sample_count++;

        /* Calculate scores (all in fixed-point * 100) */
        recency_rank = div64_u64((page->last_access_time - min_time) * FP_SCALE,
                                 time_range);
        frequency = min(page->access_count * 10, 100u);
        reuse = ctm_get_reuse_score(ctrl, page->pfn);
        coherence = page->coherence;
        neighbor_hot = ctm_get_neighbor_hotness(ctrl, page->pfn);

        /* Weighted score (lower = evict first)
         * 40% recency + 30% frequency + 15% reuse + 10% coherence - 10% neighbor
         */
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

        if (score < best_score) {
            best_score = score;
            victim = page;
        }
    }

    if (victim)
        atomic64_inc(&ctrl->stats.smart_victim_selections);

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

int ctm_on_access(struct ctm_controller *ctrl, unsigned long pfn,
                  bool is_write, bool *promoted, bool *demoted)
{
    struct ctm_page_state *page;
    unsigned long flags;
    bool in_tier0, in_tier1;
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
    in_tier1 = page->flags & CTM_PAGE_IN_TIER1;

    if (in_tier0) {
        /* Case 1: Hit in Tier 0 - just update LRU */
        atomic64_inc(&ctrl->stats.tier0_hits);
        list_move_tail(&page->lru_list, &ctrl->tier0_lru);

    } else if (in_tier1) {
        /* Case 2: Hit in Tier 1 - consider promotion */
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
            /* Calculate combined score */
            combined_score = FP_MUL(50, reuse_score) +
                            FP_MUL(30, page->coherence) +
                            FP_MUL(20, neighbor_hot);
            should_promote = combined_score > ctrl->config.promotion_threshold;
        }

        if (should_promote && ctrl->tier0_size < ctrl->tier0_capacity) {
            /* Promote to tier0 */
            page->flags &= ~CTM_PAGE_IN_TIER1;
            page->flags |= CTM_PAGE_IN_TIER0;
            list_move_tail(&page->lru_list, &ctrl->tier0_lru);
            ctrl->tier0_size++;
            ctrl->tier1_size--;
            atomic64_inc(&ctrl->stats.promotions);
            *promoted = true;
        } else if (should_promote && ctrl->tier0_size >= ctrl->tier0_capacity) {
            /* Need to evict from tier0 first */
            struct ctm_page_state *victim = ctrl->config.enable_smart_victim ?
                ctm_select_victim_smart(ctrl) : ctm_select_victim_lru(ctrl);

            if (victim) {
                /* Demote victim to tier1 */
                victim->flags &= ~CTM_PAGE_IN_TIER0;
                victim->flags |= CTM_PAGE_IN_TIER1;
                list_move_tail(&victim->lru_list, &ctrl->tier1_lru);
                ctm_shadow_record(ctrl, victim->pfn, true);
                atomic64_inc(&ctrl->stats.demotions);
                *demoted = true;

                /* Now promote the accessed page */
                page->flags &= ~CTM_PAGE_IN_TIER1;
                page->flags |= CTM_PAGE_IN_TIER0;
                list_move_tail(&page->lru_list, &ctrl->tier0_lru);
                atomic64_inc(&ctrl->stats.promotions);
                *promoted = true;
            }
        } else {
            /* Just update LRU in tier1 */
            list_move_tail(&page->lru_list, &ctrl->tier1_lru);
        }

    } else {
        /* Case 3: Miss - check shadow tiers and admit */
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
            struct ctm_page_state *victim = ctrl->config.enable_smart_victim ?
                ctm_select_victim_smart(ctrl) : ctm_select_victim_lru(ctrl);

            if (victim) {
                victim->flags &= ~CTM_PAGE_IN_TIER0;
                victim->flags |= CTM_PAGE_IN_TIER1;
                list_move_tail(&victim->lru_list, &ctrl->tier1_lru);
                ctrl->tier1_size++;
                ctm_shadow_record(ctrl, victim->pfn, true);
                atomic64_inc(&ctrl->stats.demotions);
                *demoted = true;
            }

            page->flags |= CTM_PAGE_IN_TIER0;
            list_add_tail(&page->lru_list, &ctrl->tier0_lru);
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
    INIT_LIST_HEAD(&ctrl->tier1_lru);
    INIT_LIST_HEAD(&ctrl->shadow_b1);
    INIT_LIST_HEAD(&ctrl->shadow_b2);

    ctrl->tier0_capacity = tier0_cap;
    ctrl->tier1_capacity = tier1_cap;
    ctrl->adaptive_p = 50;  /* Start balanced */

    /* Default configuration */
    ctrl->config.victim_sample_size = CTM_VICTIM_SAMPLE_SIZE;
    ctrl->config.promotion_threshold = CTM_PROMOTION_THRESHOLD;
    ctrl->config.loop_pin_reuse_thresh = CTM_LOOP_PIN_REUSE_THRESH;
    ctrl->config.loop_pin_neighbor_thresh = CTM_LOOP_PIN_NEIGHBOR_THRESH;
    ctrl->config.enable_smart_victim = true;

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
    stats->tier1_hits = atomic64_read(&ctrl->stats.tier1_hits);
    stats->misses = atomic64_read(&ctrl->stats.misses);
    stats->smart_victim_selections = atomic64_read(&ctrl->stats.smart_victim_selections);
}
EXPORT_SYMBOL_GPL(ctm_get_stats);

void ctm_reset_stats(struct ctm_controller *ctrl)
{
    atomic64_set(&ctrl->stats.promotions, 0);
    atomic64_set(&ctrl->stats.demotions, 0);
    atomic64_set(&ctrl->stats.tier0_hits, 0);
    atomic64_set(&ctrl->stats.tier1_hits, 0);
    atomic64_set(&ctrl->stats.misses, 0);
    atomic64_set(&ctrl->stats.smart_victim_selections, 0);
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
        else if (page->flags & CTM_PAGE_IN_TIER1)
            tier = 1;
    }
    spin_unlock_irqrestore(&ctrl->lock, flags);

    return tier;
}
EXPORT_SYMBOL_GPL(ctm_get_tier);
