/*
 * COHERA Runtime API
 *
 * Software stack for PA-VPU / Universal Coherence Processor
 *
 * Copyright (c) 2024 Symbolu
 */

#ifndef COHERA_H
#define COHERA_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/*============================================================================
 * Error Codes
 *============================================================================*/

typedef enum {
    COHERA_SUCCESS = 0,
    COHERA_ERROR_INVALID_DEVICE = 1,
    COHERA_ERROR_OUT_OF_MEMORY = 2,
    COHERA_ERROR_INVALID_VALUE = 3,
    COHERA_ERROR_NOT_INITIALIZED = 4,
    COHERA_ERROR_ALREADY_INITIALIZED = 5,
    COHERA_ERROR_DRIVER_ERROR = 6,
    COHERA_ERROR_TIMEOUT = 7,
    COHERA_ERROR_COHERENCE_LOW = 8,
    COHERA_ERROR_TCU_OVERFLOW = 9,
    COHERA_ERROR_UNKNOWN = 999,
} cohera_error_t;

/*============================================================================
 * Data Types
 *============================================================================*/

typedef enum {
    COHERA_DTYPE_FP16 = 0,
    COHERA_DTYPE_BF16 = 1,
    COHERA_DTYPE_FP32 = 2,
    COHERA_DTYPE_INT8 = 3,
} cohera_dtype_t;

typedef enum {
    COHERA_VRITTI_PRAMANA = 0,    /* Valid cognition */
    COHERA_VRITTI_VIPARYAYA = 1,  /* Misperception */
    COHERA_VRITTI_VIKALPA = 2,    /* Imagination */
    COHERA_VRITTI_SMRTI = 3,      /* Memory */
    COHERA_VRITTI_NIDRA = 4,      /* Dormancy */
} cohera_vritti_t;

typedef enum {
    COHERA_KOSHA_PRE_ANNAMAYA = 0,
    COHERA_KOSHA_ANNAMAYA = 1,
    COHERA_KOSHA_PRANAMAYA = 2,
    COHERA_KOSHA_MANOMAYA = 3,
    COHERA_KOSHA_VIJNANAMAYA = 4,
    COHERA_KOSHA_ANANDAMAYA = 5,
} cohera_kosha_t;

/*============================================================================
 * Opaque Handles
 *============================================================================*/

typedef struct cohera_device_st* cohera_device_t;
typedef struct cohera_stream_st* cohera_stream_t;
typedef struct cohera_event_st* cohera_event_t;
typedef struct cohera_kernel_st* cohera_kernel_t;

/*============================================================================
 * Device Capabilities
 *============================================================================*/

typedef struct {
    uint32_t device_id;
    uint32_t num_pau;              /* Phase Attention Units */
    uint32_t num_tcu;              /* Temporal Context Units */
    uint32_t hbm_size_mb;          /* HBM3 capacity in MB */
    uint32_t max_seq_len;          /* Maximum sequence length */
    uint32_t ontology_layers;      /* Always 12 */
    uint32_t phase_precision_ps;   /* Phase precision in picoseconds */
    uint32_t firmware_version;
    char device_name[64];
} cohera_caps_t;

/*============================================================================
 * Tensor Descriptor
 *============================================================================*/

typedef struct {
    void* data;                    /* Device pointer */
    int64_t shape[4];              /* [batch, seq, heads, dim] */
    int64_t strides[4];            /* Strides in elements */
    cohera_dtype_t dtype;
    int ontology_layer;            /* Associated layer (0-11, -1 for none) */
    size_t size_bytes;
} cohera_tensor_t;

/*============================================================================
 * Cognitive State (124 dimensions)
 *============================================================================*/

typedef struct {
    float phoneme_energy[44];      /* Phonemic layer */
    float topic_embedding[64];     /* Topic/semantic layer */
    float ontology_probs[12];      /* 12-layer activations */
    float coherence;               /* [0, 1] */
    float entropy;                 /* [0, 1] */
    float confidence;              /* [0, 1] */
    float momentum;                /* Rate of meaning change */
} cohera_cognitive_state_t;

/*============================================================================
 * Sovereign State (32 dimensions) — matches mistral_cg SovereignStateProjector
 *  layout: Bhava(12) + Kosha(5) + Vritti(5) + Guna(6) + Reserved(4) = 32
 *============================================================================*/

#define COHERA_SOVEREIGN_BHAVA_DIM    12
#define COHERA_SOVEREIGN_KOSHA_DIM    5
#define COHERA_SOVEREIGN_VRITTI_DIM   5
#define COHERA_SOVEREIGN_GUNA_DIM     6
#define COHERA_SOVEREIGN_RESERVED_DIM 4
#define COHERA_SOVEREIGN_TOTAL_DIM    32

