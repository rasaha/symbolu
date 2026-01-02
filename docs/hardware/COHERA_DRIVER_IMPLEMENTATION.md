# COHERA Driver Implementation Guide

## Linux Kernel Driver for PA-VPU / UCP

**Version:** 1.0
**Date:** 2024-12-30

---

## 1. Driver Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER SPACE                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ libcohera.so │  │ Python bindings│ │ PyTorch ext │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         └──────────────────┼──────────────────┘                 │
│                            │ ioctl(), mmap()                    │
├────────────────────────────┼────────────────────────────────────┤
│                     KERNEL SPACE                                 │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    cohera.ko                             │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │   │
│  │  │  PCIe    │ │   DMA    │ │Interrupt │ │  Power   │   │   │
│  │  │  Driver  │ │  Engine  │ │ Handler  │ │  Mgmt    │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                     │
├────────────────────────────┼────────────────────────────────────┤
│                     HARDWARE                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    PA-VPU / UCP                          │   │
│  │     BAR0 (Registers)    │     BAR2 (HBM3 Window)        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. PCIe Configuration

### 2.1 Device Identification

```c
#define COHERA_VENDOR_ID     0x1C0D
#define COHERA_PAVPU_ID      0x0001
#define COHERA_UCP_ID        0x0002

static const struct pci_device_id cohera_pci_ids[] = {
    { PCI_DEVICE(COHERA_VENDOR_ID, COHERA_PAVPU_ID) },
    { PCI_DEVICE(COHERA_VENDOR_ID, COHERA_UCP_ID) },
    { 0, }
};
MODULE_DEVICE_TABLE(pci, cohera_pci_ids);
```

### 2.2 BAR Layout

| BAR | Size | Purpose |
|-----|------|---------|
| BAR0 | 64 KB | Control/Status Registers |
| BAR1 | Reserved | - |
| BAR2 | 256 MB | HBM3 Doorbell Window |
| BAR3 | Reserved | - |
| BAR4 | 4 KB | MSI-X Table |

### 2.3 Probe Function

```c
static int cohera_pci_probe(struct pci_dev *pdev,
                            const struct pci_device_id *id)
{
    struct cohera_device *cdev;
    int ret;

    cdev = kzalloc(sizeof(*cdev), GFP_KERNEL);
    if (!cdev)
        return -ENOMEM;

    ret = pci_enable_device(pdev);
    if (ret)
        goto err_free;

    ret = pci_request_regions(pdev, "cohera");
    if (ret)
        goto err_disable;

    /* Map BAR0 for registers */
    cdev->regs = pci_iomap(pdev, 0, 0);
    if (!cdev->regs) {
        ret = -ENOMEM;
        goto err_regions;
    }

    /* Map BAR2 for HBM3 doorbell */
    cdev->hbm_doorbell = pci_iomap(pdev, 2, 0);

    /* Enable bus mastering for DMA */
    pci_set_master(pdev);

    /* Set DMA mask for 64-bit addressing */
    ret = dma_set_mask_and_coherent(&pdev->dev, DMA_BIT_MASK(64));
    if (ret)
        goto err_unmap;

    /* Initialize interrupt handling */
    ret = cohera_init_interrupts(cdev, pdev);
    if (ret)
        goto err_unmap;

    /* Register character device */
    ret = cohera_register_chardev(cdev);
    if (ret)
        goto err_irq;

    pci_set_drvdata(pdev, cdev);

    dev_info(&pdev->dev, "COHERA device initialized\n");
    return 0;

err_irq:
    cohera_free_interrupts(cdev);
err_unmap:
    pci_iounmap(pdev, cdev->regs);
    if (cdev->hbm_doorbell)
        pci_iounmap(pdev, cdev->hbm_doorbell);
err_regions:
    pci_release_regions(pdev);
err_disable:
    pci_disable_device(pdev);
err_free:
    kfree(cdev);
    return ret;
}
```

---

## 3. Register Access

### 3.1 Register Map

