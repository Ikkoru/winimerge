"""Reference resamplers (float, pixel-centre convention), nearest-neighbour variants,
unsharp mask, and the "website" shrinking pipelines used to make small copies.

All functions take and return numpy arrays (H, W, 3) uint8 RGB unless noted.
Pixel-centre convention everywhere: destination pixel u samples source coordinate
x = (u + 0.5) * src / dst - 0.5 (pixel i has its centre at i).
"""
import math

import cv2
import numpy as np
from PIL import Image

# ---------------------------------------------------------------- kernels

def k_box(x):
    return ((x > -0.5) & (x <= 0.5)).astype(np.float64)


def k_triangle(x):
    x = np.abs(x)
    return np.where(x < 1, 1 - x, 0.0)


def k_cubic_bc(B, C):
    def k(x):
        x = np.abs(x)
        x2, x3 = x * x, x * x * x
        a = ((12 - 9 * B - 6 * C) * x3 + (-18 + 12 * B + 6 * C) * x2 + (6 - 2 * B)) / 6
        b = ((-B - 6 * C) * x3 + (6 * B + 30 * C) * x2 + (-12 * B - 48 * C) * x + (8 * B + 24 * C)) / 6
        return np.where(x < 1, a, np.where(x < 2, b, 0.0))
    return k


def k_keys(a):
    """Keys cubic convolution; a=-0.5 is Catmull-Rom, a=-0.75 is OpenCV INTER_CUBIC."""
    def k(x):
        x = np.abs(x)
        x2, x3 = x * x, x * x * x
        p = (a + 2) * x3 - (a + 3) * x2 + 1
        q = a * x3 - 5 * a * x2 + 8 * a * x - 4 * a
        return np.where(x < 1, p, np.where(x < 2, q, 0.0))
    return k


def k_lanczos(n):
    def k(x):
        x = np.asarray(x, np.float64)
        out = np.sinc(x) * np.sinc(x / n)
        return np.where(np.abs(x) < n, out, 0.0)
    return k


def k_gauss(sigma):
    return lambda x: np.exp(-0.5 * (x / sigma) ** 2)


KERNELS = {
    'box': (k_box, 0.5),
    'triangle': (k_triangle, 1.0),
    'bspline': (k_cubic_bc(1, 0), 2.0),
    'mitchell': (k_cubic_bc(1 / 3, 1 / 3), 2.0),
    'catmullrom': (k_keys(-0.5), 2.0),
    'keys075': (k_keys(-0.75), 2.0),
    'lanczos2': (k_lanczos(2), 2.0),
    'lanczos3': (k_lanczos(3), 3.0),
    'lanczos4': (k_lanczos(4), 4.0),
}


def _weights(src, dst, kernel, support):
    scale = dst / src
    fs = min(scale, 1.0)          # widen the kernel when shrinking (antialiasing)
    width = support / fs
    centers = (np.arange(dst) + 0.5) / scale - 0.5
    left = np.floor(centers - width).astype(int) + 1
    n = int(math.ceil(2 * width)) + 1
    idx = left[:, None] + np.arange(n)[None, :]
    w = kernel((idx - centers[:, None]) * fs)
    valid = (idx >= 0) & (idx < src)
    w = np.where(valid, w, 0.0)          # cut at the border, renormalise (like FreeImage)
    w /= w.sum(axis=1, keepdims=True)
    idx = np.clip(idx, 0, src - 1)
    return idx, w


def resize_float(img, w, h, kernel='lanczos3'):
    """Separable resize with a float intermediate. img float or uint8 (H,W,C); returns float64."""
    k, sup = KERNELS[kernel]
    a = img.astype(np.float64)
    iy, wy = _weights(a.shape[0], h, k, sup)
    a = np.einsum('yk,ykxc->yxc', wy, a[iy])
    ix, wx = _weights(a.shape[1], w, k, sup)
    a = np.einsum('xk,yxkc->yxc', wx, a[:, ix])
    return a


def to_u8(a):
    return np.clip(np.floor(a + 0.5), 0, 255).astype(np.uint8)


