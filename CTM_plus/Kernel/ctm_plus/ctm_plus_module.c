// SPDX-License-Identifier: GPL-2.0
/*
 * CTM+ Kernel Module
 *
 * Provides a loadable kernel module interface for the CTM+ memory
 * tiering controller. Exposes configuration via sysfs and integrates
 * with the Linux memory management subsystem.
 *
 * Usage:
 *   insmod ctm_plus.ko tier0_pages=1000 tier1_pages=100000
 *
 * sysfs interface:
 *   /sys/kernel/ctm_plus/stats
 *   /sys/kernel/ctm_plus/config/*
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/sysfs.h>
#include <linux/kobject.h>
#include <linux/mm.h>
#include <linux/mmu_notifier.h>
#include "ctm_plus.h"

#define CTM_VERSION "1.0.0"

/* Module parameters */
static unsigned int tier0_pages = 1000;
module_param(tier0_pages, uint, 0444);
MODULE_PARM_DESC(tier0_pages, "Number of pages in fast tier (default: 1000)");

static unsigned int tier1_pages = 100000;
module_param(tier1_pages, uint, 0444);
MODULE_PARM_DESC(tier1_pages, "Number of pages in slow tier (default: 100000)");

static bool smart_victim = true;
module_param(smart_victim, bool, 0644);
MODULE_PARM_DESC(smart_victim, "Enable smart victim selection (default: true)");

/* Global controller instance */
static struct ctm_controller *ctm_ctrl;
static struct kobject *ctm_kobj;

/* ========== sysfs Interface ========== */

static ssize_t stats_show(struct kobject *kobj, struct kobj_attribute *attr,
                          char *buf)
{
    struct ctm_stats stats;
    u64 total_accesses, hit_rate;

    ctm_get_stats(ctm_ctrl, &stats);

    total_accesses = stats.tier0_hits + stats.tier1_hits + stats.misses;
    hit_rate = total_accesses ?
               div64_u64((stats.tier0_hits + stats.tier1_hits) * 10000,
                         total_accesses) : 0;

    return sysfs_emit(buf,
        "version: %s\n"
        "tier0_hits: %llu\n"
        "tier1_hits: %llu\n"
        "misses: %llu\n"
        "hit_rate: %llu.%02llu%%\n"
        "promotions: %llu\n"
        "demotions: %llu\n"
        "smart_selections: %llu\n"
        "tier0_size: %u/%u\n"
        "tier1_size: %u/%u\n"
        "adaptive_p: %u\n",
        CTM_VERSION,
        stats.tier0_hits,
        stats.tier1_hits,
        stats.misses,
        hit_rate / 100, hit_rate % 100,
        stats.promotions,
        stats.demotions,
        stats.smart_victim_selections,
        ctm_ctrl->tier0_size, ctm_ctrl->tier0_capacity,
        ctm_ctrl->tier1_size, ctm_ctrl->tier1_capacity,
        ctm_ctrl->adaptive_p);
}

static ssize_t stats_store(struct kobject *kobj, struct kobj_attribute *attr,
                           const char *buf, size_t count)
{
    if (sysfs_streq(buf, "reset"))
        ctm_reset_stats(ctm_ctrl);
    return count;
}

static ssize_t victim_sample_size_show(struct kobject *kobj,
                                       struct kobj_attribute *attr, char *buf)
{
    return sysfs_emit(buf, "%u\n", ctm_ctrl->config.victim_sample_size);
}

static ssize_t victim_sample_size_store(struct kobject *kobj,
                                        struct kobj_attribute *attr,
                                        const char *buf, size_t count)
{
    unsigned int val;
    if (kstrtouint(buf, 10, &val) < 0)
        return -EINVAL;
    if (val < 8 || val > 256)
        return -EINVAL;
    ctm_ctrl->config.victim_sample_size = val;
    return count;
}

static ssize_t promotion_threshold_show(struct kobject *kobj,
                                        struct kobj_attribute *attr, char *buf)
{
    return sysfs_emit(buf, "%u\n", ctm_ctrl->config.promotion_threshold);
}

static ssize_t promotion_threshold_store(struct kobject *kobj,
                                         struct kobj_attribute *attr,
                                         const char *buf, size_t count)
{
    unsigned int val;
    if (kstrtouint(buf, 10, &val) < 0)
        return -EINVAL;
    if (val > 100)
        return -EINVAL;
    ctm_ctrl->config.promotion_threshold = val;
    return count;
}

static ssize_t smart_victim_show(struct kobject *kobj,
                                 struct kobj_attribute *attr, char *buf)
{
    return sysfs_emit(buf, "%d\n", ctm_ctrl->config.enable_smart_victim);
}

