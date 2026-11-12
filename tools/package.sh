#!/usr/bin/env bash
# The release zips. Builds the release identity ("JV-880", uid JV88), runs the offline tests, then packs (tools/package_catalog.sh):
#   dist/JV-880-<ver>-mpc-armv7.zip    Force and other 32-bit MPCs: install.sh (MPC.settings), upgrades 1.x in place
#   dist/JV-880-<ver>-mpc-aarch64.zip  Live III and other 64-bit MPCs, same installer
#   dist/JV-880-<ver>-mpc-sdk.zip      one folder for every MPC, to copy into "VST2 Plugins"
# then SHA256SUMS for the three.
set -euo pipefail
cd "$(dirname "$0")/.."
./build-sdk.sh test
tools/package_catalog.sh
VER=$(python3 -c 'import json; print(json.load(open("plugin.json"))["version"])')
(cd dist && sha256sum "JV-880-$VER-mpc-armv7.zip" "JV-880-$VER-mpc-aarch64.zip" "JV-880-$VER-mpc-sdk.zip" > "JV-880-$VER-SHA256SUMS.txt" && cat "JV-880-$VER-SHA256SUMS.txt")
