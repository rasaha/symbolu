cmake_minimum_required(VERSION 3.18)
project(ctm_plus_cuda LANGUAGES CXX CUDA)

# CUDA settings
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find CUDA
find_package(CUDAToolkit REQUIRED)

# Detect GPU architecture (default to common architectures)
if(NOT DEFINED CMAKE_CUDA_ARCHITECTURES)
    set(CMAKE_CUDA_ARCHITECTURES 70 75 80 86 89 90)
endif()

# Library sources
set(CTM_SOURCES
    ctm_plus.cu
    turboquant.cu
    turboquant_ctxl_integration.cu
)

set(CTM_HEADERS
    ctm_plus.cuh
    turboquant.cuh
    turboquant_ctxl_integration.cuh
)

# Build shared library
add_library(ctm_plus_cuda SHARED ${CTM_SOURCES})

target_include_directories(ctm_plus_cuda PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(ctm_plus_cuda
    CUDA::cudart
    CUDA::curand
)

# Build static library
add_library(ctm_plus_cuda_static STATIC ${CTM_SOURCES})

target_include_directories(ctm_plus_cuda_static PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(ctm_plus_cuda_static
    CUDA::cudart_static
    CUDA::curand_static
)

# Example executable
add_executable(ctm_example example.cu)
target_link_libraries(ctm_example ctm_plus_cuda)

# Benchmark executable
add_executable(ctm_benchmark benchmark.cu)
target_link_libraries(ctm_benchmark ctm_plus_cuda)

# TurboQuant + CTXL integrated benchmark
add_executable(turboquant_benchmark turboquant_benchmark.cu)
target_link_libraries(turboquant_benchmark ctm_plus_cuda)

# Installation
install(TARGETS ctm_plus_cuda ctm_plus_cuda_static
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)

install(FILES ${CTM_HEADERS}
    DESTINATION include/ctm_plus
)

# Package configuration
include(CMakePackageConfigHelpers)
write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/ctm_plus_cudaConfigVersion.cmake"
    VERSION 1.0.0
    COMPATIBILITY SameMajorVersion
)

# Print configuration
message(STATUS "CTM+ CUDA Configuration:")
message(STATUS "  CUDA Toolkit: ${CUDAToolkit_VERSION}")
message(STATUS "  Architectures: ${CMAKE_CUDA_ARCHITECTURES}")
message(STATUS "  Build type: ${CMAKE_BUILD_TYPE}")
