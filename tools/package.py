#!/usr/bin/env python3
"""Packs the release zip from build/"sd88me - VST - JV-880" (made by ./build-sdk.sh, release identity) into dist/:
  dist/JV-880-<ver>-VST2-Plugins.zip
    VST2 Plugins/sd88me - VST - JV-880/   the plugin (arm32 + arm64 .so), its skin, an empty jv880-roms/roms/ for your ROMs
    install-force.sh, plugin_list.awk      the installer for the Force and other MPCs that list plugins in MPC.settings
    INSTALL.txt, ROMS.md
No ROM, firmware or expansion-card data is included (copyrighted Roland firmware: bring your own, docs/ROMS.md)."""
import json, os, stat, sys, zipfile
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
VER = json.load(open(os.path.join(ROOT, "plugin.json")))["version"]
NAME = "sd88me - VST - JV-880"
DIST = os.path.join(ROOT, "dist")
STAMP = (2026, 11, 10, 0, 0, 0)

INSTALL = """JV-880 %(v)s for MPC and Force

Needs your own JV-880 ROMs (firmware v1.0.0). They are not included: see ROMS.md.

A) MPC Live III and other MPCs that load plugin folders from "VST2 Plugins":
   1. Copy the folder "VST2 Plugins/%(n)s" into a folder named exactly "VST2 Plugins" at the root of a drive the MPC can
      see (internal storage, SD card or USB drive).
   2. Put your ROMs in its jv880-roms/roms/ folder (expansion cards in jv880-roms/roms/expansions/). Upgrading from 1.x:
      copy the jv880-roms folder (and jv880-favourites.dat, if you have one) from the old plugin folder.
   3. Preferences > Enhancements: Enable Enhancements and VST2 Support must be on. Restart the MPC.
   4. Add "JV-880" to a track from the plugin browser (External VST Plugins).

B) Force and other MPCs that list plugins in MPC.settings (needs root shell access to the device):
   scp -r <this unzipped folder> root@<device-ip>:/tmp/jv880
   ssh root@<device-ip> sh /tmp/jv880/install-force.sh
   This stops the MPC (save your project first), copies the plugin to /sdcard/Synths, backs up and edits MPC.settings,
   and restarts the MPC. A JV-880 1.x install is upgraded in place: your ROMs, expansion cards and favourites are kept.
   Then add "JV-880" to a track from the plugin browser.

Projects saved with JV-880 1.x load in 2.0 with their patch and edits.
To upgrade later, replace the plugin folder but keep jv880-roms/ and jv880-favourites.dat.
More: https://github.com/sd88me/mpc-vst-jv880
"""

ROMS_README = """Put your own JV-880 ROMs here (firmware v1.0.0): jv880_rom1.bin, jv880_rom2.bin, jv880_waverom1.bin,
jv880_waverom2.bin, jv880_nvram.bin. SR-JV80 expansion cards go in expansions/. Details: ROMS.md in the release zip.
"""


def zinfo(arc, mode):
    zi = zipfile.ZipInfo(arc, STAMP)
    zi.external_attr = (stat.S_IFREG | mode) << 16
    zi.compress_type = zipfile.ZIP_DEFLATED
    return zi


def add_tree(z, src, arc):
    for d, _, files in os.walk(src):
        for f in sorted(files):
            if f.endswith(":Zone.Identifier"):
                continue
            full = os.path.join(d, f)
            rel = os.path.join(arc, os.path.relpath(full, src)).replace(os.sep, "/")
            mode = stat.S_IMODE(os.stat(full).st_mode)
            z.writestr(zinfo(rel, 0o755 if mode & 0o100 else 0o644), open(full, "rb").read())


def main():
    src = os.path.join(ROOT, "build", NAME)
    if not os.path.isdir(src):
        sys.exit("missing %s: run ./build-sdk.sh first" % src)
    meta = json.load(open(os.path.join(src, "plugin.json")))
    if "Beta" in meta["name"] or meta["uid"] != "JV88":
        sys.exit("%s is not the release identity (name %s, uid %s)" % (src, meta["name"], meta["uid"]))
    for d, _, files in os.walk(src):   # never ship ROM data
        for f in files:
            if f.endswith(".bin"):
                sys.exit("refusing to package %s: ROM data" % os.path.join(d, f))
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "JV-880-%s-VST2-Plugins.zip" % VER)
    base = "VST2 Plugins/" + NAME
    with zipfile.ZipFile(out, "w") as z:
        add_tree(z, src, base)
        z.writestr(zinfo(base + "/jv880-roms/roms/PUT-YOUR-ROMS-HERE.txt", 0o644), ROMS_README)
        z.writestr(zinfo(base + "/jv880-roms/roms/expansions/PUT-SR-JV80-CARDS-HERE.txt", 0o644), "SR-JV80 expansion card images (.bin).\n")
        z.writestr(zinfo(base + "/LICENSE", 0o644), open(os.path.join(ROOT, "LICENSE"), "rb").read())
        z.writestr(zinfo("INSTALL.txt", 0o644), INSTALL % {"v": VER, "n": NAME})
        z.writestr(zinfo("ROMS.md", 0o644), open(os.path.join(ROOT, "docs", "ROMS.md"), "rb").read())
        z.writestr(zinfo("install-force.sh", 0o755), open(os.path.join(ROOT, "tools", "install-force.sh"), "rb").read())
        z.writestr(zinfo("plugin_list.awk", 0o644), open(os.path.join(ROOT, "tools", "plugin_list.awk"), "rb").read())
    print(out, "%.1f MB" % (os.path.getsize(out) / 1e6))


if __name__ == "__main__":
    main()