typedef enum {
    COHERA_KOSHA_MODE_SIGMOID = 0,
    COHERA_KOSHA_MODE_SOFTMAX = 1,
} cohera_kosha_mode_t;

typedef struct {
    float bhava[COHERA_SOVEREIGN_BHAVA_DIM];        /* softmax */
    float kosha[COHERA_SOVEREIGN_KOSHA_DIM];        /* sigmoid / softmax */
    float vritti[COHERA_SOVEREIGN_VRITTI_DIM];      /* softmax */
    float guna[COHERA_SOVEREIGN_GUNA_DIM];          /* sigmoid */
    float reserved[COHERA_SOVEREIGN_RESERVED_DIM];  /* tanh */
} cohera_sovereign_state_t;

/*============================================================================
 * Runtime Metrics
 *============================================================================*/

typedef struct {
    float coherence;
    float entropy;
    float confidence;
    float momentum;
    int dominant_layer;            /* 0-11 */
    cohera_vritti_t vritti_state;
    cohera_kosha_t kosha_level;
    uint64_t frame_count;
    uint64_t tcu_updates;
} cohera_metrics_t;

/*============================================================================
 * Attention Configuration
 *============================================================================*/

/*
 * Field ordering note: v1 fields (seq_len..coherence_threshold) come first
 * and must not be reordered. v2 fields (num_kv_heads onward) are append-only
 * so zero-initialized v1 callers keep working — defaulting num_kv_heads=0
 * selects MHA, dtype=FP16 selects the legacy path, window_size=0 is coerced
 * to full attention by the kernel, and rope_* default NULL/0 disables RoPE.
 */
typedef struct {
    /* --- v1: stable --- */
    int seq_len;
    int embed_dim;
    int num_heads;
    int sync_steps;                /* Phase sync iterations (default: 3) */
    float sync_lr;                 /* Phase learning rate (default: 0.1) */
    float temperature;             /* Attention temperature */
    int causal;                    /* Enable causal masking */
    int use_tcu;                   /* Enable temporal context */
    int ontology_layer;            /* Bound to layer (0-11, -1 for all) */
    float coherence_threshold;     /* Gating threshold */
    /* --- v2: append-only --- */
    int num_kv_heads;              /* GQA: KV head count (<= num_heads). 0 -> MHA (num_heads). */
    cohera_dtype_t dtype;          /* Compute dtype (FP16 / BF16 / FP32) */
    int window_size;               /* Sliding window (<= 0 = full attention) */
    const cohera_tensor_t* rope_freqs; /* Device tensor [rope_dim/2] FP32, or NULL */
    int rope_dim;                  /* Dim to apply RoPE over (0 = disabled) */
    int rope_base_position;        /* Starting position id (for KV cache continuation) */
} cohera_attention_config_t;

/*============================================================================
 * Initialization / Shutdown
 *============================================================================*/

/**
 * Initialize the COHERA runtime.
 * Must be called before any other COHERA function.
 */
cohera_error_t cohera_init(void);

/**
 * Shutdown the COHERA runtime and release all resources.
 */
cohera_error_t cohera_shutdown(void);

/**
 * Get the last error message.
 */
const char* cohera_get_error_string(cohera_error_t error);

/*============================================================================
 * Device Management
 *============================================================================*/

/**
 * Get the number of available COHERA devices.
 */
int cohera_get_device_count(void);

/**
 * Get a device handle by index.
 */
cohera_error_t cohera_get_device(int index, cohera_device_t* device);

/**
 * Set the current device for subsequent operations.
 */
cohera_error_t cohera_set_device(int index);

/**
 * Get the current device index.
 */
cohera_error_t cohera_get_current_device(int* index);

/**
 * Get device capabilities.
 */
cohera_error_t cohera_get_caps(cohera_device_t device, cohera_caps_t* caps);

/**
 * Synchronize all pending operations on the device.
 */
cohera_error_t cohera_device_synchronize(void);

/*============================================================================
 * Memory Management
 *============================================================================*/

/**
 * Allocate device memory (HBM3).
 */
cohera_error_t cohera_malloc(void** ptr, size_t size);

/**
 * Allocate device memory with specific alignment.
 */
cohera_error_t cohera_malloc_aligned(void** ptr, size_t size, size_t alignment);

/**
 * Free device memory.
 */
cohera_error_t cohera_free(void* ptr);

/**
 * Copy from host to device.
 */
cohera_error_t cohera_memcpy_h2d(void* dst, const void* src, size_t size);

/**
 * Copy from device to host.
 */
cohera_error_t cohera_memcpy_d2h(void* dst, const void* src, size_t size);

/**
 * Copy within device memory.
 */
cohera_error_t cohera_memcpy_d2d(void* dst, const void* src, size_t size);

