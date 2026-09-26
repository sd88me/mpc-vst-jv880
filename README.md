# JV880 Emulator VST Plugin for MPC OS

**JV-880** — a native VST2 instrument for Akai MPC OS standalone devices (MPC Live/One/X/Key,
Force), loaded by MPC's built-in JUCE plugin host with a native touchscreen skin (Q-Links included).

ROM-based PCM rompler emulation via a vendored copy of
[schwung-jv880](https://github.com/charlesvestal/schwung-jv880) (a `plugin_api_v2` build of the
JV-880's H8/300 MCU + PCM wavetable emulator, originally written for Ableton Move — see
`src/VENDORED.md` for exactly what's vendored, from which commit, and our one local source change),
wrapped as an MPC OS VST2 plugin with `mpc-vst-plugins`' shared tooling. The touchscreen skin, tab
layout and colour palette are converted from [force-jv880](https://github.com/sd88me/force-jv880)'s
Force Shadow page — this repo is purely the VST port; `force-jv880` remains the separate
MockbaMod/Force Shadow addon for the Force's own on-device app (a different architecture: a separate
host process with an audio-injection tap, not a VST, no plugin host involved).

This repo is fully self-contained: no third-party source is fetched at build time. The only external
dependency is a sibling checkout of `mpc-vst-plugins` for the shared wrapper/build tooling, same as
every port in that ecosystem.

## Build

Needs a sibling checkout of [mpc-vst-plugins](https://github.com/sd88me/mpc-vst-plugins) (the shared
wrapper, `build_port.sh`, skin tooling) at `../mpc-vst-plugins`, or set `MPC_VST` to point at one.
Docker (with QEMU for arm32v7) is needed by `mpc-vst-plugins`' build pipeline; see its own docs.

```
./build.sh
```

Builds the vendored `src/dsp/` via `mpc-vst-plugins/tools/build_port.sh` — no network fetch. Output
in `build/`: `jv880.so`, the skin folder, and `pluginlist-entry.xml`.

## ROMs (not included)

The JV-880's ROMs and any SR-JV80 expansion cards are copyrighted Roland firmware and are not
included, bundled or committed anywhere in this repo. You need your own dumps, staged yourself on
the device — see [docs/ROMS.md](docs/ROMS.md) for exact filenames, sizes and where MPC expects them
(`/sdcard/vst/jv880-roms/roms/`, baked in via `vst.json`'s `defines.MODULE_DIR`).

## Install (just want it working on your MPC/Force)

No release zip is published for this port yet (ROMs can't legally be bundled, so there's less to
gain from one than DX7's factory-bank zip). Build it yourself with `./build.sh`, then:

```
scp build/jv880.so root@<device-ip>:/sdcard/vst/jv880.so.new
ssh root@<device-ip> 'mv /sdcard/vst/jv880.so.new /sdcard/vst/jv880.so'
scp -r "build/skin/sd88me - VST - JV-880" "root@<device-ip>:/sdcard/Synths/"
```

then register it in `MPC.settings` (`build/pluginlist-entry.xml` has the `<PLUGIN …/>` line —
back up `MPC.settings` first, MPC stopped) and stage your own ROMs per docs/ROMS.md before first
load. See `mpc-vst-plugins`' `docs/PORTING.md`/`.claude/skills/mpc-vst-plugin/SKILL.md` for the full
device workflow (staged `.so` deploys, when a restart is/isn't needed).

## Bank/patch/expansion browsing

The BANKS tab's Bank/Patch steppers reach every loaded bank, including any SR-JV80 expansions found
under `roms/expansions/` — stepping through banks jumps straight to an expansion's first patch, no
separate expansion control needed (see docs/DESIGN-NOTES.md for why that page was simplified down
from an earlier three-control design). All other tabs are capped to one Q-Link bank each, so every
physical knob nudge lands on-screen without any sub-page swiping — busy Tone tabs lose knob access
to some deeper envelope/LFO parameters as a result (still visible and touchable, just not
Q-Link-bound); see docs/DESIGN-NOTES.md for the full rationale.

## Credits

- **Roland** — the original JV-880 hardware and its ROMs (not included; see docs/ROMS.md).
- **[nukeykt](https://github.com/nukeykt)** — the H8/300 MCU + PCM emulation core this traces back
  to (originally written for [Nuked-SC55](https://github.com/nukeykt/Nuked-SC55)).
- **[giulioz](https://github.com/giulioz)** — [mini-jv880](https://github.com/giulioz/mini-jv880) /
  juce-jv880, adapting that core specifically into a standalone JV-880 emulator.
- **[charlesvestal](https://github.com/charlesvestal)** —
  [schwung-jv880](https://github.com/charlesvestal/schwung-jv880), the `plugin_api_v2` build for
  Ableton Move this port vendors directly (see `src/VENDORED.md`).
- **[sd88me](https://github.com/sd88me)** — this MPC OS VST2 port, and
  [force-jv880](https://github.com/sd88me/force-jv880) (the separate Force Shadow addon this skin's
  layout and palette are converted from).

## Status

Builds clean for armhf, confirmed running live on a real Force with all ROMs + 19 SR-JV80 expansions
loaded (4133 patches / 22 banks), audio render and bank/patch browsing both verified against real
hardware. CPU isn't release-benched yet (`tools/bench.sh` understates this port specifically, since
its real work runs on an independently-paced background thread — see `mpc-vst-plugins`'
docs/NOTES.md — so a live on-device sample is needed instead of the synthetic bench number).

[docs/DESIGN-NOTES.md](docs/DESIGN-NOTES.md) has the full port rationale and every deviation from
force-jv880's original shadow page. [docs/ROMS.md](docs/ROMS.md) covers ROM/expansion staging.
[src/VENDORED.md](src/VENDORED.md) covers exactly what's vendored from schwung-jv880 and why.
