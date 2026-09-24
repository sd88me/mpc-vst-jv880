#!/usr/bin/env python3
"""One-off converter: force-jv880's addon/shadow_page.conf (Force Shadow widget
syntax, proven on real hardware) -> mpc-jv880/vst/{module.json,layout.conf}
(mpc-vst-plugins' shadow_page.conf-derived layout.conf + a matching module.json
chain_params table, since gen_vst.py builds the VST param table from
module.json's chain_params generically -- no size limit, so a full param set
works same as the original curated 14-key one).

Coordinates: mpc-vst's layout.conf uses the SAME absolute shadow-canvas
coordinates as shadow_page.conf itself (y 88..714) -- shadow_skin.py's own
crop step subtracts Y_OFF=86 when baking the final skin PNG, exactly like
maze-voice/vst/layout.conf's "y=88" is left unshifted. (v1 of this script got
this wrong -- shifted everything by -86 itself -- which pushed the whole page
above y=0 and out of the crop entirely; fixed here.)

Force Shadow's own topbar (bank name / patch stepper) lives in its OUTER
CHROME band (y<86), which MPC skins have no equivalent of. There's no spare
margin at y=88 to put an in-canvas copy (content starts right at 88), so
every tab is vertically compressed by BODY_SCALE and a dot-matrix bar is
placed in the reclaimed space at the BOTTOM of the tab instead.

Drops: mix.dest_idx / mix.gain (Force-audio-injection routing; MPC gives a
plugin its own L/R out, no injection routing needed -- same reasoning as
maze-voice/vst/layout.conf's "no DEST / GAIN" comment).
Drops: the two BANKS `list` grids (dynamic 128-entry pagination doesn't fit
mpc-vst's `list` widget, which binds each tile to its OWN fixed VST param).
v1 browses by the PATCH stepper only (same pattern DX7 already uses on MPC).
Converts: each `env` block -> a row of `slider_v` bars (one per envelope
stage's level) + a `knob` per stage's time, i.e. a bar-graph envelope
DISPLAY (live, from real params) rather than a draggable curve.
"""
import json
import os
import re
import shlex
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# Default: a force-jv880 checkout next to this repo (../../force-jv880), overridable by argv[1]
# for re-running this against a revised shadow_page.conf later.
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "force-jv880", "addon", "shadow_page.conf")
OUT_LAYOUT = os.path.join(HERE, "..", "vst", "layout.conf")
OUT_MODULE = os.path.join(HERE, "..", "vst", "module.json")

DROP_KEYS = {"mix.dest_idx", "mix.gain"}

# Original labels are shouting LCD-panel caps ("CUTOFF", "TVF DEPTH"); the baked font has
# lowercase (font8x8.h's font_chars includes a-z) and reads much better in Title Case at a
# tighter scale (see shadow_skin.py's LABEL_SCALE). A short allowlist keeps real acronyms
# (LFO, FXM, TVF...) from being mangled to "Lfo"/"Fxm"/"Tvf" by a plain .title().
ACRONYMS = {"LFO", "FXM", "TVF", "FX", "LFO1", "LFO2"}


def cap(s):
    return " ".join(w if w.upper() in ACRONYMS else w.capitalize() for w in s.split(" "))

# Vertical compression to make room for the bottom dot-matrix bar. BODY_TOP is
# where content already starts (unchanged); everything below it scales toward
# BODY_TOP by BODY_SCALE, then the bar sits in the reclaimed strip at the
# bottom. Original tab bottoms run up to y=724 (PLAY: 430+294=724, TONE: 512+
# 212=724); compressed by 0.9 that's 88+(724-88)*0.9=660.4, leaving 88..714's
# last ~50px for the bar.
BODY_TOP = 88
BODY_SCALE = 0.90
BAR_CY = 690   # absolute shadow y; bar spans 668..712, safely inside the 88..714 crop


def sy(y, scale=BODY_SCALE):
    return round(BODY_TOP + (int(y) - BODY_TOP) * scale)


def sh(h, scale=BODY_SCALE):
    return round(int(h) * scale)


