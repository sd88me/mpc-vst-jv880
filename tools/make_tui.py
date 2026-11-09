#!/usr/bin/env python3
"""Write skins/TUI.json + skins/Q-Links.json (the MPC's native skin) and the art they use, from tools/skin_pages.py.
Structure from Dexed 2.0 (~/mpc-vst-dx7 tools/make_tui.py): reusable slider / field components, the live Envelope widget,
membrane-style Buttons, Labels for live text, Q-Link groups of four per printed section.

    python3 tools/make_tui.py              # -> skins/
    python3 tools/make_tui.py --preview    # also docs/skin-preview/<tab>.png: the page as the MPC should draw it (mock-up)
"""
import os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "skins")
PREVIEW = os.path.join(ROOT, "docs", "skin-preview")
KEYS = re.findall(r'^\s*\{"([^"]+)"', open(os.path.join(ROOT, "src", "params_gen.h")).read(), re.M)   # VST order (generated)


def P(key):
    return "Parameter %d" % KEYS.index(key)


# ---- a JSON writer that keeps key order and allows the overlay widgets' duplicate "version" key ------------------------
class Obj:
    def __init__(self, *pairs):
        self.pairs = list(pairs)


def dump(v, ind=0):
    sp = "  " * ind
    pairs = v.pairs if hasattr(v, "pairs") else list(v.items()) if isinstance(v, dict) else None
    if pairs is not None:
        if not pairs:
            return "{}"
        return "{\n%s\n%s}" % (",\n".join("%s  %s: %s" % (sp, dump(k), dump(x, ind + 1)) for k, x in pairs), sp)
    if isinstance(v, list):
        return "[]" if not v else "[\n%s\n%s]" % (",\n".join(sp + "  " + dump(x, ind + 1) for x in v), sp)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v) if isinstance(v, float) else str(v)
    return '"%s"' % str(v).replace("\\", "\\\\").replace('"', '\\"')


# ---- building blocks -----------------------------------------------------------------------------------------------------
def bounds(b, focus="No", visible="Always"):
    return {"version": 1, "acceptsHWFocus": focus, "showWhenDataModelInvalid": "Show", "whenVisible": visible,
            "boundsType": "Absolute", "bounds": b}


def entry(name, typ, data, b, remap=None, focus="No", visible="Always"):
    return {"version": 2, "componentData": {"version": 1, "name": name, "type": typ, "data": data},
            "handle remapping": {"version": 1, "map": [{"key": "Data", "value": remap}] if remap else []},
            "bounds": bounds(b, focus, visible)}


def bg(colour="0", image=""):
    return {"version": 1, "focussed": {"version": 1, "colour": colour, "image": image},
            "unfocussed": {"version": 1, "colour": colour, "image": image}}


def component(children, actions=None, ignore=False, background=None):
    return {"version": 2, "actions": actions or [], "backgroundData": background or bg(), "ignoreMousePresses": ignore,
            "disableCoarseDataWheel": False, "componentsData": children}


def act(on, handler, extra=""):
    return {"version": 1, "onAction": on, "handler": handler, "handleName": "Data", "additionalData": extra}


FOCUS = {"version": 1, "backgroundColour": "19ffffff", "outlineColour": "ffe81f40", "backgroundInset": 4.0, "outlineThickness": 1.0}


def text_style(h=22.0, colour="ffd6d4cc", style="SemiBold", just="left verticallyCentred", case="Upper Case", font="Roboto"):
    return {"version": 1, "font": {"version": 1, "name": font, "style": style, "height": h}, "colour": colour,
            "justification": just, "case": case}


def label(kind, b, remap=None, **ts):
    d = {"version": 1, "textStyle": text_style(**ts), "type": kind, "handleName": "Data" if remap else "Invalid"}
    return entry("label", "Label", d, b, remap)


def button(name, key, on, off, b, button_id=1, group=1, focus="Yes"):
    return entry(name, "Button", {"version": 2, "onImage": on, "offImage": off, "buttonId": button_id, "numButtonsInGroup": group,
                                  "handleName": "Data", "gestureBehaviour": "Instant"}, b, remap=P(key), focus=focus)


