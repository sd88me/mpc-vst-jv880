#!/usr/bin/env python3
"""Filmstrips for the envelope view on the TONE pages (layout `meter` lines; src/dsp v2_envv_update computes the values).

A skin can't draw, MPC only shows the frame matching a parameter's value, so each envelope is a row of narrow columns.
Each column is two stacked display-only strips following two values the plugin computes (the curve's top and bottom edge
inside that column, 0..127):
  env_hi.png  frame k = bright fill from the bottom up to the top edge (plus a 3 px minimum, so a flat part still has a line)
  env_lo.png  frame k = opaque dim fill from the bottom up to the bottom edge, drawn over the first
so what stays bright is a bar from the bottom edge to the top edge: a continuous line, with a dim area under it.
Frames are COL_W x H, 128 of them (15360 px: MPC garbles strips over 16384 px).
Run:  python3 tools/make_env_strips.py   (needs Pillow; writes images/env_hi.png and images/env_lo.png)
"""
import os
from PIL import Image, ImageDraw

COL_W, H, FRAMES, SS = 11, 120, 128, 1
ACCENT = (0xf2, 0xa8, 0x3c, 255)          # theme_accent_hi
PANEL = (0x20, 0x1f, 0x1e)                # theme_panel: what the dim fill is blended over
DIM = tuple(int(p + (a - p) * 0.28) for p, a in zip(PANEL, ACCENT[:3])) + (255,)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images")


def px(k):
    return round(k / (FRAMES - 1) * (H - 4))


def strip(fill, colour):
    im = Image.new("RGBA", (COL_W, H * FRAMES), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for k in range(FRAMES):
        h = fill(k)
        if h > 0:
            d.rectangle([0, k * H + H - h, COL_W - 1, k * H + H - 1], fill=colour)
    return im


if __name__ == "__main__":
    os.makedirs(ROOT, exist_ok=True)
    strip(lambda k: px(k) + 3, ACCENT).save(os.path.join(ROOT, "env_hi.png"))
    strip(px, DIM).save(os.path.join(ROOT, "env_lo.png"))
    print("wrote images/env_hi.png, images/env_lo.png")