def sr(r, scale=BODY_SCALE):
    return max(14, round(int(r) * scale))


def parse(path):
    tabs, top = [], []
    for raw in open(path):
        line = raw.rstrip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = re.match(r"\[tab (.+)\]$", line.strip())
        if m:
            tabs.append({"name": m.group(1).strip(), "lines": []})
            continue
        if not tabs:
            top.append(line)
            continue
        tabs[-1]["lines"].append(line)
    return tabs, top


def toks(line):
    parts = shlex.split(line)
    w = {"kind": parts[0]}
    for t in parts[1:]:
        k, _, v = t.partition("=")
        w[k] = v
    return w


params = {}   # key -> dict(name,type,min,max,options,default)


def add_param(key, name, kind, **kw):
    if key in DROP_KEYS or key in params:
        return
    p = {"key": key, "name": name}
    if kind == "enum":
        p["type"], p["options"], p["default"] = "enum", kw["options"], kw.get("default", 0)
    elif kind == "toggle":
        p["type"], p["options"], p["default"] = "enum", ["OFF", "ON"], 0
    elif kind == "string":
        # A pure text readout (bank/patch name): the DSP's get_param() returns real text, not a
        # number -- "display":"string" tells gen_vst.py/vst2_wrap.c to pass it through verbatim
        # instead of reformatting via atof() (which mangled it down to "0" -- see docs/NOTES.md).
        p["type"], p["min"], p["max"], p["default"], p["display"] = "int", 0, 0, 0, "string"
    elif kind == "trigger":
        # A momentary DSP verb with no meaningful "value" of its own (e.g. jv880's real
        # next_bank/prev_bank) -- access:"write" makes the wrapper spring it back after firing
        # (docs/PORTING.md) instead of staying visually "pressed".
        p["type"], p["min"], p["max"], p["default"], p["access"] = "int", 0, 1, 0, "write"
    elif kind == "step":
        # A momentary nudge of ANOTHER param by kw["delta"], for a DSP with no native next/prev
        # verb of its own (e.g. jv880's preset has no "next preset", only an absolute set_param) --
        # see gen_vst.py's step_of/step_delta and docs/NOTES.md.
        p["type"], p["min"], p["max"], p["default"], p["access"] = "int", 0, 1, 0, "write"
        p["step_of"], p["step_delta"] = kw["of"], kw["delta"]
    else:
        # Every plain numeric jv880 param is a genuine whole number (MIDI-scale ranges: 0-127,
        # -63..63, -4..4 octave, etc.) -- never fractional -- so force integer display always.
        # Without this a narrow range (e.g. octave, width 8) shows a spurious "0.0" instead of "0"
        # (the wrapper's default heuristic assumes narrow range = fine continuous value).
        p["type"] = "int"
        p["min"], p["max"] = kw.get("min", 0), kw.get("max", 127)
        p["default"] = kw.get("default", kw.get("min", 0))
        p["display"] = "int"
    params[key] = p


# TONE tabs are already dense (WAVE/PITCH row + 3 envelope columns + LFO1/LFO2
# row) with tight gaps even at full scale; compressing them 10%% collided
# labels between sections (verified visually via tools/studio.py preview).
# They keep the PATCH stepper one Q-Link nudge away on PLAY, so skip the bar
# there and use scale=1.0; PLAY/PATCH (lighter tabs, and where users browse
# banks/patches) get the compressed body + bottom bar.
BAR_TABS = {"PLAY", "PATCH"}

