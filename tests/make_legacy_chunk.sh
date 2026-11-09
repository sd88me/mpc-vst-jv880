#!/usr/bin/env bash
# Make tests/data/legacy-1.0.9.chunk: what a project saved with the released 1.0.9 build stores (effGetChunk), from that build's own code.
# Builds the v1.0.9 tree (engine + mpc-vst-plugins' wrapper, as released) for x86 as a shared library, loads it like a host, waits for the
# ROMs, picks patch 37, sets CUTOFF (a macro) and PATCH LVL (an NVRAM byte), and saves the chunk. Run once; the output is committed.
# JV_ROMS: a folder with the five ROM files (default ~/roms/jv880). MPC_VST: the mpc-vst-plugins checkout.
set -euo pipefail
cd "$(dirname "$0")/.."
MV="${MPC_VST:-$HOME/mpc-vst-plugins}"
ROMS="${JV_ROMS:-$HOME/roms/jv880}"
W=build/legacy; rm -rf "$W"; mkdir -p "$W/src" "$W/plug/jv880-roms"
git archive v1.0.9 | tar -x -C "$W/src"
ln -s "$ROMS" "$W/plug/jv880-roms/roms"
( cd "$W/src" && python3 "$MV/tools/gen_vst.py" vst.json --params-h >/dev/null )
F="-O1 -g -fPIC -fvisibility=hidden -Wno-unused-parameter -I$W/src/build -I$MV/wrapper -I$W/src/src/dsp -I$W/src/src/dsp/resample"
objs=()
for f in "$W"/src/src/dsp/{jv880_plugin,mcu,mcu_opcodes,pcm}.cpp; do o="$W/$(basename "$f").o"; g++ $F -std=gnu++11 -fno-exceptions -fno-rtti -c "$f" -o "$o"; objs+=("$o"); done
for f in "$W"/src/src/dsp/resample/{resample,resamplesubs,filterkit}.c "$MV/wrapper/vst2_wrap.c" "$MV/adapters/schwung/schwung_engine.c"; do
  o="$W/$(basename "$f").o"; gcc $F -std=gnu11 -c "$f" -o "$o"; objs+=("$o"); done
g++ -shared -o "$W/plug/jv880.so" "${objs[@]}" -lpthread -lm -ldl
g++ -O1 -g -std=c++17 -o "$W/dump" tests/legacy_dump.cpp -ldl -lpthread
"$W/dump" "$W/plug/jv880.so" tests/data/legacy-1.0.9.chunk
