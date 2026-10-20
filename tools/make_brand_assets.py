#!/usr/bin/env python3
"""Draw Fanxi's icon set: assets/icon.png, icon.icns and icon.ico.

Run after changing the mark:  python3 tools/make_brand_assets.py
Needs Pillow (pip install pillow) and, on macOS, iconutil.
"""
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 4  # draw at four times the size, then downsample


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def vertical_gradient(size, top, bottom):
    im = Image.new('RGB', (1, size))
    px = im.load()
    for y in range(size):
        px[0, y] = lerp(top, bottom, y / max(size - 1, 1))
    return im.resize((size, size))


def rounded_mask(size, radius):
    mask = Image.new('L', (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def build():
    n = 1024 * S
    margin = int(44 * S)
    radius = int(224 * S)
    inner = n - 2 * margin

    bg = vertical_gradient(inner, (10, 24, 48), (18, 58, 92)).convert('RGBA')
    mask = rounded_mask(inner, radius)
    icon = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    icon.paste(bg, (margin, margin), mask)

    d = ImageDraw.Draw(icon, 'RGBA')
    # a soft rim and a faint inner glow
    d.rounded_rectangle((margin, margin, margin + inner - 1, margin + inner - 1), radius=radius,
                        outline=(120, 220, 255, 90), width=int(3 * S))
    d.rounded_rectangle((margin + int(10 * S), margin + int(10 * S), margin + inner - int(10 * S),
                         margin + inner - int(10 * S)), radius=radius - int(10 * S),
                        outline=(160, 240, 255, 26), width=int(2 * S))

    # the F: a stem and two bars, cut at 45 degrees in the lower right of each arm
    x0, x1 = int(360 * S), int(468 * S)
    top, bottom = int(304 * S), int(756 * S)
    arm_end = int(704 * S)
    mid_end = int(632 * S)
    mid_top, mid_bot = int(470 * S), int(570 * S)
    bevel = int(26 * S)

    def arm(y_a, y_b, x_end):
        return [(x0, y_a), (x_end - bevel, y_a), (x_end, y_a + bevel), (x_end, y_b - bevel),
                (x_end - bevel, y_b), (x0, y_b)]

    f_shape = [(x0, top), (x1, top), (x1, bottom - bevel), (x1 - bevel, bottom), (x0, bottom)]
    grad = vertical_gradient(n, (126, 240, 255), (30, 138, 184)).convert('RGBA')
    f_mask = Image.new('L', (n, n), 0)
    fd = ImageDraw.Draw(f_mask)
    fd.polygon(f_shape, fill=255)
    fd.polygon(arm(top, top + int(104 * S), arm_end), fill=255)
    fd.polygon(arm(mid_top, mid_bot, mid_end), fill=255)
    icon.paste(grad, (0, 0), f_mask)

    # a brighter edge along the top of each bar and the stem
    edge = ImageDraw.Draw(icon, 'RGBA')
    edge.line([(x0, top), (x1, top), (x1, bottom - bevel)], fill=(220, 250, 255, 210), width=int(5 * S))
    edge.line([(x1, mid_top), (mid_end - bevel, mid_top)], fill=(220, 250, 255, 190), width=int(5 * S))
    edge.line([(x1, mid_bot), (mid_end - bevel, mid_bot)], fill=(40, 120, 150, 150), width=int(3 * S))

    # a crystal spark: two diamonds, the Fanxi mark's accent
    def diamond(cx, cy, r, fill):
        edge = ImageDraw.Draw(icon, 'RGBA')
        edge.polygon([(cx, cy - r), (cx + r * 0.62, cy), (cx, cy + r), (cx - r * 0.62, cy)], fill=fill)

    diamond(int(742 * S), int(276 * S), int(54 * S), (255, 214, 120, 235))
    diamond(int(742 * S), int(276 * S), int(30 * S), (255, 246, 205, 255))
    diamond(int(800 * S), int(196 * S), int(20 * S), (120, 235, 255, 190))

    return icon.resize((1024, 1024), Image.LANCZOS)


def main():
    icon = build()
    png = os.path.join(ROOT, 'assets', 'icon.png')
    icon.save(png)

    ico = os.path.join(ROOT, 'assets', 'icon.ico')
    icon.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    # Tk 8.5 cannot read PNG; the launcher falls back to this GIF.
    gif = os.path.join(ROOT, 'assets', 'icon.gif')
    icon.resize((128, 128), Image.LANCZOS).convert('P', palette=Image.ADAPTIVE, colors=128).save(gif)

    icns = os.path.join(ROOT, 'assets', 'icon.icns')
    if shutil.which('iconutil'):
        with tempfile.TemporaryDirectory() as tmp:
            iconset = os.path.join(tmp, 'Fanxi.iconset')
            os.makedirs(iconset)
            for px in (16, 32, 64, 128, 256, 512):
                icon.resize((px, px), Image.LANCZOS).save(os.path.join(iconset, 'icon_%dx%d.png' % (px, px)))
                icon.resize((px * 2, px * 2), Image.LANCZOS).save(os.path.join(iconset, 'icon_%dx%d@2x.png' % (px, px)))
            subprocess.run(['iconutil', '-c', 'icns', iconset, '-o', icns], check=True)
    print('wrote', png, ico, gif, icns if os.path.exists(icns) else '(no icns)')


if __name__ == '__main__':
    main()
