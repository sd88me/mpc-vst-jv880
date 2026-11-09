# JV-880 2.0.0

A rebuilt plugin with a new screen: JV-880 is now built on Akai's MPC Plugin SDK, with a rack-style panel and backlit LCD screens.

## What's new
- **New screen**:
  - A matte black panel with blue and orange print and red-LED keys.
  - Every value on a backlit LCD, with a big number and a bar graph. Drag it, turn its Q-Link, or use the data wheel.
- **Live envelopes**: each tone's pitch, filter and amp envelopes are drawn on LCD displays, and you can drag the points.
  PLAY has a live ADSR for the envelope macros.
- **RANDOM**: a random patch from any bank, from every page.
- **Favourites in MPC's PRESET list**:
  - **+FAV** saves the current patch with your edits (up to 64).
  - Pick a favourite from the PRESET list on the track or from a pad.
  - **−FAV** removes the favourite that is currently picked.
- **New COMMON page**:
  - Bend, portamento, reverb and chorus in full, with type keys.
  - Tabs: PLAY, BANKS, COMMON, TONE 1–4. Press a TONE key again for that tone's LFOs.
- **More per tone**: cutoff, resonance, filter mode, filter envelope depth, level, pan, pitch envelope depth and amp release.
- **One package for both device families**: 64-bit MPCs (Live III and others) and 32-bit MPCs (Force, Live, Live II,
  One, X, Key).
- **Projects saved with 1.x still load** with their patch and edits. The parameter order is unchanged, so automation
  and MIDI control (CC 20–35, NRPN) carry over.

## Install
Download `JV-880-2.0.0-VST2-Plugins.zip`, unzip it and follow `INSTALL.txt`:
- **MPCs that load plugin folders from `VST2 Plugins`:** copy the plugin folder there and put your ROMs in its
  `jv880-roms/roms/`.
- **Force and other MPCs that list plugins in `MPC.settings`:** run `install-force.sh` on the device. It needs root shell
  access. A 1.x install is upgraded in place, and your ROMs, expansion cards and favourites are kept.

Your own JV-880 ROMs (v1.0.0) are required and not included; see `ROMS.md`.

## Notes
- Tested on an MPC Live III and a Force.
- Favourites are stored in `jv880-favourites.dat` in the plugin folder. Keep it, along with `jv880-roms/`, when you
  replace the folder by hand.
