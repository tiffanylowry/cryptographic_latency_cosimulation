#!/bin/bash
# 01_install_dependencies.sh
# Install system packages required for HELICS, GridLAB-D, and NS-3
# Run this first on a fresh Ubuntu 22.04 WSL2 instance.

set -euo pipefail

echo "=== Installing system dependencies ==="

sudo apt update && sudo apt upgrade -y

sudo apt install -y \
  build-essential gcc g++ gdb \
  cmake \
  git \
  libboost-dev libboost-filesystem-dev libboost-program-options-dev libboost-test-dev \
  libzmq5 libzmq3-dev \
  autoconf automake libtool \
  python3 python3-dev python3-pip \
  pkg-config \
  libxerces-c-dev \
  libsqlite3-dev \
  libxml2-dev \
  wget curl unzip

echo ""
echo "=== System dependencies installed ==="
echo "Next: run 02_install_helics.sh"
