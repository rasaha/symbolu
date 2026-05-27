"""Phase 6E — build script for the fused decode-write CUDA extension.

Build:
    cd CTM_plus/CUDA_int4_protected
    pip install -e .

Or for in-tree development on the pod:
    cd CTM_plus/CUDA_int4_protected
    python setup.py build_ext --inplace

The built extension exposes:
    int4_protected_C.fused_decode_write_v(...)
    int4_protected_C.fused_decode_write_k(...)

The Python wrapper in phase5b_4c_paged_writer.py looks up these via
`import int4_protected_C` and falls back to the Python reference if
the import fails (so the package is still usable during the CUDA
implementation phase without a built extension).
"""
from setuptools import setup
from torch.utils.cpp_extension import BuildExtension, CUDAExtension

setup(
    name="int4_protected_C",
    version="0.1.0",
    ext_modules=[
        CUDAExtension(
            name="int4_protected_C",
            sources=[
                "csrc/binding.cpp",
                "csrc/fused_decode_write_v.cu",
                "csrc/fused_decode_write_k.cu",
            ],
            extra_compile_args={
                "cxx":  ["-O3", "-std=c++17"],
                "nvcc": ["-O3", "--use_fast_math",
                         "-gencode=arch=compute_80,code=sm_80",     # A100
                         "-gencode=arch=compute_90,code=sm_90"],    # H100
            },
        ),
    ],
    cmdclass={"build_ext": BuildExtension},
    description="Phase 6E fused decode-write kernels for int4_protected",
)
