#!/usr/bin/env python3
"""params.json -> src/params_gen.h: the parameter table of the SDK front end (src/JV880Plugin.cpp).

Order = params.json = params.lock (checked): the VST parameter index that automation, MIDI NRPN and the skin bind to. Append only.
params.json is the 1.0.9 wrapper build's table, frozen once by tools/sdk/freeze_params.py. The wrapper's two popup "open" flags
(indices 470, 471) become ONE UI-only "ui_open" (470, which drawn pick-list is open) and a reserved, inert slot (471), so no later
parameter moves. New parameters go in APPENDED below, never in between.

Flags (src/params_gen.h):
  kMomentary  a verb: 0 -> 1 fires it, the front end drops it back to 0
  kText       the value text is the engine's get_param(key) (bank / patch names, page text); the value is a change counter
  kChoice     an option list (engine value = option index)
  kUi         UI plumbing, never sent to the engine (ui_open, the reserved slot)
  kReadOnly   the engine owns it (the envelope-view columns): host writes are ignored, the worker pushes it
  kStep       a momentary that nudges ANOTHER param (step_target) by step_delta (PATCH -/+)
  kTile       a momentary text tile (bank / patch list): its value is the engine's "<key>_on" (lit when selected)
  kNoAuto     not automatable (readouts, tiles, page plumbing): kept out of the MPC's automation lists
  kAnchor     UI-only fixed level an envelope handle starts from: the front end puts it back after a drag
  kLocal      a front-end function with no engine key (random patch, favourites): handled in src/JV880Plugin.cpp
  kPolled     an engine value the worker reads back (the engine changes it itself: patch loads, bank steps, macros)
"""
import json, os, re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
D = json.load(open(os.path.join(ROOT, "params.json")))
P = D["params"]
lock = [l.strip() for l in open(os.path.join(ROOT, "params.lock")) if l.strip()]
keys = [p["key"] for p in P]
if keys[:len(lock)] != lock:
    raise SystemExit("params.json no longer starts with params.lock: the order is frozen (append only)")
if keys[470:472] != ["nvram_patchCommon_reverbtype__open", "nvram_patchCommon_chorustype__open"]:
    raise SystemExit("params.json: expected the two 1.x popup flags at 470/471")

# Parameters added by the SDK port (appended after index 471, in this order). Keep this list append-only too.
TONE_NEW = [   # (engine name, label, min, max, default, options)
    ("cutofffrequency", "CUTOFF", 0, 127, 127, None),
    ("resonance", "RESO", 0, 127, 0, None),
    ("filtermode", "FLT MODE", 0, 2, 1, ["OFF", "LPF", "HPF"]),
    ("tvfenvdepth", "FLT ENV", -63, 63, 0, None),
    ("level", "LEVEL", 0, 127, 127, None),
    ("pan", "PAN", -64, 63, 0, None),
    ("penvdepth", "P-ENV DEPTH", -12, 12, 0, None),
    ("tvaenvtime4", "AMP T4", 0, 127, 0, None),
]
APPENDED = []
for t in range(4):   # 472..503: per tone, the controls the 1.x TONE pages lacked (2026-11-09)
    for n, label, lo, hi, d, opts in TONE_NEW:
        q = {"key": "nvram_tone_%d_%s" % (t, n), "name": "T%d %s" % (t + 1, label)}
        if opts: q.update(options=opts, default=d)
        else: q.update(min=float(lo), max=float(hi), default=float(d))
        APPENDED.append(q)
# 504, 505: UI-only anchors for the live envelopes (JV pitch / filter / amp envelopes start from a fixed level): a drag snaps back
APPENDED.append({"key": "env_anchor_zero", "name": "ENV 0", "min": 0.0, "max": 127.0, "default": 0.0, "anchor": True})
APPENDED.append({"key": "env_anchor_mid", "name": "ENV MID", "min": -63.0, "max": 63.0, "default": 0.0, "anchor": True})
# 506..509: front-end functions (no engine key): a random patch; favourites in the MPC's own PRESET list (+FAV saves the current
# patch with its edits, -FAV deletes the favourite that is picked), and their status text
APPENDED.append({"key": "patch_random", "name": "RANDOM", "min": 0.0, "max": 1.0, "default": 0.0, "momentary": True, "local": True})
APPENDED.append({"key": "fav_save", "name": "+FAV", "min": 0.0, "max": 1.0, "default": 0.0, "momentary": True, "local": True})
APPENDED.append({"key": "fav_delete", "name": "-FAV", "min": 0.0, "max": 1.0, "default": 0.0, "momentary": True, "local": True})
APPENDED.append({"key": "fav_text", "name": "FAVOURITES", "min": 0.0, "max": 0.0, "default": 0.0, "display": "string", "local": True})
# 510..513: per tone, the wave's number (1-based) and name as text, read from the ROM's multisample table (engine key wavename_<tone>)
for t in range(4):
    APPENDED.append({"key": "wavename_%d" % t, "name": "T%d WAVE" % (t + 1), "min": 0.0, "max": 0.0, "default": 0.0, "display": "string"})
