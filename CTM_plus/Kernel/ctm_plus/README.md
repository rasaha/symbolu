# CTM+ Kernel Module

A Linux kernel module implementing the CTM+ (Coherence-Tier Memory Plus) memory tiering controller.

## Overview

CTM+ provides intelligent page placement between fast (Tier 0) and slow (Tier 1) memory tiers, optimizing for various workload patterns including:

- **Zipfian** (database-like): Frequent access to hot pages
- **Temporal** (LLM/streaming): Recent pages likely to be reaccessed
- **Hotspot** (batch processing): 80/20 access distribution

## Building

### Prerequisites

```bash
# Ubuntu/Debian
sudo apt install build-essential linux-headers-$(uname -r)

# RHEL/CentOS
sudo yum install kernel-devel kernel-headers
```

### Compile

```bash
cd kernel/ctm_plus
make
```

### Install

```bash
sudo make install
sudo depmod -a
```

## Usage

### Load Module

```bash
# Default configuration
sudo modprobe ctm_plus

# Custom tier sizes
sudo modprobe ctm_plus tier0_pages=2000 tier1_pages=200000

# Disable smart victim selection (use LRU)
sudo modprobe ctm_plus smart_victim=0
```

### Module Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `tier0_pages` | 1000 | Pages in fast tier (HBM/DRAM) |
| `tier1_pages` | 100000 | Pages in slow tier (DDR/NVMe) |
| `smart_victim` | true | Enable smart victim selection |

### sysfs Interface

```bash
# View statistics
cat /sys/kernel/ctm_plus/stats

# Reset statistics
echo reset > /sys/kernel/ctm_plus/stats

# Adjust sample size (8-256)
echo 64 > /sys/kernel/ctm_plus/victim_sample_size

# Adjust promotion threshold (0-100, scaled by 100)
echo 40 > /sys/kernel/ctm_plus/promotion_threshold

# Enable/disable smart victim selection
echo 1 > /sys/kernel/ctm_plus/smart_victim
```

### Example Output

```
$ cat /sys/kernel/ctm_plus/stats
version: 1.0.0
tier0_hits: 892341
tier1_hits: 45123
misses: 12456
hit_rate: 98.67%
promotions: 34521
demotions: 33012
smart_selections: 33012
tier0_size: 1000/1000
tier1_size: 45234/100000
adaptive_p: 52
```

### Unload Module

```bash
sudo rmmod ctm_plus
```

## Integration Points

### DAMON (Data Access MONitor)

CTM+ can integrate with DAMON for hardware-accelerated access monitoring:

```bash
# Enable DAMON integration (requires CONFIG_DAMON)
echo 1 > /sys/kernel/mm/damon/admin/kdamonds/0/state
```

### CXL Memory Tiering

For CXL-attached memory, CTM+ can be used with the Linux memory tiering subsystem:

```bash
# Check available memory tiers
cat /sys/devices/system/node/node*/memory_tier
```

### Memory Hotplug

CTM+ supports dynamic tier capacity changes:

```bash
# Tier capacities are fixed at module load time
# To change, unload and reload with new parameters
sudo rmmod ctm_plus
sudo modprobe ctm_plus tier0_pages=2000
```

## Performance Tuning

### For Database Workloads (Zipfian)

```bash
# Higher sample size for better victim selection
echo 64 > /sys/kernel/ctm_plus/victim_sample_size
echo 25 > /sys/kernel/ctm_plus/promotion_threshold
```

### For LLM/Streaming Workloads (Temporal)

```bash
# Lower thresholds for faster promotion
echo 32 > /sys/kernel/ctm_plus/victim_sample_size
echo 20 > /sys/kernel/ctm_plus/promotion_threshold
```

### For Batch Processing (Hotspot)

```bash
# Default settings work well
echo 48 > /sys/kernel/ctm_plus/victim_sample_size
echo 30 > /sys/kernel/ctm_plus/promotion_threshold
```

## Architecture

```
┌─────────────────────────────────────────┐
│           User Space                     │
│  ┌─────────────────────────────────┐    │
│  │  /sys/kernel/ctm_plus/*         │    │
│  └─────────────────────────────────┘    │
└──────────────────┬──────────────────────┘
                   │ sysfs
┌──────────────────┼──────────────────────┐
│                  ▼                       │
│  ┌─────────────────────────────────┐    │
│  │      CTM+ Kernel Module         │    │
│  │  ┌───────────┐ ┌─────────────┐  │    │
│  │  │ Victim    │ │ Shadow Tier │  │    │
│  │  │ Selection │ │ (B1/B2)     │  │    │
│  │  └───────────┘ └─────────────┘  │    │
│  │  ┌───────────┐ ┌─────────────┐  │    │
│  │  │ Neighbor  │ │ Transition  │  │    │
│  │  │ Tracker   │ │ Tracker     │  │    │
│  │  └───────────┘ └─────────────┘  │    │
│  └─────────────────────────────────┘    │
│                  │                       │
│                  ▼                       │
│  ┌─────────────────────────────────┐    │
│  │   Linux Memory Management       │    │
│  │   (mm/migrate.c, mm/damon/)     │    │
│  └─────────────────────────────────┘    │
│              Kernel Space                │
└─────────────────────────────────────────┘
```

## Files

| File | Description |
|------|-------------|
| `ctm_plus.h` | Header with data structures and API |
| `ctm_plus_core.c` | Core algorithm implementation |
| `ctm_plus_module.c` | Kernel module entry/exit and sysfs |
| `Makefile` | Build system |

## License

GPL-2.0

## References

- [Linux Memory Tiering](https://docs.kernel.org/admin-guide/mm/memory-tiering.html)
- [DAMON Documentation](https://docs.kernel.org/mm/damon/index.html)
- [CXL Memory](https://docs.kernel.org/driver-api/cxl/memory-devices.html)