/**
 * Async copy from host to device.
 */
cohera_error_t cohera_memcpy_h2d_async(void* dst, const void* src,
                                        size_t size, cohera_stream_t stream);

/**
 * Async copy from device to host.
 */
cohera_error_t cohera_memcpy_d2h_async(void* dst, const void* src,
                                        size_t size, cohera_stream_t stream);

/**
 * Set device memory to a value.
 */
cohera_error_t cohera_memset(void* ptr, int value, size_t size);

/*============================================================================
 * Tensor Operations
 *============================================================================*/

/**
 * Create a tensor on device.
 */
cohera_error_t cohera_tensor_create(cohera_tensor_t* tensor,
                                     const int64_t* shape, int ndim,
                                     cohera_dtype_t dtype,
                                     int ontology_layer);

/**
 * Destroy a tensor and free its memory.
 */
cohera_error_t cohera_tensor_destroy(cohera_tensor_t* tensor);

/**
 * Copy tensor from host.
 */
cohera_error_t cohera_tensor_copy_from_host(cohera_tensor_t* tensor,
                                             const void* host_data);

/**
 * Copy tensor to host.
 */
cohera_error_t cohera_tensor_copy_to_host(const cohera_tensor_t* tensor,
                                           void* host_data);

/*============================================================================
 * Stream Management (Ontology-Aware Scheduling)
 *============================================================================*/

/**
 * Create a stream bound to an ontology layer.
 * Layer affects scheduling priority (O1=highest, O12=lowest).
 */
cohera_error_t cohera_stream_create(cohera_stream_t* stream, int ontology_layer);

/**
 * Destroy a stream.
 */
cohera_error_t cohera_stream_destroy(cohera_stream_t stream);

/**
 * Synchronize a stream (wait for all operations to complete).
 */
cohera_error_t cohera_stream_synchronize(cohera_stream_t stream);

/**
 * Query if stream is complete.
 */
cohera_error_t cohera_stream_query(cohera_stream_t stream, int* complete);

/**
 * Make a stream wait for an event.
 */
cohera_error_t cohera_stream_wait_event(cohera_stream_t stream,
                                         cohera_event_t event);

/*============================================================================
 * Event Management
 *============================================================================*/

/**
 * Create an event.
 */
cohera_error_t cohera_event_create(cohera_event_t* event);

/**
 * Destroy an event.
 */
cohera_error_t cohera_event_destroy(cohera_event_t event);

/**
 * Record an event on a stream.
 */
cohera_error_t cohera_event_record(cohera_event_t event, cohera_stream_t stream);

/**
 * Wait for an event to complete (blocking).
 */
cohera_error_t cohera_event_synchronize(cohera_event_t event);

/**
 * Get elapsed time between two events in milliseconds.
 */
cohera_error_t cohera_event_elapsed_time(float* ms,
                                          cohera_event_t start,
                                          cohera_event_t end);

/*============================================================================
 * Phase Attention Kernels
 *============================================================================*/

/**
 * Run phase attention (core operation).
 */
cohera_error_t cohera_phase_attention(
    cohera_tensor_t* output,
    const cohera_tensor_t* query,
    const cohera_tensor_t* key,
    const cohera_tensor_t* value,
    const cohera_attention_config_t* config,
    cohera_stream_t stream
);

/**
 * Run phase attention with pre-computed phases.
 */
cohera_error_t cohera_phase_attention_with_phases(
    cohera_tensor_t* output,
    const cohera_tensor_t* query,
    const cohera_tensor_t* key,
    const cohera_tensor_t* value,
    const cohera_tensor_t* phases,  /* Pre-initialized phases */
    const cohera_attention_config_t* config,
    cohera_stream_t stream
);

/**
 * Fused phase attention for Mistral-style decoders.
 *
 * Composes the standard decoder pre-steps into one call on a single stream:
 *
 *   1. If config->rope_dim > 0 and config->rope_freqs is non-NULL, apply
 *      RoPE to Q and K with position offset = config->rope_base_position.
 *   2. If config->num_kv_heads > 0 and < config->num_heads, broadcast K/V
 *      from num_kv_heads to num_heads (GQA expansion).
 *   3. Run cohera_phase_attention with the (possibly rotated / expanded)
 *      tensors.
 *   4. TCU accumulation is handled inside the phase kernel per config->use_tcu.
 *
 * Key / value shapes on entry:
 *   key   : [batch, seq, num_kv_heads, head_dim]
 *   value : [batch, seq, num_kv_heads, head_dim]
 *   query : [batch, seq, num_heads,    head_dim]
 *
 * The fused path avoids host-side chaining and lets the runtime schedule
 * all three ops on the supplied stream with no intermediate sync.
 */
