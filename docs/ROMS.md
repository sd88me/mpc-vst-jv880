# ROMs and expansion cards

**In short:** put your five JV-880 v1.0.0 ROM files, named as below, in `jv880-roms/roms/` inside the plugin folder.
Expansion cards (optional) go in `jv880-roms/roms/expansions/`.

The ROMs are not included anywhere in this repo or its release zips: they are copyrighted Roland firmware, so you need
your own dump. It must be firmware **v1.0.0**. A v1.0.1 dump crashes the emulated CPU and does not run. Without the ROMs
the plugin loads but makes no sound.

## The five files

| File | Size |
|---|---|
| `jv880_rom1.bin` | 32 KB (32,768 bytes) |
| `jv880_rom2.bin` | 256 KB (262,144 bytes) |
| `jv880_waverom1.bin` | 2 MB (2,097,152 bytes) |
| `jv880_waverom2.bin` | 2 MB (2,097,152 bytes) |
| `jv880_nvram.bin` | 32 KB (32,768 bytes) |

All five are needed, with exactly these names. If your files have other names, rename them before copying them over.

## Where the plugin folder is

| How you installed | Plugin folder |
|---|---|
| `-mpc-sdk.zip`, copied into `VST2 Plugins` | `VST2 Plugins/sd88me - VST - JV-880/` on that drive |
| `-mpc-armv7.zip` or `-mpc-aarch64.zip`, with `install.sh` | `sd88me - VST - JV-880/` in the Synths folder the installer used, for example `/sdcard/Synths/` (32-bit MPCs) or `/nvme/Synths/` (64-bit MPCs) |

So the files end up at, for example:

```
VST2 Plugins/sd88me - VST - JV-880/jv880-roms/roms/jv880_rom1.bin
```

## Copying the files

Use either way:

- **By hand:** copy the files over USB, with `scp`, or with the MPC's file browser before you first load the plugin.
  This works for every install type.
- **With the installer:** the `install.sh` zips have a **Your ROMs and files** step. It checks each file's size and
  copies it to the right folder. It recognises the 256 KB file whatever its name and saves it as `jv880_rom2.bin`. The
  other four must already have their exact names, because two are 32 KB and two are 2 MB, so only the name tells them
  apart.

## Upgrading

Your `jv880-roms/` folder is kept when `install.sh` upgrades or uninstalls the plugin. If you update the `-sdk` zip by
hand, copy the new folder over the old one (merge, don't delete the old folder first) so `jv880-roms/` stays.

## Expansion cards (SR-JV80)

These are optional, and you can load several at once. Put the card images in:

```
<plugin folder>/jv880-roms/roms/expansions/
```

The plugin loads a file only if its name contains `SR-JV80` in capitals and ends in `.bin`. Name each file
`SR-JV80-<number>_<name>.bin`, for example `SR-JV80-04_Vintage_Synth.bin`. The BANKS page then shows it as
`04 Vintage Synth`.

Supported cards:

- 8 MB cards: SR-JV80-01 to SR-JV80-19 (Pop, Orchestral, Piano, Vintage Synth, World, Dance and so on)
- 2 MB cards: SR-JV80-97, 98 and 99 (the Experience series)

Cards appear on the BANKS page after the three built-in banks. You can load up to 32 cards, with up to 64 banks in all,
counting the built-in ones.

Only one card is active at a time: the card the current patch comes from. A patch can't use waves from two cards.

### Patch cache

On first load the plugin reads every card and writes `patch_cache.bin` in `jv880-roms/roms/`, so later loads are faster.
The plugin rebuilds the cache when you add, remove or change a card. You can delete it safely.

## Other locations

If `jv880_rom1.bin` isn't in `<plugin folder>/jv880-roms/roms/` but is in `<plugin folder>/Content/jv880-roms/roms/`,
the plugin uses that folder instead.
