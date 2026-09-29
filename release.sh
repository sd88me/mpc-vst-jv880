#!/usr/bin/env bash
# Build and package JV-880 as one shareable zip: dist/JV-880-<version>-mpc-armv7.zip.
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
python3 "$MPC_VST/tools/release.py" \
  --so "$here/build/jv880.so" \
  --skin "$here/build/skin/sd88me - VST - JV-880" \
  --entry "$here/build/pluginlist-entry.xml" \
  --version "$VERSION" --user-data jv880-roms \
  --repo sd88me/mpc-vst-jv880 --license "MAME license" --id jv-880 \
  --requires "Your own JV-880 ROMs in the plugin folder's jv880-roms/roms/ (see docs/ROMS.md)" \
  --about "Roland JV-880 emulation with a native MPC skin: BANKS browser, one-page PLAY, tone editors." \
  -o "$here/dist"