cohera_error_t cohera_phase_attention_fused(
    cohera_tensor_t* output,
    const cohera_tensor_t* query,
    const cohera_tensor_t* key,
    const cohera_tensor_t* value,
    const cohera_attention_config_t* config,
    cohera_stream_t stream
);

/**
 * Project hidden states to cognitive state.
 */
cohera_error_t cohera_ontology_project(
    cohera_cognitive_state_t* output,
    const cohera_tensor_t* hidden,
    cohera_stream_t stream
);

/**
 * Project hidden states to 32-D Sovereign State
 * (mistral_cg SovereignStateProjector).
 *
 * hidden: [batch, seq, hidden_dim] or [batch, hidden_dim]
 */
cohera_error_t cohera_ontology_project_sovereign(
    cohera_sovereign_state_t* output,
    const cohera_tensor_t* hidden,
    cohera_kosha_mode_t kosha_mode,
    cohera_stream_t stream
);

/**
 * Apply Rotary Position Embedding (RoPE) in-place / to output.
 *
 * input / output shape: [batch, seq, heads, head_dim]
 * rope_freqs:           device tensor [rope_dim / 2] FP32
 *                       (typically head_dim / 2 precomputed inverse freqs)
 * position_offset:      base token position (supports KV-cache continuation)
 */
cohera_error_t cohera_apply_rope(
    cohera_tensor_t* output,
    const cohera_tensor_t* input,
    const cohera_tensor_t* rope_freqs,
    int rope_dim,
    int position_offset,
    cohera_stream_t stream
);

/**
 * Broadcast KV heads for Grouped Query Attention.
 *
 * Expands   kv [batch, seq, num_kv_heads, head_dim]
 *       to kv' [batch, seq, num_heads,    head_dim]
 * by repeating each KV head (num_heads / num_kv_heads) times.
 */
cohera_error_t cohera_gqa_broadcast(
    cohera_tensor_t* kv_expanded,
    const cohera_tensor_t* kv,
    int num_heads,
    cohera_stream_t stream
);

/**
 * Build a causal + sliding-window mask on device.
 * mask shape: [seq_len, seq_len], dtype FP32, 0.0 = keep, -INF = drop.
 * window_size < 0 or >= seq_len -> full causal only.
 */
cohera_error_t cohera_build_sliding_window_mask(
    cohera_tensor_t* mask,
    int seq_len,
    int window_size,
    cohera_stream_t stream
);

/**
 * Compute state delta between consecutive states.
 */
cohera_error_t cohera_state_delta(
    cohera_cognitive_state_t* delta,
    const cohera_cognitive_state_t* prev_state,
    const cohera_cognitive_state_t* curr_state,
    cohera_stream_t stream
);

/*============================================================================
 * Temporal Context Unit (TCU)
 *============================================================================*/

/**
 * Reset all TCU accumulators.
 */
cohera_error_t cohera_tcu_reset(void);

/**
 * Get current frame count from TCU.
 */
cohera_error_t cohera_tcu_get_frame_count(uint64_t* count);

/**
 * Set TCU decay factor for exponential moving average.
 */
cohera_error_t cohera_tcu_set_decay(float decay);

/**
 * Read phase context from TCU.
 */
cohera_error_t cohera_tcu_read_context(cohera_tensor_t* context, int head);

/*============================================================================
 * Coherence Monitoring
 *============================================================================*/

/**
 * Get current runtime metrics.
 */
cohera_error_t cohera_get_metrics(cohera_metrics_t* metrics);

/**
 * Callback type for coherence events.
 */
typedef void (*cohera_coherence_callback_t)(float coherence, void* user_data);

/**
 * Register a callback for when coherence drops below threshold.
 */
cohera_error_t cohera_register_coherence_callback(
    cohera_coherence_callback_t callback,
    float threshold,
    void* user_data
);

/**
 * Unregister the coherence callback.
 */
cohera_error_t cohera_unregister_coherence_callback(void);

/*============================================================================
 * Kernel Compilation & Launch (Advanced)
 *============================================================================*/

/**
 * Load a compiled kernel from file.
 */
cohera_error_t cohera_kernel_load(cohera_kernel_t* kernel,
                                   const char* filename);

/**
 * Load a kernel from memory.
 */
cohera_error_t cohera_kernel_load_from_memory(cohera_kernel_t* kernel,
                                               const void* data,
                                               size_t size);

/**
 * Destroy a kernel.
 */
cohera_error_t cohera_kernel_destroy(cohera_kernel_t kernel);

/**
 * Launch a kernel.
 */
cohera_error_t cohera_kernel_launch(
    cohera_kernel_t kernel,
    int grid_dim,
    int block_dim,
    void** args,
    size_t shared_mem_size,
    cohera_stream_t stream
);

#ifdef __cplusplus
}
#endif

#endif /* COHERA_H */