def definitions():
    knob_overlay = component([entry("overlay", "KnobOverlay", Obj(
        ("version", 2), ("version", 1),
        ("actions", [{"version": 1, "onAction": "Focus Lost", "handler": "Focus Lost", "handleName": "Focus Lost", "additionalData": ""}]),
        ("overlayType", "Knob With Header"), ("scaleType", "Linear"), ("polarityType", "Unipolar"),
        ("showMinusSign", True), ("handleName", "Data")), "0 0 1280 800", focus="Yes")], ignore=True)
    return [{"key": "knob overlay", "value": knob_overlay}]


def envelope(handles, name, line="ff1a2008", accent="ff1a2008"):
    """The live envelope widget, transparent (the window art shows through), stage letters hidden. handles: [(key, binding)]."""
    return Obj(*([("version", 1), ("envelopeType", "Pitch" if handles[0][0].startswith("pitch") else "ADSR"),
                  ("envelopeStyle", "WithoutHeader"), ("envelopeName", name),
                  ("backgroundColour", "00000000"), ("scaleColour", "00000000"), ("lineColour", line), ("fillColour", "00000000"),
                  ("highlightColour", accent), ("lineWidth", 3), ("handleWidth", 18), ("handleHeight", 18), ("handleShape", "Circle"),
                  ("handleLineWidth", 2), ("handleLineColour", accent), ("handleFillColour", "ffc4dc58"), ("handleTextColour", "00000000"),
                  ("handleLineWidthOnPressed", 3), ("handleLineColourOnPressed", "ffffffff"), ("handleFillColourOnPressed", "ffff2e22"),
                  ("handleTextColourOnPressed", "00000000"), ("handleArrowLineColourOnPressed", "ffffffff"),
                  ("handleArrowFillColourOnPressed", "ffff2e22")]
                 + handles
                 + ([("attackShapeHandle", "Invalid"), ("decayShapeHandle", "Invalid"), ("releaseShapeHandle", "Invalid")]
                    if not handles[0][0].startswith("pitch") else [])
                 + [("forceHideShapeHandles", True), ("forceCurveShape", 0.5), ("curveType", "Quadratic")]))


def jv_env(kind, tone):
    """A JV-880 tone envelope on the "Pitch" widget (5 levels, 4 times): start level (an anchor param: the JV starts from 0,
    or the centre for pitch), T1 -> L1, T2 -> L2, T3 -> L3 (held while the key is down), T4 -> L4 (amp: down to 0)."""
    k = lambda s: P("nvram_tone_%d_%s" % (tone, s))
    pre = {"pitch": "penv", "filter": "tvfenv", "amp": "tvaenv"}[kind]
    start = P("env_anchor_mid" if kind == "pitch" else "env_anchor_zero")
    end = P("env_anchor_zero") if kind == "amp" else k(pre + "level4")
    return envelope([("pitchEnvelopeLevel1Handle", start), ("pitchEnvelopeDelayHandle", k(pre + "time1")),
                     ("pitchEnvelopeLevel2Handle", k(pre + "level1")), ("pitchEnvelopeAttackHandle", k(pre + "time2")),
                     ("pitchEnvelopeLevel3Handle", k(pre + "level2")), ("pitchEnvelopeDecayHandle", k(pre + "time3")),
                     ("pitchEnvelopeSustainHandle", k(pre + "level3")), ("pitchEnvelopeReleaseHandle", k(pre + "time4")),
                     ("pitchEnvelopeLevel5Handle", end)], "%s env %d" % (kind, tone + 1))


def adsr_env(a, d, s, r, name):
    return envelope([("attackHandle", P(a)), ("decayHandle", P(d)), ("sustainHandle", P(s)), ("releaseHandle", P(r))], name)


SLIDERS = {}   # component name -> (film strip file, w, h, drag orientation)
FIELDS = set()


def need_slider(name, strip, w, h, orient="Horizontal"):
    SLIDERS[name] = (strip, w, h, orient)


def need_field(w, h):
    FIELDS.add((w, h))


