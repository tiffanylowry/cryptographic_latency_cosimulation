#!/bin/bash
# 03_install_gridlabd.sh
# Build and install GridLAB-D v5.3.0 with HELICS support.
# Requires HELICS to be installed first (run 02_install_helics.sh).

set -euo pipefail

GRIDLABD_VERSION="v5.3.0"
INSTALL_PREFIX="/usr/local"
HELICS_DIR="${HELICS_DIR:-/usr/local}"

if [ ! -d "$HELICS_DIR" ]; then
    echo "ERROR: HELICS not found at $HELICS_DIR"
    echo "Run 02_install_helics.sh first, then source setup_env.sh"
    exit 1
fi

echo "=== Building GridLAB-D $GRIDLABD_VERSION with HELICS ==="
echo "Install prefix: $INSTALL_PREFIX"
echo "HELICS dir:     $HELICS_DIR"

cd ~

if [ -d "gridlab-d" ]; then
    echo "Removing existing GridLAB-D source directory..."
    rm -rf gridlab-d
fi

git clone --branch "$GRIDLABD_VERSION" --depth 1 https://github.com/gridlab-d/gridlab-d.git
cd gridlab-d
git submodule update --init

mkdir -p cmake-build && cd cmake-build

cmake \
  -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGLD_USE_HELICS=ON \
  -DGLD_HELICS_DIR="$HELICS_DIR" \
  ..

cmake --build . -j"$(nproc)" --target install

echo ""
echo "=== GridLAB-D $GRIDLABD_VERSION installed to $INSTALL_PREFIX ==="
echo ""
echo "Add these to your ~/.bashrc (or run setup_env.sh):"
echo "  export GRIDLABD_DIR=$INSTALL_PREFIX"
echo "  export PATH=\$GRIDLABD_DIR/bin:\$PATH"
echo "  export GLPATH=\$GRIDLABD_DIR/share/gridlabd:\$GRIDLABD_DIR/lib/gridlabd"
echo "  export LD_LIBRARY_PATH=\$GRIDLABD_DIR/lib:\$LD_LIBRARY_PATH"
echo ""
echo "Verify with: gridlabd --version"
