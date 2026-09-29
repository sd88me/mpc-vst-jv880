# ROMs and expansion cards

Not included, not bundled, not committed anywhere in this repo or its release zip -- copyrighted
Roland firmware. You need your own JV-880 ROM dump, and it must be **v1.0.0** specifically:
v1.0.1 causes CPU traps in the emulated H8/300 core (see upstream schwung-jv880 and
force-jv880's own notes).

## Required files

Place these in a `roms/` folder:

| File | Size | Required |
|---|---|---|
| `jv880_rom1.bin` | 32 KB | yes |
| `jv880_rom2.bin` | 256 KB | yes |
| `jv880_waverom1.bin` | 2 MB | yes |
| `jv880_waverom2.bin` | 2 MB | yes |
| `jv880_nvram.bin` | 32 KB | no -- falls back to a zeroed NVRAM buffer, and the plugin writes/persists this file itself once you save a patch or performance |

## Where MPC expects them

The DSP (`jv880_plugin.cpp`'s `create_instance`) reads `<module_dir>/roms/<file>`, where
`module_dir` is the folder `jv880-roms` next to the plugin's `.so` (`vst.json`'s `defines.MODULE_SUBDIR`, found at
runtime). With the portable install, where `<Synths>` is `/sdcard/Synths` (or another Synths folder), that is:

```
<Synths>/sd88me - VST - JV-880/jv880-roms/roms/jv880_rom1.bin
<Synths>/sd88me - VST - JV-880/jv880-roms/roms/jv880_rom2.bin
<Synths>/sd88me - VST - JV-880/jv880-roms/roms/jv880_waverom1.bin
<Synths>/sd88me - VST - JV-880/jv880-roms/roms/jv880_waverom2.bin
<Synths>/sd88me - VST - JV-880/jv880-roms/roms/jv880_nvram.bin        (optional)
```

Stage these yourself (scp/USB/MPC's own file browser) before first loading the plugin. Nothing in
`tools/build_port.sh` or the release packager touches this path -- it's entirely separate from the
`.so` and skin, same as any other user-supplied content on MPC.

## Expansion cards (SR-JV80)

Optional, and multiple cards can be loaded at once. Place them in:

```
<Synths>/sd88me - VST - JV-880/jv880-roms/roms/expansions/
```

Filenames must contain `SR-JV80` (case-insensitive), e.g. `SR-JV80-01_Pop.bin`,
`SR-JV80-04_Vintage_Synth.bin`. They're auto-unscrambled on first load, with a patch cache
(`patch_cache.bin`, written next to the ROMs) speeding up subsequent loads. Supported:

- 8 MB cards: SR-JV80-01 through SR-JV80-19 (Pop, Orchestral, Piano, Vintage Synth, World, Dance, etc.)
- 2 MB cards: SR-JV80-97, 98, 99 (Experience series)

## Other locations

The folder is found next to the `.so`, so installing the plugin folder somewhere else (another Synths folder, for
example a card) moves the ROMs with it. `defines.MODULE_DIR` in `vst.json` is only a fallback if the plugin's location
can't be determined (a plain C string literal, compiled in).
