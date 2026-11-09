#!/usr/bin/env python3
"""The JV-880 2.0 skin pages. Each page's coordinates are defined once, here: a Page draws its static art (panel, section print,
tick scales, windows, the LCD) into a background PNG and records the live widgets (film-strip sliders, value labels, keys,
envelopes, list tiles) for TUI.json at exactly the same positions. Structure from Dexed 2.0's tools/skin_pages.py.

Tabs (the 1.x order, COMMON added last): PLAY, BANKS, TONE 1..4 (two sub-tabs each: MAIN and LFO), COMMON.
Every section is a block of up to four controls = one Q-Link group with its own printed panel (the MPC's bounds overlay).
Content area: 1280 x 628 (the MPC's tab area starts 110 px down the screen).
"""
import os, re
from PIL import Image, ImageDraw

import make_jv_skin as art
import make_tui as tui

SKINS = tui.OUT
_made = set()
NUM = {k: None for k in tui.KEYS}
X0, X1 = 16, 1010          # left block area; the right column runs from RX to 1262
RX, RW = 1030, 232
SW = 232                   # slider width in a row of four
STYLE = os.environ.get("JV_CTRL", "fader")   # continuous-control style (see Page.slider)


def asset(name, make):
    if name not in _made:
        make().save(os.path.join(SKINS, name))
        _made.add(name)
    return name


def spec(key):
    """(min, max, options) of a parameter, from the generated table."""
    src = open(os.path.join(tui.ROOT, "src", "params_gen.h")).read()
    m = re.search(r'\{"%s", "[^"]*", (-?[\d.]+)f, (-?[\d.]+)f, (-?[\d.]+)f, (\d+), (ch_\d+|nullptr)' % re.escape(key), src)
    lo, hi = float(m.group(1)), float(m.group(2))
    opts = None
    if m.group(5) != "nullptr":
        opts = re.findall(r'"([^"]*)"', re.search(r"%s\[\] = \{(.*?)\};" % m.group(5), src).group(1))
    return lo, hi, opts


def slider_strip(w, bipolar):
    return asset("slider_%d%s.png" % (w, "b" if bipolar else ""),
                 lambda: art.film_strip([art.fader_frame(w, 30, i / 127, bipolar=bipolar) for i in range(128)]))


def key_img(w, h, lit, caption, led=True, size=None):
    slug = re.sub(r"[^A-Za-z0-9]", "_", (caption or "blank").replace("+", "p").replace("-", "m").replace("#", "n"))
    return asset("key_%dx%d_%s_%s%s.png" % (w, h, "on" if lit else "off", slug, "" if led else "_nl"),
                 lambda: art.key(w, h, lit, caption, led=led, size=size))


