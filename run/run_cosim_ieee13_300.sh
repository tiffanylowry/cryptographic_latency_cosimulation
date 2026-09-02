#!/bin/bash
# run_cosim_ieee13_300.sh
# Phase 4: launch the full-scale 300-house AMI co-simulation:
#   1. HELICS broker
#   2. GridLAB-D federate (IEEE-13 + 300 houses)
#   3. NS-3 federate (4-tier CSMA/P2P hierarchy + demand response controller)

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$PROJECT_DIR/output"
NS3_DIR="${NS3_DIR:-$HOME/cosim/src/ns-3.39}"
NS3_EXEC="$NS3_DIR/build/scratch/ns3.39-ns3-cosim-300"

if [ -f "$PROJECT_DIR/install/setup_env.sh" ]; then
    source "$PROJECT_DIR/install/setup_env.sh"
fi

NUM_FEDERATES=2

CRYPTO_ENABLED="${CRYPTO_ENABLED:-}"
CRYPTO_CONFIG="${CRYPTO_CONFIG:-crypto/crypto_config_300.txt}"
CRYPTO_ARGS=""
if [ -n "$CRYPTO_ENABLED" ]; then
    CRYPTO_ARGS="--crypto-enabled=$CRYPTO_ENABLED"
fi

echo "============================================"
echo "  HELICS Co-Simulation: Phase 4 (300-house AMI)"
echo "============================================"
echo "  Project dir:  $PROJECT_DIR"
echo "  NS-3 exec:    $NS3_EXEC"
echo "  Federates:    $NUM_FEDERATES"
echo "  Duration:     3600s (1 hour simulated)"
echo "  Crypto:       ${CRYPTO_ENABLED:-<unset, use crypto_config_300.txt default>}"
echo "============================================"
echo ""

if [ ! -f "$NS3_EXEC" ]; then
    echo "ERROR: NS-3 federate not built. Run: bash ns3/build_ns3_federate_300.sh"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

cleanup() {
    echo ""
    echo "Cleaning up..."
    kill "$BROKER_PID" "$GLD_PID" "$NS3_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT

echo "[1/3] Starting HELICS broker..."
helics_broker -f "$NUM_FEDERATES" --loglevel=warning --name=mainBroker300 &
BROKER_PID=$!
echo "      Broker PID: $BROKER_PID"
sleep 2

echo "[2/3] Starting GridLAB-D federate..."
cd "$PROJECT_DIR/gridlabd"
gridlabd ieee13_300house_helics.glm &
GLD_PID=$!
echo "      GridLAB-D PID: $GLD_PID"

echo "[3/3] Starting NS-3 federate..."
cd "$PROJECT_DIR/ns3"
export LD_LIBRARY_PATH="$NS3_DIR/build/lib:${LD_LIBRARY_PATH:-}"
"$NS3_EXEC" --config=ns3_federate_config_300.json --output="$OUTPUT_DIR/" \
    --crypto-config="$CRYPTO_CONFIG" --topology-config=topology_config.txt $CRYPTO_ARGS &
NS3_PID=$!
echo "      NS-3 PID: $NS3_PID"

echo ""
echo "All federates launched. Waiting for simulation to complete..."
echo ""

GLD_EXIT=0
NS3_EXIT=0
BROKER_EXIT=0

wait "$GLD_PID" || GLD_EXIT=$?
echo "GridLAB-D exited (code $GLD_EXIT)"

wait "$NS3_PID" || NS3_EXIT=$?
echo "NS-3 federate exited (code $NS3_EXIT)"

wait "$BROKER_PID" || BROKER_EXIT=$?
echo "Broker exited (code $BROKER_EXIT)"

trap - EXIT

echo ""
echo "============================================"
echo "  Simulation Complete"
echo "============================================"
echo "  GridLAB-D exit:  $GLD_EXIT"
echo "  NS-3 exit:       $NS3_EXIT"
echo "  Broker exit:     $BROKER_EXIT"
echo ""
echo "  Output log: $OUTPUT_DIR/comm_federate_log_300.csv"
echo "============================================"
