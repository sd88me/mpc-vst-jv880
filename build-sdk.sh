#!/usr/bin/env bash
# Build JV-880 2.0 with the MPC Plugin SDK (tools/build.py, zig): native test build + arm32 (Force, MPC Gen1) + arm64 (Live III and other
# 64-bit units), into build/"sd88me - VST - JV-880"/. The ROMs are not part of the build (copyrighted Roland firmware): the plugin reads
# them from jv880-roms/roms/ inside its folder (docs/ROMS.md).
#   ./build-sdk.sh          build
#   ./build-sdk.sh test     build, the offline ASan/UBSan host test (tests/run.sh, needs your ROMs: JV_ROMS) and the SDK's host_sim
#   ./build-sdk.sh beta     a "JV-880 2 Beta" (uid JV8B) build that installs next to the release: build/beta-project/build/...
# MPC_SDK: the mpc-plugin-builder-sdk checkout.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
SDK="${MPC_SDK:-$HOME/mpc-310-private/mpc-plugin-builder-sdk}"
[ -f "$SDK/tools/build.py" ] || { echo "need the SDK (MPC_SDK)" >&2; exit 1; }
python3 "$here/tools/sdk/gen_sdk_params.py"
[ -f "$here/tools/make_tui.py" ] && python3 "$here/tools/make_tui.py"

# The arm32 .so must load on the Force (MPC OS 3.9, glibc 2.29 or older): fail if it asks for a newer glibc symbol.
glibc_check() {
  local so="$1" max
  max="$(readelf -V "$so" | grep -o 'GLIBC_[0-9.]*' | sed 's/GLIBC_//' | sort -uV | tail -n 1)"
  echo "  $(basename "$so"): newest glibc symbol $max"
  [ "$(printf '%s\n2.29\n' "$max" | sort -V | tail -n 1)" = 2.29 ] || { echo "$so needs glibc $max > 2.29 (the Force)" >&2; exit 1; }
}

if [ "${1:-}" = beta ]; then
  # "JV-880 2 Beta" (uid JV8B): a staging project with its own plugin.json, so it installs next to the release.
  stage="$here/build/beta-project"; rm -rf "$stage"; mkdir -p "$stage"
  ln -s "$here/src" "$stage/src"; [ -d "$here/skins" ] && ln -s "$here/skins" "$stage/skins"
  python3 - "$here/plugin.json" "$stage/plugin.json" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
m.update(name="JV-880 2 Beta", uid="JV8B", file32="VST/jv8802beta-arm32.so", file64="VST/jv8802beta-arm64.so")
json.dump(m, open(sys.argv[2], "w"), indent=2)
PY
  python3 "$SDK/tools/build.py" "$stage" --no-ui --define 'JV_NAME="JV-880 2 Beta"' --define "JV_UID='J','V','8','B'"
  glibc_check "$stage/build/sd88me - VST - JV-880 2 Beta/VST/jv8802beta-arm32.so"
  exit
fi
python3 "$SDK/tools/build.py" "$here" --no-ui
glibc_check "$here/build/sd88me - VST - JV-880/VST/jv880-arm32.so"
if [ "${1:-}" = test ]; then
  "$here/tests/run.sh"
  # host_sim renders far faster than real time, so the engine (its own emulator thread, ROM load in the background) stays silent
  # here: its "silence" WARN is expected. Sound, state and the 1.x chunk are checked in real time by tests/run.sh above.
  scratch="$(mktemp -d)"; trap 'rm -rf "$scratch"' EXIT
  cp "$here/plugin.json" "$scratch/"; mkdir -p "$scratch/jv880-roms"
  [ -d "${JV_ROMS:-$HOME/roms/jv880}" ] && cp -r "${JV_ROMS:-$HOME/roms/jv880}" "$scratch/jv880-roms/roms"
  MPC_PLUGIN_FOLDER="$scratch" "$SDK/.sdk-tools/host_sim" "$here/build/native/jv-880.so" test --notes 60,64,67 --wav "$here/build/test.wav" \
    2>&1 | grep -v '^JV880 v2\|^\[JV'
fi
