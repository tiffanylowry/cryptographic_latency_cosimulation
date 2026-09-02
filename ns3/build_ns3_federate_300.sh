#!/bin/bash
# build_ns3_federate_300.sh
# Compile the Phase 4 (300-house AMI) NS-3 HELICS co-simulation federate.
# Requires NS-3 with helics module built (run 04_install_ns3.sh + 05_install_helics_ns3.sh).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NS3_DIR="${NS3_DIR:-$HOME/cosim/src/ns-3.39}"

if [ ! -f "$NS3_DIR/build/lib/libns3.39-helics.so" ]; then
    echo "ERROR: NS-3 helics module not found at $NS3_DIR/build/lib/"
    echo "Run install/04_install_ns3.sh and install/05_install_helics_ns3.sh first."
    exit 1
fi

echo "Building ns3_cosim_300..."
echo "  NS3_DIR: $NS3_DIR"

# Same pattern as build_ns3_federate.sh: symlink source + its crypto/
# include directory into NS-3's scratch/ (the scratch build doesn't
# auto-include subdirectories that aren't physically present next to the
# symlinked source). cosim_topology.h also needs its own symlink for the
# same reason -- it's a sibling header, not inside crypto/.
ln -sf "$SCRIPT_DIR/ns3_cosim_300.cc" "$NS3_DIR/scratch/ns3-cosim-300.cc"
ln -sf "$SCRIPT_DIR/crypto" "$NS3_DIR/scratch/crypto"
ln -sf "$SCRIPT_DIR/cosim_topology.h" "$NS3_DIR/scratch/cosim_topology.h"
ln -sf "$SCRIPT_DIR/cosim_crypto_config.h" "$NS3_DIR/scratch/cosim_crypto_config.h"
ln -sf "$SCRIPT_DIR/cosim_relay.h" "$NS3_DIR/scratch/cosim_relay.h"

# Also build the standalone HELICS-free smoke test if present.
if [ -f "$SCRIPT_DIR/standalone_crypto_topology_test.cc" ]; then
    ln -sf "$SCRIPT_DIR/standalone_crypto_topology_test.cc" "$NS3_DIR/scratch/standalone-crypto-topology-test.cc"
fi

cd "$NS3_DIR"
./ns3 build 2>&1

EXEC="$NS3_DIR/build/scratch/ns3.39-ns3-cosim-300"
if [ -f "$EXEC" ]; then
    echo "Build successful: $EXEC"
else
    echo "ERROR: Expected executable not found at $EXEC"
    exit 1
fi
