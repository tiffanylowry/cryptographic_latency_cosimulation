#!/bin/bash
# 05_install_helics_ns3.sh
# Install the HELICS NS-3 integration module as an NS-3 contrib module.
# Requires NS-3 (04_install_ns3.sh) and HELICS at /usr/local.

set -euo pipefail

NS3_SRC_DIR="$HOME/cosim/src/ns-3.39"
HELICS_DIR="${HELICS_DIR:-/usr/local}"

if [ ! -d "$NS3_SRC_DIR" ]; then
    echo "ERROR: NS-3 not found at $NS3_SRC_DIR"
    echo "Run 04_install_ns3.sh first."
    exit 1
fi

if [ ! -f "$HELICS_DIR/lib/libhelics.so" ]; then
    echo "ERROR: HELICS C shared library not found at $HELICS_DIR/lib/libhelics.so"
    echo "HELICS must be installed with C shared library support."
    exit 1
fi

echo "=== Installing helics-ns3 Module ==="
echo "NS-3 source: $NS3_SRC_DIR"
echo "HELICS:      $HELICS_DIR"

cd "$NS3_SRC_DIR/contrib"

if [ -d "helics" ]; then
    echo "helics-ns3 module already cloned, pulling latest..."
    cd helics && git pull && cd ..
else
    echo "Cloning helics-ns3 module..."
    git clone https://github.com/GMLC-TDC/helics-ns3.git helics
fi

echo "Reconfiguring NS-3 with helics module..."
cd "$NS3_SRC_DIR"
export CMAKE_PREFIX_PATH="$HELICS_DIR:${CMAKE_PREFIX_PATH:-}"
./ns3 configure --build-profile=release --enable-examples

echo "Rebuilding NS-3 with helics module..."
./ns3 build

echo ""
echo "=== helics-ns3 module installed ==="
echo "The module should appear as 'helics' in the contrib modules above."
echo "NS-3 source: $NS3_SRC_DIR"
