# CTM+ CUDA Makefile
#
# Build:
#   make              # Build all
#   make lib          # Build library only
#   make example      # Build example
#   make benchmark    # Build benchmark
#
# Clean:
#   make clean
#

# CUDA compiler
NVCC ?= nvcc

# Detect GPU architecture (default to common ones)
GPU_ARCH ?= -gencode arch=compute_70,code=sm_70 \
            -gencode arch=compute_75,code=sm_75 \
            -gencode arch=compute_80,code=sm_80 \
            -gencode arch=compute_86,code=sm_86

# Compiler flags
NVCC_FLAGS := -std=c++17 -O3 $(GPU_ARCH)
NVCC_FLAGS += -Xcompiler -Wall,-Wextra
LDFLAGS := -lcurand

# Debug build
ifdef DEBUG
NVCC_FLAGS += -g -G -DDEBUG
endif

# Source files
LIB_SRC := ctm_plus.cu
LIB_HDR := ctm_plus.cuh

# Output
LIB_SHARED := libctm_plus_cuda.so
LIB_STATIC := libctm_plus_cuda.a
EXAMPLE := example
BENCHMARK := benchmark

# Default target
all: lib $(EXAMPLE) $(BENCHMARK)

# Shared library
lib: $(LIB_SHARED) $(LIB_STATIC)

$(LIB_SHARED): $(LIB_SRC) $(LIB_HDR)
	$(NVCC) $(NVCC_FLAGS) -shared -Xcompiler -fPIC -o $@ $(LIB_SRC) $(LDFLAGS)

$(LIB_STATIC): ctm_plus.o
	ar rcs $@ $<

ctm_plus.o: $(LIB_SRC) $(LIB_HDR)
	$(NVCC) $(NVCC_FLAGS) -c -Xcompiler -fPIC -o $@ $(LIB_SRC)

# Example
$(EXAMPLE): example.cu $(LIB_SHARED)
	$(NVCC) $(NVCC_FLAGS) -o $@ example.cu -L. -lctm_plus_cuda $(LDFLAGS) -Wl,-rpath,.

# Standalone example (no library)
example_standalone: example.cu $(LIB_SRC) $(LIB_HDR)
	$(NVCC) $(NVCC_FLAGS) -o $@ example.cu $(LIB_SRC) $(LDFLAGS)

# Benchmark
$(BENCHMARK): benchmark.cu $(LIB_SHARED)
	$(NVCC) $(NVCC_FLAGS) -o $@ benchmark.cu -L. -lctm_plus_cuda $(LDFLAGS) -Wl,-rpath,.

# Standalone benchmark (no library)
benchmark_standalone: benchmark.cu $(LIB_SRC) $(LIB_HDR)
	$(NVCC) $(NVCC_FLAGS) -o $@ benchmark.cu $(LIB_SRC) $(LDFLAGS)

# Install
PREFIX ?= /usr/local

install: lib
	install -d $(PREFIX)/lib
	install -d $(PREFIX)/include/ctm_plus
	install -m 644 $(LIB_SHARED) $(PREFIX)/lib/
	install -m 644 $(LIB_STATIC) $(PREFIX)/lib/
	install -m 644 $(LIB_HDR) $(PREFIX)/include/ctm_plus/
	ldconfig

uninstall:
	rm -f $(PREFIX)/lib/$(LIB_SHARED)
	rm -f $(PREFIX)/lib/$(LIB_STATIC)
	rm -rf $(PREFIX)/include/ctm_plus

# Clean
clean:
	rm -f $(LIB_SHARED) $(LIB_STATIC) *.o $(EXAMPLE) $(BENCHMARK)
	rm -f example_standalone benchmark_standalone

# Run
run_example: $(EXAMPLE)
	LD_LIBRARY_PATH=. ./$(EXAMPLE)

run_benchmark: $(BENCHMARK)
	LD_LIBRARY_PATH=. ./$(BENCHMARK)

# Help
help:
	@echo "CTM+ CUDA Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all              - Build library, example, and benchmark"
	@echo "  lib              - Build shared and static libraries"
	@echo "  example          - Build example (requires library)"
	@echo "  benchmark        - Build benchmark (requires library)"
	@echo "  example_standalone  - Build example (statically linked)"
	@echo "  benchmark_standalone - Build benchmark (statically linked)"
	@echo "  install          - Install to PREFIX (default: /usr/local)"
	@echo "  clean            - Remove build artifacts"
	@echo ""
	@echo "Variables:"
	@echo "  NVCC=<compiler>  - CUDA compiler (default: nvcc)"
	@echo "  GPU_ARCH=<arch>  - GPU architectures"
	@echo "  DEBUG=1          - Enable debug build"
	@echo "  PREFIX=<path>    - Install prefix"

.PHONY: all lib install uninstall clean run_example run_benchmark help