class Page:
    def __init__(self, name, key_name, fn, sub=0, seed=7):
        self.name, self.key_name, self.fn, self.sub = name, key_name, fn, sub
        self.bg = art.panel(1280, 628, seed=seed)
        self.d = ImageDraw.Draw(self.bg)
        self.kids, self.groups, self.qlink_rows, self.choices = [], [], [], {}
        self.sample, self.env_samples = {}, {}

    # ---- static art ----
    def header(self, x0, x1, y, text, q=False):
        """Section print. q: the section is a Q-Link block, whose top-left corner gets the MPC's "Q" tag: start the title clear of it."""
        art.group_header(self.d, x0, x1, y, text, indent=28 if q else 0)

    def legend(self, x, y, text, size=13, col=art.INK_DIM, wght=600, anchor="la"):
        art.legend(self.d, x, y, text, size, col, wght, anchor)

    # ---- widgets ----
    def slider(self, key, x, y, w, name, sample=0.5):
        """One continuous control in a w-wide column, y = its top (about 64 px tall). Style from JV_CTRL:
        fader  name + value + horizontal LED-ladder fader + tick scale
        cells  a backlit LCD cell: name, big value, bar graph (drag sideways anywhere on it)
        knobs  a rack knob with a red LED dot ring, name and value beside it (drag up / down)
        ladder a vertical LED ladder at the right, name and value beside it (drag up / down)
        Bipolar when the range straddles zero (lit from the centre)."""
        lo, hi, _ = spec(key)
        bip = lo < 0 < hi
        tag = "b" if bip else ""
        self.sample[key] = sample
        self.sample[key + "$"] = str(int(round(lo + sample * (hi - lo))))
        if STYLE == "cells":
            h = 62
            art.lcd_cell(self.bg, x, y - 4, x + w - 1, y - 4 + h - 1)
            self.legend(x + 8, y - 1, name, 12, art.LCD_INK, 700)
            self.kids.append(tui.label("Value", "%d %d 100 30" % (x + w - 108, y + 12), remap=tui.P(key),
                                       just="right verticallyCentred", colour="ff161a08", style="Bold", h=28.0))
            comp = "cell%d%s" % (w, tag)
            tui.need_slider(comp, asset("cell_%d%s.png" % (w, tag), lambda: art.film_strip(
                [art.cell_frame(w, h, i / 127, bip) for i in range(128)])), w, h)
            self.kids.append(tui.entry(key, comp, {"version": 1, "handleName": "Data"}, "%d %d %d %d" % (x, y - 4, w, h),
                                       remap=tui.P(key), focus="Yes"))
            return
        if STYLE == "knobs":
            D = 60
            self.legend(x + D + 10, y + 2, name, 12)
            self.kids.append(tui.label("Value", "%d %d %d 32" % (x + D + 10, y + 20, w - D - 10), remap=tui.P(key),
                                       just="left verticallyCentred", colour="fff4f1e8", style="Medium", h=28.0))
            comp = "knob%d%s" % (D, tag)
            tui.need_slider(comp, asset("knob_%d%s.png" % (D, tag), lambda: art.film_strip(
                [art.knob_frame(D, i / 127, bip) for i in range(128)])), D, D, "Vertical")
            self.kids.append(tui.entry(key, comp, {"version": 1, "handleName": "Data"}, "%d %d %d %d" % (x, y - 2, D, D),
                                       remap=tui.P(key), focus="Yes"))
            return
        if STYLE == "ladder":
            LW_, LH = 24, 60
            self.legend(x, y + 2, name, 12)
            self.kids.append(tui.label("Value", "%d %d %d 32" % (x, y + 22, w - LW_ - 16), remap=tui.P(key),
                                       just="left verticallyCentred", colour="fff4f1e8", style="Medium", h=28.0))
            comp = "ladder%d%s" % (LH, tag)
            tui.need_slider(comp, asset("ladder_%d%s.png" % (LH, tag), lambda: art.film_strip(
                [art.ladder_frame(LW_, LH, i / 127, bip) for i in range(128)])), LW_, LH, "Vertical")
            self.kids.append(tui.entry(key, comp, {"version": 1, "handleName": "Data"}, "%d %d %d %d" % (x + w - LW_ - 8, y - 2, LW_, LH),
                                       remap=tui.P(key), focus="Yes"))
            return
        self.legend(x, y, name)
        art.scale_ticks(self.d, x + 9, y + 50, w - 18)
        self.kids.append(tui.label("Value", "%d %d 110 24" % (x + w - 110, y - 5), remap=tui.P(key),
                                   just="right verticallyCentred", colour="fff4f1e8", style="Medium", h=23.0))
        tui.need_slider("hslider%d%s" % (w, tag), slider_strip(w, bip), w, 30)
        self.kids.append(tui.entry(key, "hslider%d%s" % (w, tag), {"version": 1, "handleName": "Data"},
                                   "%d %d %d 30" % (x, y + 20, w), remap=tui.P(key), focus="Yes"))

    def toggle(self, key, x, y, w, h, caption, lit=False):
        """An OFF/ON choice (or a momentary verb) as one rubber key with an LED (single Button: buttonId 1)."""
        on, off = key_img(w, h, True, caption), key_img(w, h, False, caption)
        self.kids.append(tui.button(key, key, on, off, "%d %d %d %d" % (x - 6, y - 6, w + 12, h + 12)))
        _, _, opts = spec(key)
        if opts:
            self.choices[key] = opts
        self.sample[key + "#"] = 1 if lit else 0

    def momentary(self, key, x, y, w, h, caption, led=False, size=None):
        on, off = key_img(w, h, True, caption, led=led, size=size), key_img(w, h, False, caption, led=led, size=size)
        self.kids.append(tui.button(key, key, on, off, "%d %d %d %d" % (x - 6, y - 6, w + 12, h + 12)))

    def segments(self, key, x, y, w, h, labels=None, cols=None, gap=6, sel=0, row_gap=8):
        """A radio group of keys, one per option (captions baked), in `cols` columns."""
        labels = labels or spec(key)[2]
        cols = cols or len(labels)
        rows = (len(labels) + cols - 1) // cols
        bw = (w - (cols - 1) * gap) // cols
        for i, lb in enumerate(labels):
            r, c = divmod(i, cols)
            on, off = key_img(bw, h, True, lb), key_img(bw, h, False, lb)
            self.kids.append(tui.button("%s %d" % (key, i), key, on, off,
                                        "%d %d %d %d" % (x + c * (bw + gap) - 3, y + r * (h + row_gap) - 3, bw + 6, h + 6),
                                        button_id=i, group=len(labels)))
        self.choices[key] = spec(key)[2] or labels
        self.sample[key + "#"] = sel
        return y + rows * h + (rows - 1) * row_gap

    def lcd_field(self, key, x, y, w, h):
        self.kids.append(tui.entry(key + " field", "lcdfield%dx%d" % (w, h), {"version": 1, "handleName": "Data"},
                                   "%d %d %d %d" % (x, y, w, h), remap=tui.P(key), focus="Yes"))
        tui.need_field(w, h)

    def hit(self, key, x, y, w, h):
        """An invisible momentary touch zone (on printed LCD arrows)."""
        off = asset("hit_off_%dx%d.png" % (w, h), lambda: Image.new("RGBA", (w, h), (0, 0, 0, 0)))
        on = asset("hit_on_%dx%d.png" % (w, h), lambda: Image.new("RGBA", (w, h), (0, 0, 0, 70)))
        self.kids.append(tui.button(key, key, on, off, "%d %d %d %d" % (x, y, w, h), focus="No"))

    def envelope_window(self, x0, y0, x1, y1, title, data, name, mid=False, sample=None):
        self.header(x0, x1, y0 - 14, title)
        art.window(self.bg, x0, y0, x1, y1, grid=(8, 4), mid=mid)
        self.kids.append(tui.entry(name, "Envelope", data, "%d %d %d %d" % (x0, y0, x1 - x0, y1 - y0), focus="Yes"))
        if sample:
            self.env_samples[name] = sample

    def qlink_group(self, rect, keys):
        """One Q-Link block (up to four controls), with a faint printed panel so the bounds overlay frames a real section."""
        x0, y0, x1, y1 = rect
        self.d.rounded_rectangle([x0, y0, x1, y1], 6, outline=(58, 58, 60), width=1)
        self.groups.append("%d %d %d %d" % (x0, y0, x1 - x0, y1 - y0))
        self.qlink_rows.append(keys)

    def tab(self):
        self.bgname = "bg_%s.png" % re.sub(r"[^a-z0-9]+", "_", self.name.lower()).strip("_")
        self.bg.save(os.path.join(SKINS, self.bgname))
        kids = [tui.entry("bg", "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": self.bgname}, "0 0 1280 628")] + self.kids
        return {"version": 1, "tabName": self.key_name, "fnKeyIndex": self.fn, "fnKeySubIndex": self.sub,
                "componentDefinition": tui.component(kids, background=tui.bg("ff1a1a1b")), "qlinkBoundsData": self.groups}


