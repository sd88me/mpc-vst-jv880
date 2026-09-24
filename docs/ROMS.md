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
`module_dir` is whatever `wrapper/vst2_wrap.c` was built with (`vst.json`'s `defines.MODULE_DIR`,
currently `/sdcard/vst/jv880-roms`). So on the device:

```
/sdcard/vst/jv880-roms/roms/jv880_rom1.bin
/sdcard/vst/jv880-roms/roms/jv880_rom2.bin
/sdcard/vst/jv880-roms/roms/jv880_waverom1.bin
/sdcard/vst/jv880-roms/roms/jv880_waverom2.bin
/sdcard/vst/jv880-roms/roms/jv880_nvram.bin        (optional)
```

Stage these yourself (scp/USB/MPC's own file browser) before first loading the plugin. Nothing in
`tools/build_port.sh` or the release packager touches this path -- it's entirely separate from the
`.so` and skin, same as any other user-supplied content on MPC.

## Expansion cards (SR-JV80)

Optional, and multiple cards can be loaded at once. Place them in:

```
/sdcard/vst/jv880-roms/roms/expansions/
```

Filenames must contain `SR-JV80` (case-insensitive), e.g. `SR-JV80-01_Pop.bin`,
`SR-JV80-04_Vintage_Synth.bin`. They're auto-unscrambled on first load, with a patch cache
(`patch_cache.bin`, written next to the ROMs) speeding up subsequent loads. Supported:

- 8 MB cards: SR-JV80-01 through SR-JV80-19 (Pop, Orchestral, Piano, Vintage Synth, World, Dance, etc.)
- 2 MB cards: SR-JV80-97, 98, 99 (Experience series)

## Changing `MODULE_DIR`

If `/sdcard/vst/jv880-roms` doesn't suit your device's storage layout, edit `defines.MODULE_DIR` in
`vst/vst.json` (a plain C string literal, e.g. `"\"/media/somewhere/jv880-roms\""`) and rebuild --
it's compiled in, not read from a config file at runtime.
