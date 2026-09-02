#!/bin/bash
# 04_install_ns3.sh
# Build and install NS-3 v3.36.1 from source.
# Requires system dependencies from 01_install_dependencies.sh.

set -euo pipefail

NS3_VERSION="ns-3.39"
NS3_SRC_DIR="$HOME/cosim/src/ns-3.39"

echo "=== Installing NS-3 $NS3_VERSION ==="
echo "Source dir: $NS3_SRC_DIR"

# Install NS-3-specific dependencies (skip if already installed)
if ! dpkg -l libgsl-dev &>/dev/null; then
    sudo apt install -y libgsl-dev
fi

mkdir -p "$HOME/cosim/src"
cd "$HOME/cosim/src"

if [ -d "$NS3_SRC_DIR" ]; then
    echo "NS-3 source directory already exists, skipping clone."
else
    echo "Cloning NS-3 $NS3_VERSION..."
    git clone --branch "$NS3_VERSION" --depth 1 \
        https://gitlab.com/nsnam/ns-3-dev.git "ns-3.39"
fi

cd "$NS3_SRC_DIR"

echo "Configuring NS-3..."
./ns3 configure --build-profile=release --enable-examples

echo "Building NS-3 (this may take 20-30 minutes)..."
./ns3 build

echo ""
echo "=== NS-3 $NS3_VERSION built successfully ==="
echo "Source: $NS3_SRC_DIR"
echo ""
echo "Verify with: cd $NS3_SRC_DIR && ./ns3 run scratch/scratch-simulator"
echo "Next: run 05_install_helics_ns3.sh"
