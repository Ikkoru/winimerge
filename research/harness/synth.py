"""Synthetic, licence-free test images that mimic the content the user compares.

Each generator renders with anti-aliasing (skia) at the final resolution, the way a
drawing program renders vector strokes, and returns an RGB uint8 array.

    python3 synth.py OUTDIR        # writes <name>.png for every generator
"""
import math
import os
import sys

import numpy as np
import skia

FONT_SANS = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT_SERIF = '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'


def _surface(w, h, bg=(255, 255, 255)):
    surf = skia.Surface(w, h)
    canvas = surf.getCanvas()
    canvas.clear(skia.Color(*bg))
    return surf, canvas


def _to_rgb(surf):
    img = surf.makeImageSnapshot()
    arr = img.toarray(colorType=skia.kRGBA_8888_ColorType)
    return np.ascontiguousarray(arr[:, :, :3])


def _paint(color=(0, 0, 0), alpha=255, width=1.0, stroke=True, aa=True, cap=skia.Paint.kRound_Cap):
    p = skia.Paint(AntiAlias=aa, Color=skia.Color(*color, alpha))
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(width)
        p.setStrokeCap(cap)
        p.setStrokeJoin(skia.Paint.kRound_Join)
    else:
        p.setStyle(skia.Paint.kFill_Style)
    return p


def _rand_curve(rng, x, y, length, bend):
    a = rng.uniform(0, 2 * math.pi)
    pts = [(x, y)]
    for _ in range(3):
        a += rng.normal(0, bend)
        x += math.cos(a) * length / 3
        y += math.sin(a) * length / 3
        pts.append((x, y))
    path = skia.Path()
    path.moveTo(*pts[0])
    path.cubicTo(*pts[1], *pts[2], *pts[3])
    return path


def _tapered_stroke(canvas, rng, x, y, length, wmax, color=(20, 20, 25), bend=0.6):
    """A brush/pen stroke whose width tapers at both ends (filled polygon)."""
    a = rng.uniform(0, 2 * math.pi)
    n = 40
    pts = []
    cx, cy = x, y
    for i in range(n):
        a += rng.normal(0, bend / n * 3)
        cx += math.cos(a) * length / n
        cy += math.sin(a) * length / n
        pts.append((cx, cy, a))
    left, right = [], []
    for i, (px, py, pa) in enumerate(pts):
        t = i / (n - 1)
        w = wmax * math.sin(math.pi * t) ** 0.6 / 2 + 0.15
        nx, ny = -math.sin(pa), math.cos(pa)
        left.append((px + nx * w, py + ny * w))
        right.append((px - nx * w, py - ny * w))
    path = skia.Path()
    path.moveTo(*left[0])
    for p in left[1:]:
        path.lineTo(*p)
    for p in reversed(right):
        path.lineTo(*p)
    path.close()
    canvas.drawPath(path, _paint(color, stroke=False))


def lineart(w=1200, h=1600, seed=1):
    """Anti-aliased black line art on white: tapered pen strokes, hair bundles, hatching, dots."""
    rng = np.random.default_rng(seed)
    surf, c = _surface(w, h)
    # big flowing contours
    for _ in range(70):
        _tapered_stroke(c, rng, rng.uniform(0, w), rng.uniform(0, h), rng.uniform(150, 600), rng.uniform(1.5, 5.5))
    # hair-like bundles of thin strokes
    for _ in range(14):
        x, y = rng.uniform(100, w - 100), rng.uniform(100, h - 100)
        a0 = rng.uniform(0, 2 * math.pi)
        for k in range(18):
            path = skia.Path()
            x0, y0 = x + k * 3.1 * math.cos(a0 + 1.57), y + k * 3.1 * math.sin(a0 + 1.57)
            path.moveTo(x0, y0)
            path.cubicTo(x0 + 80 * math.cos(a0), y0 + 80 * math.sin(a0) + rng.normal(0, 10),
                         x0 + 160 * math.cos(a0) + rng.normal(0, 10), y0 + 160 * math.sin(a0),
                         x0 + 240 * math.cos(a0 + 0.3), y0 + 240 * math.sin(a0 + 0.3))
            c.drawPath(path, _paint((15, 15, 20), width=rng.uniform(0.8, 1.6)))
    # hatching patches (parallel thin lines 3-6 px apart)
    for _ in range(10):
        x, y = rng.uniform(50, w - 250), rng.uniform(50, h - 250)
        sp = rng.uniform(3.0, 6.0)
        ang = rng.uniform(0, math.pi)
        for k in range(int(180 / sp)):
            dx, dy = math.cos(ang), math.sin(ang)
            ox, oy = x + k * sp * -dy, y + k * sp * dx
            c.drawLine(ox, oy, ox + 160 * dx, oy + 160 * dy, _paint((30, 30, 30), width=1.0))
    # eyes / small closed shapes and dots
    for _ in range(40):
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(2, 14)
        c.drawOval(skia.Rect(x - r, y - r * 0.7, x + r, y + r * 0.7), _paint((10, 10, 10), width=rng.uniform(1, 2.5)))
        if rng.random() < 0.5:
            c.drawCircle(x, y, r * 0.35, _paint((10, 10, 10), stroke=False))
    return _to_rgb(surf)


