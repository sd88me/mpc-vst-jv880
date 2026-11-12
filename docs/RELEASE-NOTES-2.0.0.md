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
- **Wave names**: each TONE page shows the wave's number (counted from 1) and its name from the ROM's wave table, on the
  WAVE title line. The wave number steps one wave at a time with +/− and the data wheel, and stops at the end of its table.
- **WAVES pages**: press a TONE key a third time for that tone's wave list. Tap a name to set the wave, page with the arrows;
  the wave group keys are on the page.
- **More per tone**: cutoff, resonance, filter mode, filter envelope depth, level, pan, pitch envelope depth and amp release.
- **Both device families**: 64-bit MPCs (Live III and others) and 32-bit MPCs (Force, Live, Live II, One, X, Key), plus
  one plugin folder that works on every MPC.
- **Projects saved with 1.x still load** with their patch and edits. The parameter order is unchanged, so automation
  and MIDI control (CC 20–35, NRPN) carry over.

## Install
- `JV-880-2.0.0-mpc-sdk.zip`: for MPCs that load plugin folders from `VST2 Plugins`. Copy the plugin folder there, and put
  your ROMs in its `jv880-roms/roms/`.
- `JV-880-2.0.0-mpc-armv7.zip` (Force and other 32-bit MPCs) and `-mpc-aarch64.zip` (64-bit MPCs): run `install.sh` on the
  device. It needs root shell access. A 1.x install is upgraded in place, and your ROMs, expansion cards and favourites
  are kept.

Your own JV-880 ROMs (v1.0.0) are required and not included; see `docs/ROMS.md`.

## Notes
- One expansion card is active at a time (the one the current patch came from), so a patch cannot mix waves from two cards.
  The wave name is read from the card that is loaded.
- Needs MPC OS 3.x. The new screen uses skin features MPC OS 2.x doesn't have; on 2.x, stay on 1.0.9.
- Tested on an MPC Live III and a Force.
- Favourites are stored in `jv880-favourites.dat` in the plugin folder. Keep it, along with `jv880-roms/`, when you
  replace the folder by hand.
