#!/bin/sh
# Installs JV-880 on a Force or another MPC whose MPC OS lists plugins in MPC.settings. Run on the device as root, from the unzipped folder:
#   sh install-force.sh [-y] [-t <synths-dir>]
# Copies "VST2 Plugins/sd88me - VST - JV-880" into a Synths folder (default /sdcard/Synths), backs up MPC.settings, registers the plugin
# and restarts MPC. A JV-880 1.x install (same uid) is upgraded: your ROMs and expansion cards (jv880-roms/) and your favourites
# (jv880-favourites.dat) are carried over, from wherever MPC.settings says the old plugin is. Safe to run again.
set -e
cd "$(dirname "$0")"
NAME='JV-880'; DIR='sd88me - VST - JV-880'; SO='jv880-arm32.so'; UID_HEX='4a563838'
SYNTHS=/sdcard/Synths; YES=0
die() { echo "error: $*" >&2; exit 1; }
while [ $# -gt 0 ]; do
    case "$1" in
        -y) YES=1; shift ;;
        -t) [ -n "$2" ] || die "-t needs a folder"; SYNTHS="$2"; shift 2 ;;
        *) die "usage: sh install-force.sh [-y] [-t <synths-dir>]" ;;
    esac
done
case "$SYNTHS" in /*) ;; *) die "-t must be an absolute path" ;; esac
case "$SYNTHS" in *"&"*|*"|"*|*"\\"*) die "the Synths path may not contain & | or backslash" ;; esac
FILE="$SYNTHS/$DIR/VST/$SO"
if [ -z "$MPC_INSTALL_TEST" ]; then
    [ "$(id -u)" = 0 ] || die "run as root"
    case "$(uname -m)" in armv7*) ;; *) die "this installer is for 32-bit ARM MPCs (Force, Live, Live II, One, X, Key); this device is $(uname -m): see INSTALL.txt (VST2 Plugins folder)" ;; esac
    command -v systemctl >/dev/null || die "systemctl not found"
fi
SETTINGS="${MPC_SETTINGS:-$(ls /media/az01-internal/Settings/*/MPC.settings /data/Settings/*/MPC.settings 2>/dev/null | head -n 1)}"
[ -n "$SETTINGS" ] && [ -f "$SETTINGS" ] || die "MPC.settings not found (not an MPC OS device?)"
[ -f "VST2 Plugins/$DIR/VST/$SO" ] || die "this package is damaged: VST2 Plugins/$DIR/VST/$SO is missing"
mkdir -p "$SYNTHS" || die "cannot create $SYNTHS"
MP=$(df -kP "$SYNTHS" 2>/dev/null | awk 'NR==2 {m = $6; for (i = 7; i <= NF; i++) m = m " " $i; print m}' | sed 's/ /\\040/g')
if [ -n "$MP" ] && MP="$MP" awk '$2 == ENVIRON["MP"] {print $4}' /proc/mounts 2>/dev/null | grep -q '\(^\|,\)noexec\(,\|$\)'; then
    echo "warning: $SYNTHS is on a noexec mount, so MPC will not be able to load this plugin from it. Use the internal drive or an SD card (-t /sdcard/Synths)."
fi

# Where an installed JV-880 keeps its ROMs and favourites: the folder of the .so MPC.settings lists for this uid
# (1.x: <folder>/jv880.so; 2.x: <folder>/VST/jv880-arm32.so), and the target folder itself.
OLD_SO=$(grep -o "file=\"[^\"]*\"[^>]* uid=\"$UID_HEX\"" "$SETTINGS" 2>/dev/null | head -n 1 | sed 's/^file="\([^"]*\)".*/\1/')
OLD_DIR=""
if [ -n "$OLD_SO" ]; then
    OLD_DIR=$(dirname "$OLD_SO")
    [ "$(basename "$OLD_DIR")" = VST ] && OLD_DIR=$(dirname "$OLD_DIR")
fi
NEW="$SYNTHS/$DIR"
echo "Installing $NAME 2:"
echo "  $NEW/ (plugin and skin), and an entry in $SETTINGS"
[ -n "$OLD_DIR" ] && echo "  upgrading the install in $OLD_DIR (ROMs, expansion cards and favourites are kept)"
if [ $YES = 0 ]; then
    printf "MPC will be stopped and restarted. Save your project first. Continue? [y/N] "
    read -r ok; case "$ok" in y|Y|yes) ;; *) echo "cancelled"; exit 1 ;; esac
