#!/usr/bin/env bash
# Offline x86 test under ASan/UBSan (no device): the SDK front end + the real engine and your ROMs, driven by tests/host_test.cpp in
# real time. Must print OK. JV_ROMS: a folder with the five ROM files (default ~/roms/jv880). JV_NAME: the build's name (beta tests).
set -euo pipefail
cd "$(dirname "$0")/.."
SDK="${MPC_SDK:-$(cd "$(dirname "$0")/../.." && pwd)/mpc-plugin-builder-sdk}"
ROMS="${JV_ROMS:-$HOME/roms/jv880}"
python3 tools/sdk/gen_sdk_params.py >/dev/null
# A project chunk saved by the released 1.0.9 build, made from that build's own code and your ROMs (not committed: it holds a factory
# patch's bytes from the Roland ROM).
[ -f tests/data/legacy-1.0.9.chunk ] || JV_ROMS="$ROMS" tests/make_legacy_chunk.sh >/dev/null 2>&1
T=build/test; mkdir -p "$T"
S="-fsanitize=address,undefined -fno-sanitize-recover=undefined -O1 -g -std=c++17 -pthread"
objs=()
for f in src/*.cpp tests/host_test.cpp; do
  o="$T/$(basename "$f" .cpp).o"; objs+=("$o")
  [ "$o" -nt "$f" ] && [ "$o" -nt src/params_gen.h ] && [ "$o" -nt src/dsp/jv880_plugin.cpp ] && continue
  X=""; case "$f" in src/engine_*) X="-fno-sanitize=shift" ;; esac   # the vendored core shifts negative samples on purpose
  g++ $S $X -w -DJV_TEST -DJV_EXPECT_NAME='"JV-880"' -I"$SDK/framework" -Isrc -c "$f" -o "$o" &
done
wait
g++ $S -o "$T/jvtest" "${objs[@]}" -lm
pf="$(mktemp -d)"; trap 'rm -rf "$pf"' EXIT
mkdir -p "$pf/jv880-roms"; cp -r "$ROMS" "$pf/jv880-roms/roms"; cp plugin.json "$pf/"
MPC_PLUGIN_FOLDER="$pf" ASAN_OPTIONS=detect_leaks=1 "$T/jvtest" tests/data/legacy-1.0.9.chunk 2>&1 | grep -v '^JV880 v2\|^\[JV' | tail -${TAIL:-80}
exit "${PIPESTATUS[0]}"
