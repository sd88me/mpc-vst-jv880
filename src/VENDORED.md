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
  one call) instead. Everything else in `dsp/` is byte-for-byte upstream.

## Updating from upstream

1. Diff `dsp/jv880_plugin.cpp` against a fresh clone of schwung-jv880 to isolate our local change
   (or just recreate it -- the whole diff is two new functions, both self-contained: search upstream
   for `v2_jump_to_bank` and add `v2_jump_to_expansion_step` right after it in the same style, then
   wire `next_expansion`/`prev_expansion` into the `set_param` dispatch and `current_expansion_name`
   into `get_param`, alongside the existing `current_expansion` entries).
2. Copy the new upstream `dsp/` over this one, reapply that one change.
3. Update the commit hash above.
4. Rebuild (`./build.sh`), rerun the offline host test (`tools/test_port.sh vst.json` in a sibling
   mpc-vst-plugins checkout), redo a device smoke test with real ROMs before releasing.