fi
mpc_service() { if systemctl cat acvs >/dev/null 2>&1; then echo acvs; elif systemctl cat inmusic-mpc >/dev/null 2>&1; then echo inmusic-mpc; else echo acvs; fi; }
mpc_ctl() { if [ -n "$MPC_INSTALL_TEST" ]; then return 0; fi; systemctl "$1" "$(mpc_service)"; }
mpc_ctl stop
trap 'mpc_ctl start' EXIT
if [ -z "$MPC_INSTALL_TEST" ]; then
    i=0; while pidof MPC >/dev/null && [ $i -lt 30 ]; do sleep 1; i=$((i + 1)); done
    pidof MPC >/dev/null && die "MPC did not stop"
fi

# 1. the folder: staged next to the target, the user's files carried over, then swapped in
STAGE="$SYNTHS/.$DIR.new"; OLD="$SYNTHS/.$DIR.old"
rm -rf "$STAGE" "$OLD"
cp -r "VST2 Plugins/$DIR" "$STAGE"
for src in "$NEW" "$OLD_DIR"; do   # the target folder first, then the old install if it lives elsewhere
    [ -n "$src" ] && [ -d "$src" ] || continue
    if [ -d "$src/jv880-roms" ] && [ ! -f "$STAGE/jv880-roms/.carried" ]; then
        rm -rf "$STAGE/jv880-roms"
        if [ "$src" = "$NEW" ]; then mv "$src/jv880-roms" "$STAGE/jv880-roms"; else cp -r "$src/jv880-roms" "$STAGE/jv880-roms"; fi
        : > "$STAGE/jv880-roms/.carried"
        echo "kept your ROMs from $src/jv880-roms"
    fi
    if [ -f "$src/jv880-favourites.dat" ] && [ ! -f "$STAGE/jv880-favourites.dat" ]; then
        cp "$src/jv880-favourites.dat" "$STAGE/jv880-favourites.dat"
        echo "kept your favourites from $src"
    fi
done
rm -f "$STAGE/jv880-roms/.carried"
mkdir -p "$STAGE/jv880-roms/roms/expansions"
if [ -e "$NEW" ]; then mv "$NEW" "$OLD"; fi
mv "$STAGE" "$NEW"
rm -rf "$OLD"

# 2. the plugin-list entry (entries with the same file= or uid, including a 1.x install, are replaced)
BAK="$SETTINGS.bak-jv880-$(date +%Y%m%d-%H%M%S)"
cp "$SETTINGS" "$BAK"
printf '<PLUGIN name="JV-880" descriptiveName="JV-880" format="VST" category="Synth" manufacturer="sd88me" version="2.0" file="%s" uid="%s" isInstrument="1" fileTime="0" infoUpdateTime="0" numInputs="0" numOutputs="2" isShell="0"/>\n' "$FILE" "$UID_HEX" > "$SETTINGS.entry"
awk -v mode=add -v file="$FILE" -v uid="$UID_HEX" -v entryfile="$SETTINGS.entry" -v listkey=pluginList-arm -f plugin_list.awk "$SETTINGS" > "$SETTINGS.new"
rm -f "$SETTINGS.entry"
n=$(grep -c "file=\"$FILE\"" "$SETTINGS.new" || true)
u=$(grep -c " uid=\"$UID_HEX\"" "$SETTINGS.new" || true)
[ "$n" = 1 ] && [ "$u" = 1 ] || { rm -f "$SETTINGS.new"; die "settings edit failed (entries: $n by file, $u by uid); MPC.settings unchanged"; }
grep -q '<PROPERTIES' "$SETTINGS.new" && grep -q '</PROPERTIES>' "$SETTINGS.new" || { rm -f "$SETTINGS.new"; die "edited settings lost their root element; MPC.settings unchanged"; }
mv "$SETTINGS.new" "$SETTINGS"
# 3. the 1.x plugin file in the new folder's root is gone with the old folder; one elsewhere is left in place (not listed any more)
sync
[ -f "$NEW/jv880-roms/roms/jv880_rom1.bin" ] || echo "note: no ROMs yet. Put your JV-880 ROMs in $NEW/jv880-roms/roms/ (see ROMS.md)."
echo "Done. Settings backup: $BAK"
echo "Starting MPC. Add '$NAME' to a track from the plugin browser."
