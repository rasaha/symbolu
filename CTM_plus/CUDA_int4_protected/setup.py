"""Phase 6E — build script for the fused decode-write CUDA extension.

Build:
    cd CTM_plus/CUDA_int4_protected
    pip install --no-build-isolation -e .       # uses venv's torch (faster)
    # OR
    pip install -e .                             # uses pyproject's build deps

The built extension exposes:
    int4_protected_C.fused_decode_write_v(...)
    int4_protected_C.fused_decode_write_k(...)

IMPORT ORDER NOTE: when loading the extension, `import torch` must
come first. The .so depends on libc10.so / libtorch_cpu.so which
torch's own import loads into the process; without it, the .so fails
to load with "libc10.so: cannot open shared object file". Either:

    import torch                # always do this FIRST
    import int4_protected_C

Or set LD_LIBRARY_PATH explicitly:

    export LD_LIBRARY_PATH=$(python -c "import torch, os; print(os.path.dirname(torch.__file__) + '/lib')")

The dispatch wrapper in phase5b_4c_paged_writer.py handles the
import order correctly when the fused path is enabled. The CPU
verifier (verify_phase6e_fused_byte_eq.py) uses the Python
reference and doesn't need the .so at all.
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
            # Embed an rpath to torch's lib directory so the loader can
            # find libc10.so / libtorch_cuda.so etc. without requiring
            # the user to export LD_LIBRARY_PATH. $ORIGIN/../torch/lib
            # is correct when the extension is installed next to torch
            # in site-packages; for editable installs it's whatever
            # path torch.__file__'s parent + /lib resolves to.
            extra_link_args=[
                "-Wl,-rpath,$ORIGIN/../torch/lib",
            ],
        ),
    ],
    cmdclass={"build_ext": BuildExtension},
    description="Phase 6E fused decode-write kernels for int4_protected",
)