def col(i, w=SW, x0=X0):
    return x0 + 14 + i * (w + 16)


# ---- the header every page shares: badge, the LCD (bank | patch, with step arrows), the page's own right part ---------------
LX, LW, SPLIT = 196, 760, 330


def header(p, right_title=None):
    b = art.badge(44)
    p.bg.paste(b, (18, 16), b)
    lcd = art.lcd(LW, 60, cols=34, dividers=(SPLIT,), arrows=((22, -1), (SPLIT - 22, 1), (SPLIT + 22, -1), (LW - 22, 1)))
    p.bg.paste(lcd, (LX, 10), lcd)
    for key, x, w, txt in (("bank_name", LX + 44, SPLIT - 88, "Preset A"), ("patch_name", LX + SPLIT + 44, LW - SPLIT - 88, "A.Piano 1")):
        p.kids.append(tui.label("Value", "%d 14 %d 52" % (x, w), remap=tui.P(key), just="left verticallyCentred",
                                colour="ff141311", style="Medium", case="Original", h=34.0))
        p.sample[key + "$"] = txt
    p.lcd_field("preset", LX + SPLIT + 44, 10, LW - SPLIT - 88, 60)   # data wheel / Q-Link / drag steps the patch
    for key, x in (("prev_bank", 0), ("next_bank", SPLIT - 44), ("preset_prev", SPLIT), ("preset_next", LW - 44)):
        p.hit(key, LX + x, 10, 44, 60)
    if right_title:
        p.legend(1262, 26, right_title[0], 15, art.ORANGE, 650, anchor="ra")
        p.d.text((1262, 30), right_title[1], font=art.font(40, 700), fill=art.BLUE, anchor="ra")
    # RANDOM: a random patch from every bank, on every page
    p.legend(1026, 14, "PATCH", 12, art.ORANGE, 650, anchor="ma")
    p.momentary("patch_random", 976, 30, 100, 42, "RANDOM", led=False, size=15)
    p.d.line([16, 84, 1262, 84], fill=art.BLUE_DIM, width=1)