static ssize_t smart_victim_store(struct kobject *kobj,
                                  struct kobj_attribute *attr,
                                  const char *buf, size_t count)
{
    bool val;
    if (kstrtobool(buf, &val) < 0)
        return -EINVAL;
    ctm_ctrl->config.enable_smart_victim = val;
    return count;
}

static struct kobj_attribute stats_attr = __ATTR_RW(stats);
static struct kobj_attribute victim_sample_size_attr = __ATTR_RW(victim_sample_size);
static struct kobj_attribute promotion_threshold_attr = __ATTR_RW(promotion_threshold);
static struct kobj_attribute smart_victim_attr = __ATTR_RW(smart_victim);

static struct attribute *ctm_attrs[] = {
    &stats_attr.attr,
    &victim_sample_size_attr.attr,
    &promotion_threshold_attr.attr,
    &smart_victim_attr.attr,
    NULL,
};

struct attribute_group ctm_attr_group = {
    .attrs = ctm_attrs,
};
EXPORT_SYMBOL_GPL(ctm_attr_group);

/* ========== Memory Management Hooks ========== */

/*
 * These hooks can be connected to:
 * - DAMON (Data Access MONitor) for access pattern tracking
 * - Memory tiering subsystem for CXL/NUMA tiering
 * - Page migration hooks for actual data movement
 */

#ifdef CONFIG_DAMON
/*
 * DAMON integration callback - called when DAMON detects access patterns
 */
static int ctm_damon_callback(struct damon_ctx *ctx)
{
    /* TODO: Integrate with DAMON for access monitoring */
    return 0;
}
#endif

#ifdef CONFIG_NUMA_BALANCING
/*
 * NUMA balancing integration - use CTM+ for placement decisions
 */
static bool ctm_should_migrate(struct page *page, int target_nid)
{
    unsigned long pfn = page_to_pfn(page);
    return ctm_is_in_tier0(ctm_ctrl, pfn);
}
#endif

/* ========== Module Init/Exit ========== */

static int __init ctm_plus_init(void)
{
    int ret;

    pr_info("CTM+ v%s: Initializing memory tiering controller\n", CTM_VERSION);
    pr_info("CTM+: tier0=%u pages, tier1=%u pages, smart_victim=%d\n",
            tier0_pages, tier1_pages, smart_victim);

    /* Allocate controller */
    ctm_ctrl = kzalloc(sizeof(*ctm_ctrl), GFP_KERNEL);
    if (!ctm_ctrl)
        return -ENOMEM;

    /* Initialize controller */
    ret = ctm_init(ctm_ctrl, tier0_pages, tier1_pages);
    if (ret) {
        pr_err("CTM+: Failed to initialize controller\n");
        kfree(ctm_ctrl);
        return ret;
    }

    ctm_ctrl->config.enable_smart_victim = smart_victim;

    /* Create sysfs interface */
    ctm_kobj = kobject_create_and_add("ctm_plus", kernel_kobj);
    if (!ctm_kobj) {
        pr_err("CTM+: Failed to create sysfs kobject\n");
        ctm_destroy(ctm_ctrl);
        kfree(ctm_ctrl);
        return -ENOMEM;
    }

    ret = sysfs_create_group(ctm_kobj, &ctm_attr_group);
    if (ret) {
        pr_err("CTM+: Failed to create sysfs group\n");
        kobject_put(ctm_kobj);
        ctm_destroy(ctm_ctrl);
        kfree(ctm_ctrl);
        return ret;
    }

    pr_info("CTM+: Module loaded successfully\n");
    pr_info("CTM+: sysfs interface at /sys/kernel/ctm_plus/\n");

    return 0;
}

static void __exit ctm_plus_exit(void)
{
    struct ctm_stats stats;

    ctm_get_stats(ctm_ctrl, &stats);

    pr_info("CTM+: Unloading module\n");
    pr_info("CTM+: Final stats - promotions=%llu, demotions=%llu, "
            "tier0_hits=%llu, tier1_hits=%llu, misses=%llu\n",
            stats.promotions, stats.demotions,
            stats.tier0_hits, stats.tier1_hits, stats.misses);

    sysfs_remove_group(ctm_kobj, &ctm_attr_group);
    kobject_put(ctm_kobj);
    ctm_destroy(ctm_ctrl);
    kfree(ctm_ctrl);

    pr_info("CTM+: Module unloaded\n");
}

module_init(ctm_plus_init);
module_exit(ctm_plus_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("CTM+ Team");
MODULE_DESCRIPTION("CTM+ Memory Tiering Controller");
MODULE_VERSION(CTM_VERSION);