```c
/* Global Control Registers */
#define GCR_CTRL           0x0000
#define GCR_STATUS         0x0004
#define GCR_IRQ_EN         0x0008
#define GCR_IRQ_STAT       0x000C
#define GCR_FRAME_CNT_LO   0x0010
#define GCR_FRAME_CNT_HI   0x0014
#define GCR_CLK_CTRL       0x0018

/* Patch Embedder Unit */
#define PEU_CTRL           0x0100
#define PEU_IMG_W          0x0104
#define PEU_IMG_H          0x0106
#define PEU_PATCH_SZ       0x0108

/* Phase Attention Unit */
#define PAU_CTRL           0x0200
#define PAU_STATUS         0x0204
#define PAU_SEQ_LEN        0x0208
#define PAU_EMBED_DIM      0x020C
#define PAU_NUM_HEADS      0x020E
#define PAU_SYNC_LR        0x0210
#define PAU_SYNC_STEPS     0x0214

/* Temporal Context Unit */
#define TCU_CTRL           0x0300
#define TCU_STATUS         0x0304
#define TCU_FRAME_CNT_LO   0x0308
#define TCU_FRAME_CNT_HI   0x030C
#define TCU_DECAY          0x0310

/* Ontology Projector Unit */
#define OPU_CTRL           0x0400
#define OPU_HIDDEN_DIM     0x0408
#define OPU_STATE_DIM      0x040A

/* State Delta Unit */
#define SDU_CTRL           0x0500
#define SDU_LOSS_MSE       0x0528
#define SDU_LOSS_TOTAL     0x0534

/* Kosha Entropy Engine */
#define KEE_CTRL           0x0600
#define KEE_KOSHA_LEVEL    0x0604
#define KEE_VRITTI_STATE   0x0608

/* Ontology Layer Blocks (12 layers) */
#define OLB_BASE(n)        (0x1000 + (n) * 0x100)
#define OLB_CTRL(n)        (OLB_BASE(n) + 0x00)
#define OLB_FREQ_DIV(n)    (OLB_BASE(n) + 0x08)
#define OLB_PHASE_ACC(n)   (OLB_BASE(n) + 0x0C)
#define OLB_ACTIVATION(n)  (OLB_BASE(n) + 0x10)
#define OLB_COHERENCE(n)   (OLB_BASE(n) + 0x14)
```

### 3.2 Register Access Functions

```c
static inline u32 cohera_read32(struct cohera_device *cdev, u32 offset)
{
    return ioread32(cdev->regs + offset);
}

static inline void cohera_write32(struct cohera_device *cdev,
                                   u32 offset, u32 value)
{
    iowrite32(value, cdev->regs + offset);
}

static inline u64 cohera_read64(struct cohera_device *cdev, u32 offset)
{
    u64 lo = ioread32(cdev->regs + offset);
    u64 hi = ioread32(cdev->regs + offset + 4);
    return (hi << 32) | lo;
}

static inline void cohera_write64(struct cohera_device *cdev,
                                   u32 offset, u64 value)
{
    iowrite32(value & 0xFFFFFFFF, cdev->regs + offset);
    iowrite32(value >> 32, cdev->regs + offset + 4);
}
```

---

## 4. DMA Engine

### 4.1 DMA Descriptor Ring

```c
#define COHERA_DMA_RING_SIZE  256

struct cohera_dma_desc {
    u64 src_addr;        /* Source address (host or device) */
    u64 dst_addr;        /* Destination address */
    u32 size;            /* Transfer size in bytes */
    u32 flags;           /* DMA flags */
#define DMA_FLAG_TO_DEVICE   (1 << 0)
#define DMA_FLAG_FROM_DEVICE (1 << 1)
#define DMA_FLAG_INTERRUPT   (1 << 2)
#define DMA_FLAG_LAST        (1 << 3)
    u32 status;          /* Completion status */
    u32 reserved;
} __packed;

struct cohera_dma_ring {
    struct cohera_dma_desc *descs;
    dma_addr_t descs_dma;
    u32 head;            /* Next to submit */
    u32 tail;            /* Next to complete */
    spinlock_t lock;
    struct completion done;
};
```

