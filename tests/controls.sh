#!/usr/bin/env bash
# Real-time checks of the patch / bank controls (tests/controls_test.cpp): a fast Q-Link turn on PATCH, the bank value, a PATCH step
# after browsing a bank on BANKS, patch tiles. Runs in real time against the plugin's own worker thread. Must print OK.
# JV_ROMS: a folder with the five ROM files and expansions/ (default ~/roms/jv880). JV_SRC: the source tree to build (default: this one).
set -euo pipefail
cd "$(dirname "$0")/.."
here="$(pwd)"
SDK="${MPC_SDK:-$(cd "$here/.." && pwd)/mpc-plugin-builder-sdk}"
ROMS="${JV_ROMS:-$HOME/roms/jv880}"
SRC="${JV_SRC:-$here}"
T="${JV_BUILD:-build/controls}"; mkdir -p "$T"
objs=()
for f in "$SRC"/src/*.cpp "$here/tests/controls_test.cpp"; do
  o="$T/$(basename "$f" .cpp).o"; objs+=("$o")
  g++ -O2 -g -std=c++17 -pthread -w -DJV_TEST -I"$SDK/framework" -I"$SRC/src" -c "$f" -o "$o" &
done
wait
g++ -pthread -o "$T/controlstest" "${objs[@]}" -lm
pf="$(mktemp -d)"; trap 'rm -rf "$pf"' EXIT
mkdir -p "$pf/jv880-roms"; cp -r "$ROMS" "$pf/jv880-roms/roms"; cp "$SRC/plugin.json" "$pf/"
# A first start writes the patch cache; the test then runs as every later start does, with each card read from its file on first use.
MPC_PLUGIN_FOLDER="$pf" "$T/controlstest" warm >/dev/null 2>&1 || { echo "the plugin did not come up (ROMs in $ROMS?)" >&2; exit 1; }
MPC_PLUGIN_FOLDER="$pf" "$T/controlstest" 2>&1 | grep -v '^JV880 v2\|^\[JV'
exit "${PIPESTATUS[0]}"
