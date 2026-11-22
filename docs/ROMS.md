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

All five are needed, with these names. Capitals don't matter (`JV880_ROM1.BIN` works), and files left directly in `jv880-roms/`, or in a
`roms/` folder copied inside `roms/`, are found too. If your files have other names, rename them before copying them over.

When a file is missing or the wrong size, the patch name line says which one (`No jv880_rom2.bin`, or `jv880_rom2.bin: not 256 KB`)
and the header shows `ROM error`.

## Where the plugin folder is

The plugin folder depends on which of the two plugin formats you installed:

| Plugin format | Zip | How it is installed | Plugin folder |
|---|---|---|---|
| **SDK format** (MPC OS 3.10.1 or later) | `JV-880-<version>-mpc-sdk.zip` | By hand: unzip it and copy the folder into `VST2 Plugins` at the root of a drive the MPC can see, then turn on External Plugin Support in Preferences > Enhancements | `VST2 Plugins/sd88me - VST - JV-880/` on that drive |
| **Older format** (MPC OS 3.x before 3.10.1; plugins listed in `MPC.settings`) | `JV-880-<version>-mpc-armv7.zip` (Force, Live, Live II, One, X, Key) or `-mpc-aarch64.zip` (Live III and other 64-bit MPCs) | With the plugin manager app, or by hand over SSH with the zip's `install.sh` (needs root access) | `sd88me - VST - JV-880/` in the Synths folder it was installed to: usually `/sdcard/Synths/` on 32-bit MPCs and `/nvme/Synths/` on 64-bit MPCs |

For example, with the SDK format the first ROM file ends up at:

```
VST2 Plugins/sd88me - VST - JV-880/jv880-roms/roms/jv880_rom1.bin
```

## Copying the files

| Plugin format | How to add the ROMs |
|---|---|
| SDK format | By hand only. Copy the files into the plugin folder's `jv880-roms/roms/` over USB or with the MPC's file browser before you first load the plugin. |
| Older format, installed with the plugin manager | Use its **Your ROMs and files** step, or copy them by hand. |
| Older format, installed with `install.sh` | By hand: over SSH with `scp`, over USB, or with the MPC's file browser. |

About the plugin manager's **Your ROMs and files** step: it checks each file's size and copies it to the right folder.
It recognises the 256 KB file whatever its name and saves it as `jv880_rom2.bin`. The other four must already have
their exact names, because two are 32 KB and two are 2 MB, so only the name tells them apart.

## Upgrading

| Plugin format | What to do so your ROMs stay |
|---|---|
| SDK format | Copy the new folder over the old one: merge it, don't delete the old folder first. `jv880-roms/` and `jv880-favourites.dat` stay. |
| Older format (plugin manager or `install.sh`) | Nothing: an upgrade or uninstall keeps `jv880-roms/` and `jv880-favourites.dat`. |

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
