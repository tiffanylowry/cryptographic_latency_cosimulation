#!/bin/bash
# run_cosim.sh
# Launch the full HELICS co-simulation:
#   1. HELICS broker
#   2. GridLAB-D federate (power distribution)
#   3. Communication delay federate (network effects)
#
# Usage:
#   cd ~/co-sim-project/run   (or wherever this project lives in WSL2)
#   bash run_cosim.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$PROJECT_DIR/output"

# Source environment
if [ -f "$PROJECT_DIR/install/setup_env.sh" ]; then
    source "$PROJECT_DIR/install/setup_env.sh"
fi

NUM_FEDERATES=2

echo "============================================"
echo "  HELICS Co-Simulation: Smart Grid Comms"
echo "============================================"
echo "  Project dir:  $PROJECT_DIR"
echo "  Federates:    $NUM_FEDERATES"
echo "  Duration:     3600s (1 hour simulated)"
echo "============================================"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Cleanup function to kill background processes on exit
cleanup() {
    echo ""
    echo "Cleaning up..."
    kill "$BROKER_PID" "$GLD_PID" "$COMM_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT

# ---- Step 1: Start the HELICS Broker ----
echo "[1/3] Starting HELICS broker..."
helics_broker -f "$NUM_FEDERATES" --loglevel=warning --name=mainBroker &
BROKER_PID=$!
echo "      Broker PID: $BROKER_PID"
sleep 2

# ---- Step 2: Start GridLAB-D Federate ----
echo "[2/3] Starting GridLAB-D federate..."
cd "$PROJECT_DIR/gridlabd"
gridlabd residential_feeder.glm &
GLD_PID=$!
echo "      GridLAB-D PID: $GLD_PID"

# ---- Step 3: Start Communication Delay Federate ----
echo "[3/3] Starting communication delay federate..."
cd "$PROJECT_DIR/ns3"
./comm_delay_federate comm_federate_config.json &
COMM_PID=$!
echo "      Comm federate PID: $COMM_PID"

echo ""
echo "All federates launched. Waiting for simulation to complete..."
echo ""

# Wait for federates to finish
GLD_EXIT=0
COMM_EXIT=0
BROKER_EXIT=0

wait "$GLD_PID" || GLD_EXIT=$?
echo "GridLAB-D exited (code $GLD_EXIT)"

wait "$COMM_PID" || COMM_EXIT=$?
echo "Comm federate exited (code $COMM_EXIT)"

wait "$BROKER_PID" || BROKER_EXIT=$?
echo "Broker exited (code $BROKER_EXIT)"

# Disable cleanup trap since processes already exited
trap - EXIT

echo ""
echo "============================================"
echo "  Simulation Complete"
echo "============================================"
echo "  GridLAB-D exit:  $GLD_EXIT"
echo "  Comm exit:       $COMM_EXIT"
echo "  Broker exit:     $BROKER_EXIT"
echo ""
echo "  Output log: $OUTPUT_DIR/comm_federate_log.csv"
echo "============================================"
