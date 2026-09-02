#!/bin/bash
# build_comm_federate.sh
# Compile the standalone communication delay federate.
# Requires HELICS to be installed and setup_env.sh sourced.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HELICS_DIR="${HELICS_DIR:-/usr/local}"

if [ ! -d "$HELICS_DIR/include/helics" ]; then
    echo "ERROR: HELICS headers not found at $HELICS_DIR/include/helics"
    echo "Run 02_install_helics.sh first, then: source ../install/setup_env.sh"
    exit 1
fi

echo "Building comm_delay_federate..."
echo "  HELICS_DIR: $HELICS_DIR"

g++ -std=c++17 -O2 \
    -I"$HELICS_DIR/include" \
    -L"$HELICS_DIR/lib" \
    -Wl,-rpath,"$HELICS_DIR/lib" \
    -o "$SCRIPT_DIR/comm_delay_federate" \
    "$SCRIPT_DIR/comm_delay_federate.cpp" \
    -lhelicscpp

echo "Build successful: $SCRIPT_DIR/comm_delay_federate"
