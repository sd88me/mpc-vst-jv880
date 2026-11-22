# JV-880 2.0.4

## Fixed
- **Wave number stopped at 128** (#31). On expansion cards with more than 128 waves (Vintage Synth has 255) a wave picked above 128 jumped back to 128. It now goes up to the end of the card's wave table.
- **Bend Down read wrong and, once touched, bent by octaves.** A patch's Bend Down showed a wrong number (A.Piano 1 read 126 instead of 2), and the first move of the control set a bend of 16 to 48 semitones down. It now reads and sets 0 to 48 semitones.
- **A missing ROM file now says which one.** The patch name line shows `No jv880_rom2.bin` (or `jv880_rom2.bin: not 256 KB` for a file of the wrong size) and the header shows `ROM error`, instead of "Loading..." and "ROMs not found". File names are matched without regard to case (`JV880_ROM1.BIN`), and files left in `jv880-roms/` itself or in a `roms/` folder inside `roms/` are found too.

## Install
- `JV-880-2.0.4-mpc-sdk.zip`: one folder for every MPC. Copy it into `VST2 Plugins` (MPC OS 3.10.1 or later). To update, copy it over the old folder (merge it, don't delete the old folder first) so your ROMs in `jv880-roms/` stay.
- `JV-880-2.0.4-mpc-armv7.zip` (Force and other 32-bit MPCs) or `-mpc-aarch64.zip` (Live III and other 64-bit MPCs): run `install.sh` on the device as root. It upgrades in place and keeps your ROMs.

Projects, automation and Q-Link assignments from 2.0.x carry over.

**Checked:** offline tests (ASan/UBSan, the controls test with new Bend Down and wave-number checks, the stall test). Not yet on a device.
