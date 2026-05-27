// Phase 6E — PyTorch binding for the fused decode-write kernels.
//
// Registers _int4_protected_C.fused_decode_write_v and
// fused_decode_write_k as torch.ops, so Python callers can invoke
// them like any other native op (and they'll be traced into CUDA
// graphs cleanly by vLLM's capture pipeline).

#include "fused_decode_write.h"

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("fused_decode_write_v",
          &int4_protected::fused_decode_write_v,
          "Phase 6E fused V-side decode write (int4 quant + scatter).");
    m.def("fused_decode_write_k",
          &int4_protected::fused_decode_write_k,
          "Phase 6E fused K-side decode write (stage update + protect + finalize).");
}