### 4.2 DMA Submission

```c
int cohera_dma_submit(struct cohera_device *cdev,
                      dma_addr_t src, dma_addr_t dst,
                      size_t size, u32 flags)
{
    struct cohera_dma_ring *ring = &cdev->dma_ring;
    struct cohera_dma_desc *desc;
    unsigned long irqflags;
    u32 head;

    spin_lock_irqsave(&ring->lock, irqflags);

    /* Check for space in ring */
    if (((ring->head + 1) % COHERA_DMA_RING_SIZE) == ring->tail) {
        spin_unlock_irqrestore(&ring->lock, irqflags);
        return -EBUSY;
    }

    head = ring->head;
    desc = &ring->descs[head];

    desc->src_addr = src;
    desc->dst_addr = dst;
    desc->size = size;
    desc->flags = flags | DMA_FLAG_INTERRUPT;
    desc->status = 0;

    /* Memory barrier before updating head */
    wmb();

    ring->head = (head + 1) % COHERA_DMA_RING_SIZE;

    /* Ring doorbell */
    cohera_write32(cdev, DMA_DOORBELL, ring->head);

    spin_unlock_irqrestore(&ring->lock, irqflags);

    return 0;
}

int cohera_dma_wait(struct cohera_device *cdev, unsigned long timeout_ms)
{
    struct cohera_dma_ring *ring = &cdev->dma_ring;

    if (!wait_for_completion_timeout(&ring->done,
                                      msecs_to_jiffies(timeout_ms)))
        return -ETIMEDOUT;

    return 0;
}
```

---

## 5. Interrupt Handling

### 5.1 MSI-X Setup

```c
#define COHERA_NUM_MSIX_VECTORS  8

enum cohera_irq_vector {
    IRQ_VEC_FRAME_DONE = 0,
    IRQ_VEC_DMA_COMPLETE,
    IRQ_VEC_COHERENCE_LOW,
    IRQ_VEC_TCU_OVERFLOW,
    IRQ_VEC_ERROR,
    IRQ_VEC_LAYER_SYNC,
    IRQ_VEC_RESERVED1,
    IRQ_VEC_RESERVED2,
};

static int cohera_init_interrupts(struct cohera_device *cdev,
                                   struct pci_dev *pdev)
{
    int ret, i;

    ret = pci_alloc_irq_vectors(pdev, 1, COHERA_NUM_MSIX_VECTORS,
                                 PCI_IRQ_MSIX | PCI_IRQ_MSI);
    if (ret < 0)
        return ret;

    cdev->num_irq_vectors = ret;

    for (i = 0; i < cdev->num_irq_vectors; i++) {
        int irq = pci_irq_vector(pdev, i);

        ret = request_irq(irq, cohera_irq_handler, 0,
                          "cohera", cdev);
        if (ret)
            goto err_free_irqs;

        cdev->irqs[i] = irq;
    }

    /* Enable interrupts */
    cohera_write32(cdev, GCR_IRQ_EN,
                   IRQ_FRAME_DONE | IRQ_DMA_COMPLETE | IRQ_ERROR);

    return 0;

err_free_irqs:
    while (--i >= 0)
        free_irq(cdev->irqs[i], cdev);
    pci_free_irq_vectors(pdev);
    return ret;
}
```

### 5.2 Interrupt Handler

