#!/usr/bin/env bash
set -e

# We are going to build ncnn for baremetal aarch64 inside the bao docker container
# We assume the toolchain aarch64-none-elf- is available in PATH inside docker.

cd /workspace/prototype/stage2_bao/ncnn

# Clean previous build if any
rm -rf build_baremetal
mkdir build_baremetal
cd build_baremetal

# Create a simple toolchain file for baremetal
cat << 'EOF' > aarch64-baremetal.toolchain.cmake
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

set(CMAKE_C_COMPILER aarch64-none-elf-gcc)
set(CMAKE_CXX_COMPILER aarch64-none-elf-g++)

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
EOF

echo "Running CMake..."
cmake -DCMAKE_TOOLCHAIN_FILE=aarch64-baremetal.toolchain.cmake \
      -DCMAKE_BUILD_TYPE=Release \
      -DNCNN_OPENMP=OFF \
      -DNCNN_THREADS=OFF \
      -DNCNN_VULKAN=OFF \
      -DNCNN_BUILD_TESTS=OFF \
      -DNCNN_BUILD_TOOLS=OFF \
      -DNCNN_BUILD_EXAMPLES=OFF \
      -DNCNN_DISABLE_RTTI=ON \
      -DNCNN_DISABLE_EXCEPTION=ON \
      -DNCNN_SIMPLEOCV=OFF \
      -DNCNN_SHARED_LIB=OFF \
      -DNCNN_ENABLE_LTO=ON \
      ..

echo "Building ncnn..."
make -j$(nproc)

echo "Done! libncnn.a should be in build_baremetal/src/libncnn.a"
ls -la src/libncnn.a
