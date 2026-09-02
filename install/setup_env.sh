#!/bin/bash
# setup_env.sh
# Source this file to set up environment variables for the co-simulation tools.
# Usage: source setup_env.sh

export HELICS_DIR="${HELICS_DIR:-/usr/local}"
export GRIDLABD_DIR="${GRIDLABD_DIR:-/usr/local}"

export PATH="$HELICS_DIR/bin:$GRIDLABD_DIR/bin:$PATH"
export LD_LIBRARY_PATH="$HELICS_DIR/lib:$GRIDLABD_DIR/lib:${LD_LIBRARY_PATH:-}"
export GLPATH="$GRIDLABD_DIR/share/gridlabd:$GRIDLABD_DIR/lib/gridlabd"
export CMAKE_PREFIX_PATH="$HELICS_DIR:${CMAKE_PREFIX_PATH:-}"

echo "Environment configured:"
echo "  HELICS:    $HELICS_DIR"
echo "  GridLAB-D: $GRIDLABD_DIR"
