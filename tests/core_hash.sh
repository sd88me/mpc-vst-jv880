#!/usr/bin/env bash
# Bit-exact check of the emulator core (tests/core_hash.cpp): renders a fixed MIDI script offline and compares every scenario's
# hash with the saved baseline. Needs your ROMs: JV_ROMS = a folder with the five jv880_*.bin files and, optionally,
# expansions/SR-JV80-*.bin (default ~/roms/jv880).
#   tests/core_hash.sh            build, render, compare with tests/data/core_hash.baseline
#   tests/core_hash.sh baseline   build, render, save the result as the new baseline
# CXX (default clang++) and CXXFLAGS (default -O2) choose the build; the baseline is only valid for the same compiler and flags.
set -euo pipefail
cd "$(dirname "$0")/.."
ROMS="${JV_ROMS:-$HOME/roms/jv880}"
CXX="${CXX:-clang++}"
OUT="${JV_BUILD:-build/corehash}"
mkdir -p "$OUT" tests/data
# The core as the plugin build compiles it: the src/engine_*.cpp wrappers (without the plugin layer and the resampler).
srcs=()
for f in src/engine_*.cpp; do
  case "$f" in src/engine_jv880.cpp|src/engine_resample.cpp) ;; *) srcs+=("$f") ;; esac
done
# shellcheck disable=SC2086
"$CXX" ${CXXFLAGS:--O2} -std=c++17 -w -Isrc -o "$OUT/core_hash" tests/core_hash.cpp "${srcs[@]}" -lm
"$OUT/core_hash" "$ROMS" ${JV_SCALE:-1} > "$OUT/core_hash.out"
if [ "${1:-}" = baseline ]; then
  cp "$OUT/core_hash.out" tests/data/core_hash.baseline
  echo "baseline saved: $(wc -l < tests/data/core_hash.baseline) lines"
  exit 0
fi
[ -f tests/data/core_hash.baseline ] || { echo "no baseline yet: run tests/core_hash.sh baseline" >&2; exit 1; }
if diff -u tests/data/core_hash.baseline "$OUT/core_hash.out"; then
  echo "core_hash: OK (bit-exact with the baseline)"
else
  echo "core_hash: OUTPUT CHANGED" >&2
  exit 1
fi
