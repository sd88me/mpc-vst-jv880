#!/usr/bin/env bash
# Build JV-880 as an MPC OS VST2 instrument with mpc-vst-plugins' generic port builder (vst.json).
#   vst/build/jv880.so                    -> /sdcard/vst/ on the device
#   vst/build/skin/<folder>/              -> /sdcard/Synths/ on the device
#   vst/build/pluginlist-entry.xml        the <PLUGIN> line for MPC.settings' pluginList-arm
# Needs checkouts of mpc-vst-plugins (MPC_VST) and force-shadow (FORCE_SHADOW) next to mpc-jv880.
# ROMs are NOT part of the build: copy your own to /sdcard/vst/jv880-roms/roms/ on the device
# (see docs/ROMS.md). Not included -- copyrighted Roland firmware.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
MPC_VST="${MPC_VST:-$here/../../mpc-vst}"
[ -x "$MPC_VST/tools/build_port.sh" ] || { echo "need an mpc-vst-plugins checkout (MPC_VST)" >&2; exit 1; }
exec "$MPC_VST/tools/build_port.sh" "$here/vst.json"