def slider_defs():
    """One reusable component per slider width: the film strip (a Knob dragged sideways), a focus ring, Q-Link on touch, the big
    knob overlay on double tap / Enter. LCD fields: an invisible value slider over live text (data wheel, Q-Link, drag)."""
    out = []
    for name, (strip, w, h, orient) in sorted(SLIDERS.items()):
        fb = "-6 -30 %d 66" % (w + 12) if h <= 30 else "-4 -4 %d %d" % (w + 8, h + 8)
        out.append({"key": name, "value": component([
            entry("focus", "Focus", FOCUS, fb, visible="WhenFocussed"),
            entry("strip", "Knob", {"version": 3, "knobType": "FilmStrip", "filmStrip": strip, "numFrames": 128, "invert": False,
                                    "dragOrientation": orient, "handleName": "Data"}, "0 0 %d %d" % (w, h)),
        ], actions=[act("Mouse Down", "Q-Link"), act("Double Click", "Show Overlay", "knob overlay"),
                    act("Enter Pressed", "Show Overlay", "knob overlay")])})
    for w, h in sorted(FIELDS):
        ts = {"version": 1, "font": {"version": 1, "name": "Roboto", "style": "Regular", "height": 20.0}, "colour": "00000000",
              "justification": "horizontallyCentred verticallyCentred", "case": "Original"}
        out.append({"key": "lcdfield%dx%d" % (w, h), "value": component([
            entry("focus", "Focus", {"version": 1, "backgroundColour": "224ea0e2", "outlineColour": "ff4ea0e2",
                                     "backgroundInset": 0.0, "outlineThickness": 2.0}, "0 0 %d %d" % (w, h), visible="WhenFocussed"),
            entry("field", "Knob", {"version": 4, "knobType": "ValueSlider", "textStyle": ts, "dragOrientation": "Horizontal",
                                    "handleName": "Data"}, "0 0 %d %d" % (w, h)),
        ], actions=[act("Mouse Down", "Q-Link")])})
    return out


def qlinks_for(pages):
    """Screen-mode Q-Links: each page's groups of four, first group on the top knob row (Bank Direction RowTopDown)."""
    maps = []
    for p in pages:
        q = {"Q-Link %d" % n: -1 for n in range(1, 17)}
        for gi, keys in enumerate(p.qlink_rows[:4]):
            for i, key in enumerate(keys[:4]):
                q["Q-Link %d" % (13 - 4 * gi + i)] = KEYS.index(key)
        maps.append({"Tab": p.fn + 1, "SubTab": p.sub + 1, "Bank Direction": "RowTopDown", "Q-Links": q})
    return {"version": 4, "info": {"version": 1, "type": "CompleteDescription"},
            "Screen Mode Q-Links": {"version": 4, "map": maps}, "Program Mode Q-Links": {"Q-Link %d" % n: -1 for n in range(1, 17)}}