def tone_switches(p, x, y, w=108, h=50):
    p.header(x, x + 2 * w + 16, y - 10, "TONES")
    for t in range(4):
        r, c = divmod(t, 2)
        p.toggle("nvram_tone_%d_toneswitch" % t, x + c * (w + 16), y + 4 + r * (h + 14), w, h, "TONE %d" % (t + 1), lit=t < 2)


# ---------------------------------------------------------------------------------------------------------------------------
def play_page():
    """PLAY: the macros (filter, envelope), output and effect sends as four Q-Link blocks; the macro envelope as a live ADSR."""
    p = Page("PLAY", "PLAY", 0, seed=9)
    header(p)
    rows = [("FILTER  (MACRO)", [("macro_cutoff", "CUTOFF", .62), ("macro_resonance", "RESONANCE", .3),
                                  ("macro_tvf_env_depth", "FILTER ENV DEPTH", .66), ("macro_lfo_depth", "LFO DEPTH", .5)]),
            ("OUTPUT", [("nvram_patchCommon_patchlevel", "PATCH LEVEL", 1.0), ("nvram_patchCommon_patchpan", "PATCH PAN", .5),
                        ("octave_transpose", "OCTAVE", .5), ("nvram_patchCommon_analogfeel", "ANALOG FEEL", .1)]),
            ("EFFECT SENDS", [("nvram_patchCommon_reverblevel", "REVERB", .7), ("nvram_patchCommon_reverbtime", "REVERB TIME", .55),
                              ("nvram_patchCommon_choruslevel", "CHORUS", .7), ("nvram_patchCommon_chorusdepth", "CHORUS DEPTH", .12)])]
    for gi, (title, ctl) in enumerate(rows):
        y = 104 + gi * 100
        p.header(X0 + 8, X1 - 8, y, title, q=True)
        for i, (k, n, s) in enumerate(ctl):
            p.slider(k, col(i), y + 12, SW, n, s)
        p.qlink_group((X0, y - 16, X1, y + 76), [c[0] for c in ctl])
    # macro envelope: four sliders (Q-Link block) beside the live ADSR
    EW = 140
    p.header(X0 + 8, 632, 418, "ENVELOPE  (MACRO)", q=True)
    env = [("macro_attack", "ATTACK", .1), ("macro_decay", "DECAY", .45), ("macro_sustain", "SUSTAIN", .6), ("macro_release", "RELEASE", .35)]
    for i, (k, n, s) in enumerate(env):
        p.slider(k, col(i, EW), 430, EW, n, s)
    p.qlink_group((X0, 402, 640, 494), [e[0] for e in env])
    p.envelope_window(666, 412, 1256, 612, "ENVELOPE", tui.adsr_env(*[e[0] for e in env], name="macro env"), "macro env",
                      sample=[(0, 0), (.12, 1), (.35, .6), (.7, .6), (.92, 0)])
    # key mode (screen only)
    p.header(X0 + 8, 632, 528, "KEY MODE")
    p.segments("nvram_patchCommon_keyassign", col(0, EW), 542, 2 * EW + 16, 44)
    p.toggle("nvram_patchCommon_sololegato", col(2, EW), 542, EW, 44, "LEGATO")
    p.toggle("nvram_patchCommon_portamentoswitch", col(3, EW), 542, EW, 44, "PORTA")
    # right column: tone on/off, velocity switch
    tone_switches(p, RX, 104)
    p.header(RX, 1262, 262, "VELOCITY")
    p.toggle("nvram_patchCommon_velocityswitch", RX, 276, RW, 44, "VELOCITY SWITCH")
    return p


