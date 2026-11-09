#!/usr/bin/env python3
"""The JV-880 2.0 skin art library: panel, section print, rubber keys with LEDs, slider film strips, the green LCD, display
windows. Pillow only, everything drawn from code (Roboto Condensed, OFL) except the 1.x MINI-JV badge (images/jv880_badge.png).
Adapted from Dexed 2.0's tools/make_dx7_skin.py (same primitives, the JV-880 rack palette of the 1.x skin: near-black chassis,
amber print, a green LCD with black text). Used by tools/skin_pages.py; previews come from tools/make_tui.py --preview.
"""
import math, os, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONT = os.path.join(HERE, "fonts", "RobotoCondensed.ttf")
BADGE = os.path.join(ROOT, "images", "jv880_badge.png")
SS = 3  # supersampling for small parts

# ---- palette: the JV-880 rack (1.x layout.conf theme) ----------------------------------------------------------------
PANEL_TOP = (46, 46, 47)      # charcoal, lit
PANEL_BOT = (22, 22, 23)
INK = (214, 212, 204)         # white panel print
INK_DIM = (138, 136, 128)
AMBER = (217, 134, 31)        # section print, slider fill
AMBER_HI = (242, 168, 60)
KEY = (78, 78, 80)            # grey rubber key
KEY_DARK = (52, 52, 54)
LED_ON = (255, 120, 40)
LED_OFF = (70, 34, 24)
LCD_BG = (143, 174, 58)       # green STN LCD, black ink
LCD_CELL = (152, 184, 64)
LCD_INK = (20, 19, 17)
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
    """Charcoal rack panel: vertical gradient, top-left key light, fine brushed grain, edge vignette."""
    rnd = random.Random(seed)
    base = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(base)
    for y in range(h):
        d.line([0, y, w, y], fill=lerp(PANEL_TOP, PANEL_BOT, y / max(1, h - 1)))
    # key light off the top left
    light = Image.new("L", (w, h), 0)
    ImageDraw.Draw(light).ellipse([-0.6 * w, -0.9 * h, 0.7 * w, 0.6 * h], fill=26)
    light = light.filter(ImageFilter.GaussianBlur(120))
    base = Image.composite(Image.new("RGB", (w, h), (120, 120, 122)), base, light)
    # brushed grain: noise stretched sideways into fine horizontal streaks, plus a little per-pixel noise
    random.seed(seed)
    streak = Image.effect_noise((max(1, w // 24), h), 40).convert("L").resize((w, h), Image.BICUBIC)
    fine = Image.effect_noise((w, h), 18).convert("L")
    grain = Image.blend(streak, fine, 0.4)                         # ~128 +- noise
    up = grain.point(lambda v: max(0, v - 128) // 10)              # lighten where above the mean
    dn = grain.point(lambda v: max(0, 128 - v) // 10)              # darken where below
    base = ImageChops.subtract(ImageChops.add(base, Image.merge("RGB", (up, up, up))), Image.merge("RGB", (dn, dn, dn)))
    del rnd
    # vignette
    vig = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vig).rectangle([0, 0, w, h], outline=70, width=40)
    vig = vig.filter(ImageFilter.GaussianBlur(40))
    base = Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), base, vig)
    return base


def window(img, x0, y0, x1, y1, grid=(8, 4), mid=False):
    """A recessed display window: dark glass with a moulded bezel lit from the top left, a faint grid, a glass sheen.
    mid: a brighter middle line (the zero line of a bipolar envelope)."""
    d = ImageDraw.Draw(img)
    d.rectangle([x0 - 6, y0 - 6, x1 + 6, y1 + 6], fill=(28, 28, 29))
    d.line([x0 - 6, y1 + 6, x1 + 6, y1 + 6], fill=(84, 84, 86), width=2)
    d.line([x1 + 6, y0 - 6, x1 + 6, y1 + 6], fill=(70, 70, 72), width=2)
    d.line([x0 - 6, y0 - 6, x1 + 6, y0 - 6], fill=(8, 8, 8), width=2)
    d.line([x0 - 6, y0 - 6, x0 - 6, y1 + 6], fill=(10, 10, 10), width=2)
    for y in range(y0, y1 + 1):
        d.line([x0, y, x1, y], fill=lerp((24, 23, 22), (12, 12, 12), (y - y0) / max(1, y1 - y0)))
    gx, gy = grid
    for i in range(1, gx):
        xx = x0 + i * (x1 - x0) / gx
        d.line([xx, y0 + 2, xx, y1 - 2], fill=(36, 35, 33))
    for i in range(1, gy):
        yy = y0 + i * (y1 - y0) / gy
        d.line([x0 + 2, yy, x1 - 2, yy], fill=(36, 35, 33))
    if mid:
        d.line([x0 + 2, (y0 + y1) // 2, x1 - 2, (y0 + y1) // 2], fill=(84, 66, 40))
    sh = Image.new("L", img.size, 0)
    ImageDraw.Draw(sh).rectangle([x0, y0, x1, y0 + 8], fill=110)
    sh = sh.filter(ImageFilter.GaussianBlur(5))
    clip = Image.new("L", img.size, 0)
    ImageDraw.Draw(clip).rectangle([x0, y0, x1, y1], fill=255)
    img.paste((0, 0, 0), (0, 0), ImageChops.multiply(sh, clip))
    gl = Image.new("L", img.size, 0)
    ImageDraw.Draw(gl).polygon([(x0 + 40, y0), (x0 + 140, y0), (x0 + 60, y1), (max(x0, x0 - 40), y1)], fill=5)
    img.paste((255, 255, 255), (0, 0), ImageChops.multiply(gl, clip))


def legend(d, x, y, text, size=15, col=INK, wght=500, anchor="la"):
    d.text((x, y), text, font=font(size, wght), fill=col, anchor=anchor)


def group_header(d, x0, x1, y, text, col=AMBER, indent=0):
    """Amber section title with the thin rule under the whole section (the JV-880's panel print)."""
    d.text((x0 + indent, y), text, font=font(15, 650), fill=col, anchor="ls")
    d.line([x0, y + 4, x1, y + 4], fill=tuple(int(c * 0.75) for c in col), width=1)


# ---- rubber key with LED ----------------------------------------------------------------------------------------------
def key(w, h, lit=False, caption=None, led=True, colour=KEY, ink=INK, size=None):
    """A JV-880 style rubber key: grey rounded cap, soft shadow, top bevel; an LED in the top-left corner when `led`
    (lit: orange with a glow). The caption is baked in. A key without an LED shows `lit` as a brighter cap."""
    pad = 6
    W, H = (w + pad * 2) * SS, (h + pad * 2) * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rounded_rectangle([pad * SS + SS, pad * SS + 3 * SS, (pad + w) * SS + SS, (pad + h) * SS + 3 * SS], 5 * SS, fill=190)
    img.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(2.5 * SS)))
    base = colour if (led or not lit) else lerp(colour, AMBER, 0.75)
    face = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    fd = ImageDraw.Draw(face)
    for yy in range(h * SS):
        fd.line([0, yy, w * SS, yy], fill=lerp(tuple(min(255, v + 22) for v in base), tuple(int(v * 0.78) for v in base), yy / (h * SS)) + (255,))
    fd.line([3 * SS, SS, w * SS - 3 * SS, SS], fill=tuple(min(255, v + 70) for v in base) + (255,), width=SS)
    mask = Image.new("L", face.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], 5 * SS, fill=255)
    out = Image.new("RGBA", face.size, (0, 0, 0, 0))
    out.paste(face, (0, 0), mask)
    od = ImageDraw.Draw(out)
    od.rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], 5 * SS, outline=tuple(int(v * 0.45) for v in base) + (255,), width=SS)
    if led:
        r = 3.5 * SS
        cx, cy = 9 * SS, 9 * SS
        if lit:
            glow = Image.new("RGBA", out.size, (0, 0, 0, 0))
            ImageDraw.Draw(glow).ellipse([cx - 3 * r, cy - 3 * r, cx + 3 * r, cy + 3 * r], fill=LED_ON + (150,))
            out.alpha_composite(glow.filter(ImageFilter.GaussianBlur(3 * SS)))
        od.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(LED_ON if lit else LED_OFF) + (255,), outline=(20, 10, 6, 255))
        if lit:
            od.ellipse([cx - r * 0.4, cy - r * 0.6, cx + r * 0.1, cy - r * 0.1], fill=(255, 220, 180, 255))
    if caption:
        txt_ink = (24, 22, 20) if (lit and not led) else ink
        s = size or min(15, h * 0.42)
        dx = 6 * SS if led else 0
        od.text(((w * SS) // 2 + dx, (h * SS) // 2 + (2 * SS if led else 0)), caption, font=font(s * SS, 650), fill=txt_ink + (255,), anchor="mm")
    img.alpha_composite(out, (pad * SS, pad * SS))
    return img.resize((w + pad * 2, h + pad * 2), Image.LANCZOS)


# ---- sliders ----------------------------------------------------------------------------------------------------------
def slider_cap(w, h, accent=True):
    """A black ribbed fader cap with a white index line, lit from the top left, with a cast shadow (horizontal travel)."""
    pad = 8
    W, H = (w + pad * 2) * SS, (h + pad * 2) * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rounded_rectangle([(pad + 2) * SS, (pad + 4) * SS, (pad + w + 2) * SS, (pad + h + 4) * SS], 3 * SS, fill=200)
    img.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(3 * SS)))
    cap = Image.new("RGBA", (w * SS, h * SS))
    cd = ImageDraw.Draw(cap)
    for i in range(w * SS):
        cd.line([i, 0, i, h * SS], fill=lerp((120, 118, 114), (26, 26, 26), i / (w * SS)) + (255,))
    step = 4 * SS
    for x in range(step, w * SS - step, step):
        cd.line([x, 3 * SS, x, h * SS - 3 * SS], fill=(0, 0, 0, 160), width=SS)
        cd.line([x + SS, 3 * SS, x + SS, h * SS - 3 * SS], fill=(110, 108, 104, 90), width=SS)
    cd.line([w * SS // 2, 0, w * SS // 2, h * SS], fill=(255, 255, 255, 255), width=3 * SS)
    cd.rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], 3 * SS, outline=(0, 0, 0, 255), width=SS)
    cd.line([2 * SS, SS, w * SS - 3 * SS, SS], fill=(150, 146, 140, 255), width=SS)
    mask = Image.new("L", cap.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], 3 * SS, fill=255)
    img.paste(cap, (pad * SS, pad * SS), mask)
    return img.resize((w + pad * 2, h + pad * 2), Image.LANCZOS), pad


