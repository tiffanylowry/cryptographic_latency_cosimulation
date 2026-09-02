#!/bin/bash
# build_ns3_federate.sh
# Compile the NS-3 HELICS co-simulation federate.
# Requires NS-3 with helics module built (run 04_install_ns3.sh + 05_install_helics_ns3.sh).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NS3_DIR="${NS3_DIR:-$HOME/cosim/src/ns-3.39}"

if [ ! -f "$NS3_DIR/build/lib/libns3.39-helics.so" ]; then
    echo "ERROR: NS-3 helics module not found at $NS3_DIR/build/lib/"
    echo "Run install/04_install_ns3.sh and install/05_install_helics_ns3.sh first."
    exit 1
fi

echo "Building ns3_cosim..."
echo "  NS3_DIR: $NS3_DIR"

# Symlink source into NS-3 scratch directory. ns3_cosim.cc #includes
# "crypto/crypto_benchmarks.h" (Phase 3) via a path relative to itself, so
# the crypto/ directory needs its own symlink alongside the .cc file —
# NS-3's single-file scratch build only auto-includes the scratch/
# directory itself, not subdirectories that aren't physically present.
ln -sf "$SCRIPT_DIR/ns3_cosim.cc" "$NS3_DIR/scratch/ns3-cosim.cc"
ln -sf "$SCRIPT_DIR/crypto" "$NS3_DIR/scratch/crypto"

# Build
cd "$NS3_DIR"
./ns3 build 2>&1

# Verify the executable was built
EXEC="$NS3_DIR/build/scratch/ns3.39-ns3-cosim"
if [ -f "$EXEC" ]; then
    echo "Build successful: $EXEC"
else
    echo "ERROR: Expected executable not found at $EXEC"
    exit 1
fi
