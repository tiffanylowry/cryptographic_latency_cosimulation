#!/bin/bash
# run_cosim_ieee13_300_realistic.sh
# Phase 4 decoupled physics/control cadence scenario (plan Section 6):
# GridLAB-D's own physics timestep and both HELICS configs' period are 1s
# (fine enough to resolve delivery-timing effects), while the aggregator's
# own control-decision cadence is a separate, AMI-plausible 30s (unchanged
# from production's exponential-smoothing DR logic, just a faster tempo).
# This is what makes crypto-induced delivery delay visible in
# total_load_kw/worst_voltage_v without requiring an unrealistically fast
# control period -- see CLAUDE.md's Phase 4 section for the mechanism.
# Does not replace run_cosim_ieee13_300.sh (60s production) or
# run_cosim_ieee13_300_fine.sh (1s stress-test diagnostic).

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$PROJECT_DIR/output"
NS3_DIR="${NS3_DIR:-$HOME/cosim/src/ns-3.39}"
NS3_EXEC="$NS3_DIR/build/scratch/ns3.39-ns3-cosim-300"

if [ -f "$PROJECT_DIR/install/setup_env.sh" ]; then
    source "$PROJECT_DIR/install/setup_env.sh"
fi

NUM_FEDERATES=2
CONTROL_PERIOD="${CONTROL_PERIOD:-30}"
SIM_DURATION="${SIM_DURATION:-3600}"
# Only forwarded if explicitly set -- otherwise the executable auto-derives
# the tau-preserving alpha for whatever --period it's given.
SMOOTHING_ALPHA_ARG=""
if [ -n "${SMOOTHING_ALPHA:-}" ]; then
    SMOOTHING_ALPHA_ARG="--smoothing-alpha=$SMOOTHING_ALPHA"
fi

CRYPTO_ENABLED="${CRYPTO_ENABLED:-true}"
CRYPTO_CONFIG="${CRYPTO_CONFIG:-crypto/crypto_config_300.txt}"
CRYPTO_ARGS=""
if [ -n "$CRYPTO_ENABLED" ]; then
    CRYPTO_ARGS="--crypto-enabled=$CRYPTO_ENABLED"
fi

echo "============================================"
echo "  HELICS Co-Simulation: Phase 4 DECOUPLED CADENCE (realistic)"
echo "============================================"
echo "  Project dir:     $PROJECT_DIR"
echo "  NS-3 exec:       $NS3_EXEC"
echo "  Physics period:  1s (GLM minimum_timestep / HELICS JSON period)"
echo "  Control period:  ${CONTROL_PERIOD}s (aggregator decision cadence)"
echo "  Duration:        ${SIM_DURATION}s simulated"
echo "  Crypto:          ${CRYPTO_ENABLED}"
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
helics_broker -f "$NUM_FEDERATES" --loglevel=warning --name=mainBroker300Realistic &
BROKER_PID=$!
sleep 2

echo "[2/3] Starting GridLAB-D federate (decoupled-cadence GLM)..."
cd "$PROJECT_DIR/gridlabd"
gridlabd ieee13_300house_helics_realistic.glm &
GLD_PID=$!

echo "[3/3] Starting NS-3 federate (control period=${CONTROL_PERIOD}s, duration=${SIM_DURATION}s)..."
cd "$PROJECT_DIR/ns3"
export LD_LIBRARY_PATH="$NS3_DIR/build/lib:${LD_LIBRARY_PATH:-}"
"$NS3_EXEC" --config=ns3_federate_config_300_realistic.json --output="$OUTPUT_DIR/" \
    --crypto-config="$CRYPTO_CONFIG" --topology-config=topology_config.txt \
    --period="$CONTROL_PERIOD" --duration="$SIM_DURATION" $SMOOTHING_ALPHA_ARG $CRYPTO_ARGS &
NS3_PID=$!

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
echo "  Decoupled-Cadence Run Complete"
echo "============================================"
echo "  GridLAB-D exit:  $GLD_EXIT"
echo "  NS-3 exit:       $NS3_EXIT"
echo "  Broker exit:     $BROKER_EXIT"
echo "  Output log: $OUTPUT_DIR/comm_federate_log_300.csv"
echo "============================================"
