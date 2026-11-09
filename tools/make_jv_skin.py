#!/usr/bin/env python3
"""The JV-880 2.0 skin art library: panel, section print, rubber keys with LEDs, slider film strips, the green LCD, display
windows. Pillow only, everything drawn from code (Roboto Condensed, OFL) except the 1.x MINI-JV badge (images/jv880_badge.png).
The look follows the late-80s / 90s Roland rack modules: a matte black chassis, blue and orange print in bracket lines, flat
dark-grey buttons with red LED slots, a backlit yellow-green LCD (also used for the envelope displays) and LED-ladder faders. Used by tools/skin_pages.py; previews come from tools/make_tui.py --preview.
"""
import math, os, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONT = os.path.join(HERE, "fonts", "RobotoCondensed.ttf")
BADGE = os.path.join(ROOT, "images", "jv880_badge.png")
SS = 3  # supersampling for small parts

# ---- palette: the late-80s / 90s Roland rack (JV-880, JV-1080): matte black chassis, blue and orange print, red LEDs ----------
PANEL_TOP = (30, 31, 34)      # matte black powder coat
PANEL_BOT = (20, 21, 23)
INK = (226, 228, 230)         # white panel print
INK_DIM = (150, 156, 166)
BLUE = (78, 160, 226)         # the rack's blue print (section titles, mode names)
BLUE_DIM = (42, 92, 136)
ORANGE = (236, 128, 46)       # the rack's orange print (secondary legends)
AMBER = ORANGE                # kept for callers
AMBER_HI = (255, 170, 90)
KEY = (64, 65, 70)            # flat dark-grey rack button
KEY_DARK = (40, 41, 45)
LED_ON = (255, 46, 34)        # red LED
LED_OFF = (74, 22, 22)
LCD_BG = (176, 200, 62)       # backlit yellow-green LCD, black ink
LCD_CELL = (186, 210, 72)
LCD_INK = (22, 26, 8)
QLINK = (232, 31, 64)         # MPC focus colour (previews only)


def font(px, wght=500):
    f = ImageFont.truetype(FONT, max(1, int(px)))
    try:
        f.set_variation_by_axes([wght])
    except Exception:
        pass
    return f


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(len(a)))