def flatcolor(w=1600, h=1200, seed=2):
    """Anime-style cel shading: gradients, flat fills, darker shadow shapes, highlights, outlines."""
    rng = np.random.default_rng(seed)
    surf, c = _surface(w, h)
    # sky gradient background
    shader = skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, h)],
                                            [skia.Color(120, 170, 235), skia.Color(250, 220, 235)])
    c.drawPaint(skia.Paint(Shader=shader))
    # soft radial glow
    glow = skia.GradientShader.MakeRadial(skia.Point(w * 0.75, h * 0.25), h * 0.35,
                                          [skia.Color(255, 250, 220, 200), skia.Color(255, 250, 220, 0)])
    c.drawPaint(skia.Paint(Shader=glow))
    palette = [(250, 214, 190), (240, 120, 140), (90, 70, 160), (255, 230, 120), (120, 200, 160),
               (70, 60, 70), (230, 230, 245), (200, 90, 60)]
    for i in range(22):
        cx, cy = rng.uniform(0, w), rng.uniform(h * 0.15, h)
        rx, ry = rng.uniform(60, 260), rng.uniform(60, 260)
        col = palette[i % len(palette)]
        shape = skia.Path()
        shape.addOval(skia.Rect(cx - rx, cy - ry, cx + rx, cy + ry))
        if rng.random() < 0.5:
            shape = skia.Path()
            shape.addRRect(skia.RRect.MakeRectXY(skia.Rect(cx - rx, cy - ry, cx + rx, cy + ry), rx * 0.4, ry * 0.4))
        c.drawPath(shape, _paint(col, stroke=False))
        # cel shadow: same shape offset, clipped, darker flat colour
        c.save()
        c.clipPath(shape, doAntiAlias=True)
        sh = skia.Path()
        sh.addOval(skia.Rect(cx - rx * 0.6, cy - ry * 0.2, cx + rx * 1.4, cy + ry * 1.6))
        c.drawPath(sh, _paint(tuple(int(v * 0.72) for v in col), stroke=False))
        # soft gradient shading inside
        g = skia.GradientShader.MakeLinear([skia.Point(cx, cy - ry), skia.Point(cx, cy + ry)],
                                           [skia.Color(255, 255, 255, 60), skia.Color(0, 0, 40, 50)])
        c.drawPaint(skia.Paint(Shader=g))
        # highlight
        c.drawOval(skia.Rect(cx - rx * 0.5, cy - ry * 0.75, cx - rx * 0.1, cy - ry * 0.55), _paint((255, 255, 255), alpha=220, stroke=False))
        c.restore()
        c.drawPath(shape, _paint((50, 30, 40), width=rng.uniform(2.0, 4.0)))
    # hard colour-to-colour boundaries without outlines (stripes on a ribbon)
    for k in range(9):
        x0 = w * 0.08 + k * 18
        c.drawRect(skia.Rect(x0, h * 0.05, x0 + 9, h * 0.45), _paint((255, 80 + k * 15, 120), stroke=False))
    # sparkles
    for _ in range(30):
        x, y, r = rng.uniform(0, w), rng.uniform(0, h * 0.5), rng.uniform(3, 9)
        p = skia.Path()
        p.moveTo(x, y - r); p.lineTo(x + r * 0.25, y - r * 0.25); p.lineTo(x + r, y); p.lineTo(x + r * 0.25, y + r * 0.25)
        p.lineTo(x, y + r); p.lineTo(x - r * 0.25, y + r * 0.25); p.lineTo(x - r, y); p.lineTo(x - r * 0.25, y - r * 0.25); p.close()
        c.drawPath(p, _paint((255, 255, 240), stroke=False))
    # eyes-like detail with thin lines
    for _ in range(6):
        x, y = rng.uniform(200, w - 200), rng.uniform(300, h - 200)
        c.drawOval(skia.Rect(x - 30, y - 40, x + 30, y + 40), _paint((255, 255, 255), stroke=False))
        c.drawOval(skia.Rect(x - 18, y - 28, x + 18, y + 34), _paint((70, 120, 200), stroke=False))
        c.drawOval(skia.Rect(x - 8, y - 10, x + 8, y + 14), _paint((20, 20, 40), stroke=False))
        c.drawCircle(x - 6, y - 14, 5, _paint((255, 255, 255), stroke=False))
        c.drawOval(skia.Rect(x - 30, y - 40, x + 30, y + 40), _paint((40, 20, 30), width=3))
        for k in range(5):
            c.drawLine(x - 30 + k * 13, y - 40, x - 36 + k * 15, y - 52, _paint((40, 20, 30), width=1.5))
    return _to_rgb(surf)