out_tabs = []
tabs, top = parse(SRC)
for tab in tabs:
    if tab["name"] == "BANKS":
        continue   # v1: browse by the PATCH stepper only, see module docstring
    scale = BODY_SCALE if tab["name"] in BAR_TABS else 1.0
    def sy(y, scale=scale): return round(BODY_TOP + (int(y) - BODY_TOP) * scale)
    def sh(h, scale=scale): return round(int(h) * scale)
    def sr(r, scale=scale): return max(14, round(int(r) * scale))
    ol = ["[tab %s]" % tab["name"]]
    keyed = []   # ordered (frame_title, key) for every param-bearing widget, for qlink bank grouping
    lines = tab["lines"]
    i = 0
    cur_frame = None         # last frame's SCALED (y, h), for positioning an env block below it
    cur_frame_title = tab["name"]
    while i < len(lines):
        w = toks(lines[i])
        kind = w["kind"]
        if kind == "frame":
            fy, fh = sy(w["y"]), sh(w["h"])
            cur_frame = (fy, fh)
            cur_frame_title = cap(w.get("title", "")) or tab["name"]
            ol.append('frame x=%s y=%d w=%s h=%d title="%s"' % (w["x"], fy, w["w"], fh, cap(w.get("title", ""))))
        elif kind in ("readout", "stepper"):
            pass   # the ORIGINAL topbar (shadow's outer chrome, y<86); replaced per-tab below
        elif kind == "toggle":
            if w["key"] in DROP_KEYS:
                i += 1; continue
            add_param(w["key"], cap(w["label"]), "toggle")
            ol.append('toggle cx=%s cy=%d label="%s" key=%s' % (w["cx"], sy(w["cy"]), cap(w["label"]), w["key"]))
            keyed.append((cur_frame_title, w["key"]))
        elif kind == "button":
            add_param(w["key"], cap(w["label"]), "int", min=0, max=1)
            ol.append('button cx=%s cy=%d label="%s" key=%s' % (w["cx"], sy(w["cy"]), cap(w["label"]), w["key"]))
            keyed.append((cur_frame_title, w["key"]))
        elif kind in ("enum_h", "enum_v"):
            if w["key"] in DROP_KEYS:
                i += 1; continue
            opts = w["options"].split(",")
            opts_disp = [cap(o) for o in opts]
            add_param(w["key"], cap(w.get("label") or w["key"]), "enum", options=opts_disp)
            extra = ""
            if "sw" in w:
                extra += " sw=%s" % w["sw"]
            rows = w.get("rows")
            if not rows and kind == "enum_h" and len(opts) > 6:
                rows = 2   # long option rows (e.g. 8-option REVERB TYPE) wrap instead of crowding
            if rows:
                extra += " rows=%s" % rows
            ol.append('%s cx=%s cy=%d label="%s" key=%s options="%s"%s' %
                       (kind, w["cx"], sy(w["cy"]), cap(w.get("label", "")), w["key"], ",".join(opts_disp), extra))
            keyed.append((cur_frame_title, w["key"]))
        elif kind == "knob":
            if w["key"] in DROP_KEYS or w.get("hidden") == "1":
                # hidden=1: shadow's own dummy companion knob for an `env` block above,
                # whose real widgets (slider_v bars + time knobs) we already emit below.
                i += 1; continue
            add_param(w["key"], cap(w.get("label", w["key"])), "int", min=int(w.get("min", 0)), max=int(w.get("max", 127)))
            ol.append('knob cx=%s cy=%d r=%d label="%s" key=%s' %
                       (w["cx"], sy(w["cy"]), sr(w["r"]), cap(w.get("label", "")), w["key"]))
            keyed.append((cur_frame_title, w["key"]))
        elif kind == "env":
            # Bar-graph envelope DISPLAY: one slider_v per level stage (height = level,
            # live from the real param) plus a small time knob under each bar. No line/
            # curve/drag -- see docs/NOTES.md "No draggable/graph widgets in plugin skins".
            #
            # Positioned relative to the FRAME's own geometry, not the original `env`
            # widget's cx/cy/w/h (tuned for Force Shadow's own live-drawn curve, whose
            # component is just the visible box). A slider_v's COMPONENT bounding box is
            # taller than its visible track (room for the value-label text below), so
            # centering on the old cy pushed that box up past the frame's title/divider
            # and the slider's filmstrip image painted over the title text (found via
            # tools/studio.py preview + comparing sh_bg_N.png before/after compositing).
            cx = int(w["cx"])
            nl = int(w["nl"])
            tkey, lkey = w["tkey"], w["lkey"]
            lmin, lmax = int(w["lmin"]), int(w["lmax"])
            fy, fh = cur_frame
            content_top, content_bottom = fy + 44, fy + fh - 8
            avail = content_bottom - content_top
            bar_w, gap = 34, 18
            total = nl * bar_w + (nl - 1) * gap
            x0 = cx - total // 2
            bar_h = int(avail * 0.5)
            bars_cy = content_top + bar_h // 2
            for s in range(1, nl + 1):
                bx = x0 + (s - 1) * (bar_w + gap) + bar_w // 2
                lk = lkey % s
                add_param(lk, "L%d" % s, "int", min=lmin, max=lmax)
                ol.append('slider_v cx=%d cy=%d w=%d h=%d label="L%d" key=%s' %
                           (bx, bars_cy, bar_w, bar_h, s, lk))
                keyed.append((cur_frame_title, lk))
            knob_r, knob_gap = 18, 16
            knob_ch = (2 * knob_r + 10) // 2 + knob_r + 56   # matches shadow_skin.py's own knob def height
            tk_cy = min(bars_cy + bar_h // 2 + knob_gap + knob_ch // 2, content_bottom - knob_ch // 2)
            tx0 = cx - (nl * 56) // 2
            for s in range(1, nl + 1):
                tk = tkey % s
                add_param(tk, "T%d" % s, "int", min=0, max=127)
                ol.append('knob cx=%d cy=%d r=%d label="T%d" key=%s' %
                          (tx0 + (s - 1) * 56 + 28, tk_cy, knob_r, s, tk))
                keyed.append((cur_frame_title, tk))
        elif kind == "list":
            pass   # dropped tab (BANKS) only; no other tab uses `list`
        i += 1

    # Bottom dot-matrix bar, in the strip reclaimed by BODY_SCALE (PLAY/PATCH only).
    if tab["name"] in BAR_TABS:
        add_param("bank_name", "Bank", "string")
        add_param("patch_name", "Patch Name", "string")
        # max was 127 (an early guess) -- the real total is 4133 with all 19 expansions loaded on
        # THIS device (192 internal + patches per card), and any patch index above the declared max
        # gets CLAMPED there by the step_target mechanism below, which silently snapped an
        # expansion-backed patch (index > 127) back down to 127 -- landing in "Preset B"'s own
        # internal-bank range, so stepping patches looked like it was reverting to a fixed bank.
        # 8191 is generous headroom, not exact -- like expansion_index below, this is a static bound
        # on a device/ROM-set-dependent real count (get_param("total_patches") has the live number).
        add_param("preset", "Patch", "int", min=0, max=8191)
        # No native "next preset"/"prev preset" DSP verb (only an absolute set_param("preset", N)) --
        # nudge "preset" itself by +-1 in the wrapper instead (gen_vst.py's step_of/step_delta).
        add_param("preset_prev", "Patch -", "step", of="preset", delta=-1)
        add_param("preset_next", "Patch +", "step", of="preset", delta=1)
        # bank_index is a dummy (Q-Link nudge on it is a no-op) -- next_bank/prev_bank ARE real DSP
        # verbs, so the arrows call them directly rather than going through the step mechanism.
        add_param("bank_index", "Bank", "int", min=0, max=0)
        add_param("prev_bank", "Bank -", "trigger")
        add_param("next_bank", "Bank +", "trigger")
        # get=bank_name/patch_name: show the real NAME text, not the raw index/dummy each steps
        # (separate parameters -- see shadow_skin.py's stepper "Text" handle).
        ol.append('stepper cx=350 cy=%d w=300 h=44 label="" key=bank_index get=bank_name prev=prev_bank next=next_bank style=dotmatrix persistent=1' % BAR_CY)
        ol.append('stepper cx=775 cy=%d w=490 h=44 label="" key=preset get=patch_name style=dotmatrix persistent=1' % BAR_CY)
    out_tabs.append((ol, keyed))

# BANKS tab: a real bank/expansion/patch browser, dedicated screen -- v1 dropped this entirely
# (dynamic 128-entry list widgets don't fit mpc-vst's `list`, which binds each tile to its OWN
# fixed VST param), but the DSP turns out to have real bank/expansion stepping verbs (see
# docs/DESIGN-NOTES.md), so browsing by number is workable even without a scrollable list.
# Expansion browsing uses next_expansion/prev_expansion (a real DSP verb, added alongside this --
# one bounded transition per call), NOT the absolute jump_to_expansion bound to a knob: jumping
# does a synchronous 8MB memcpy (+ a first-access disk read/unscramble), undebounced, and a
# continuously-nudgeable knob can fire several of those from one touch/turn gesture -- this is
# almost certainly what "banks/patches hanging, says loading emulator" was (found after the fact,
# from that exact symptom). A stepper's arrow tap can only ever fire ONE call.
banks_keyed = []
banks_ol = ["[tab BANKS]"]
banks_ol.append('frame x=36 y=88 w=1208 h=280 title="Bank / Expansion"')
add_param("bank_index", "Bank", "int", min=0, max=0)
add_param("bank_name", "Bank", "string")
add_param("prev_bank", "Bank -", "trigger")
add_param("next_bank", "Bank +", "trigger")
banks_ol.append('stepper cx=638 cy=200 w=900 h=70 label="" key=bank_index get=bank_name prev=prev_bank next=next_bank style=dotmatrix')
add_param("expansion_index", "Expansion", "int", min=0, max=0)
add_param("current_expansion_name", "Expansion Name", "string")
add_param("prev_expansion", "Expansion -", "trigger")
add_param("next_expansion", "Expansion +", "trigger")
# get=current_expansion_name, NOT bank_name: this stepper used to show the same text as the bank
# stepper right above it (both bound to bank_name, since either control changes the current bank)
# -- confusingly duplicated. This dedicated key only reflects the EXPANSION stepper's own selection.
banks_ol.append('stepper cx=638 cy=320 w=900 h=70 label="" key=expansion_index get=current_expansion_name prev=prev_expansion next=next_expansion style=dotmatrix')
banks_keyed += [("Bank / Expansion", "bank_index"), ("Bank / Expansion", "expansion_index")]
banks_ol.append('frame x=36 y=400 w=1208 h=280 title="Patch"')
add_param("preset", "Patch", "int", min=0, max=8191)
add_param("patch_name", "Patch Name", "string")
add_param("preset_prev", "Patch -", "step", of="preset", delta=-1)
add_param("preset_next", "Patch +", "step", of="preset", delta=1)
banks_ol.append('stepper cx=638 cy=500 w=900 h=70 label="" key=preset get=patch_name style=dotmatrix')
banks_keyed.append(("Patch", "preset"))
out_tabs.append((banks_ol, banks_keyed))

# qlinks: nested Q-Link banks (mpc-vst's `qlinks "<name>" = ...` lines are exactly this --
# several banks sharing one tab's design, each its own Q-Link set, per docs/PORTING.md). Grouped
# by FRAME so a bank doesn't split a section awkwardly: accumulate whole frame-groups until the
# next one would exceed 16 keys, then start a new bank; a single frame with >16 keys on its own
# splits at 16 (only TONE tabs' LFO 1 + LFO 2 pair is anywhere close, and that's exactly 15).
def make_banks(keyed):
    # Frames are ATOMIC: never split one frame's keys across two banks. shadow_skin.py's
    # split-screen pages (one screen per bank, not the whole tab with just the Q-Link map
    # changing -- see docs/NOTES.md) include a WHOLE frame if any of its keys are in that bank, so
    # a split frame here would show up complete on BOTH banks (found via an offline preview: the
    # Play bank showed Effect Sends' chorus/tone knobs too, because reverb -- one of Effect Sends'
    # own keys -- had been grouped into Play by the old key-count-only accumulation).
    groups = []   # ordered (frame_title, [keys]), one whole frame's keys each
    for frame_title, key in keyed:
        if groups and groups[-1][0] == frame_title:
            groups[-1][1].append(key)
        else:
            groups.append((frame_title, [key]))
    banks = []   # (title, [keys])
    cur_titles, cur_keys = [], []
    for frame_title, keys in groups:
        if len(keys) > 16:
            raise SystemExit("layout: frame %r has %d keys alone (max 16 per Q-Link bank)" % (frame_title, len(keys)))
        if cur_keys and len(cur_keys) + len(keys) > 16:
            banks.append((" + ".join(cur_titles), cur_keys))
            cur_titles, cur_keys = [], []
        cur_titles.append(frame_title)
        cur_keys += keys
    if cur_keys:
        banks.append((" + ".join(cur_titles), cur_keys))
    return banks

# Bank NAMES also become MPC's bottom function-key tab-strip caption for that sub-page (confirmed
# on a real device: a long "+"-joined frame-title name truncates into an unreadable run-on strip
# across all 6 tabs -- that's the whole strip's width, not one tab's). Stock skins keep these to a
# single short word/number; short, curated names per tab instead of the frame-title concatenation.
SHORT_BANK_NAMES = {"PLAY": ["Play", "Sends"], "PATCH": ["Patch", "FX"]}

final = []
for ol, keyed in out_tabs:
    name = ol[0][5:-1]
    banks = make_banks(keyed) if keyed else [(name, [])]
    if name in SHORT_BANK_NAMES:
        short_titles = SHORT_BANK_NAMES[name]
    elif name.startswith("TONE"):
        n = name.split()[1]
        short_titles = ["Tone %s" % n, "Env %s" % n, "LFO %s" % n]
    else:
        short_titles = [name] * len(banks)
    for (_, keys), short in zip(banks, short_titles):
        ol = ol + ['qlinks "%s" = %s' % (short, ",".join(keys))]
    final.append(ol)

header = """# mpc-jv880 skin layout: converted from force-jv880's addon/shadow_page.conf
# (Force Shadow widget syntax; proven on real hardware) by a one-off script,
# see mpc-jv880/docs/DESIGN-NOTES.md. Differences from the Force Shadow page:
#   - no mix.dest_idx / mix.gain (host-level mixer, not plugin parameters)
#   - dot-matrix bar (bank/patch name) moved to the BOTTOM of each tab, in a
#     strip reclaimed by compressing body content 10%% (BODY_SCALE) -- MPC
#     skins have no outer chrome band like Force Shadow's own topbar sits in,
#     and there's no spare margin at the top (content already starts at y=88)
#   - BANKS tab dropped for v1: browse by the PATCH stepper only (as DX7 does)
#   - env widgets (draggable curves) -> bar-graph envelope displays: one
#     slider_v per level stage (live), knob per time stage, no drag/line
#   - qlinks are a first pass (first 16 controls per tab); needs a manual
#     curation pass, most tabs have 20-30 controls
theme_bg=232527
theme_panel=2a2d2f
theme_line=42484a
theme_ink=e2e4de
theme_ink_dim=8f9490
theme_accent=b9d94a
theme_accent_hi=e4f38c
theme_knob_face=1a1c1d
theme_knob_ring=3b4143
theme_knob_dot=b9d94a
theme_display_ink=cdeb63
"""
open(OUT_LAYOUT, "w").write(header + "\n\n".join("\n".join(ol) for ol in final) + "\n")

module = {
    "id": "jv880mpc", "name": "JV-880", "abbrev": "JV", "version": "0.1.0",
    "description": "ROM-based PCM rompler emulator (MPC OS VST2 port)",
    "author": "nukeykt/giulioz (Move port: charlesvestal; MPC port: sd88me)",
    "license": "Non-commercial",
    "capabilities": {"chain_params": list(params.values())}
}
json.dump(module, open(OUT_MODULE, "w"), indent=2)
print("params:", len(params))
print("tabs:", [ol[0][5:-1] for ol, keyed in out_tabs])
for ol, keyed in out_tabs:
    banks = make_banks(keyed) if keyed else []
    total = sum(len(k) for _, k in banks)
    print("  %-10s controls=%-3d banks=%d sizes=%s" % (ol[0][5:-1], len(keyed), len(banks), [len(k) for _, k in banks]))
    if total != len(keyed):
        print("    !! bank key count %d != control count %d" % (total, len(keyed)))
