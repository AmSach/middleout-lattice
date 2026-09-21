#!/usr/bin/env bash
# ===========================================================================
# Middleout-Lattice Linux Installation Script
# ===========================================================================

set -e

# Terminal colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}==========================================${NC}"
echo -e "${CYAN}  Installing Middleout-Lattice CLI & Python API${NC}"
echo -e "${CYAN}==========================================${NC}"

# 1. Check Python installation
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed. Please install Python 3.10+ before running this installer.${NC}"
    exit 1
fi

py_version=$(python3 -V)
echo -e "Found Python: ${GREEN}${py_version}${NC}"

# 2. Set up Python Virtual Environment
echo -e "\n${YELLOW}[1/3] Setting up Python virtual environment (.venv)...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 3. Handle C++ Compilation
echo -e "\n${YELLOW}[2/3] Checking C++ build environment...${NC}"
compiled=false

if command -v cmake &> /dev/null && command -v g++ &> /dev/null; then
    echo -e "C++ compiler and CMake found. Building engine from source..."
    mkdir -p engine/build
    cd engine/build
    cmake .. -DCMAKE_BUILD_TYPE=Release
    make -j$(nproc)
    cd ../..
    
    # Copy compiled binaries to root
    if [ -f "engine/build/lattice_cli" ]; then
        cp engine/build/lattice_cli ./lattice_cli
        cp engine/build/liblattice_engine.so ./liblattice_engine.so || true
        compiled=true
        echo -e "${GREEN}C++ compilation successful!${NC}"
    fi
else
    echo -e "${YELLOW}Warning: CMake or g++ not found. Skipping source build.${NC}"
fi

if [ "$compiled" = false ]; then
    echo -e "${RED}Error: Cannot compile C++ engine. C++ CLI is required for Linux execution.${NC}"
    echo -e "Please install build tools: sudo apt install build-essential cmake libzstd-dev"
    exit 1
fi

# 4. Set up symbolic link for CLI execution
echo -e "\n${YELLOW}[3/3] Setting up CLI path...${NC}"
current_dir=$(pwd)

echo -e "Would you like to install the 'lattice_cli' symlink globally to /usr/local/bin? (y/n)"
read -r choice
if [[ "$choice" =~ ^[Yy]$ ]]; then
    echo "Creating symlink (may prompt for sudo password)..."
    sudo ln -sf "${current_dir}/lattice_cli" /usr/local/bin/lattice_cli
    echo -e "${GREEN}Successfully created symlink: /usr/local/bin/lattice_cli${NC}"
else
    echo -e "To run the CLI, execute: ${CYAN}${current_dir}/lattice_cli${NC}"
    echo -e "Or add it to your PATH: export PATH=\$PATH:${current_dir}"
fi

echo -e "\n${CYAN}==========================================${NC}"
echo -e "${GREEN}  Installation Completed Successfully!${NC}"
echo -e "  - Run 'lattice_cli --help' to verify the CLI"
echo -e "  - Run '.venv/bin/python' to use the Python API"
echo -e "${CYAN}==========================================${NC}"