```c
static irqreturn_t cohera_irq_handler(int irq, void *data)
{
    struct cohera_device *cdev = data;
    u32 status;

    status = cohera_read32(cdev, GCR_IRQ_STAT);
    if (!status)
        return IRQ_NONE;

    /* Acknowledge interrupts */
    cohera_write32(cdev, GCR_IRQ_STAT, status);

    if (status & IRQ_FRAME_DONE) {
        cdev->frame_count++;
        wake_up(&cdev->frame_wait);
    }

    if (status & IRQ_DMA_COMPLETE) {
        cohera_dma_complete(cdev);
        complete(&cdev->dma_ring.done);
    }

    if (status & IRQ_COHERENCE_LOW) {
        /* Coherence dropped below threshold */
        cdev->coherence_events++;
        if (cdev->coherence_callback)
            cdev->coherence_callback(cdev, cdev->callback_data);
    }

    if (status & IRQ_ERROR) {
        u32 err = cohera_read32(cdev, GCR_ERROR_CODE);
        dev_err(cdev->dev, "Hardware error: 0x%08x\n", err);
        cdev->error_count++;
    }

    return IRQ_HANDLED;
}
```

---

## 6. IOCTL Interface

### 6.1 IOCTL Commands

```c
#define COHERA_IOC_MAGIC  'C'

#define COHERA_IOC_GET_INFO      _IOR(COHERA_IOC_MAGIC, 0, struct cohera_info)
#define COHERA_IOC_ALLOC_MEM     _IOWR(COHERA_IOC_MAGIC, 1, struct cohera_mem)
#define COHERA_IOC_FREE_MEM      _IOW(COHERA_IOC_MAGIC, 2, struct cohera_mem)
#define COHERA_IOC_SUBMIT_DMA    _IOW(COHERA_IOC_MAGIC, 3, struct cohera_dma)
#define COHERA_IOC_WAIT_DMA      _IOW(COHERA_IOC_MAGIC, 4, u32)
#define COHERA_IOC_LAUNCH_KERNEL _IOW(COHERA_IOC_MAGIC, 5, struct cohera_kernel)
#define COHERA_IOC_GET_METRICS   _IOR(COHERA_IOC_MAGIC, 6, struct cohera_metrics)
#define COHERA_IOC_SET_COHERENCE_CB _IOW(COHERA_IOC_MAGIC, 7, struct cohera_callback)
#define COHERA_IOC_RESET_TCU     _IO(COHERA_IOC_MAGIC, 8)

struct cohera_info {
    u32 device_id;
    u32 num_pau;
    u32 num_tcu;
    u32 hbm_size_mb;
    u32 max_seq_len;
    u32 firmware_version;
    u32 phase_precision_ps;
};

struct cohera_mem {
    u64 size;
    u64 device_addr;  /* Output: HBM3 address */
    u64 user_addr;    /* Output: mmap-able address */
    u32 flags;
};

struct cohera_dma {
    u64 host_addr;
    u64 device_addr;
    u64 size;
    u32 direction;    /* 0 = H2D, 1 = D2H */
};

struct cohera_metrics {
    float coherence;
    float entropy;
    float confidence;
    float momentum;
    u32 dominant_layer;
    u32 vritti_state;
    u64 frame_count;
};
```

### 6.2 IOCTL Handler