def _fbm(w, h, rng, octaves=6, base=4):
    """Fractal value noise in [0,1] (bicubic-ish via cv2 resize of random grids)."""
    import cv2
    acc = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        grid = rng.random((n + 1, int(n * w / h) + 1)).astype(np.float32)
        acc += amp * cv2.resize(grid, (w, h), interpolation=cv2.INTER_CUBIC)
        tot += amp
        amp *= 0.55
    acc /= tot
    return (acc - acc.min()) / (acc.max() - acc.min() + 1e-9)


def painterly(w=1600, h=1200, seed=3):
    """Painterly digital art: layered translucent brush strokes over a textured gradient."""
    import cv2
    rng = np.random.default_rng(seed)
    surf, c = _surface(w, h)
    shader = skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(w, h)],
                                            [skia.Color(60, 80, 110), skia.Color(200, 150, 110), skia.Color(240, 220, 180)])
    c.drawPaint(skia.Paint(Shader=shader))
    cols = [(180, 60, 50), (240, 190, 120), (70, 110, 90), (40, 50, 80), (230, 230, 210), (150, 90, 140), (250, 140, 60)]
    for i in range(900):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        col = cols[rng.integers(len(cols))]
        col = tuple(int(np.clip(v + rng.normal(0, 18), 0, 255)) for v in col)
        path = _rand_curve(rng, x, y, rng.uniform(30, 160), 0.7)
        c.drawPath(path, _paint(col, alpha=int(rng.uniform(40, 150)), width=rng.uniform(4, 26), cap=skia.Paint.kRound_Cap))
    for i in range(400):  # fine detail strokes
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        path = _rand_curve(rng, x, y, rng.uniform(10, 50), 0.9)
        c.drawPath(path, _paint((30, 25, 30) if rng.random() < 0.5 else (250, 245, 230), alpha=int(rng.uniform(80, 220)), width=rng.uniform(0.8, 2.5)))
    img = _to_rgb(surf).astype(np.float32)
    tex = _fbm(w, h, rng, octaves=7, base=8)
    grain = rng.normal(0, 1, (h, w)).astype(np.float32)
    grain = cv2.GaussianBlur(grain, (0, 0), 0.7)
    img *= (0.88 + 0.24 * tex)[..., None]
    img += 4.0 * grain[..., None]
    return np.clip(img + 0.5, 0, 255).astype(np.uint8)


