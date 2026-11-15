# JV-880 2.0.3

## New
- **Name your favourites.** **+FAV** now opens an on-screen keyboard on the patch's name. Type a name (up to 20 characters; SHIFT, DELETE and SPACE are there) and press **SAVE** to store the patch in the PRESET list under it, or **CANCEL** to close it.

## Fixed
- **Bounce to audio, export and project preview came out as static** (#25). The emulator now gets a moment to catch up when the host renders faster than real time, instead of the missing audio being filled with silence.
- **Patch mode answers on every MIDI channel (omni).** It used to hear channel 1 only, so a track on any other channel was silent. Performance mode keeps its per-part channels.

## Install
- `JV-880-2.0.3-mpc-sdk.zip`: one folder for every MPC. Copy it into `VST2 Plugins` (MPC OS 3.10.1 or later). To update, copy it over the old folder (merge it, don't delete the old folder first) so your ROMs in `jv880-roms/` stay.
- `JV-880-2.0.3-mpc-armv7.zip` (Force and other 32-bit MPCs) or `-mpc-aarch64.zip` (Live III and other 64-bit MPCs): run `install.sh` on the device as root. It upgrades in place and keeps your ROMs.

Projects, automation and Q-Link assignments from 2.0.x carry over.

**Checked:** offline tests (ASan/UBSan, including the keyboard), and the keyboard, a bounce and omni MIDI on an MPC Live III (beta build of the same code).
