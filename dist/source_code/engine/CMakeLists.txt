# ===========================================================================
# CMakeLists.txt — Middleout-Lattice Compression Engine
#
# Build targets:
#   lattice_engine  — Shared library (.dll / .so)
#   lattice_cli     — Command-line interface executable
#   lattice_python  — (Optional) Python extension via pybind11
#
# Requirements:
#   - C++17 compiler (MSVC 2019+, GCC 9+, Clang 10+)
#   - zstd library (libzstd)
#   - AVX2-capable CPU (runtime fallback for non-AVX2 systems)
#   - (Optional) pybind11 for Python bindings
# ===========================================================================

cmake_minimum_required(VERSION 3.16)
project(MiddleoutLattice
    VERSION 1.0.0
    DESCRIPTION "Middleout-Lattice Compression Engine"
    LANGUAGES CXX
)

# ---------------------------------------------------------------------------
# C++ Standard
# ---------------------------------------------------------------------------
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ---------------------------------------------------------------------------
# Build Type Defaults
# ---------------------------------------------------------------------------
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# ---------------------------------------------------------------------------
# Compiler-Specific Flags
# ---------------------------------------------------------------------------

# AVX2 SIMD support
if(MSVC)
    # MSVC: /arch:AVX2 enables AVX2 intrinsics and defines __AVX2__
    add_compile_options(/arch:AVX2)
    # Enable parallel compilation on MSVC
    add_compile_options(/MP)
    # Suppress deprecation warnings for standard C functions
    add_compile_definitions(_CRT_SECURE_NO_WARNINGS)
    # Enable large object file support (for template-heavy code)
    add_compile_options(/bigobj)
elseif(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    # GCC/Clang: -mavx2 enables AVX2 intrinsics
    add_compile_options(-mavx2 -mfma -mbmi2)
    # Optimization flags for Release builds
    if(CMAKE_BUILD_TYPE STREQUAL "Release")
        add_compile_options(-O3 -DNDEBUG -march=haswell)
    endif()
    # Warning flags
    add_compile_options(-Wall -Wextra -Wpedantic -Wno-unused-parameter)
endif()

# ---------------------------------------------------------------------------
# Find Dependencies
# ---------------------------------------------------------------------------

# zstd — Facebook's Zstandard compression library
# Try pkg-config first, then cmake find_package, then manual search
find_package(PkgConfig QUIET)
if(PkgConfig_FOUND)
    pkg_check_modules(ZSTD QUIET libzstd)
endif()

if(NOT ZSTD_FOUND)
    find_package(zstd QUIET CONFIG)
    if(zstd_FOUND)
        # Modern zstd CMake config provides zstd::libzstd_shared or zstd::libzstd_static
        if(TARGET zstd::libzstd_shared)
            set(ZSTD_LIBRARIES zstd::libzstd_shared)
        elseif(TARGET zstd::libzstd_static)
            set(ZSTD_LIBRARIES zstd::libzstd_static)
        endif()
        set(ZSTD_FOUND TRUE)
    endif()
endif()

if(NOT ZSTD_FOUND)
    # Manual search: look for zstd.h and libzstd
    find_path(ZSTD_INCLUDE_DIRS zstd.h
        PATHS
            "${CMAKE_CURRENT_SOURCE_DIR}/../third_party/zstd/include"
            /usr/include
            /usr/local/include
            "$ENV{VCPKG_ROOT}/installed/x64-windows/include"
            "$ENV{CONDA_PREFIX}/include"
    )
    find_library(ZSTD_LIBRARIES
        NAMES zstd libzstd zstd_static libzstd_static
        PATHS
            "${CMAKE_CURRENT_SOURCE_DIR}/../third_party/zstd/lib"
            /usr/lib
            /usr/local/lib
            "$ENV{VCPKG_ROOT}/installed/x64-windows/lib"
            "$ENV{CONDA_PREFIX}/lib"
    )
    if(ZSTD_INCLUDE_DIRS AND ZSTD_LIBRARIES)
        set(ZSTD_FOUND TRUE)
        message(STATUS "Found zstd manually: ${ZSTD_LIBRARIES}")
    else()
        message(WARNING
            "zstd not found. Building with built-in fallback compression.\n"
            "Install zstd: vcpkg install zstd:x64-windows  (Windows)\n"
            "              apt install libzstd-dev           (Ubuntu)\n"
            "              brew install zstd                 (macOS)"
        )
        # Define fallback flag
        add_compile_definitions(LATTICE_NO_ZSTD)
    endif()
endif()

# ---------------------------------------------------------------------------
# Source Files
# ---------------------------------------------------------------------------

# Bundle Brotli statically
set(BUILD_SHARED_LIBS OFF CACHE BOOL "Build shared libraries" FORCE)
set(BROTLI_BUNDLED_MODE ON CACHE BOOL "Bundle Brotli" FORCE)
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../third_party/brotli ${CMAKE_CURRENT_BINARY_DIR}/brotli)