def manga(w=1200, h=1600, seed=4):
    """Manga page: panel borders, line art, screentone (halftone dots) gradients and flats, text."""
    rng = np.random.default_rng(seed)
    surf, c = _surface(w, h)
    panels = [(30, 30, 1170, 520), (30, 545, 640, 1100), (665, 545, 1170, 1100), (30, 1125, 1170, 1570)]
    for (x0, y0, x1, y1) in panels:
        c.save()
        c.clipRect(skia.Rect(x0, y0, x1, y1))
        # screentone region: dots on a 45-degree grid, period 6 px (about 60 lpi at 360 dpi)
        period = rng.choice([5.0, 6.0, 7.5])
        tone_x0, tone_x1 = x0 + rng.uniform(0, (x1 - x0) * 0.3), x1 - rng.uniform(0, (x1 - x0) * 0.3)
        c.save()
        c.rotate(45, (x0 + x1) / 2, (y0 + y1) / 2)
        diag = math.hypot(x1 - x0, y1 - y0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        n = int(diag / period) + 2
        for i in range(-n // 2, n // 2):
            for j in range(-n // 2, n // 2):
                px, py = cx + i * period, cy + j * period
                # gradient tone: dot radius grows along the panel
                t = (j + n / 2) / n
                r = period * 0.5 * (0.15 + 0.75 * t)
                c.drawCircle(px, py, r, _paint((0, 0, 0), stroke=False))
        c.restore()
        # flat white mask so tone is only in part of the panel
        c.drawRect(skia.Rect(x0, y0, tone_x0, y1), _paint((255, 255, 255), stroke=False))
        c.drawRect(skia.Rect(tone_x1, y0, x1, y1), _paint((255, 255, 255), stroke=False))
        # speed lines
        if rng.random() < 0.6:
            fx, fy = rng.uniform(x0, x1), rng.uniform(y0, y1)
            for k in range(60):
                a = k / 60 * 2 * math.pi
                c.drawLine(fx + math.cos(a) * 120, fy + math.sin(a) * 120, fx + math.cos(a) * 900, fy + math.sin(a) * 900,
                           _paint((0, 0, 0), width=rng.uniform(0.6, 2.2)))
        # characters-ish line art
        for _ in range(18):
            _tapered_stroke(c, rng, rng.uniform(x0, x1), rng.uniform(y0, y1), rng.uniform(80, 400), rng.uniform(1.5, 4.5), color=(0, 0, 0))
        c.restore()
        c.drawRect(skia.Rect(x0, y0, x1, y1), _paint((0, 0, 0), width=4, cap=skia.Paint.kButt_Cap))
    # speech balloons with text
    font = skia.Font(skia.Typeface.MakeFromFile(FONT_SERIF), 22)
    for (bx, by) in [(820, 120), (180, 640), (800, 1250)]:
        c.drawOval(skia.Rect(bx - 150, by - 70, bx + 150, by + 70), _paint((255, 255, 255), stroke=False))
        c.drawOval(skia.Rect(bx - 150, by - 70, bx + 150, by + 70), _paint((0, 0, 0), width=2.5))
        c.drawString('What was that?!', bx - 95, by - 8, font, _paint((0, 0, 0), stroke=False))
        c.drawString('It moved again...', bx - 100, by + 24, font, _paint((0, 0, 0), stroke=False))
    return _to_rgb(surf)


def text_ui(w=1600, h=1200, seed=5):
    """Interface screenshot: 1-px rules, buttons, checkboxes, small text, table grid, icons."""
    rng = np.random.default_rng(seed)
    surf, c = _surface(w, h, (240, 240, 240))
    sans = skia.Typeface.MakeFromFile(FONT_SANS)
    c.drawRect(skia.Rect(0, 0, w, 32), _paint((45, 85, 160), stroke=False))
    c.drawString('Compare Images - WinMerge', 12, 22, skia.Font(sans, 15), _paint((255, 255, 255), stroke=False))
    y = 60
    for size in (11, 12, 13, 14, 16, 18, 22):
        f = skia.Font(sans, size)
        f.setEdging(skia.Font.Edging.kAntiAlias)
        c.drawString(f'{size}px The quick brown fox jumps over the lazy dog 0123456789 (+-*/=) [WinMerge]', 20, y, f, _paint((20, 20, 20), stroke=False))
        y += size + 14
    # buttons and checkboxes
    for i in range(8):
        x0, y0 = 20 + i * 190, 330
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0, x0 + 170, y0 + 34), 4, 4), _paint((225, 225, 225), stroke=False))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0 + 0.5, y0 + 0.5, x0 + 169.5, y0 + 33.5), 4, 4), _paint((150, 150, 150), width=1))
        c.drawString(f'Button {i + 1}', x0 + 50, y0 + 22, skia.Font(sans, 13), _paint((0, 0, 0), stroke=False))
        c.drawRect(skia.Rect(x0 + 0.5, y0 + 60.5, x0 + 14.5, y0 + 74.5), _paint((90, 90, 90), width=1, aa=False))
        if i % 2:
            c.drawLine(x0 + 3, y0 + 67, x0 + 7, y0 + 72, _paint((0, 120, 0), width=2))
            c.drawLine(x0 + 7, y0 + 72, x0 + 13, y0 + 62, _paint((0, 120, 0), width=2))
        c.drawString('Option', x0 + 22, y0 + 72, skia.Font(sans, 12), _paint((0, 0, 0), stroke=False))
    # table with 1-px grid
    x0, y0, cw, rh = 20, 460, 150, 24
    for r in range(25):
        for col in range(10):
            if (r + col) % 7 == 0:
                c.drawRect(skia.Rect(x0 + col * cw, y0 + r * rh, x0 + (col + 1) * cw, y0 + (r + 1) * rh), _paint((255, 255, 200), stroke=False))
            c.drawString(f'{(r * 31 + col * 17) % 1000:4d}.{r % 10}', x0 + col * cw + 8, y0 + r * rh + 17, skia.Font(sans, 12), _paint((0, 0, 0), stroke=False))
    for r in range(26):
        c.drawLine(x0, y0 + r * rh + 0.5, x0 + 10 * cw, y0 + r * rh + 0.5, _paint((180, 180, 180), width=1, aa=False))
    for col in range(11):
        c.drawLine(x0 + col * cw + 0.5, y0, x0 + col * cw + 0.5, y0 + 25 * rh, _paint((180, 180, 180), width=1, aa=False))
    # icons
    for i in range(12):
        cx, cy = 1560 - (i % 3) * 30, 70 + (i // 3) * 30
        c.drawCircle(cx, cy, 9, _paint([(220, 60, 60), (60, 160, 60), (60, 90, 220)][i % 3], stroke=False))
    return _to_rgb(surf)


def pixelart(w=1600, h=1200, seed=6, scale=8):
    """Procedural pixel-art scene (200x150 logical pixels) enlarged x8 with nearest neighbour."""
    rng = np.random.default_rng(seed)
    lw, lh = w // scale, h // scale
    pal = np.array([[20, 16, 32], [72, 59, 121], [111, 134, 201], [190, 220, 240], [70, 130, 60], [130, 190, 80],
                    [150, 100, 60], [220, 180, 120], [240, 240, 220], [200, 60, 60], [250, 200, 60]], np.uint8)
    idx = np.zeros((lh, lw), np.int64)
    sky = np.linspace(0, 1, lh)[:, None] + rng.random((lh, lw)) * 0.15
    idx[:] = np.where(sky < 0.35, 1, np.where(sky < 0.7, 2, 3))
    ground = (lh * 0.65 + 6 * np.sin(np.arange(lw) / 9.0)).astype(int)
    for x in range(lw):
        idx[ground[x]:, x] = 4
        idx[ground[x]:ground[x] + 2, x] = 5
        idx[ground[x] + 8::5, x] = 6
    for _ in range(9):  # trees
        x, base = rng.integers(5, lw - 5), 0
        base = ground[x]
        idx[base - 12:base, x] = 6
        for dy in range(-22, -8):
            for dx in range(-5, 6):
                if dx * dx + (dy + 15) ** 2 < 30 and 0 <= x + dx < lw:
                    idx[base + dy, x + dx] = 5 if (dx + dy) % 3 else 4
    for _ in range(4):  # houses
        x, wdt = rng.integers(10, lw - 30), rng.integers(12, 20)
        base = ground[min(x + wdt // 2, lw - 1)]
        idx[base - 12:base, x:x + wdt] = 7
        for k in range(8):
            idx[base - 12 - k, x + k:x + wdt - k] = 9
        idx[base - 6:base, x + 3:x + 6] = 6
        idx[base - 10:base - 7, x + wdt - 6:x + wdt - 3] = 10
    for _ in range(25):  # stars / sparkles
        idx[rng.integers(0, lh // 3), rng.integers(0, lw)] = 8
    small = pal[idx]
    return np.repeat(np.repeat(small, scale, 0), scale, 1)


def zoneplate(w=1200, h=1200):
    """Zone plate (frequency rises to the Nyquist limit at the edge) with a slanted edge strip."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float64)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    r2 = (x - cx) ** 2 + (y - cy) ** 2
    km = math.pi / (2 * max(cx, cy))  # local frequency = km * r, reaches pi (Nyquist) at r = max(cx, cy) * 2... clipped
    v = 0.5 + 0.5 * np.cos(km * r2 / 2)
    img = np.clip(v * 255 + 0.5, 0, 255)
    # slanted edge strip at the bottom (5 degrees), anti-aliased by supersampling
    ss = 4
    yy, xx = np.mgrid[0:120 * ss, 0:w * ss].astype(np.float64) / ss
    edge = (xx - w / 2) * math.cos(math.radians(5)) + yy * math.sin(math.radians(5)) > 0
    strip = edge.reshape(120, ss, w, ss).mean(axis=(1, 3)) * 255
    img[h - 120:] = strip
    return np.repeat(img[:, :, None], 3, axis=2).astype(np.uint8)


GENERATORS = {
    'lineart': lineart,
    'flatcolor': flatcolor,
    'painterly': painterly,
    'manga': manga,
    'text_ui': text_ui,
    'pixelart': pixelart,
    'zoneplate': zoneplate,
}


if __name__ == '__main__':
    from PIL import Image
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    os.makedirs(out, exist_ok=True)
    for name, gen in GENERATORS.items():
        arr = gen()
        Image.fromarray(arr).save(os.path.join(out, f'synth_{name}.png'), optimize=False, compress_level=6)
        print(name, arr.shape)