# ---- panel ------------------------------------------------------------------------------------------------------------
def panel(w, h, seed=7):
    """Matte black rack panel: an even powder-coat stipple (no brushing), a soft top light, a rolled top and bottom edge."""
    base = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(base)
    for y in range(h):
        d.line([0, y, w, y], fill=lerp(PANEL_TOP, PANEL_BOT, y / max(1, h - 1)))
    random.seed(seed)
    fine = Image.effect_noise((w, h), 26).convert("L")
    up = fine.point(lambda v: max(0, v - 128) // 14)
    dn = fine.point(lambda v: max(0, 128 - v) // 14)
    base = ImageChops.subtract(ImageChops.add(base, Image.merge("RGB", (up, up, up))), Image.merge("RGB", (dn, dn, dn)))
    d = ImageDraw.Draw(base)
    d.line([0, 0, w, 0], fill=(70, 72, 78), width=1)
    d.line([0, h - 1, w, h - 1], fill=(6, 6, 7), width=1)
    return base


def window(img, x0, y0, x1, y1, grid=(8, 4), mid=False):
    """A small backlit LCD (the rack's display, for the live envelopes): yellow-green glass in a black bezel, a dot grid,
    a dark mid line for a bipolar envelope. The envelope draws in dark ink on top."""
    d = ImageDraw.Draw(img)
    d.rectangle([x0 - 8, y0 - 8, x1 + 8, y1 + 8], fill=(8, 8, 9))
    d.line([x0 - 8, y1 + 8, x1 + 8, y1 + 8], fill=(60, 62, 68), width=1)
    for y in range(y0, y1 + 1):
        t = abs((y - y0) / max(1, y1 - y0) - 0.45)
        d.line([x0, y, x1, y], fill=lerp((196, 220, 84), (150, 176, 46), t * 1.6))
    gx, gy = grid
    for i in range(1, gx):
        xx = x0 + i * (x1 - x0) / gx
        for yy in range(y0 + 4, y1 - 2, 6):
            d.point((xx, yy), fill=(128, 152, 40))
    for i in range(1, gy):
        yy = y0 + i * (y1 - y0) / gy
        for xx in range(x0 + 4, x1 - 2, 6):
            d.point((xx, yy), fill=(128, 152, 40))
    if mid:
        d.line([x0 + 2, (y0 + y1) // 2, x1 - 2, (y0 + y1) // 2], fill=(96, 118, 30), width=2)
    sh = Image.new("L", img.size, 0)
    ImageDraw.Draw(sh).rectangle([x0, y0, x1, y0 + 6], fill=120)
    sh = sh.filter(ImageFilter.GaussianBlur(4))
    clip = Image.new("L", img.size, 0)
    ImageDraw.Draw(clip).rectangle([x0, y0, x1, y1], fill=255)
    img.paste((0, 0, 0), (0, 0), ImageChops.multiply(sh, clip))


def legend(d, x, y, text, size=15, col=INK, wght=500, anchor="la"):
    d.text((x, y), text, font=font(size, wght), fill=col, anchor=anchor)


def group_header(d, x0, x1, y, text, col=BLUE, indent=0):
    """The rack's bracket print: a thin line across the section whose ends turn down, the title on it in blue
    (left, after `indent`, clear of the MPC's Q tag)."""
    f = font(15, 650)
    tx = x0 + 10 + indent
    tw = d.textlength(text, font=f)
    ly = y - 5
    lc = BLUE_DIM
    d.line([x0, ly, tx - 6, ly], fill=lc, width=1)
    d.line([tx + tw + 6, ly, x1, ly], fill=lc, width=1)
    d.line([x0, ly, x0, ly + 7], fill=lc, width=1)
    d.line([x1, ly, x1, ly + 7], fill=lc, width=1)
    d.text((tx, y), text, font=f, fill=col, anchor="ls")


# ---- rubber key with LED ----------------------------------------------------------------------------------------------
def key(w, h, lit=False, caption=None, led=True, colour=KEY, ink=INK, size=None):
    """A rack button: a flat, nearly square-cornered dark-grey cap with a soft shadow and a hairline top light, and a red
    LED slot at the top centre (lit: bright, with a glow). Keys without an LED show `lit` the same way (the LED appears)."""
    pad = 6
    W, H = (w + pad * 2) * SS, (h + pad * 2) * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rounded_rectangle([pad * SS, pad * SS + 2 * SS, (pad + w) * SS, (pad + h) * SS + 3 * SS], 2 * SS, fill=210)
    img.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(2 * SS)))
    out = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    od = ImageDraw.Draw(out)
    base = colour
    od.rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], 2 * SS, fill=(12, 12, 13, 255))
    for yy in range(SS, h * SS - SS):
        od.line([SS, yy, w * SS - SS - 1, yy], fill=lerp(tuple(min(255, v + 10) for v in base), tuple(int(v * 0.86) for v in base), yy / (h * SS)) + (255,))
    od.line([2 * SS, SS, w * SS - 3 * SS, SS], fill=tuple(min(255, v + 46) for v in base) + (255,), width=SS)
    show_led = led or lit
    small = h < 36                       # a short key: the LED is a slot at the left, the caption stays centred
    lw, lh = (4 * SS, h * SS - 14 * SS) if small else (min(26, w // 3) * SS, 4 * SS)
    lx, ly = (7 * SS, 7 * SS) if small else ((w * SS - lw) // 2, 6 * SS)
    if show_led:
        if lit:
            glow = Image.new("RGBA", out.size, (0, 0, 0, 0))
            ImageDraw.Draw(glow).rectangle([lx - 4 * SS, ly - 3 * SS, lx + lw + 4 * SS, ly + lh + 3 * SS], fill=LED_ON + (170,))
            out.alpha_composite(glow.filter(ImageFilter.GaussianBlur(3 * SS)))
            od = ImageDraw.Draw(out)
        od.rectangle([lx, ly, lx + lw, ly + lh], fill=(LED_ON if lit else LED_OFF) + (255,), outline=(16, 4, 4, 255))
        if lit:
            od.line([lx + SS, ly + SS, lx + lw - SS, ly + SS], fill=(255, 190, 170, 255), width=SS)
    if caption:
        s = size or min(15, h * 0.40)
        cy = (h * SS) // 2 + (4 * SS if show_led and not small else 0)
        od.text(((w * SS) // 2 + (4 * SS if show_led and small else 0), cy), caption, font=font(s * SS, 650), fill=ink + (255,), anchor="mm")
    img.alpha_composite(out, (pad * SS, pad * SS))
    return img.resize((w + pad * 2, h + pad * 2), Image.LANCZOS)


# ---- sliders ----------------------------------------------------------------------------------------------------------
def slider_cap(w, h, accent=True):
    """A flat rack-button cap (dark grey, hairline top light) with a white index line, and a cast shadow."""
    pad = 8
    W, H = (w + pad * 2) * SS, (h + pad * 2) * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rectangle([(pad + 1) * SS, (pad + 3) * SS, (pad + w + 1) * SS, (pad + h + 3) * SS], fill=210)
    img.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(2.5 * SS)))
    cap = Image.new("RGBA", (w * SS, h * SS))
    cd = ImageDraw.Draw(cap)
    cd.rectangle([0, 0, w * SS - 1, h * SS - 1], fill=(10, 10, 11, 255))
    for yy in range(SS, h * SS - SS):
        cd.line([SS, yy, w * SS - SS - 1, yy], fill=lerp((86, 88, 94), (52, 53, 58), yy / (h * SS)) + (255,))
    cd.line([2 * SS, SS, w * SS - 3 * SS, SS], fill=(130, 132, 138, 255), width=SS)
    cd.line([w * SS // 2, 3 * SS, w * SS // 2, h * SS - 3 * SS], fill=(250, 250, 250, 255), width=2 * SS)
    img.paste(cap, (pad * SS, pad * SS))
    return img.resize((w + pad * 2, h + pad * 2), Image.LANCZOS), pad


_CAP = {}


def fader_frame(length, thick, value, fill=LED_ON, bipolar=False):
    """One frame of a horizontal fader film strip (transparent: the panel shows through): a black slot with an LED ladder,
    segments lit red up to the cap (from the centre when bipolar), dark segments beyond."""
    W, H = length, thick
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    capL, capS = 14, 22
    cy = H // 2
    x0, x1 = capL // 2 + 2, W - capL // 2 - 2
    d.rectangle([x0 - 2, cy - 5, x1 + 2, cy + 5], fill=(4, 4, 5), outline=(56, 58, 64))
    cx = x0 + value * (x1 - x0)
    c0 = (x0 + x1) / 2 if bipolar else x0
    a_, b_ = sorted((c0, cx))
    seg, gap = 5, 2
    lit_any = False
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    x = x0 + 1
    while x + seg <= x1:
        on = a_ <= x + seg / 2 <= b_ and b_ - a_ >= 1
        col = fill if on else (52, 18, 18)
        d.rectangle([x, cy - 2, x + seg - 1, cy + 2], fill=col + (255,))
        if on:
            gd.rectangle([x - 1, cy - 4, x + seg, cy + 4], fill=fill + (120,))
            lit_any = True
        x += seg + gap
    if lit_any:
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(2.5)))
    if bipolar:
        d.line([(x0 + x1) // 2, cy - 8, (x0 + x1) // 2, cy + 7], fill=(230, 232, 236, 255))
    if (capL, capS) not in _CAP:
        _CAP[(capL, capS)] = slider_cap(capL, capS)
    cap, pad = _CAP[(capL, capS)]
    img.paste(cap, (int(cx) - capL // 2 - pad, (H - capS) // 2 - pad), cap)
    return img


def film_strip(frames):
    w, h = frames[0].size
    strip = Image.new("RGBA", (w, h * len(frames)), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(f, (0, i * h))
    return strip


def scale_ticks(d, x0, y0, length, n=11, col=INK_DIM):
    col = tuple(int(c * 0.8) for c in col)
    for i in range(n):
        x = x0 + i / (n - 1) * length
        d.line([x, y0, x, y0 + (6 if i % 5 == 0 else 3)], fill=col)


# ---- LCD --------------------------------------------------------------------------------------------------------------
def lcd(w, h, cols=24, rows=1, dividers=(), arrows=()):
    """The rack's backlit yellow-green LCD in a black bezel with a rolled frame: a dot-cell grid (art), bright in the middle;
    live text goes on top as Labels. dividers: printed rules between fields; arrows: (x, -1|1) step arrows (touch zones on top)."""
    img = Image.new("RGBA", (w, h), (6, 6, 7, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(52, 54, 60))
    gx0, gy0, gx1, gy1 = 10, 8, w - 10, h - 8
    for y in range(gy0, gy1 + 1):
        t = abs((y - gy0) / max(1, gy1 - gy0) - 0.45)
        d.line([gx0, y, gx1, y], fill=lerp((198, 222, 86), (150, 176, 46), t * 1.6))
    cw = (gx1 - gx0 - 8) / cols
    chh = (gy1 - gy0 - 6) / rows
    for r in range(rows):
        for c in range(cols):
            x, y = gx0 + 4 + c * cw, gy0 + 3 + r * chh
            d.rectangle([x + 1, y + 1, x + cw - 2, y + chh - 2], outline=(168, 194, 60))
    for cx, direction in arrows:
        cy, hw, hh = h // 2, 6, 10
        pts = [(cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy)] if direction < 0 else [(cx - hw, cy - hh), (cx - hw, cy + hh), (cx + hw, cy)]
        d.polygon(pts, fill=LCD_INK)
    for x in dividers:
        d.line([x, gy0 + 4, x, gy1 - 4], fill=(84, 104, 26), width=2)
    sh = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sh).rectangle([gx0, gy0, gx1, gy0 + 5], fill=110)
    img.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(3)))
    return img


def badge(h):
    """The 1.x MINI-JV badge, scaled to height h."""
    b = Image.open(BADGE).convert("RGBA")
    return b.resize((int(b.width * h / b.height), h), Image.LANCZOS)


def tile_frame(w, h, lit):
    """A list tile (bank / patch / favourite): a thin printed frame with a transparent middle, so the live name Label under it
    shows through (a Label on top of a Button swallows its taps). Lit: a red LED at the left and a blue frame."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if lit:
        d.rectangle([0, 0, w - 1, h - 1], fill=BLUE + (34,))
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(glow).rectangle([3, 4, 9, h - 5], fill=LED_ON + (180,))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(2)))
        d = ImageDraw.Draw(img)
    d.rectangle([5, 6, 7, h - 7], fill=(LED_ON if lit else LED_OFF) + (255,))
    d.rectangle([0, 0, w - 1, h - 1], outline=(BLUE if lit else (58, 60, 66)) + (255,), width=1 if not lit else 2)
    return img


# ---- alternative control styles (JV_CTRL=cells | knobs | ladder; "fader" = the LED-ladder horizontal fader above) ------------
def lcd_cell(img, x0, y0, x1, y1):
    """Static art of an LCD parameter cell: a small backlit yellow-green pane in a black bezel."""
    d = ImageDraw.Draw(img)
    d.rectangle([x0 - 4, y0 - 4, x1 + 4, y1 + 4], fill=(6, 6, 7))
    d.line([x0 - 4, y1 + 4, x1 + 4, y1 + 4], fill=(60, 62, 68))
    for y in range(y0, y1 + 1):
        t = abs((y - y0) / max(1, y1 - y0) - 0.45)
        d.line([x0, y, x1, y], fill=lerp((198, 222, 86), (152, 178, 48), t * 1.6))


def cell_frame(w, h, value, bipolar=False):
    """Film-strip frame of an LCD cell's bar graph (dark LCD segments, transparent elsewhere: the cell art shows through)."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, x1, yb = 10, w - 10, h - 12
    n = max(8, (x1 - x0) // 7)
    sw = (x1 - x0) / n
    mid = n / 2
    pos = value * n
    for i in range(n):
        c = i + 0.5
        on = (min(mid, pos) <= c <= max(mid, pos)) if bipolar else c <= pos
        col = (24, 30, 8, 255) if on else (24, 30, 8, 34)
        d.rectangle([x0 + i * sw + 1, yb - 8, x0 + (i + 1) * sw - 2, yb], fill=col)
    if bipolar:
        d.line([(x0 + x1) // 2, yb - 12, (x0 + x1) // 2, yb + 3], fill=(24, 30, 8, 255), width=2)
    return img


_KNOB = {}


def knob_frame(D, value, bipolar=False):
    """Film-strip frame of a rack knob: a red LED dot ring (lit to the value, from the top when bipolar) around a black
    knurled cap with a white pointer. 270 degrees of travel."""
    S2 = SS
    W = D * S2
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = W / 2
    R_ring = W * 0.46
    a0, a1 = 135.0, 405.0
    av = a0 + value * (a1 - a0)
    amid = 270.0
    n = 21
    for i in range(n):
        a = a0 + i * (a1 - a0) / (n - 1)
        on = (min(amid, av) - 0.1 <= a <= max(amid, av) + 0.1) if bipolar else a <= av + 0.1
        r = W * 0.028
        x, y = c + R_ring * math.cos(math.radians(a)), c + R_ring * math.sin(math.radians(a))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(LED_ON if on else LED_OFF) + (255,))
    key = D
    if key not in _KNOB:
        cap = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cap)
        Rc = W * 0.34
        sh = Image.new("L", (W, W), 0)
        ImageDraw.Draw(sh).ellipse([c - Rc + S2, c - Rc + 3 * S2, c + Rc + S2, c + Rc + 3 * S2], fill=200)
        cap.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(3 * S2)))
        for i in range(36):   # knurled skirt
            a = math.radians(i * 10)
            cd.line([c + Rc * math.cos(a), c + Rc * math.sin(a), c + Rc * 0.86 * math.cos(a), c + Rc * 0.86 * math.sin(a)],
                    fill=(70, 72, 78, 255), width=S2)
        cd.ellipse([c - Rc, c - Rc, c + Rc, c + Rc], outline=(8, 8, 9, 255), width=S2)
        Rt = Rc * 0.8
        for k in range(int(Rt), 0, -1):
            t = k / Rt
            cd.ellipse([c - k - Rt * 0.1 * (1 - t), c - k - Rt * 0.15 * (1 - t), c + k, c + k],
                       fill=lerp((22, 22, 24), (74, 76, 82), 1 - t) + (255,))
        _KNOB[key] = cap
    img.alpha_composite(_KNOB[key])
    Rc = W * 0.34
    a = math.radians(av)
    d.line([c + Rc * 0.25 * math.cos(a), c + Rc * 0.25 * math.sin(a), c + Rc * 0.78 * math.cos(a), c + Rc * 0.78 * math.sin(a)],
           fill=(250, 250, 250, 255), width=3 * S2)
    return img.resize((D, D), Image.LANCZOS)


def ladder_frame(w, h, value, bipolar=False):
    """Film-strip frame of a vertical LED ladder: a black slot of red segments, lit from the bottom (from the middle when
    bipolar) up to the value, with a small white level mark."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], fill=(4, 4, 5, 255), outline=(56, 58, 64, 255))
    n = max(6, (h - 6) // 5)
    sh_ = (h - 6) / n
    pos = value * n
    mid = n / 2
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i in range(n):
        c = i + 0.5
        on = (min(mid, pos) <= c <= max(mid, pos)) if bipolar else c <= pos
        y1 = h - 3 - i * sh_
        y0 = y1 - sh_ + 2
        d.rectangle([4, y0, w - 5, y1], fill=(LED_ON if on else (52, 18, 18)) + (255,))
        if on:
            gd.rectangle([2, y0 - 1, w - 3, y1 + 1], fill=LED_ON + (110,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(2)))
    return img
