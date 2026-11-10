#!/bin/sh
# Registers JV-880 2 Beta (uid JV8B = 4a563842) in MPC.settings. Run with MPC stopped:  sh jv2_register.sh [dry]
SET=/data/Settings/MPC/MPC.settings
FILE="/sdcard/Synths/sd88me - VST - JV-880 2 Beta/VST/jv8802beta-arm32.so"
cat > /tmp/jv2.entry <<EOF
<PLUGIN name="JV-880 2 Beta" descriptiveName="JV-880 2 Beta" format="VST" category="Synth" manufacturer="sd88me" version="1.0" file="$FILE" uid="4a563842" isInstrument="1" fileTime="0" infoUpdateTime="0" numInputs="0" numOutputs="2" isShell="0"/>
EOF
OUT=/tmp/jv2.settings.new
awk -v mode=add -v file="$FILE" -v uid=4a563842 -v entryfile=/tmp/jv2.entry -v listkey=pluginList-arm -f /tmp/plugin_list.awk "$SET" > $OUT || exit 1
n=$(grep -c "file=\"$FILE\"" $OUT); u=$(grep -c ' uid="4a563842"' $OUT)
echo "entries by file: $n, by uid: $u"
[ "$n" = 1 ] && [ "$u" = 1 ] || { echo "bad edit, nothing changed"; exit 1; }
grep -q '</PROPERTIES>' $OUT || { echo "lost root element"; exit 1; }
[ "$1" = dry ] && { echo "dry run ok"; exit 0; }
cp "$SET" "$SET.bak-jv2-$(date +%Y%m%d-%H%M%S)" && mv $OUT "$SET" && echo registered