# ---- preview: the page as the MPC should draw it (sample values), for mock-up review ------------------------------------
def render_preview(page, tab_names, active, qlink_group=0):
    from PIL import Image, ImageDraw
    import make_jv_skin as art
    W, H, TOP = 1280, 800, 110
    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    # MPC chrome: track / plugin / preset bar on top, tab keys at the bottom
    for i, (t, v) in enumerate([("TRACK", "Plugin 001"), ("PLUGIN", "JV-880 2 Beta"), ("PRESET", "Default")]):
        x = 18 + i * 352
        d.text((x, 30), t, font=art.font(16, 500), fill=(120, 120, 120))
        d.text((x, 54), v, font=art.font(30, 400), fill=(235, 235, 235))
    content = Image.open(os.path.join(OUT, page.bgname)).convert("RGB")
    img.paste(content, (0, TOP))
    S = page.sample
    for k in page.kids:
        cd, b = k["componentData"], [int(float(x)) for x in k["bounds"]["bounds"].split()]
        x, y, w, h = b[0], b[1] + TOP, b[2], b[3]
        typ, data = cd["type"], cd["data"]
        remap = k["handle remapping"]["map"][0]["value"] if k["handle remapping"]["map"] else None
        key = KEYS[int(remap.split()[-1])] if remap and remap.startswith("Parameter") else None
        if typ == "Image" and data.get("imageType") == "Regular":
            continue
        if typ in SLIDERS:
            strip = Image.open(os.path.join(OUT, SLIDERS[typ][0]))
            v = S.get(key, 0.5)
            fh = strip.height // 128
            f = strip.crop((0, int(round(v * 127)) * fh, strip.width, int(round(v * 127)) * fh + fh))
            img.paste(f, (x, y), f)
        elif typ == "Button":
            on = key is not None and data["buttonId"] == S.get(key + "#", 0 if data["numButtonsInGroup"] > 1 else -1)
            pic = Image.open(os.path.join(OUT, data["onImage" if on else "offImage"])).convert("RGBA")
            img.paste(pic, (x + (w - pic.width) // 2, y + (h - pic.height) // 2), pic)
        elif typ == "Label":
            ts = data["textStyle"]
            txt = S.get(("text", key), S.get(key + "$", "64") if key else "")
            if ts["case"] == "Upper Case":
                txt = txt.upper()
            fnt = art.font(ts["font"]["height"] * 0.66 / 0.62, 500)
            col = ts["colour"]
            rgb = tuple(int(col[i:i + 2], 16) for i in (2, 4, 6))
            just = ts["justification"]
            ax = x if "left" in just else x + w if "right" in just else x + w // 2
            d.text((ax, y + h // 2), txt, font=fnt, fill=rgb, anchor=("l" if "left" in just else "r" if "right" in just else "m") + "m")
        elif typ == "Envelope":
            pts = page.env_samples.get(cd["name"])
            if pts:
                P_ = [(x + px * w, y + (1 - py) * h) for px, py in pts]
                d.line(P_, fill=(26, 32, 8), width=3)
                for q in P_:
                    d.ellipse([q[0] - 8, q[1] - 8, q[0] + 8, q[1] + 8], outline=(26, 32, 8), width=2, fill=(196, 220, 88))
        elif typ.startswith("lcdfield"):
            pass
    if page.groups and qlink_group is not None and qlink_group < len(page.groups):
        gx, gy, gw, gh = [int(v) for v in page.groups[qlink_group].split()]
        d.rectangle([gx, gy + TOP, gx + gw, gy + gh + TOP], outline=art.QLINK, width=2)
        d.rectangle([gx, gy + TOP, gx + 22, gy + TOP + 20], fill=art.QLINK)
        d.text((gx + 11, gy + TOP + 10), "Q", font=art.font(15, 700), fill=(255, 255, 255), anchor="mm")
    kw = W // max(6, min(len(tab_names), 6))
    for i, t in enumerate(tab_names[:6]):
        cx = i * kw + kw // 2
        if i == active:
            d.rectangle([i * kw + 16, 740, i * kw + kw - 16, 744], fill=(232, 31, 64))
        d.text((cx, 770), t, font=art.font(22, 500), fill=(235, 235, 235), anchor="mm")
    return img


def main():
    preview = "--preview" in sys.argv
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import skin_pages
    pages = skin_pages.all_pages()
    tabs = [p.tab() for p in pages]
    repl, seen = [], set()
    for p in pages:
        for key, labels in p.choices.items():
            if key not in seen:
                seen.add(key)
                repl.append({"key": P(key), "value": labels})
    tui = {"pageData": {"version": 1,
                        "componentDefinitions": {"version": 2, "importFiles": [], "localComponentDefinitions": definitions() + slider_defs()},
                        "replacementStrings": repl, "info": {"version": 1, "type": "CompleteDescription"}, "tabs": tabs}}
    open(os.path.join(OUT, "TUI.json"), "w").write(dump(tui) + "\n")
    open(os.path.join(OUT, "Q-Links.json"), "w").write(dump(qlinks_for(pages)) + "\n")
    print("wrote", OUT, "-", len(tabs), "tabs,", len(os.listdir(OUT)), "files")
    if preview:
        os.makedirs(PREVIEW, exist_ok=True)
        keys_by_fn = {}
        for p in pages:
            keys_by_fn.setdefault(p.fn, p.key_name)
        names = [keys_by_fn[i] for i in sorted(keys_by_fn)]
        for p in pages:
            out = os.path.join(PREVIEW, "%s.png" % re.sub(r"[^a-z0-9]+", "_", p.name.lower()).strip("_"))
            render_preview(p, names, p.fn).save(out)
            print("preview", out)


if __name__ == "__main__":
    # Run inside the importable module, not __main__: skin_pages imports make_tui, and two copies would keep two slider registries
    # (TUI.json then lacks the slider components: SDK-PORTING.md "imported twice").
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import make_tui
    make_tui.main()