def banks_page():
    """BANKS: the bank list (22 tiles: browse a bank) and the browsed bank's patches (28 tiles per page: load one), paged."""
    p = Page("BANKS", "BANKS", 1, seed=11)
    header(p)
    p.header(24, 560, 104, "BANKS", q=True)
    names = ["Preset A", "Preset B", "Internal", "Card", "Pop", "Orchestral", "Piano", "Vintage", "World", "Dance", "Super Sound"]
    for i in range(22):
        c, r = divmod(i, 11)
        x, y = 24 + c * 272, 116 + r * 30
        k = "bank_slot_%d" % (i + 1)
        p.d.rectangle([x, y, x + 261, y + 25], fill=(12, 12, 13))
        p.kids.append(tui.label("Value", "%d %d 236 26" % (x + 16, y), remap=tui.P(k), colour="ffe2e4e6", style="Medium", case="Original", h=17.0))
        p.kids.append(tui.button(k, k, asset("tile_262x26_on.png", lambda: art.tile_frame(262, 26, True)),
                                 asset("tile_262x26_off.png", lambda: art.tile_frame(262, 26, False)), "%d %d 262 26" % (x, y)))
        p.sample[k + "$"] = names[i] if i < len(names) else ""
        p.sample[k + "#"] = 1 if i == 0 else 0
    # favourites: 8 slots (bank + patch, shared by every project); STORE on, then a slot, stores the current patch there
    p.header(24, 430, 474, "FAVOURITES")
    p.toggle("fav_store", 448, 454, 112, 34, "STORE")
    favs = ["1: Velo Harmnix", "2: Nylon Chord", "3: ---", "4: ---", "5: ---", "6: ---", "7: ---", "8: ---"]
    for i in range(8):
        c, r = divmod(i, 4)
        x, y = 24 + c * 272, 498 + r * 30
        k = "fav_%d" % (i + 1)
        p.d.rectangle([x, y, x + 261, y + 25], fill=(12, 12, 13))
        p.kids.append(tui.label("Value", "%d %d 236 26" % (x + 16, y), remap=tui.P(k), colour="ffe2e4e6", style="Medium", case="Original", h=17.0))
        p.kids.append(tui.button(k, k, asset("tile_262x26_on.png", lambda: art.tile_frame(262, 26, True)),
                                 asset("tile_262x26_off.png", lambda: art.tile_frame(262, 26, False)), "%d %d 262 26" % (x, y)))
        p.sample[k + "$"] = favs[i]
        p.sample[k + "#"] = 1 if i == 1 else 0
    p.header(590, 1262, 104, "PATCHES")
    p.kids.append(tui.label("Value", "690 86 400 24", remap=tui.P("browse_bank_name"), colour="ffec802e", style="Medium", case="Original", h=17.0))
    p.sample["browse_bank_name$"] = "Preset A"
    pn = ["A.Piano 1", "A.Piano 2", "Mellow Piano", "Pop Piano 1", "Pop Piano 2", "Pop Piano 3", "MIDIed Grand", "Country Bar",
          "Glass Piano", "Shimmer Pno", "Rock Piano", "Ballad Piano", "Echo Piano", "E.Piano 1"]
    for i in range(28):
        c, r = divmod(i, 14)
        x, y = 590 + c * 340, 116 + r * 32
        k = "patch_slot_%d" % (i + 1)
        p.d.rectangle([x, y, x + 329, y + 27], fill=(12, 12, 13))
        p.kids.append(tui.label("Value", "%d %d 300 28" % (x + 16, y), remap=tui.P(k), colour="ffe2e4e6", style="Regular", case="Original", h=17.0))
        p.kids.append(tui.button(k, k, asset("tile_330x28_on.png", lambda: art.tile_frame(330, 28, True)),
                                 asset("tile_330x28_off.png", lambda: art.tile_frame(330, 28, False)), "%d %d 330 28" % (x, y)))
        p.sample[k + "$"] = (pn + pn)[i]
        p.sample[k + "#"] = 1 if i == 0 else 0
    y = 572
    p.momentary("patch_page_prev", 590, y, 110, 40, "< PAGE", size=15)
    p.kids.append(tui.label("Value", "716 %d 230 40" % y, remap=tui.P("patch_page_text"), just="horizontallyCentred verticallyCentred",
                            colour="ffd6d4cc", style="Medium", case="Original", h=19.0))
    p.sample["patch_page_text$"] = "1 / 5"
    p.momentary("patch_page_next", 960, y, 110, 40, "PAGE >", size=15)
    p.qlink_group((X0, 92, 1270, 622), ["browse_bank_index", "preset", "patch_page_index"])
    return p


