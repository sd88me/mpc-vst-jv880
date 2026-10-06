# Design notes: JV-880 as an MPC OS VST2 plugin

## HANDOFF (2026-09-26): skin-redesign-lime branch, real-device feedback pending

Deployed to the device and working end-to-end (BANKS list browses/pages/commits correctly,
uppercase labels, amber/dark-rack palette, blue badge, white titles/pointers -- see the commits
below). Three things flagged live on the device, **not yet fixed, need a screenshot to diagnose
correctly rather than guess** (guessing at visual issues without seeing them has caused rework
before on this port -- see the split-screen saga earlier in this file):

1. **BANKS list tile highlights are inconsistent** -- "some aren't highlighted while some are",
   hard to tell what's selected on the PATCHES side, and "sometimes see a flash of the orange
   highlights". Likely cause (unconfirmed): `list` tiles are pure momentary triggers (`Toggle
   Switch`, springs back next `processReplacing` -- same as every other trigger in this repo), so
   there's no PERSISTENT "this is the current bank/patch" indicator at all, only a brief flash on
   tap. That flash is probably what's being seen as "inconsistent" -- but confirm on a real
   screenshot before changing anything, since the actual bug might be something else (e.g. a
   stale `on` state left set from a `Q-Link` binding, or JUCE's default `Button` focus-ring
   getting confused with the fill colour).
2. **Envelope Q-Link highlights on the TONE pages are too big and overlap other controls.** Not
   yet located precisely -- need a screenshot of a TONE page to see which control (the level
   sliders, the time knobs, or something in `.knob-arc`/`.slider-fill` sizing) is actually
   oversized, and whether it's an `html_art` CSS geometry bug (a `.knob-arc` radius or a
   `.slider-fill` rect computed too large) or a Q-Link *bounds* box drawn oversized (the qlink
   selection outline, not the control's own highlight).
3. Bank-table sizing was CONFIRMED fine as-is (fixed 22-slot grid, matches the real device's max
   of 3 internal + 19 possible SR-JV80 expansions; empty tail slots if fewer are loaded). No
   action needed unless the user wants the cap raised past 19 expansions.

**Next session**: ask for the two screenshots (BANKS tab mid-tap/just-after-tap; a TONE page
showing the envelope overlap) before touching `skin.css` or `layout.conf` again for these three
items. Everything else in this session's work is done and deployed -- see the commit log on
`skin-redesign-lime` (`git log --oneline` in this repo) for the full trail: html_art renderer
pivot, amber/dark-rack palette match to a real JV-880 photo, uppercase labels, and the BANKS
list/pagination feature (see `src/VENDORED.md`'s "Third local change" for the DSP side).

## Revisions after real-device feedback (2026-09-24)

- **Stepper cycling was broken** (`preset_prev`/`preset_next` referenced a "_prev"/"_next" DSP
  convention that doesn't exist) and **bank cycling was missing entirely** -- both fixed using
  mpc-vst-plugins' new `step_of`/`step_delta` and `prev=`/`next=` stepper mechanisms. Verified
  against real ROMs before redeploying.
- **Every tab's Q-Link banks used to show the identical screen.** mpc-vst-plugins' `shadow_skin.py`
  now gives each bank its own screen (frame-based segments); this port's tabs were restructured to
  keep frames atomic per bank (Play/Sends, Patch/FX, Tone/Env/LFO per tone).
  a real BANKS tab (bank/expansion/patch browsing, using the DSP's real `next_bank`/`prev_bank`/
  `jump_to_expansion` verbs) replaced the v1 "dropped entirely" decision -- still not the original
  scrollable list design (no such widget exists on MPC), but no longer nothing.
- **Frame titles now use a real font** (Audiowide, SIL Open Font License, fetched from
  `google/fonts`' GitHub repo -- see `Audiowide-Regular.ttf`) instead of the baked bitmap font,
  via mpc-vst-plugins' new `title_font` mechanism. This is a stand-in for Roland's own proprietary
  panel font (the one with the custom-altered 'A'/'G'), not a recreation of it -- that font wasn't
  something available to source or safely reproduce.
- **Knobs got a dotted arc** instead of a solid ring, closer to the original shadow mockups.

See mpc-vst-plugins' own `docs/NOTES.md` for the full technical detail behind each of these.

## Revisions after a JV-880 hardware reference photo + mpc-vst-plugins' new tooling (2026-09-26)

- **Skin re-themed to match the real unit**: mpc-vst-plugins' new `html_art` renderer (`"art": "html"`
  in vst.json, real CSS/fonts via headless Chromium instead of shadow_art's baked bitmap font)
  replaced the earlier lime-green touchscreen-app palette with the JV-880's actual dark-rack/amber
  look -- amber value arcs/active-states, white Univers frame titles and knob pointers (not amber --
  the real unit's silkscreen and pointer lines are plain white), a genuine green LCD with black text
  for the dot-matrix readouts, uppercase panel labels throughout, and a blue "JV-880" badge (Earth
  Normal font -- a deliberate stylization, not a hardware match: the real logotype is white like
  everything else). See `skin.css`.
- **BANKS tab got the scrollable-list design back.** The "no such widget exists on MPC" limitation
  above is now out of date: mpc-vst-plugins gained a `list` skin widget (a fixed grid, one VST param
  per tile) since that note was written. The BANKS tab is now a 2x11 bank list (left) and a
  paginated 2x14 patch list (right, `patch_page_next`/`patch_page_prev` steps through the browsed
  bank's patches 28 at a time) -- picking a bank only moves the list's browse cursor, tapping a
  patch tile is what actually loads it. New DSP verbs for this in `src/dsp/jv880_plugin.cpp` --
  see `src/VENDORED.md`'s "Third local change". The Bank/Patch steppers from the v1 BANKS design
  were removed from this tab (redundant with the list) but stay on the PLAY tab's top bar.

## Source and architecture

Ported from [`schwung-jv880`](https://github.com/charlesvestal/schwung-jv880) (charlesvestal's
Ableton Move module), not from `giulioz/mini-jv880` (bare-metal Raspberry Pi firmware, no plugin
ABI) or `sd88me/force-jv880` (a MockbaMod Force addon: separate host process + audio-injection tap,
architecturally a poor fit for an in-process VST2 `.so`). schwung-jv880 already implements Schwung's
`plugin_api_v2` (`create_instance`/`on_midi`/`set_param`/`get_param`/`render_block`, all string-keyed)
-- the exact ABI `mpc-vst-plugins/wrapper/vst2_wrap.c` already wraps for Maze Voice, and the same DSP
force-jv880 itself links in verbatim. `src/dsp/` here is `schwung-jv880/src/dsp/*` vendored verbatim
(H8/300 MCU emulator + PCM wavetable synth + libresample), compiled as C++ (`-std=gnu++11`) via
`mpc-vst-plugins/tools/build_port.sh`'s C++ support (added for this port -- see that repo's
docs/NOTES.md). See `src/VENDORED.md` for the exact upstream commit and the one local change made
to it.

`module.json` here is NOT schwung-jv880's own (that one's `chain_params` is a curated 14-key macro
set for Move's Signal Chain slots). This port's `module.json` has a superset -- 211 keys -- covering
the full tone/patch/performance edit surface, since `gen_vst.py`'s `module_params()` reads
`chain_params` generically with no size cap, and `vst2_wrap.c` already calls the DSP's `set_param`/
`get_param` by string key regardless of how many are declared. No custom wrapper was needed.

## Skin: converted from force-jv880's shadow_page.conf

The layout, palette and tab structure come from `force-jv880`'s `addon/shadow_page.conf` (its
Force Shadow touchscreen page, proven on real hardware) via a one-off script
(`tools/convert_shadow_page.py`, which takes a shadow_page.conf path and can be re-run against a
revised source page). Differences from
that source, and why:

- **No `mix.dest_idx` / `mix.gain`.** Force-audio-injection routing (which Audio-In slot to mix
  into) isn't a plugin parameter on MPC -- a VST2 gets its own normal stereo pair, same reasoning as
  `maze-voice/vst/layout.conf`'s own "no DEST / GAIN" comment.
- **Dot-matrix bar moved to the BOTTOM of PLAY/PATCH tabs, not the top.** Force Shadow's version
  lives in its own outer chrome band (y < 86 in shadow coordinates), which MPC skins have no
  equivalent of -- a plugin's whole canvas starts at y=88 with content already touching that edge, no
  spare margin. Content on PLAY/PATCH is compressed 10% (`BODY_SCALE`) to reclaim a strip at the
  bottom instead. TONE 1-4 are already dense (wave/pitch row + 3 envelope columns + 2 LFOs) and
  compressing them further collided labels between sections, so they keep the bar off and stay at
  full scale -- the patch stepper is one Q-Link nudge away on PLAY regardless.
- **BANKS tab dropped for v1.** Its two `list` grids (bank/expansion browser, patch browser) assumed
  Force Shadow's dynamic list widget, which has no VST equivalent -- `mpc-vst-plugins`'s own `list`
  widget binds each tile to its OWN fixed VST parameter, which doesn't fit a scrollable 128-entry
  patch list or a ROM-dependent expansion count unknown at build time. v1 browses by the PATCH
  stepper only (same pattern DX7 already uses on MPC). A paged/fixed-slot browser (N tiles + next/
  prev page, bounded at build time) is the plausible v2 if this turns out to matter in practice.
- **`env` widgets (draggable envelope curves) became bar-graph displays.** MPC's plugin skin format
  has no draggable/curve-drawing widget at all -- confirmed by inspecting real stock skins including
  AIR's own TubeSynth (see `mpc-vst-plugins/docs/NOTES.md`, "No draggable/graph widgets"). Each stage
  becomes a `slider_v` (height = level, live) plus a small time knob below it -- still fully live off
  the real parameters, just not a connected line you can drag.
- **Control name labels use MPC's native `Label` `"type":"Name"` component**, not baked bitmap text.
  The baked 9x9 font (`shadow_art.c`/`render_conf_preview.c`) reads as monospace/shouty even after
  scale and case fixes -- its glyphs are blocky pixel art filling most of their cell, so there's no
  tuning that makes it look like normal proportional type. Native Name labels use MPC's own on-device
  Titillium Web font instead (same mechanism as the existing Value labels), which is genuinely
  proportional. Frame titles and enum option segments (e.g. "Tri"/"Sin"/"Int-a") don't have a single
  parameter index to bind a native label to, so they still use the baked font -- Title Case and a
  tighter scale (see `mpc-vst-plugins/docs/NOTES.md`) at least keep those legible.
- **Q-Links are curated by frame section**, not truncated at 16. A tab with more than 16 controls
  gets several `qlinks "<name>" = ...` banks (nested pages, same tab design, different Q-Link maps
  per `mpc-vst-plugins/docs/PORTING.md`), grouped so each bank reads as one coherent area (e.g. a Tone
  tab's 44 controls split into "Wave/Pitch + Pitch Env" / "Filter Env + Amp Env" / "LFO 1 + LFO 2"
  rather than silently dropping everything past the first section).

## Envelope curves on the Tone pages

A skin can't draw, MPC only shows the frame of a filmstrip that matches a parameter's value (the idea comes from
MPC Plaits and Helm, which draw an ADSR this way from layered strips). The JV-880's four-level envelopes need
more than one parameter per picture, so the plugin computes the curve: `v2_envv_update` in
`src/dsp/jv880_plugin.cpp` turns the viewed tone's levels and times into 32 columns per envelope (the curve's top and
bottom edge inside each column, 0..127) and bumps `display_rev` when they change (`HAS_DISPLAY_REV` in `vst.json`;
the wrapper polls it and tells MPC). Each column is two stacked display-only `meter` strips from
`tools/make_env_strips.py` (`images/env_hi.png`, `images/env_lo.png`: bright fill to the top edge, opaque dim fill
to the bottom edge), so what stays bright is a continuous line with a dim area under it. `env_view_N` (OFF/ON,
`when=` panels in `layout.conf`) shows them: an envelope knob that changes value opens the view for 3 seconds
(`ENVV_TIMEOUT_MS`), and the VIEW toggle pins it open or closes it. A meter frame is at most 128 px high (128 frames
in a strip of at most 16384 px). The `envv_*` values are not saved and a touch on them is ignored.
Not verified: whether opening the view marks a project as changed; the project-load behaviour.

## ROMs

See `docs/ROMS.md`. Not included, not committed -- copyrighted Roland firmware, staged by the user
like any other file, at a path baked in via `vst.json`'s `defines.MODULE_DIR`.

## Status (as of this port's initial build)

Builds clean end-to-end: x86 ASan smoke test (two instances, param round-trip, MIDI->render, chunk
save) and the real armhf cross-build (exports only `move_plugin_init_v2`/`VSTPluginMain`, glibc 2.34
<= device's 2.39). Not yet benched, not yet deployed, no ROMs tested against real audio yet.
