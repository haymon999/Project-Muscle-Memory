#!/bin/sh
# One-tap server starter: Termux (+ Termux:Widget) or any Linux PC.
# First use: set GAME_DIR below to the folder holding this repo.
GAME_DIR="$HOME/muscle-memory"

cd "$GAME_DIR" || { echo "Edit GAME_DIR in this script first."; exit 1; }
termux-wake-lock 2>/dev/null
echo "=== Muscle Memory server on :8080 (keep this running) ==="
if command -v python3 >/dev/null 2>&1; then
  python3 tools/proxy/offline_mock.py
else
  python tools/proxy/offline_mock.py
fi
