#!/usr/bin/env bash
# Build and package JV-880 as shareable zips: dist/JV-880-<version>-mpc-armv7.zip (Gen1/Force) and -mpc-aarch64.zip (Gen2).
#   ./release.sh <version>            e.g. ./release.sh 1.0.2
# Needs a sibling mpc-vst-plugins checkout (see build.sh); MPC_VST overrides its location.
# The ROMs are the user's own and are not shipped: they live in jv880-roms/roms/ inside the plugin folder
# (--user-data keeps them across upgrades and uninstalls).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
MPC_VST="${MPC_VST:-$here/../mpc-vst-plugins}"
[ -f "$MPC_VST/tools/release.py" ] || { echo "need an mpc-vst-plugins checkout (MPC_VST)" >&2; exit 1; }
VERSION="${1:?usage: release.sh <version>}"
bash "$here/build.sh"
# One zip per CPU, same arguments: Gen1 MPC / Force (armv7) and Gen2 (aarch64, build/aarch64/jv880.so). Both go on the same GitHub release.
for so in "$here/build/jv880.so" "$here/build/aarch64/jv880.so"; do
  [ -f "$so" ] || { echo "missing $so (build.sh builds both targets from vst.json)" >&2; exit 1; }
  python3 "$MPC_VST/tools/release.py" \
    --so "$so" \
    --skin "$here/build/skin/sd88me - VST - JV-880" \
    --entry "$here/build/pluginlist-entry.xml" \
    --version "$VERSION" --user-data jv880-roms \
    --repo sd88me/mpc-vst-jv880 --license "MAME license" --id jv-880 \
    --requires "Your own JV-880 ROMs in the plugin folder's jv880-roms/roms/ (see docs/ROMS.md)" \
    --about "Roland JV-880 emulation with a native MPC skin: BANKS browser, one-page PLAY, tone editors." \
    -o "$here/dist"
done
