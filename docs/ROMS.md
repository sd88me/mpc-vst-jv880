# ROMs and expansion cards

The ROMs are not included, not bundled and not committed anywhere in this repo or its release zips: they are copyrighted
Roland firmware. You need your own JV-880 ROM dump, and it must be **v1.0.0** specifically. A v1.0.1 dump causes CPU
traps in the emulated H8/300 core and does not run.

Without the five files below the plugin loads but makes no sound.

## Required files

Put these five files in the plugin folder's `jv880-roms/roms/` (see [Where to put them](#where-to-put-them)):

| File | Size | Required |
|---|---|---|
| `jv880_rom1.bin` | 32 KB (32,768 bytes) | yes |
| `jv880_rom2.bin` | 256 KB (262,144 bytes) | yes |
| `jv880_waverom1.bin` | 2 MB (2,097,152 bytes) | yes |
| `jv880_waverom2.bin` | 2 MB (2,097,152 bytes) | yes |
| `jv880_nvram.bin` | 32 KB (32,768 bytes) | yes |

The names must match exactly. Dumps found online often use other names, so rename them to the names above.

## Where to put them

The plugin looks in a `jv880-roms` folder **inside its own plugin folder**, wherever that folder is installed:

```
<plugin folder>/jv880-roms/roms/jv880_rom1.bin
<plugin folder>/jv880-roms/roms/jv880_rom2.bin
<plugin folder>/jv880-roms/roms/jv880_waverom1.bin
<plugin folder>/jv880-roms/roms/jv880_waverom2.bin
<plugin folder>/jv880-roms/roms/jv880_nvram.bin
```

If `jv880_rom1.bin` is not there but is in `<plugin folder>/Content/jv880-roms/roms/`, that folder is used instead.

`<plugin folder>` depends on how you installed:

- **`-mpc-sdk.zip`**: `VST2 Plugins/sd88me - VST - JV-880/` on the drive you copied it to.
- **`-mpc-armv7.zip` / `-mpc-aarch64.zip`** (installed with `install.sh`): `sd88me - VST - JV-880/` inside the Synths folder
  the installer used, for example `/sdcard/Synths/` on a 32-bit MPC or `/nvme/Synths/` on a 64-bit one.

How to get the files there:

- **Copy them yourself** (USB, `scp`, or the MPC's file browser) before first loading the plugin. This works for every
  install type.
- **Or let the installer do it.** The `install.sh` zips include a **Your ROMs and files** step (rules in
  `userfiles.json`). It checks each file before copying it into the right folder. It saves the 256 KB program ROM as
  `jv880_rom2.bin` whatever it is called, but `jv880_rom1.bin`, `jv880_nvram.bin`, `jv880_waverom1.bin` and
  `jv880_waverom2.bin` must keep their names (rom1 and nvram are both 32 KB, and the two wave ROMs are both 2 MB, so
  the name is what tells them apart).

The `jv880-roms/` folder is your data: upgrades and uninstalls with `install.sh` keep it. If you update the `-sdk` zip by
hand, copy it over the old folder (merge it, don't delete the old folder first) so `jv880-roms/` stays.

## Expansion cards (SR-JV80)

Optional, and any number can be loaded at once. Put the card images in:

```
<plugin folder>/jv880-roms/roms/expansions/
```

A file is picked up if its name contains `SR-JV80` (upper case, exactly) and ends in `.bin` (any case), for example
`SR-JV80-01_Pop.bin` or `SR-JV80-04_Vintage_Synth.bin`. A bank's name in the browser comes from the part after the
number (`01 Pop`). Supported:

- 8 MB cards: SR-JV80-01 to SR-JV80-19 (Pop, Orchestral, Piano, Vintage Synth, World, Dance and so on)
- 2 MB cards: SR-JV80-97, 98 and 99 (the Experience series)

Each card appears in the **BANKS** page as extra banks after the three built-in ones. The limits are 32 cards, 256 patches
per card and 64 banks in all, counting the built-in banks.

The first load unscrambles each card and writes `patch_cache.bin` next to the ROMs (in `jv880-roms/roms/`). That cache
makes later loads quicker and is rebuilt when the files change, so you can delete it safely.

One card is active at a time (the one the current patch came from), so a patch cannot mix waves from two cards.
