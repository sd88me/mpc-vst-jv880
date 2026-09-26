# JV880 Emulator VST Plugin for MPC OS

**Roland JV-880** as a native VST2 instrument for Akai MPC OS standalone devices (MPC Live/One/X/Key,
Force). It loads in MPC's built-in plugin host and has its own touchscreen skin with Q-Link support.
**JV-880** — a native VST2 instrument for Akai MPC OS standalone devices (MPC Live/One/X/Key,
Force), loaded by MPC's built-in JUCE plugin host with a native touchscreen skin (Q-Links included).

Current release: **v1.0.0** — see [Releases](https://github.com/sd88me/mpc-vst-jv880/releases).

## Features

- JV-880 sample-based (ROM PCM) sound engine, with the JV-880's own reverb and chorus.
- **Play page**: eight macros (cutoff, resonance, filter envelope depth, LFO depth, attack, decay,
  sustain, release), output (octave, patch pan, patch level, tone 1-4 on/off), patch settings (analog
  feel, bend range, portamento, key assign, velocity switch, solo legato) and reverb and chorus,
  all on one screen.
- **Banks page**: a paginated list of every loaded bank and its patches. Tap a bank to browse it, tap a
  patch to load it; the selected bank and the loaded patch stay highlighted. The top strip shows the
  browsed bank, the current patch, the page number and PREV / NEXT paging.
- **Tone 1-4 pages**: wave selection, pitch, pitch/filter/amp envelopes and both LFOs for each tone.
- **SR-JV80 expansion cards** load automatically and appear as extra banks (up to 19 in addition to the
  3 built-in banks; verified with 4133 patches across 22 banks).
- 16 Q-Links per page, following the page you are on.
- Hardware-style panel: dark rack, amber highlights, green dot-matrix LCD, black keycap buttons.

## ROMs (required, not included)

The plugin makes no sound without your own JV-880 ROM dump, which must be **v1.0.0** (v1.0.1 causes
CPU traps in the emulated H8/300 core). The ROMs and any SR-JV80 expansion cards are copyrighted Roland
firmware, so they are not included, bundled or committed anywhere in this repo or its release zip. Stage
them on the device yourself: see [docs/ROMS.md](docs/ROMS.md) for exact filenames, sizes and locations
(`/sdcard/vst/jv880-roms/roms/`, expansions under `roms/expansions/`).

## Requirements

- A first-generation MPC OS standalone device (32-bit ARM: Force, MPC Live / Live II, One, X, Key 61).
  Tested on a Force.
- Root SSH access to the device. Installing plugins this way is unofficial: back up first, use at your
  own risk.

## Install

1. Download `JV-880-1.0.0-mpc-armv7.zip` from the [latest release](https://github.com/sd88me/mpc-vst-jv880/releases/latest)
   and unzip it.
2. Copy the folder to the device and run the installer (it stops MPC, so save your project first):

   ```
   scp -r JV-880-1.0.0 root@<device-ip>:/tmp/
   ssh root@<device-ip> sh /tmp/JV-880-1.0.0/install.sh
   ```

3. Stage your ROMs as described in [docs/ROMS.md](docs/ROMS.md).
4. Add **JV-880** to a track from the plugin browser (Instrument plugins).

The zip's `INSTALL.md` has the manual steps and the uninstall command. Running the installer again
upgrades in place. After replacing the plugin file on a running device, remove and re-insert the plugin
on any track that uses it.

## Build from source

Needs a sibling checkout of [mpc-vst-plugins](https://github.com/sd88me/mpc-vst-plugins) (the shared
wrapper, `build_port.sh`, skin tooling) at `../mpc-vst-plugins`, or set `MPC_VST` to point at one.
Docker (with QEMU for arm32v7) is needed by its build pipeline.

```
./build.sh
```

Output in `build/`: `jv880.so`, the skin folder, and `pluginlist-entry.xml`. No third-party source is
fetched at build time. To deploy by hand:

```
scp build/jv880.so root@<device-ip>:/sdcard/vst/jv880.so.new
ssh root@<device-ip> 'mv /sdcard/vst/jv880.so.new /sdcard/vst/jv880.so'
tar -C build/skin -cf - "sd88me - VST - JV-880" | ssh root@<device-ip> 'tar -C /sdcard/Synths -xf -'
```

A skin-only change needs no MPC restart: re-insert the plugin or reload the project. Registering the
plugin in `MPC.settings` and the rest of the device workflow are in `mpc-vst-plugins`'
`docs/PORTING.md` and `.claude/skills/mpc-vst-plugin/SKILL.md`.

## Status

v1.0.0. Builds clean for armhf and runs on a real Force with all ROMs and 19 SR-JV80 expansions loaded;
audio, bank/patch browsing and Q-Link control are checked on that hardware. CPU is not release-benched
(`tools/bench.sh` understates this port, since its real work runs on an independently-paced background
thread; see `mpc-vst-plugins`' docs/NOTES.md). The release zip was not run through its own installer
on a device before publishing; the plugin and skin it contains are the ones tested.

## Background

The sound engine is a vendored copy of [schwung-jv880](https://github.com/charlesvestal/schwung-jv880),
a `plugin_api_v2` build of the JV-880's H8/300 MCU and PCM wavetable emulator originally written for
Ableton Move. `src/VENDORED.md` lists exactly what is vendored, from which commit, and our local source
changes. It is wrapped as an MPC OS VST2 plugin with `mpc-vst-plugins`' shared tooling.

The screen layout and colour palette started from [force-jv880](https://github.com/sd88me/force-jv880)'s
Force Shadow page, then were reworked for this plugin (the Play/Patch merge, the Banks page and the
palette are specific to this port). This repo is purely the VST port; `force-jv880` remains the separate
MockbaMod/Force Shadow addon for the Force's own on-device app, a different architecture (a separate host
process with an audio-injection tap, not a VST).

More detail: [docs/DESIGN-NOTES.md](docs/DESIGN-NOTES.md) (port rationale and every deviation from the
Force Shadow page), [docs/ROMS.md](docs/ROMS.md) (ROM and expansion staging),
[src/VENDORED.md](src/VENDORED.md) (what is vendored and why).

## Credits

- **Roland**: the original JV-880 hardware and its ROMs (not included; see docs/ROMS.md).
- **[nukeykt](https://github.com/nukeykt)**: the H8/300 MCU + PCM emulation core this traces back to
  (originally written for [Nuked-SC55](https://github.com/nukeykt/Nuked-SC55)).
- **[giulioz](https://github.com/giulioz)**: [mini-jv880](https://github.com/giulioz/mini-jv880) /
  juce-jv880, adapting that core specifically into a standalone JV-880 emulator.
- **[charlesvestal](https://github.com/charlesvestal)**:
  [schwung-jv880](https://github.com/charlesvestal/schwung-jv880), the `plugin_api_v2` build for
  Ableton Move this port vendors directly.
- **[sd88me](https://github.com/sd88me)**: this MPC OS VST2 port, and
  [force-jv880](https://github.com/sd88me/force-jv880).
