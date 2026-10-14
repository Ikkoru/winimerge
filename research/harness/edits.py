"""Edits applied to the large image before shrinking, like a real variant would differ.

Each edit returns (edited_image, changed_mask). Positions are chosen deterministically where the
image has content (highest local standard deviation among candidate spots), so edits do not land
on blank margins. Sizes are in large-image pixels; with 1200-1600 px originals and factors 2-4,
some edits are near one small-image pixel on purpose (the detection floor).
"""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def _spot(img, fw, fh, salt, avoid=()):
    """Pick a top-left corner for a fw x fh footprint on a 7x7 grid, maximising local std."""
    H, W = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32)
    best, best_s = None, -1
    rng = np.random.default_rng(salt)
    for gy in np.linspace(0.08, 0.86, 7):
        for gx in np.linspace(0.08, 0.86, 7):
            x, y = int(gx * (W - fw)), int(gy * (H - fh))
            if any(abs(x - ax) < fw and abs(y - ay) < fh for ax, ay in avoid):
                continue
            s = g[y:y + fh, x:x + fw].std() + rng.uniform(0, 1.0)  # small jitter breaks ties
            if s > best_s:
                best, best_s = (x, y), s
    return best


def _contrast_color(img, x, y, w, h):
    m = img[y:y + h, x:x + w].reshape(-1, 3).mean(axis=0)
    lum = 0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]
    return (20, 20, 20) if lum > 128 else (240, 240, 240)


def edit_text(img, size=20, text='EDIT 42', salt=1):
    font = ImageFont.truetype(FONT, size)
    tw, th = font.getbbox(text)[2:]
    x, y = _spot(img, tw + 4, th + 4, salt)
    pil = Image.fromarray(img.copy())
    ImageDraw.Draw(pil).text((x + 2, y + 2), text, font=font, fill=_contrast_color(img, x, y, tw, th))
    return np.asarray(pil)


def edit_line(img, length=140, width=2, salt=2):
    x, y = _spot(img, length, 24, salt)
    out = img.copy()
    col = _contrast_color(img, x, y, length, 24)
    cv2.line(out, (x, y + 6), (x + length, y + 18), col, width, lineType=cv2.LINE_AA)
    return out


def edit_recolor(img, size=90, shift=(18, -6, -18), salt=3):
    x, y = _spot(img, size, size, salt)
    out = img.astype(np.int32).copy()
    out[y:y + size, x:x + size] += np.array(shift)
    return np.clip(out, 0, 255).astype(np.uint8)


def edit_bar(img, w=90, h=18, salt=4):
    x, y = _spot(img, w, h, salt)
    out = img.copy()
    out[y:y + h, x:x + w] = 0
    return out


def edit_mosaic(img, size=96, cell=12, salt=5):
    x, y = _spot(img, size, size, salt)
    out = img.copy()
    reg = out[y:y + size, x:x + size].astype(np.float32)
    small = reg.reshape(size // cell, cell, size // cell, cell, 3).mean(axis=(1, 3))
    out[y:y + size, x:x + size] = np.repeat(np.repeat(small, cell, 0), cell, 1).round().astype(np.uint8)
    return out


def edit_smudge(img, radius=45, sigma=3.0, salt=6):
    x, y = _spot(img, 2 * radius, 2 * radius, salt)
    out = img.copy()
    reg = out[y:y + 2 * radius, x:x + 2 * radius].astype(np.float32)
    blur = cv2.GaussianBlur(reg, (0, 0), sigma)
    yy, xx = np.mgrid[0:2 * radius, 0:2 * radius]
    r = np.hypot(xx - radius + 0.5, yy - radius + 0.5)
    a = np.clip((radius - r) / 8.0, 0, 1)[..., None]  # feathered circle
    out[y:y + 2 * radius, x:x + 2 * radius] = np.clip(reg * (1 - a) + blur * a + 0.5, 0, 255).astype(np.uint8)
    return out


def edit_move(img, size=110, dx=2, salt=7):
    x, y = _spot(img, size + dx, size, salt)
    out = img.copy()
    out[y:y + size, x + dx:x + dx + size] = img[y:y + size, x:x + size]
    return out


def edit_dot(img, size=3, salt=8):
    x, y = _spot(img, 24, 24, salt)
    out = img.copy()
    col = _contrast_color(img, x, y, 24, 24)
    out[y + 10:y + 10 + size, x + 10:x + 10 + size] = col
    return out


EDITS = {
    'text': edit_text,
    'text_small': lambda img: edit_text(img, size=11, text='v2', salt=11),
    'line': edit_line,
    'recolor': edit_recolor,
    'bar': edit_bar,
    'mosaic': edit_mosaic,
    'smudge': edit_smudge,
    'move': edit_move,
    'dot': edit_dot,
}


def apply(name, img):
    out = EDITS[name](img)
    mask = np.any(out != img, axis=2)
    return out, mask
