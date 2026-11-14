# JV-880 2.0.2

Audio path and expansion-card fixes, contributed by @anthonytheinventor (#24).

## Fixed
- **Fewer clicks and CPU spikes.** The audio buffer holds a whole host block (512 frames on the MPC) plus a margin, so it no longer runs dry on every block. It is lock-free, and the emulator thread now runs below the MPC's own audio threads.
- **Changing to a patch on another expansion card no longer loads the card on the audio thread.** The card is read and switched on the emulator thread, and a knob or wheel sweeping across cards loads only the card it stops on. Cards load faster (the unscramble is table-driven).
- **Stepping the bank arrows quickly** no longer lands on the same card twice.
- **A saved project made while a card is still loading** keeps the patch you picked, not the previous one.
- Parameter edits made while a card loads are ignored instead of being applied to the previous patch and overwritten.
- A malformed MIDI message is ignored.

## Install
- `JV-880-2.0.2-mpc-sdk.zip`: one folder for every MPC. Copy it into `VST2 Plugins` (MPC OS 3.10.1 or later). To update, copy it over the old folder (merge it, don't delete the old folder first) so your ROMs in `jv880-roms/` stay.
- `JV-880-2.0.2-mpc-armv7.zip` (Force and other 32-bit MPCs) or `-mpc-aarch64.zip` (Live III and other 64-bit MPCs): run `install.sh` on the device as root. It upgrades in place and keeps your ROMs.

Projects, automation and Q-Link assignments from 2.0.x carry over.

**Checked:** offline tests (ASan/UBSan, and a bit-exact render of the emulator core), and on an MPC Live III: 17 card loads and a rapid bank-arrow sweep with notes held, no underruns.