def tone_head(p, t):
    header(p, ("TONE", str(t + 1)))
    p.toggle("nvram_tone_%d_toneswitch" % t, 1100, 30, 84, 42, "ON", lit=True)


def tone_envelopes(p, t):
    p.envelope_window(24, 414, 416, 612, "PITCH ENV", tui.jv_env("pitch", t), "pitch env %d" % t, mid=True,
                      sample=[(0, .5), (.1, .75), (.3, .55), (.6, .5), (.8, .5), (1, .5)])
    p.envelope_window(444, 414, 836, 612, "FILTER ENV", tui.jv_env("filter", t), "filter env %d" % t,
                      sample=[(0, 0), (.08, 1), (.3, .8), (.55, .5), (.8, .5), (1, 0)])
    p.envelope_window(864, 414, 1256, 612, "AMP ENV", tui.jv_env("amp", t), "amp env %d" % t,
                      sample=[(0, 0), (.05, 1), (.25, .85), (.5, .7), (.8, .7), (1, 0)])


def tone_main_page(t):
    """TONE n, MAIN: WAVE / FILTER / AMP blocks of four (Q-Link groups 1-3), the wave group and FXM on the right, and the tone's
    three live envelopes (pitch, filter, amp: drag the points)."""
    p = Page("TONE %d" % (t + 1), "TONE %d" % (t + 1), 2 + t, sub=0, seed=20 + t)
    tone_head(p, t)
    k = lambda s: "nvram_tone_%d_%s" % (t, s)
    rows = [("WAVE", [(k("wavenumber"), "WAVE NUMBER", .03), (k("pitchcoarse"), "COARSE TUNE", .5), (k("pitchfine"), "FINE TUNE", .5),
                      (k("fxmdepth"), "FXM DEPTH", 0.0)]),
            ("FILTER", [(k("cutofffrequency"), "CUTOFF", .8), (k("resonance"), "RESONANCE", .1), (k("tvfenvdepth"), "FILTER ENV DEPTH", .6)]),
            ("AMP / PITCH", [(k("level"), "LEVEL", 1.0), (k("pan"), "PAN", .5), (k("tvaenvtime4"), "AMP RELEASE (T4)", .3),
                             (k("penvdepth"), "PITCH ENV DEPTH", .5)])]
    for gi, (title, ctl) in enumerate(rows):
        y = 104 + gi * 100
        p.header(X0 + 8, X1 - 8, y, title, q=True)
        for i, (key, n, s) in enumerate(ctl):
            p.slider(key, col(i), y + 12, SW, n, s)
        keys = [c[0] for c in ctl]
        if title == "FILTER":   # 4th control: the filter mode keys
            p.legend(col(3), y + 12, "FILTER MODE")
            p.segments(k("filtermode"), col(3), y + 34, SW, 34, sel=1)
            keys.append(k("filtermode"))
        p.qlink_group((X0, y - 16, X1, y + 76), keys)
    p.header(RX, 1262, 104, "WAVE GROUP")
    p.segments(k("wavegroup"), RX, 118, RW, 32, cols=2, sel=0)
    p.header(RX, 1262, 204, "FXM")
    p.toggle(k("fxmswitch"), RX, 218, RW, 44, "FXM")
    p.header(RX, 1262, 304, "MORE")
    p.legend(RX, 318, "LFOs: press TONE %d again" % (t + 1), 13, art.INK_DIM, 500)
    tone_envelopes(p, t)
    return p


