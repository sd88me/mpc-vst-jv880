#!/usr/bin/env python3
"""One-off: the released 1.x build's parameter table (build/params.h from mpc-vst-plugins tools/gen_vst.py on the v1.0.9 tree)
-> params.json, the frozen record the SDK front end is generated from (tools/sdk/gen_sdk_params.py).
Order = VST parameter index. Keeps every wrapper flag that changes behaviour (momentary, text, step_of, popup, nudge_pct) and the
MIDI control map (CC 20-35, NRPN). Run once; the output is committed and never regenerated from a newer build."""
import json, re, sys
src = sys.argv[1] if len(sys.argv) > 1 else "build/params.h"
h = open(src).read()
cols = ("key name unit min max def nopts opts momentary string_display int_display step_target step_delta popup_of hold_ms "
        "dynamic_name dynamic_display qlink_ticks no_poll nudge_pct nudge_gain refresh_display").split()
opts = {m.group(1): json.loads("[" + m.group(2) + "]") for m in re.finditer(r"OPTS_(\d+)\[\] = \{(.*?)\};", h)}
rows = [l.strip().rstrip(",") for l in h.splitlines() if l.strip().startswith('{"')]
num = lambda s: float(s.rstrip("f"))
out = []
for i, r in enumerate(rows):
    f = [x.strip() for x in re.findall(r'"[^"]*"|[^,{}\s][^,{}]*', r.strip("{}"))]
    d = dict(zip(cols, f))
    p = {"key": json.loads(d["key"]), "name": json.loads(d["name"])}
    if d["nopts"] != "0":
        p["options"] = opts[d["opts"].split("_")[1]]
        p["default"] = int(num(d["def"]))
    else:
        p["min"], p["max"], p["default"] = num(d["min"]), num(d["max"]), num(d["def"])
    if d["momentary"] == "1": p["momentary"] = True
    if d["string_display"] == "1": p["display"] = "string"
    elif d["int_display"] == "1": p["display"] = "int"
    if d["step_target"] != "-1": p["step_of"] = json.loads(rows[int(d["step_target"])].split(",")[0].strip("{ ")); p["step_delta"] = num(d["step_delta"])
    if d["popup_of"] != "-1": p["popup_of"] = json.loads(rows[int(d["popup_of"])].split(",")[0].strip("{ "))
    if d["nudge_pct"] != "0": p["nudge_pct"] = int(d["nudge_pct"])
    for k in ("hold_ms", "dynamic_name", "dynamic_display", "qlink_ticks", "no_poll", "nudge_gain", "refresh_display"):
        assert d[k] == "0", (p["key"], k)   # not used by this port: the front end does not implement them
    out.append(p)
cc = re.search(r"PLUG_CC\[16\] = \{(.*?)\}", h)
meta = {"name": re.search(r'PLUG_NAME "(.*?)"', h).group(1), "uid": "JV88", "version": int(re.search(r"PLUG_VERSION (\d+)", h).group(1)),
        "release": "1.0.9", "cc_map_20_35": [int(x) for x in cc.group(1).split(",")] if cc else [], "nrpn": "HAS_NRPN" in h,
        "note": "frozen from the 1.0.9 wrapper build; the VST order is this list. Append only."}
json.dump({"meta": meta, "params": out}, open("params.json", "w"), indent=1)
print("params.json: %d params" % len(out))