```c
static long cohera_ioctl(struct file *file, unsigned int cmd,
                          unsigned long arg)
{
    struct cohera_device *cdev = file->private_data;
    void __user *argp = (void __user *)arg;

    switch (cmd) {
    case COHERA_IOC_GET_INFO: {
        struct cohera_info info = {
            .device_id = cdev->device_id,
            .num_pau = cdev->num_pau,
            .num_tcu = cdev->num_tcu,
            .hbm_size_mb = cdev->hbm_size >> 20,
            .max_seq_len = cdev->max_seq_len,
            .firmware_version = cohera_read32(cdev, FW_VERSION),
            .phase_precision_ps = 100, /* 100 picoseconds */
        };
        if (copy_to_user(argp, &info, sizeof(info)))
            return -EFAULT;
        return 0;
    }

    case COHERA_IOC_ALLOC_MEM: {
        struct cohera_mem mem;
        if (copy_from_user(&mem, argp, sizeof(mem)))
            return -EFAULT;
        return cohera_alloc_hbm(cdev, &mem, argp);
    }

    case COHERA_IOC_FREE_MEM: {
        struct cohera_mem mem;
        if (copy_from_user(&mem, argp, sizeof(mem)))
            return -EFAULT;
        return cohera_free_hbm(cdev, &mem);
    }

    case COHERA_IOC_GET_METRICS: {
        struct cohera_metrics m;
        m.coherence = cohera_read_float(cdev, KEE_COHERENCE);
        m.entropy = cohera_read_float(cdev, KEE_ENTROPY);
        m.dominant_layer = cohera_read32(cdev, OPU_DOMINANT_LAYER);
        m.vritti_state = cohera_read32(cdev, KEE_VRITTI_STATE);
        m.frame_count = cohera_read64(cdev, GCR_FRAME_CNT_LO);
        if (copy_to_user(argp, &m, sizeof(m)))
            return -EFAULT;
        return 0;
    }

    case COHERA_IOC_RESET_TCU:
        cohera_write32(cdev, TCU_CTRL,
                       cohera_read32(cdev, TCU_CTRL) | TCU_RESET);
        return 0;

    default:
        return -ENOTTY;
    }
}
```

---

## 7. Power Management

```c
static int cohera_suspend(struct device *dev)
{
    struct pci_dev *pdev = to_pci_dev(dev);
    struct cohera_device *cdev = pci_get_drvdata(pdev);

    /* Save TCU state before suspend */
    cohera_save_tcu_state(cdev);

    /* Disable interrupts */
    cohera_write32(cdev, GCR_IRQ_EN, 0);

    /* Gate clocks */
    cohera_write32(cdev, GCR_CLK_CTRL, CLK_GATE_ALL);

    return 0;
}

static int cohera_resume(struct device *dev)
{
    struct pci_dev *pdev = to_pci_dev(dev);
    struct cohera_device *cdev = pci_get_drvdata(pdev);

    /* Ungate clocks */
    cohera_write32(cdev, GCR_CLK_CTRL, 0);

    /* Restore TCU state */
    cohera_restore_tcu_state(cdev);

    /* Re-enable interrupts */
    cohera_write32(cdev, GCR_IRQ_EN,
                   IRQ_FRAME_DONE | IRQ_DMA_COMPLETE | IRQ_ERROR);

    return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(cohera_pm_ops,
                                 cohera_suspend, cohera_resume);
```

---

## 8. Module Definition

```c
static struct pci_driver cohera_pci_driver = {
    .name = "cohera",
    .id_table = cohera_pci_ids,
    .probe = cohera_pci_probe,
    .remove = cohera_pci_remove,
    .driver.pm = &cohera_pm_ops,
};

static int __init cohera_init(void)
{
    int ret;

    ret = alloc_chrdev_region(&cohera_devt, 0, COHERA_MAX_DEVICES,
                               "cohera");
    if (ret)
        return ret;

    cohera_class = class_create("cohera");
    if (IS_ERR(cohera_class)) {
        ret = PTR_ERR(cohera_class);
        goto err_chrdev;
    }

    ret = pci_register_driver(&cohera_pci_driver);
    if (ret)
        goto err_class;

    pr_info("COHERA driver loaded\n");
    return 0;

err_class:
    class_destroy(cohera_class);
err_chrdev:
    unregister_chrdev_region(cohera_devt, COHERA_MAX_DEVICES);
    return ret;
}

static void __exit cohera_exit(void)
{
    pci_unregister_driver(&cohera_pci_driver);
    class_destroy(cohera_class);
    unregister_chrdev_region(cohera_devt, COHERA_MAX_DEVICES);
    pr_info("COHERA driver unloaded\n");
}

module_init(cohera_init);
module_exit(cohera_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Symbolu");
MODULE_DESCRIPTION("COHERA PA-VPU/UCP Driver");
MODULE_VERSION("1.0");
```

---

*Document Version: 1.0*
*Related: COHERA_SDK_SPECIFICATION.md, COHERA_ISA_REFERENCE.md*