def lfo_block(p, t, n, x0, x1):
    k = lambda s: "nvram_tone_%d_lfo%d%s" % (t, n, s)
    w = (x1 - x0 - 28 - 2 * 16) // 3
    c = lambda i: x0 + 14 + i * (w + 16)
    p.header(x0 + 8, x1 - 8, 104, "LFO %d" % n)
    p.legend(c(0), 116, "WAVEFORM")
    p.segments(k("form"), c(0), 136, (x1 - x0 - 28) - (110 if n == 1 else 0), 32, sel=0, gap=5)
    if n == 1:
        p.toggle(k("synchro"), x1 - 14 - 96, 136, 96, 32, "KEY SYNC")
    for gi, (title, ctl) in enumerate([("TIME", [("rate", "RATE", .6), ("delay", "DELAY", 0), ("fadetime", "FADE", 0)]),
                                       ("DEPTH", [("pitchdepth", "PITCH", .5), ("tvfdepth", "FILTER", .5), ("tvadepth", "AMP", .5)])]):
        y = 196 + gi * 100
        p.legend(x0 + 36, y - 6, title, 12, art.AMBER, 650)
        for i, (s, nm, v) in enumerate(ctl):
            p.slider(k(s), c(i), y + 12, w, nm, v)
        p.qlink_group((x0, y - 18, x1, y + 76), [k(s) for s, _, _ in ctl])


