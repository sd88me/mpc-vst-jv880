# Vendored DSP source

`dsp/` is a vendored copy of [schwung-jv880](https://github.com/charlesvestal/schwung-jv880)'s
`src/dsp/` (a `plugin_api_v2` build of the JV-880 emulator -- H8/300 MCU core + PCM wavetable
synth + libresample, itself derived from Nuked-SC55/juce-jv880), committed directly into this repo
instead of being fetched at build time. This mirrors mpc-vst-dx7's own approach to schwung-dx7,
applied here to schwung-jv880.

- **Vendored from**: https://github.com/charlesvestal/schwung-jv880, commit
  `e907e2b96fc2514ce930390b293540e2655c998b` (`main`, 2026-08-31).
- **License**: the original MAME-derived non-commercial license (inherited from Nuked-SC55/nukeykt
  and juce-jv880/giulioz), this repo's own `LICENSE`, copied verbatim from schwung-jv880's.
- **Our one local change**: `dsp/jv880_plugin.cpp` gained a `next_expansion`/`prev_expansion` pair
  of `set_param` verbs (`v2_jump_to_expansion_step`, mirroring the upstream `v2_jump_to_bank`'s
  one-transition-per-call shape) plus a `current_expansion_name` `get_param` key. Upstream's own
  `jump_to_expansion` takes an absolute index and does its ROM swap (an 8 MB memcpy, plus a
  first-access disk read+unscramble) synchronously and undebounced; this port originally bound it
  directly to a continuously-nudgeable Q-Link knob, and a single touch/turn gesture could fire
  several of those synchronous reloads back to back -- the "hangs on Loading..." bug documented in
  mpc-vst-plugins' `docs/NOTES.md`. The new verbs give the skin a discrete stepper (one arrow tap =
  one call) instead.
- **Second local change**: `v2_load_thread_func`'s two failure paths (ROMs missing, out of memory) no longer
  `delete inst->mcu`. The load thread freed it while `set_param` on the host thread could be between its
  `inst->mcu` check and an `nvram` write (a use-after-free the offline ASan host test hits when no ROMs are
  present, e.g. turning a knob on a unit without the ROMs installed). `destroy_instance` frees it instead.
- **Third local change**: a paginated BANKS-page browser (`browse_bank`/`browse_page` fields on
  `jv880_instance_t`, `v2_bank_patch_count()`/`v2_browse_page_count()` helpers, and `bank_slot_N`/
  `patch_slot_N`/`patch_page_next`/`patch_page_prev`/`patch_page_text` `get_param`/`set_param`
  handlers) for mpc-vst-plugins' `list` skin widget -- a fixed grid of touch tiles, each bound to
  its own VST param (get_param = the tile's live text, set_param = its tap action). `bank_slot_N`
  (22 slots, one per bank) only moves the browse cursor; `patch_slot_N` (28 slots, one page of the
  browsed bank) actually commits via the existing `v2_select_patch`, same as the Bank/Patch
  steppers. Decoupled from `current_patch`/`current_bank` on purpose: picking a bank just changes
  what the patch list shows, it doesn't load anything until a patch tile is tapped.

Everything else in `dsp/` is byte-for-byte upstream.

## Updating from upstream

1. Diff `dsp/jv880_plugin.cpp` against a fresh clone of schwung-jv880 to isolate our local changes
   (or just recreate them -- see each one's description above; the BANKS-page browser is the
   biggest, but still self-contained: two struct fields, two helper functions next to
   `v2_get_bank_for_patch`, and a handful of `get_param`/`set_param` dispatch entries next to the
   existing bank/patch ones).
2. Copy the new upstream `dsp/` over this one, reapply those changes.
3. Update the commit hash above.
4. Rebuild (`./build.sh`), rerun the offline host test (`tools/test_port.sh vst.json` in a sibling
   mpc-vst-plugins checkout), redo a device smoke test with real ROMs before releasing.