_CAP = {}


def fader_frame(length, thick, value, fill=AMBER, bipolar=False):
    """One frame of a horizontal fader film strip (transparent: the panel shows through). The slot is lit in `fill` from the
    left edge, or from the centre when bipolar."""
    W, H = length, thick
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    capL, capS = 16, 22
    cy = H // 2
    x0, x1 = capL // 2 + 2, W - capL // 2 - 2
    d.rounded_rectangle([x0 - 1, cy - 5, x1 + 1, cy + 4], 3, fill=(4, 4, 4), outline=(74, 74, 76))
    if (capL, capS) not in _CAP:
        _CAP[(capL, capS)] = slider_cap(capL, capS)
    cap, pad = _CAP[(capL, capS)]
    cx = x0 + value * (x1 - x0)
    c0 = (x0 + x1) / 2 if bipolar else x0
    a_, b_ = sorted((c0, cx))
    if b_ - a_ >= 1:
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).rectangle([a_, cy - 5, b_, cy + 5], fill=fill + (110,))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(3)))
        d.rectangle([a_, cy - 3, b_, cy + 2], fill=fill + (255,))
        d.line([a_, cy - 3, b_, cy - 3], fill=tuple(min(255, c + 70) for c in fill) + (255,))
    if bipolar:
        d.line([(x0 + x1) // 2, cy - 7, (x0 + x1) // 2, cy + 6], fill=(230, 220, 200, 255))
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
    """The JV-880's green STN LCD in its black bezel: a dot-cell grid (art); live text goes on top as Labels.
    dividers: x positions of printed rules between fields; arrows: (x, -1|1) printed step arrows (touch zones on top)."""
    img = Image.new("RGBA", (w, h), (8, 8, 8, 255))
    d = ImageDraw.Draw(img)
    gx0, gy0, gx1, gy1 = 10, 8, w - 10, h - 8
    d.rectangle([gx0, gy0, gx1, gy1], fill=LCD_BG)
    cw = (gx1 - gx0 - 8) / cols
    chh = (gy1 - gy0 - 6) / rows
    for r in range(rows):
        for c in range(cols):
            x, y = gx0 + 4 + c * cw, gy0 + 3 + r * chh
            d.rectangle([x + 1, y + 1, x + cw - 2, y + chh - 2], fill=LCD_CELL)
    for cx, direction in arrows:
        cy, hw, hh = h // 2, 6, 10
        pts = [(cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy)] if direction < 0 else [(cx - hw, cy - hh), (cx - hw, cy + hh), (cx + hw, cy)]
        d.polygon(pts, fill=(52, 66, 20))
    for x in dividers:
        d.line([x, gy0 + 4, x, gy1 - 4], fill=(96, 120, 36), width=2)
    sh = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sh).rectangle([gx0, gy0, gx1, gy0 + 5], fill=90)
    img.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(3)))
    gl = Image.new("L", (w, h), 0)
    ImageDraw.Draw(gl).polygon([(gx0 + 40, gy0), (gx0 + 110, gy0), (gx0 + 70, gy1), (gx0 + 10, gy1)], fill=30)
    img.paste((255, 255, 255, 255), (0, 0), gl)
    return img


def badge(h):
    """The 1.x MINI-JV badge, scaled to height h."""
    b = Image.open(BADGE).convert("RGBA")
    return b.resize((int(b.width * h / b.height), h), Image.LANCZOS)


def tile_frame(w, h, lit):
    """A list tile (bank / patch): printed frame with a transparent middle, so the live name Label under it shows through
    (a Label on top of a Button swallows its taps). Lit: amber frame and a faint amber wash."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if lit:
        d.rectangle([0, 0, w - 1, h - 1], fill=AMBER + (46,))
    d.rectangle([0, 0, w - 1, h - 1], outline=(AMBER if lit else (74, 74, 76)) + (255,), width=2)
    d.line([2, h - 2, w - 3, h - 2], fill=(6, 6, 6, 200))
    return img
