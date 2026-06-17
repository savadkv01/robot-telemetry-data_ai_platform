#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] Updating apt packages"
sudo apt update && sudo apt upgrade -y

echo "[2/5] Installing base dependencies"
sudo apt install -y \
  curl gnupg2 lsb-release ca-certificates software-properties-common \
  git build-essential python3-pip python3-venv unzip

echo "[3/5] Preparing ROS2 locale"
sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

echo "[4/5] Creating Python virtual environment"
PROJECT_ROOT="$HOME/robot-telemetry-platform"
mkdir -p "$PROJECT_ROOT"
python3 -m venv "$PROJECT_ROOT/.venv"
source "$PROJECT_ROOT/.venv/bin/activate"
pip install --upgrade pip

if [[ -f "$PROJECT_ROOT/requirements.txt" ]]; then
  echo "[5/5] Installing Python dependencies"
  pip install -r "$PROJECT_ROOT/requirements.txt"
else
  echo "requirements.txt not found at $PROJECT_ROOT. Copy project first, then rerun pip install -r requirements.txt"
fi

echo "WSL base setup completed."
