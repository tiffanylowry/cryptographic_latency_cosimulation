#!/bin/bash
# 02_install_helics.sh
# Build and install HELICS v3.5.3 from source.
# Must be run BEFORE GridLAB-D or NS-3 installation.

set -euo pipefail

HELICS_VERSION="v3.6.1"
INSTALL_PREFIX="/usr/local"

echo "=== Building HELICS $HELICS_VERSION ==="
echo "Install prefix: $INSTALL_PREFIX"

cd ~

if [ -d "HELICS" ]; then
    echo "Removing existing HELICS source directory..."
    rm -rf HELICS
fi

git clone --branch "$HELICS_VERSION" --depth 1 https://github.com/GMLC-TDC/HELICS.git
cd HELICS
mkdir -p build && cd build

cmake \
  -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
  -DCMAKE_BUILD_TYPE=Release \
  -DHELICS_BUILD_CXX_SHARED_LIB=ON \
  -DBUILD_SHARED_LIBS=ON \
  ..

make -j"$(nproc)"
make install

echo ""
echo "=== HELICS $HELICS_VERSION installed to $INSTALL_PREFIX ==="
echo ""
echo "Add these to your ~/.bashrc (or run setup_env.sh):"
echo "  export HELICS_DIR=$INSTALL_PREFIX"
echo "  export PATH=\$HELICS_DIR/bin:\$PATH"
echo "  export LD_LIBRARY_PATH=\$HELICS_DIR/lib:\$LD_LIBRARY_PATH"
echo "  export CMAKE_PREFIX_PATH=\$HELICS_DIR:\$CMAKE_PREFIX_PATH"
echo ""
echo "Verify with: helics_broker --version"
echo "Next: run 03_install_gridlabd.sh"