# 514..621: the WAVES picker (third press of a TONE key): per tone 24 name tiles, page -/+ and the page text
for t in range(4):
    for i in range(1, 25):
        APPENDED.append({"key": "wavetile_%d_%d" % (t, i), "name": "T%d WAVE %d" % (t + 1, i), "min": 0.0, "max": 1.0, "default": 0.0,
                         "momentary": True, "display": "string"})
    APPENDED.append({"key": "wavepage_prev_%d" % t, "name": "T%d WAVES <" % (t + 1), "min": 0.0, "max": 1.0, "default": 0.0, "momentary": True})
    APPENDED.append({"key": "wavepage_next_%d" % t, "name": "T%d WAVES >" % (t + 1), "min": 0.0, "max": 1.0, "default": 0.0, "momentary": True})
    APPENDED.append({"key": "wavepage_%d" % t, "name": "T%d WAVES PAGE" % (t + 1), "min": 0.0, "max": 0.0, "default": 0.0, "display": "string"})

K = dict(kMomentary=1, kText=2, kChoice=8, kUi=16, kReadOnly=64, kStep=128, kTile=256, kNoAuto=512, kPolled=1024, kAnchor=2048, kLocal=4096)
NOAUTO_RE = re.compile(r"^(env_view_\d|envv_.*|browse_bank_index|patch_page_index|prev_browse_bank|next_browse_bank|patch_page_(next|prev))$")

out = ["/* generated by tools/sdk/gen_sdk_params.py from params.json: do not edit. One row per parameter, in the frozen VST order. */",
       "#pragma once",
       "enum { " + ", ".join("%s = %d" % kv for kv in K.items()) + " };",
       "struct PSpec { const char *key, *name; float min, max, def; int flags; const char *const *choices; int nchoices; "
       "int stepTarget; float stepDelta; int nudgePct; };", ""]
rows = []
for i, p in enumerate(P + APPENDED):
    k = p["key"]
    fl, ch, n, st, sd = 0, "nullptr", 0, -1, 0.0
    if i == 470:
        rows.append('    {"ui_open", "POPUP", 0.0f, 32.0f, 0.0f, %d, nullptr, 0, -1, 0.0f, 0},   // UI only: which drawn pick-list is open (was reverbtype__open)'
                    % (K["kUi"] | K["kNoAuto"]))
        continue
    if i == 471:
        rows.append('    {"reserved_471", "-", 0.0f, 1.0f, 0.0f, %d, nullptr, 0, -1, 0.0f, 0},   // inert (was chorustype__open): keeps later indices'
                    % (K["kUi"] | K["kNoAuto"]))
        continue
    if "options" in p:
        fl |= K["kChoice"]
        out.append("static const char *const ch_%d[] = {%s};" % (i, ", ".join(json.dumps(o) for o in p["options"])))
        ch, n = "ch_%d" % i, len(p["options"])
        lo, hi, d = 0.0, float(n - 1), float(p["default"])
    else:
        lo, hi, d = p["min"], p["max"], p["default"]
    text = p.get("display") == "string" or (hi == lo and "options" not in p)
    if p.get("momentary"):
        fl |= K["kMomentary"] | K["kNoAuto"]
        if text: fl |= K["kTile"] | K["kText"]
    elif text:
        fl |= K["kText"] | K["kNoAuto"]
        lo, hi, d = 0.0, 1023.0, 0.0      # a change counter: the host re-reads the text when the value moves
    if "step_of" in p:
        fl |= K["kStep"]
        st, sd = keys.index(p["step_of"]), p["step_delta"]
    if k.startswith("envv_"): fl |= K["kReadOnly"]
    if NOAUTO_RE.match(k): fl |= K["kNoAuto"]
    if p.get("anchor"): fl |= K["kUi"] | K["kNoAuto"] | K["kAnchor"]
    if p.get("local"): fl |= K["kLocal"] | K["kNoAuto"]
    if not (fl & (K["kMomentary"] | K["kText"] | K["kUi"] | K["kLocal"])): fl |= K["kPolled"]
    rows.append('    {%s, %s, %sf, %sf, %sf, %d, %s, %d, %d, %sf, %d},' % (
        json.dumps(k), json.dumps(p["name"]), repr(float(lo)), repr(float(hi)), repr(float(d)), fl, ch, n, st, repr(float(sd)),
        int(p.get("nudge_pct", 0))))
cc = D["meta"]["cc_map_20_35"]
out += ["", "static const PSpec g_pspecs[] = {"] + rows + ["};",
        "static const int kNumParams = %d;" % (len(P) + len(APPENDED)),
        "static const int kUiParam = 470;",
        "// MIDI control, as the 1.x build: CC 20..35 -> these parameters (-1: none); NRPN n (CC 99/98, data CC 6/38) -> parameter n.",
        "static const int g_ccMap[16] = {%s};" % ", ".join(str(x) for x in cc),
        "static const bool kHasNrpn = %s;" % ("true" if D["meta"]["nrpn"] else "false"), ""]
open(os.path.join(ROOT, "src/params_gen.h"), "w").write("\n".join(out))
print("src/params_gen.h: %d params" % (len(P) + len(APPENDED)))
