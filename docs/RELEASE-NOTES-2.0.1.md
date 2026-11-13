# JV-880 2.0.1

Fixes to the patch and bank controls, contributed by @anthonytheinventor (#22).

## Fixed
- **A fast Q-Link turn on PATCH no longer jumps to another bank.** It moves one patch a tick, through pauses and at the bottom of the range. A drag, a reset or MIDI still goes straight to the patch it names.
- **BANKS: patch tiles take every tap.** Several tiles no longer stay lit, and a tap is no longer ignored.
- **BANKS: browsing a bank and then stepping PATCH** now continues in the bank on screen, instead of jumping back to the old bank.

## New
- **The bank name in the header takes the data wheel, a Q-Link or a drag**, like the patch name beside it. It steps one bank a tick, going to the bank's first patch. On BANKS the header shows the bank being browsed.

## Install
- `JV-880-2.0.1-mpc-sdk.zip`: one folder for every MPC. Copy it into `VST2 Plugins` (MPC OS 3.10.1 or later). To update, copy it over the old folder (merge it, don't delete the old folder first) so your ROMs in `jv880-roms/` stay.
- `JV-880-2.0.1-mpc-armv7.zip` (Force and other 32-bit MPCs) or `-mpc-aarch64.zip` (Live III and other 64-bit MPCs): run `install.sh` on the device as root. It upgrades in place and keeps your ROMs.

Projects, automation and Q-Link assignments from 2.0.0 carry over. A new parameter (BANK SELECT, index 622) is appended.

**Checked:** offline tests (ASan/UBSan and the real-time controls test), and on an MPC Live III with a beta build of this code.