set(LATTICE_SOURCES
    lattice_engine.cpp
)

set(LATTICE_HEADERS
    lattice_engine.h
    ${CMAKE_CURRENT_SOURCE_DIR}/../rangecoder.h
)

# ---------------------------------------------------------------------------
# Shared Library: lattice_engine
# ---------------------------------------------------------------------------
add_library(lattice_engine SHARED ${LATTICE_SOURCES} ${LATTICE_HEADERS})
target_include_directories(lattice_engine
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/..
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/brotli/c/include
)

if(ZSTD_FOUND)
    target_include_directories(lattice_engine PRIVATE ${ZSTD_INCLUDE_DIRS})
    target_link_libraries(lattice_engine PRIVATE ${ZSTD_LIBRARIES})
endif()
target_link_libraries(lattice_engine PRIVATE brotlicommon brotlidec brotlienc)

# Export symbols on Windows
if(WIN32)
    target_compile_definitions(lattice_engine PRIVATE LATTICE_ENGINE_EXPORTS)
    target_compile_definitions(lattice_engine PUBLIC LATTICE_ENGINE_DLL)
endif()

# Set output name
set_target_properties(lattice_engine PROPERTIES
    OUTPUT_NAME "lattice_engine"
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
)

# ---------------------------------------------------------------------------
# Static Library (convenience for CLI linking)
# ---------------------------------------------------------------------------
add_library(lattice_engine_static STATIC ${LATTICE_SOURCES} ${LATTICE_HEADERS})
target_include_directories(lattice_engine_static
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/..
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/brotli/c/include
)

if(ZSTD_FOUND)
    target_include_directories(lattice_engine_static PRIVATE ${ZSTD_INCLUDE_DIRS})
    target_link_libraries(lattice_engine_static PRIVATE ${ZSTD_LIBRARIES})
endif()
target_link_libraries(lattice_engine_static PRIVATE brotlicommon brotlidec brotlienc)

# ---------------------------------------------------------------------------
# CLI Executable: lattice_cli
# ---------------------------------------------------------------------------
add_executable(lattice_cli lattice_cli.cpp)
target_link_libraries(lattice_cli PRIVATE lattice_engine_static brotlicommon brotlidec brotlienc)

if(ZSTD_FOUND)
    target_include_directories(lattice_cli PRIVATE ${ZSTD_INCLUDE_DIRS})
    target_link_libraries(lattice_cli PRIVATE ${ZSTD_LIBRARIES})
endif()

# ---------------------------------------------------------------------------
# GUI Executable: lattice_gui (Windows only)
# ---------------------------------------------------------------------------
if(WIN32)
    enable_language(RC)
    add_executable(lattice_gui WIN32 lattice_gui.cpp lattice_gui.rc)
    target_link_libraries(lattice_gui PRIVATE lattice_engine_static brotlicommon brotlidec brotlienc)
    if(ZSTD_FOUND)
        target_include_directories(lattice_gui PRIVATE ${ZSTD_INCLUDE_DIRS})
        target_link_libraries(lattice_gui PRIVATE ${ZSTD_LIBRARIES})
    endif()
    target_link_libraries(lattice_gui PRIVATE comctl32 ole32 shell32 uuid)
endif()


# ---------------------------------------------------------------------------
# Optional: Python Extension via pybind11
# ---------------------------------------------------------------------------
option(BUILD_PYTHON_BINDINGS "Build Python bindings via pybind11" OFF)

if(BUILD_PYTHON_BINDINGS)
    find_package(pybind11 QUIET CONFIG)
    if(pybind11_FOUND)
        pybind11_add_module(lattice_python
            lattice_python_bindings.cpp
        )
        target_link_libraries(lattice_python PRIVATE lattice_engine_static)
        if(ZSTD_FOUND)
            target_link_libraries(lattice_python PRIVATE ${ZSTD_LIBRARIES})
        endif()
        message(STATUS "pybind11 found — building Python extension")
    else()
        message(WARNING "pybind11 not found — skipping Python bindings")
    endif()
endif()

# ---------------------------------------------------------------------------
# Install Rules
# ---------------------------------------------------------------------------
include(GNUInstallDirs)

install(TARGETS lattice_engine lattice_cli
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
)

if(WIN32)
    install(TARGETS lattice_gui RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
endif()

install(FILES lattice_engine.h
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/lattice
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
message(STATUS "========================================")
message(STATUS " Middleout-Lattice Engine v${PROJECT_VERSION}")
message(STATUS "   Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "   Compiler:   ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")
message(STATUS "   zstd:       ${ZSTD_FOUND}")
message(STATUS "   pybind11:   ${BUILD_PYTHON_BINDINGS}")
message(STATUS "========================================")
