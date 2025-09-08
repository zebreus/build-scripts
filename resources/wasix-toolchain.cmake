# Cmake toolchain description file for the Makefile for WASI
cmake_minimum_required(VERSION 3.5.0)

# Don't set this to WASI as that leaves `UNIX` set to false.
set(CMAKE_SYSTEM_NAME UnixPaths) # Set to UnixPaths to get a UNIX like environment. We dont care about the other setting set in there.
set(WASI 1)
set(CMAKE_SYSTEM_VERSION 1)
set(CMAKE_SYSTEM_PROCESSOR wasm32)
set(CMAKE_C_COMPILER_ID Clang)
set(triple wasm32-unknown-wasi)
set(CMAKE_C_COMPILER_TARGET ${triple})
set(CMAKE_CXX_COMPILER_TARGET ${triple})
set(CMAKE_ASM_COMPILER_TARGET ${triple})
# set(CMAKE_${lang}_COMPILE_OPTIONS_SYSROOT "--sysroot=$ENV{WASIX_SYSROOT}")
# set(CMAKE_SYSROOT "$ENV{WASIX_SYSROOT}")

set(CMAKE_C_COMPILER wasix-clang)
set(CMAKE_CXX_COMPILER wasix-clang++)
set(CMAKE_LINKER wasm-ld)
set(CMAKE_AR llvm-ar)
set(CMAKE_RANLIB llvm-ranlib)

# Don't look in the sysroot for executables to run during the build
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
# Only look in the sysroot (not in the host paths) for the rest
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)