def resize(img, w, h, kernel='lanczos3'):
    return to_u8(resize_float(img, w, h, kernel))


# ---------------------------------------------------------------- sRGB <-> linear

def srgb_to_linear(u8):
    c = u8.astype(np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(lin):
    c = np.clip(lin, 0, 1)
    s = np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
    return to_u8(s * 255.0)


# ---------------------------------------------------------------- nearest neighbour

def nn_exact(img, w, h):
    """Nearest neighbour to an arbitrary size (pixel-centre convention)."""
    sy = np.minimum((np.floor((np.arange(h) + 0.5) * img.shape[0] / h)).astype(int), img.shape[0] - 1)
    sx = np.minimum((np.floor((np.arange(w) + 0.5) * img.shape[1] / w)).astype(int), img.shape[1] - 1)
    return img[sy][:, sx]


def int_factor(small_wh, large_wh):
    """Largest whole-number factor k with k*w <= W and k*h <= H (at least 1)."""
    w, h = small_wh
    W, H = large_wh
    return max(1, min(W // w, H // h))


def nn_int(img, k):
    return np.repeat(np.repeat(img, k, 0), k, 1)


# ---------------------------------------------------------------- sharpening

def unsharp(img, radius, amount, threshold=0.0):
    """Unsharp mask: out = in + amount*(in - gauss(in, sigma=radius)); threshold in 0..255 levels.

    radius is the Gaussian sigma in output pixels (ImageMagick's -unsharp 0xSIGMA convention;
    Photoshop's "radius" is roughly the same quantity). Works in float, rounds once.
    """
    a = img.astype(np.float64)
    blur = cv2.GaussianBlur(a, (0, 0), radius, borderType=cv2.BORDER_REFLECT)
    d = a - blur
    if threshold > 0:
        d = np.where(np.abs(d) * 2 > threshold, d, 0.0)
    return to_u8(a + amount * d)


# ---------------------------------------------------------------- shrinking pipelines (website stand-ins)

def _pil(img, w, h, f):
    return np.asarray(Image.fromarray(img).resize((w, h), f))


def _pil_linear(img, w, h, f):
    lin = srgb_to_linear(img).astype(np.float32)
    ch = [np.asarray(Image.fromarray(lin[:, :, i], mode='F').resize((w, h), f)) for i in range(3)]
    return linear_to_srgb(np.dstack(ch))


def _vips(img, w, h):
    import pyvips
    v = pyvips.Image.new_from_memory(np.ascontiguousarray(img).tobytes(), img.shape[1], img.shape[0], 3, 'uchar')
    r = v.resize(w / img.shape[1], vscale=h / img.shape[0])  # default kernel: lanczos3 with shrink/reduce
    out = np.ndarray(buffer=r.write_to_memory(), dtype=np.uint8, shape=[r.height, r.width, r.bands])
    return out[:h, :w].copy()


SHRINKERS = {
    'area': lambda img, w, h: cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA),
    'pil_bilinear': lambda img, w, h: _pil(img, w, h, Image.BILINEAR),       # antialiased triangle
    'cv_linear': lambda img, w, h: cv2.resize(img, (w, h), interpolation=cv2.INTER_LINEAR),  # no prefilter
    'pil_bicubic': lambda img, w, h: _pil(img, w, h, Image.BICUBIC),         # Keys a=-0.5, antialiased
    'pil_lanczos': lambda img, w, h: _pil(img, w, h, Image.LANCZOS),         # Lanczos3, antialiased
    'mitchell': lambda img, w, h: resize(img, w, h, 'mitchell'),
    'lanczos_linear': lambda img, w, h: _pil_linear(img, w, h, Image.LANCZOS),
    'lanczos_sharpened': lambda img, w, h: unsharp(_pil(img, w, h, Image.LANCZOS), 0.6, 0.6),
    'vips': _vips,
    'nearest': lambda img, w, h: _pil(img, w, h, Image.NEAREST),
}


def small_size(W, H, factor):
    return max(1, int(round(W / factor))), max(1, int(round(H / factor)))