def tone_lfo_page(t):
    """TONE n, LFO (second press of the TONE key): LFO 1 and LFO 2 side by side, each a TIME and a DEPTH block of three
    (Q-Link groups 1-4), the waveform keys; the three envelopes again underneath."""
    p = Page("TONE %d LFO" % (t + 1), "TONE %d" % (t + 1), 2 + t, sub=1, seed=30 + t)
    tone_head(p, t)
    lfo_block(p, t, 1, X0, 632)
    lfo_block(p, t, 2, 648, 1264)
    # Q-Link order: LFO 1 time, LFO 1 depth, LFO 2 time, LFO 2 depth (already in that order)
    tone_envelopes(p, t)
    return p


def common_page():
    """COMMON (new in 2.0, last key): bend / portamento, reverb and chorus in full, the key-mode switches."""
    p = Page("COMMON", "COMMON", 6, seed=13)
    header(p)
    c = lambda s: "nvram_patchCommon_" + s
    p.header(X0 + 8, X1 - 8, 104, "BEND / PORTAMENTO", q=True)
    ctl = [(c("bendrangeup"), "BEND UP", .17), (c("bendrangedown"), "BEND DOWN", .25), (c("portamentotime"), "PORTA TIME", .3),
           (c("analogfeel"), "ANALOG FEEL", .1)]
    for i, (k, n, s) in enumerate(ctl):
        p.slider(k, col(i), 116, SW, n, s)
    p.qlink_group((X0, 88, X1, 180), [x[0] for x in ctl])
    p.header(X0 + 8, X1 - 8, 204, "REVERB", q=True)
    p.segments(c("reverbtype"), col(0), 216, X1 - X0 - 28, 30, gap=5, sel=4)
    ctl = [(c("reverblevel"), "LEVEL", .7), (c("reverbtime"), "TIME", .55), (c("reverbfeedback"), "FEEDBACK", .2)]
    for i, (k, n, s) in enumerate(ctl):
        p.slider(k, col(i), 262, SW, n, s)
    p.qlink_group((X0, 188, X1, 326), [x[0] for x in ctl] + [c("reverbtype")])
    p.header(X0 + 8, X1 - 8, 352, "CHORUS", q=True)
    p.segments(c("chorustype"), col(0), 364, 3 * SW + 32, 30, gap=5, sel=0)
    p.toggle(c("chorusoutput"), col(3), 364, SW, 30, "OUTPUT: REVERB")
    ctl = [(c("choruslevel"), "LEVEL", .7), (c("chorusdepth"), "DEPTH", .12), (c("chorusrate"), "RATE", .3), (c("chorusfeedback"), "FEEDBACK", 0)]
    for i, (k, n, s) in enumerate(ctl):
        p.slider(k, col(i), 410, SW, n, s)
    p.qlink_group((X0, 336, X1, 474), [x[0] for x in ctl])
    p.header(X0 + 8, X1 - 8, 500, "KEY MODE")
    xs = [col(i) for i in range(4)]
    p.legend(xs[0], 512, "KEY ASSIGN")
    p.segments(c("keyassign"), xs[0], 532, SW, 44, sel=0)
    p.legend(xs[1], 512, "PORTAMENTO")
    p.toggle(c("portamentoswitch"), xs[1], 532, 100, 44, "PORTA")
    p.toggle(c("sololegato"), xs[1] + 116, 532, SW - 116, 44, "LEGATO")
    p.legend(xs[2], 512, "PORTA MODE")
    p.segments(c("portamentomode"), xs[2], 532, SW, 44, sel=0)
    p.legend(xs[3], 512, "PORTA TYPE")
    p.segments(c("portamentotype"), xs[3], 532, SW, 44, sel=0)
    tone_switches(p, RX, 104)
    p.header(RX, 1262, 262, "VELOCITY")
    p.toggle(c("velocityswitch"), RX, 276, RW, 44, "VELOCITY SWITCH")
    return p


def all_pages():
    pages = [play_page(), banks_page()]
    for t in range(4):
        pages += [tone_main_page(t), tone_lfo_page(t)]
    pages.append(common_page())
    return pages
