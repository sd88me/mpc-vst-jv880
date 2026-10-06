#!/usr/bin/env bash
# Build JV-880 as an MPC OS VST2 instrument with mpc-vst-plugins' generic port builder (vst.json).
# DSP source is vendored directly in src/dsp/ (see src/VENDORED.md for exactly what it is and
# where it came from) -- no network fetch, fully self-contained given a sibling mpc-vst-plugins
# checkout for the shared wrapper/tools.
#   build/jv880.so                        -> /sdcard/vst/ on the device
#   build/skin/<folder>/                  -> /sdcard/Synths/ on the device
#   build/pluginlist-entry.xml            the <PLUGIN> line for MPC.settings' pluginList-arm
# Needs a sibling checkout of https://github.com/sd88me/mpc-vst-plugins -- set MPC_VST if it's
# not at ../mpc-vst-plugins.
# ROMs are NOT part of the build: copy your own to jv880-roms/roms/ inside the plugin folder on the device
# (see docs/ROMS.md). Not included -- copyrighted Roland firmware.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
MPC_VST="${MPC_VST:-$here/../mpc-vst-plugins}"
[ -x "$MPC_VST/tools/build_port.sh" ] || { echo "need an mpc-vst-plugins checkout (MPC_VST)" >&2; exit 1; }
# MPC OS 2.x skin shape (also read by 3.x); build_port.sh passes it into the skin container.
export SHADOW_SKIN_MPC_OS=2
exec "$MPC_VST/tools/build_port.sh" "$here/vst.json"
