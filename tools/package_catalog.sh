#!/usr/bin/env bash
# The catalog-shaped release zips, from the release build (build/"sd88me - VST - JV-880", made by ./build-sdk.sh):
#   dist/JV-880-<ver>-mpc-armv7.zip, -mpc-aarch64.zip   per build, made by mpc-vst-plugins' tools/release.py (manifest, install.sh /
#                                                        uninstall.sh, the installer app's ROM step from userfiles.json)
#   dist/JV-880-<ver>-mpc-sdk.zip                       one folder for every MPC (tools/sdk_zip.py), for copying into "VST2 Plugins"
# As 1.x, the .so is jv880.so at the folder root, so the canonical installer upgrades a 1.x install in place; jv880-roms/ (your ROMs)
# and jv880-favourites.dat are user data, kept on upgrade and uninstall. MPC_VST: an mpc-vst-plugins checkout with tools/sdk_zip.py.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
MPC_VST="${MPC_VST:-$HOME/mpc-vst-plugins-postlaunch}"
[ -f "$MPC_VST/tools/release.py" ] && [ -f "$MPC_VST/tools/sdk_zip.py" ] || { echo "need mpc-vst-plugins with tools/sdk_zip.py (MPC_VST)" >&2; exit 1; }
DIR="sd88me - VST - JV-880"; SRC="$here/build/$DIR"
[ -f "$SRC/VST/jv880-arm32.so" ] || { echo "missing $SRC: run ./build-sdk.sh first" >&2; exit 1; }
VER=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$SRC/plugin.json")
python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); sys.exit(0 if m["uid"]=="JV88" and "Beta" not in m["name"] else "not the release identity")' "$SRC/plugin.json"
out="$here/dist"; mkdir -p "$out"
for pair in armv7:arm32:file32 aarch64:arm64:file64; do
  IFS=: read -r cpu so key <<<"$pair"
  st="$here/build/catalog/$cpu"; rm -rf "$st"; mkdir -p "$st/$DIR"
  cp -r "$SRC/Plugin Skins" "$SRC/version.xml" "$st/$DIR/"
  python3 - "$SRC/plugin.json" "$st/$DIR/plugin.json" "$key" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
m.pop("file32", None); m.pop("file64", None)
m[sys.argv[3]] = "jv880.so"
json.dump(m, open(sys.argv[2], "w"), indent=2)
PY
  cp "$SRC/VST/jv880-$so.so" "$st/jv880.so"
  printf '<PLUGIN name="JV-880" descriptiveName="JV-880" format="VST" category="Synth" manufacturer="sd88me" version="%s" file="jv880.so" uid="4a563838" isInstrument="1" fileTime="0" infoUpdateTime="0" numInputs="0" numOutputs="2" isShell="0"/>\n' "$VER" > "$st/entry.xml"
  python3 "$MPC_VST/tools/release.py" --so "$st/jv880.so" --skin "$st/$DIR" --entry "$st/entry.xml" --version "$VER" \
    --user-data jv880-roms --user-data jv880-favourites.dat --user-files "$here/userfiles.json" \
    --repo sd88me/mpc-vst-jv880 --license "MAME license" --id jv-880 \
    --requires "Your own JV-880 ROMs in the plugin folder's jv880-roms/roms/ (see docs/ROMS.md)" \
    --about "Roland JV-880 emulation with a native MPC skin: LCD-screen pages, BANKS browser, live envelopes, favourites in the PRESET list." \
    -o "$st/dist"
  z=$(ls "$st/dist"/*.zip); cp "$z" "$out/JV-880-$VER-mpc-$cpu.zip"
done
python3 "$MPC_VST/tools/sdk_zip.py" "$out/JV-880-$VER-mpc-sdk.zip" "$out/JV-880-$VER-mpc-armv7.zip" "$out/JV-880-$VER-mpc-aarch64.zip"
ls -la "$out"/JV-880-"$VER"-mpc-*.zip
